"""Render and verify the final strict-generalisation maps from batch archives."""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlencode

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from matplotlib.patches import PathPatch, Patch
from matplotlib.path import Path as PlotPath
import networkx as nx
import numpy as np
from PIL import Image
from shapely import from_wkb
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from voronoi_app.batch_routing_reference import interval
from voronoi_app.batch_store import BatchStore
from voronoi_app.exact_axial import candidate_graph
from voronoi_app.exact_enumeration import exact_pool_from_dict

from .strict_generalisation import ROOT
from .strict_generalisation_export import METHODS

TITLES = dict(zip(METHODS, ("Full certified pool", "Strict entrance guided",
                          "Strict backward reduction", "Geometric extreme pair",
                          "Route-ranked pair"), strict=True))
BLUE, GREY, OPEN, PURPLE = "#0d6891", "#56606b", "#e0f3ef", "#943fb0"
LINE_WIDTH = .65


def parts(geometry):
    return [geometry] if geometry.geom_type == "Polygon" else [
        part for item in geometry.geoms for part in parts(item)]


def fill(ax, geometry, color, **kwargs):
    for polygon in parts(geometry):
        poly = orient(polygon)
        path = PlotPath.make_compound_path(*(PlotPath(np.asarray(r.coords), closed=True)
                                             for r in (poly.exterior, *poly.interiors)))
        ax.add_patch(PathPatch(path, facecolor=color, **kwargs))


def caption(row):
    config=json.loads(row["configuration"])
    agg=config["aggregation_params"]
    terrain="Hill" if config["terrain_provider"]=="hill" else "Converging Valleys (Y)"
    return (f"{terrain} · Seed {config['seed']}  |  "
            f"slope {agg['building_slope_preference']} · contour {agg['contour_preference']} · "
            f"{agg['max_dyads']} max dyads · stagnation {agg['stagnation_limit']}\n"
            "Axial generator: fresh-exact v2")


def overlay(ax, lines, color=BLUE, alpha=.92):
    collection=LineCollection(lines, colors=color, linewidths=LINE_WIDTH, alpha=alpha, zorder=3)
    ax.add_collection(collection)
    if len(lines):
        assert np.array_equal(np.asarray(collection.get_segments()),np.asarray(lines))


def draw(ax, case, row, geometry, *, small=False, diagnostic=None):
    polygons,buildings,accessible,boundary,limits,segments,pool,regions,blocks=case
    fill(ax,boundary,"#f5f5f2",edgecolor="none",zorder=0)
    fill(ax,accessible,OPEN,edgecolor="#86adab",linewidth=.28,zorder=1)
    for _,poly in buildings:
        fill(ax,poly,GREY,edgecolor="#323942",linewidth=.27,zorder=2)
    ids=geometry.get("line_ids",[])
    if diagnostic is None:
        overlay(ax,[segments[i] for i in ids],alpha=.23 if row["method"]=="full_pool" else .9)
    else:
        old,new=set(diagnostic),set(ids)
        overlay(ax,[segments[i] for i in sorted(old & new)],alpha=.55)
        overlay(ax,[segments[i] for i in sorted(old-new)],"#c87933",.85)
        overlay(ax,[segments[i] for i in sorted(new-old)],PURPLE)
    checks=geometry.get("constraints",{})
    if row["status"]=="invalid":
        for i in checks.get("missing_regions",[]):
            fill(ax,regions[str(i)],"#ef6674",edgecolor="#982331",alpha=.5,zorder=4)
        for block in checks.get("missing_rings",[]):
            for i in blocks.get(block,()):
                fill(ax,polygons[str(i)],"none",edgecolor="#ffbd60",linewidth=1.4,zorder=5)
        if (checks.get("components") or 0)>1 and ids:
            lines=exact_pool_from_dict(pool).candidates
            graph=candidate_graph([lines[i] for i in ids])
            colors=("#ce314a","#7942ac","#e37430","#326489")
            for j,component in enumerate(nx.connected_components(graph)):
                overlay(ax,[segments[ids[i]] for i in sorted(component)],colors[j%len(colors)])
    for poly in parts(boundary):
        ax.plot(*poly.exterior.xy,color="#253646",linewidth=.8,zorder=6)
    for label,poly in buildings:
        p=poly.representative_point()
        ax.text(p.x,p.y,str(label),color="white",ha="center",va="center",
                fontsize=3.6 if small else 6,weight="bold",zorder=7)
    x0,y0,x1,y1=limits
    ax.set(xlim=(x0-1,x1+1),ylim=(y0-1,y1+1),aspect="equal")
    ax.tick_params(labelsize=6,length=2)
    ax.set_xticks(range(0,101,20)); ax.set_yticks(range(0,101,20))
    details=(f"{row['lines']} lines · {row['status'].upper()}\n"
             f"Rings {row['internal_blocks']} · rank {row['rank']} · coverage "
             f"{row['covered_regions']}/{row['required_regions']}")
    if row["status"]!="valid":
        details+=f"\nMissing regions {checks.get('missing_regions',[])} · missing rings {checks.get('missing_rings',[])}"
    ax.set_title(TITLES[row["method"]]+"\n"+details,fontsize=8 if small else 11)


def make_page(rows, maps, scene, *, overview=False, diagnostic=None):
    fig,axes=plt.subplots(1,len(rows),figsize=(20,6.35) if overview else (9.5,10.7),squeeze=False)
    fig.subplots_adjust(left=.045,right=.975,bottom=.13,top=.78 if overview else .81,wspace=.16)
    print_caption=caption(rows[0])
    fig.text(.045,.965,print_caption,fontsize=12,va="top")
    for ax,row in zip(axes[0],rows,strict=True):
        draw(ax,scene,row,maps[row["method"]],small=overview,diagnostic=diagnostic)
    r=rows[0]
    handles=[Patch(color=GREY,label="Original buildings"),Patch(color=OPEN,label="Accessible open space")]
    handles += ([Patch(color=BLUE,label="Retained"),Patch(color="#c87933",label="Removed"),
                 Patch(color=PURPLE,label="Added")] if diagnostic is not None else [Patch(color=BLUE,label="Axial lines")])
    fig.legend(handles=handles,loc="lower center",bbox_to_anchor=(.5,.047),ncol=len(handles),frameon=False)
    fig.text(.045,.043,f"Analysis {r['analysis_record']}   |   Corridor screen {r['physical_screen_record']}",
             fontsize=7)
    fig.text(.045,.027,f"Settlement {r['settlement_record']}   |   Candidates {r['candidate_record']}",
             fontsize=7)
    return fig


def save_pair(fig, root, stem, atlas, dpi):
    png,pdf=root/f"{stem}.png",root/f"{stem}.pdf"
    fig.savefig(png,dpi=dpi)
    fig.savefig(pdf)
    atlas.savefig(fig)
    plt.close(fig)
    with Image.open(png) as image:
        assert image.width>=3000
        image.verify()
    assert pdf.read_bytes().startswith(b"%PDF")
    return str(png.relative_to(root)),str(pdf.relative_to(root))


def write_index(out, index):
    lines=["# Final axial map index", "",
           "[Consolidated vector atlas](visual-appendix.pdf) · [Statistical CSV](../comparison.csv)", "",
           "The CSV line includes the header. Set the Streamlit viewer's saved map to the listed selection ID.", ""]
    for name in dict.fromkeys(row["case"] for row in index):
        entries=[r for r in index if r["case"]==name]
        first=entries[0]
        stats=first["statistics"]
        lines.extend([f"## {name.replace('_', ' ').title()}", "",
                      f"[Side-by-side comparison]({first['comparison']}) · [Corridor changes]({first['diagnostic']})",
                      "", f"Analysis `{stats['analysis_record']}` · physical screen `{stats['physical_screen_record']}`.",
                      "", "| Selection | Lines | Statistical CSV line | Atlas page | Files | Streamlit selection ID |",
                      "|---|---:|---:|---:|---|---|"])
        for row in entries:
            lines.append(f"| {TITLES[row['method']]} | {row['statistics']['lines']} | {row['statistical_csv_line']} | "
                         f"{row['page']} | [PNG]({row['png']}) · [PDF]({row['pdf']}) | `{row['id']}` |")
        lines.append("")
    (out/"INDEX.md").write_text("\n".join(lines)+"\n")


def export(root,out):
    out.mkdir(parents=True,exist_ok=False)
    store=BatchStore(root)
    with (root/"comparison.csv").open() as stream:
        rows=list(csv.DictReader(stream))
    index=[]
    page=0
    with PdfPages(out/"visual-appendix.pdf",metadata={"Title":"Strict axial maps · Hill and Y seeds 40–45"}) as atlas:
        for terrain in ("hill","converging_valleys"):
            for seed in range(40,46):
                name=f"{terrain}-{seed}"
                case_rows=[(i,r) for i,r in enumerate(rows,2) if r["case"]==name]
                first=case_rows[0][1]
                _,settlement,_=store.load(first["settlement_record"])
                _,candidate,_=store.load(first["candidate_record"])
                _,topology,_=store.load(first["topology_record"])
                _,analysis,analysis_hash=store.load(first["analysis_record"])
                _,screen,_=store.load(first["physical_screen_record"])
                maps=dict(analysis["maps"])
                for method,key in (("geometric_extreme","extreme"),("route_ranked","best_ranked")):
                    winner=screen["winners"][method]
                    if winner is not None:
                        maps[method]=analysis["corridors"][winner-1][key]
                    else:
                        maps[method]={"status":next(r["status"] for _,r in case_rows if r["method"]==method)}
                snapshot=json.loads((root/"selected-geometry"/f"{name}.json").read_text())
                exact=candidate["pool"]["candidates"]
                segments=np.asarray([interval(line) for line in exact],dtype=float)
                for _,r in case_rows:
                    method=r["method"]
                    item=maps[method]
                    archived=snapshot["maps"][method]
                    ids=item.get("line_ids",[])
                    assert item["status"]==archived["status"]==r["status"]
                    assert [line["id"] for line in archived["lines"]]==ids
                    assert archived["lines"]==[{k:exact[i][k] for k in ("id","start","end")} for i in ids]
                    if r["lines"]!="null":
                        assert int(r["lines"])==len(ids)
                polygons={i:from_wkb(wkb) for i,wkb in settlement["polygons_wkb"].items()}
                buildings=[(label,polygons[i]) for i,label in settlement["building_labels"].items()]
                scene=(polygons,buildings,from_wkb(topology["accessible_wkb"]),unary_union(list(polygons.values())),
                       settlement["grid"]["extent"],segments,candidate["pool"],candidate["regions_wkb"],
                       {b["id"]:b["cells"] for b in topology["topology"]["occupied_blocks"]})
                overview,_=save_pair(make_page([r for _,r in case_rows],maps,scene,overview=True),
                                     out,name+"-comparison",atlas,205)
                page+=1
                route=next(r for _,r in case_rows if r["method"]=="route_ranked")
                diag,_=save_pair(make_page([route],maps,scene,diagnostic=maps["strict_backward"]["line_ids"]),
                                 out,name+"-corridor-changes",atlas,390)
                page+=1
                for line,r in case_rows:
                    method=r["method"]
                    stem=f"{name}-{method}"
                    png,pdf=save_pair(make_page([r],maps,scene),out,stem,atlas,390)
                    page+=1
                    index.append({"id":stem,"case":name,"method":method,"statistical_csv_line":line,
                                  "page":page,"png":png,"pdf":pdf,"comparison":overview,"diagnostic":diag,
                                  "statistical_csv":"../comparison.csv","analysis_sha256":analysis_hash,
                                  "viewer_query":urlencode({"selection":stem}),"statistics":r})
                print(name,"verified",len(case_rows),"maps",flush=True)
    assert len(index)==len(rows)==60
    (out/"index.json").write_text(json.dumps(index,indent=2))
    write_index(out,index)
    with (out/"index.csv").open("x",newline="") as stream:
        keys=[k for k in index[0] if k!="statistics"]
        writer=csv.DictWriter(stream,fieldnames=keys)
        writer.writeheader()
        writer.writerows({k:r[k] for k in keys} for r in index)
    print(page,"atlas pages",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--output",type=Path,default=ROOT/"visual-report")
    args=parser.parse_args()
    export(args.root,args.output)
