"""Independent map checks, frozen doorway routing and atlas for the Flat 40 cover swap."""
import argparse
from collections import Counter
from fractions import Fraction
from pathlib import Path
from statistics import mean
import sys

import networkx as nx
import numpy as np
import pymupdf

from experiments.cross_terrain_axial import DEST
from experiments.cross_terrain_axial_routes import evaluate_active_union
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_exchange_atlas import combine, foot, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons
from experiments.flat40_maximal_convex_axial import load_experiment, save, variant
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed
from experiments.near_collinear_consolidation import CASE, certificate
from experiments.occupied_vertex_pruning import read
from voronoi_app.region_incidence_angular import halfplanes


def coverage(ids, matrix, polygons, domain):
    hits = {r:sorted(ids.intersection(v)) for r,v in matrix["by_region"].items()}
    missing = [r for r,v in hits.items() if not v]
    area = exact_coverage(domain,[polygons[int(r) if isinstance(next(iter(polygons)),int) else r] for r in missing]
                         )["covered_area"] if missing else "0"
    return {"covered":len(hits)-len(missing),"uncovered":missing,"uncovered_polygon_union_area":area,
            "unique":{r:v[0] for r,v in hits.items() if len(v)==1},
            "selected_incidence":hits,"redundancy":dict(Counter(map(len,hits.values())))}


def movement(study, maps, archived):
    output = evaluate_active_union(study.inputs,study.lines,study.clearance,study.reference,
                                   {n:{"maps":{"final":sorted(ids)}} for n,ids in maps.items()})
    methods = {n:v["final"] for n,v in output["methods"].items()}
    baseline = methods["A-C-H"]
    pairs = study.inputs["analysis"]["pairs"]
    if len(pairs)!=4950:
        raise ValueError("Unexpected doorway pair count.")
    errors = {}
    for n,r in methods.items():
        r["paired_vs_archived_CH"] = {}
        for mode in ("angular","metric"):
            k = f"{mode}_routes"
            if n.startswith("A-"):
                old = archived["methods"][n[2:]][k]
                error = max(abs(v-w) for v,w in zip(r[k],old,strict=True))
                if error > 1e-8:
                    raise ValueError(f"Archived {n} {mode} routes changed by {error}.")
                errors.setdefault(n,{})[mode] = error
            differences = [v-w if v is not None and w is not None else None
                           for v,w in zip(r[k],baseline[k],strict=True)]
            finite = [v for v in differences if v is not None]
            worst = max((i for i,d in enumerate(differences) if d is not None),key=differences.__getitem__)
            loss = [v for v in finite if v>1e-9]
            r["paired_vs_archived_CH"][mode] = {
                "improved":sum(v < -1e-9 for v in finite),"worsened":len(loss),
                "unchanged":sum(abs(v)<=1e-9 for v in finite),"both_reachable":len(finite),
                "mean_difference":mean(finite),"p95_signed_difference":float(np.percentile(finite,95)),
                "p95_of_worsened_pairs":float(np.percentile(loss,95)) if loss else 0,
                "worst_deterioration":max(0,differences[worst]),
                "worst_pair":pairs[worst] if loss else None,"difference_in_saved_pair_order":differences}
    return output|{"archived_route_replay_max_absolute_error":errors,"pairs":pairs}


def role(study, ids, matrices):
    rest = ids-{1509}
    graph = study.graph.subgraph(rest)
    w = study.geometry.geometry(frozenset(rest))
    return {"retained":1509 in ids,"selected_neighbors":sorted(study.neighbors[1509]&ids),
            "components_after_removal":nx.number_connected_components(graph),
            "doorways_lost_after_removal":[i for i,g in enumerate(study.doors) if ids&g and not rest&g],
            "rank_after_removal":w["independent_circulation_rank"],
            "independent_winding_after_removal":w,
            "regions_lost_after_removal":{cover:[r for r,g in m["by_region"].items() if ids.intersection(g)=={1509}]
                                           for cover,m in matrices.items()}}


def render(out, atlas, polygons, matrices, maps, results, routes, local):
    sources = []
    cool,warm,common = "#236e9e","#ba4b38","#4a5a66"
    def start(title, subtitle, n=1, view=None):
        fig,axes=page(title,subtitle,n)
        for ax in axes:
            atlas.base(ax) if view is None else atlas.base(ax,view)
        return fig,axes
    def write(title,fig):
        p = out/f"{len(sources)+1:02d}.pdf"
        plot_pdf(p,[fig])
        sources.append((title,p))
        return p
    def shapes(ax, group, color=cool, alpha=.10, edges="none"):
        draw_polygons(ax,[{"vertices":packed(v)} for v in group],facecolors=color,
                      edgecolors=edges,linewidths=.57,alpha=alpha,zorder=4)
    def network(ax, ids, color=cool):
        for i in sorted(ids):
            atlas.line(ax,i,color,width=.84,z=7)
    def difference(ax,a,b):
        network(ax,a&b,common)
        network(ax,a-b,warm)
        network(ax,b-a,cool)
    fig,_=start("Corrected Flat 40","Frozen numbered footprints and accessible component")
    write("Settlement geometry",fig)
    for key,name in (("A","Archived overlapping convex cover"),("B","Certified maximal convex cover")):
        fig,(ax,)=start(name,f"{len(polygons[key])} exact convex polygons")
        shapes(ax,polygons[key].values())
        write(name,fig)
    fig,axes=start("Convex overlap comparison","Identical scale and opacity for both covers",2)
    for ax,key in zip(axes,("A","B")):
        shapes(ax,polygons[key].values())
        ax.set_title(f"{key} · {len(polygons[key])} polygons",loc="left")
    write("Convex overlap comparison",fig)

    fig,axes=page("Frozen candidate incidence","Strict positive-length interior traversal",2)
    for ax,key in zip(axes,("A","B")):
        data=matrices[key]["region_candidate_count_distribution"]
        x=sorted(map(int,data))
        ax.bar(x,[data[str(i)] for i in x],color=cool)
        ax.set(title=f"Cover {key}",xlabel="Candidates per convex polygon",ylabel="Polygons")
    write("Strict incidence distribution",fig)
    for name,title in (("A-C-H","Archived C-H"),("B-C-H","Maximal-cover C-H")):
        fig,(ax,)=start(title,f"{len(maps[name])} selected lines" if name in maps else "Frozen-pool coverage gate failed")
        if name in maps:
            network(ax,maps[name])
        else:
            shapes(ax,[polygons["B"][k] for k in matrices["B"]["zero"]],warm,.72)
        write(title,fig)

    fig,(ax,)=start("C-H map difference","Grey shared · Red archived only · Blue maximal-cover only")
    if "B-C-H" in maps:
        difference(ax,maps["A-C-H"],maps["B-C-H"])
    write("C-H candidate substitutions",fig)

    fig,_=page("Independent structural certification","Exact clearance, graph connectivity and circulation winding")
    for i,(name,r) in enumerate(results.items()):
        s=r["structure"]
        text=(f'{name}    {s["lines"]} lines    {s["doorways"]}/100 doorways    '
              f'{s["components"]} component    winding {s["rank"]}/24')
        fig.text(.12,.76-i*.075,text,fontsize=16)
    write("Structural certification",fig)

    region=atlas.regions[257]
    x,y,X,Y=region.bounds
    fig,axes=start("Region 257 and the selected axial lines",
                   "Gold archived outline · Blue 1435 · Red 1509",2,(x-4,X+4,y-4,Y+4))
    for ax,name in zip(axes,("A-C-H","B-C-H")):
        shapes(ax,[polygons["B"][k] for k in local],alpha=.18)
        shapes(ax,[polygons["A"][257]],"none",1,"#ac7821")
        if name in maps:
            network(ax,maps[name],common)
        atlas.line(ax,1435,cool,width=1.8,z=9)
        selected_1509 = name in maps and 1509 in maps[name]
        atlas.line(ax,1509,warm,width=1.8,style="solid" if selected_1509 else "dashed",z=9)
        retention = "1509 retained" if selected_1509 else "1509 removed"
        ax.set_title(f"{name} · {retention}",loc="left")
    local_pdf=write("Region 257 and candidates 1435 and 1509",fig)
    with pymupdf.open(local_pdf) as pdf:
        pdf[0].get_pixmap(dpi=300,alpha=False).save(out/"region-257-300dpi.png")

    fig,axes=start("Uniquely traversed convex regions","Each shaded polygon has one selected interior traversal",2)
    for ax,name in zip(axes,("A-C-H","B-C-H")):
        if name in results:
            key=name[0]
            ids=results[name]["coverage"][key]["unique"]
            shapes(ax,[polygons[key][int(i) if key=="A" else i] for i in ids],alpha=.33)
            network(ax,set(ids.values()),common)
            ax.set_title(f"{name} · {len(ids)} polygons",loc="left")
    write("Unique selected traversals",fig)

    fig,axes=page("Doorway movement comparison","Signed paired changes from archived C-H across 4,950 doorway pairs",2)
    for ax,mode in zip(axes,("angular","metric")):
        bars={n:r["final"]["paired_vs_archived_CH"][mode]["mean_difference"]
              for n,r in routes["methods"].items() if n!="A-C-H"}
        ax.bar(list(bars),list(bars.values()),color=cool)
        ax.axhline(0,color=common,lw=.8)
        ax.set(title=mode.capitalize(),ylabel="Mean paired difference")
    write("Paired doorway movement",fig)

    fig,axes=start("C-S shortest-first comparison","Grey shared · Red archived only · Blue maximal-cover only",3)
    network(axes[0],maps["A-C-S"])
    if "B-C-S" in maps:
        network(axes[1],maps["B-C-S"])
        difference(axes[2],maps["A-C-S"],maps["B-C-S"])
    for ax,name in zip(axes,("Archived C-S","Maximal-cover C-S","Difference")):
        ax.set_title(name,loc="left")
    write("C-S selection and difference",fig)
    missed = [results[n]["coverage"]["A"]["uncovered"] for n in ("B-C-H","B-C-S")
              if n in results]
    if any(missed):
        fig,axes=start("Archived regions missed by the maximal-cover maps",
                       "Red shows archived polygons without a selected interior traversal",len(missed))
        for ax,name,ids in zip(axes,("B-C-H","B-C-S"),missed):
            network(ax,maps[name],common)
            shapes(ax,[polygons["A"][int(i)] for i in ids],warm,.63)
            ax.set_title(f'{name} · {", ".join(ids)}',loc="left")
        write("Archived coverage exceptions",fig)
    if matrices["B"]["zero"]:
        fig,(ax,)=start("Strict incidence feasibility failure","Red marks maximal polygons without a frozen traversing candidate")
        shapes(ax,[polygons["B"][k] for k in matrices["B"]["zero"]],warm,.7)
        write("Uncovered by the frozen candidate pool",fig)
    path=out/"flat40-maximal-convex-axial-selection-atlas.pdf"
    combine(path,sources)
    with pymupdf.open(path) as pdf:
        if any(p.get_images() for p in pdf):
            raise ValueError("Expected a vector atlas.")


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    for n in ("manifest","source","output"):
        parser.add_argument("--"+n,type=Path,required=True)
    a=parser.parse_args()
    study,atlas,old,new,_=load_experiment(a.manifest,a.source)
    out=a.output
    matrices={k:read(out/f"incidence-{k}.json") for k in ("A","B")}
    polygons={"A":old,"B":new}
    maps={n:set(read(out/f"{n}.json")["ids"]) for n in ("A-C-H","A-C-S","B-C-H","B-C-S")
          if (out/f"{n}.json").exists()}
    results={}
    for n,ids in maps.items():
        by_cover={k:coverage(ids,m,polygons[k],atlas.domain) for k,m in matrices.items()}
        cert=certificate(study if n[0]=="A" else variant(study,matrices["B"]),ids)
        w=cert["winding"]
        if (by_cover[n[0]]["uncovered"] or cert["doorways"]!=100 or
                w["independent_circulation_rank"]!=24 or not w["circulation_constraints_satisfied"]
                or w["lines_crossing_effective_occupied_space"]):
            raise ValueError(f"{n} failed independent structural verification.")
        results[n]={"ids":sorted(ids),"coverage":by_cover,
                    "structure":{"lines":len(ids),"doorways":cert["doorways"],"components":1,
                                 "rank":w["independent_circulation_rank"],"clearance":True},
                    "graph_degrees":dict(study.graph.subgraph(ids).degree),
                    "degree_distribution":dict(Counter(d for _,d in study.graph.subgraph(ids).degree)),
                    "selected_line_midpoints":{i:[str((a+b)/2) for a,b in
                                                 zip(study.lines[i].start,study.lines[i].end)] for i in sorted(ids)},
                    "certificate":cert,"candidate_1509":role(study,ids,matrices)}
    local={k:{"area_overlap":str(area),"traversing_candidates":[i for i in (1435,1509)
                                      if i in matrices["B"]["by_region"][k]]}
           for k,v in new.items() if (area:=exact_area(convex_intersection(old[257],halfplanes(v+v[:1]))))}
    changes={}
    for method in ("C-H","C-S"):
        if f"B-{method}" in maps:
            x,y=maps[f"A-{method}"],maps[f"B-{method}"]
            changes[method]={"shared":sorted(x&y),"archived_only":sorted(x-y),"maximal_only":sorted(y-x)}
    lost_constraints = {}
    for method in ("C-H","C-S"):
        if f"B-{method}" in results:
            old_hits = results[f"A-{method}"]["coverage"]["A"]["selected_incidence"]
            missed = results[f"B-{method}"]["coverage"]["A"]["uncovered"]
            lost_constraints[method] = {r:{"original_selected_candidates":old_hits[r],
                                          "all_frozen_candidates":matrices["A"]["by_region"][r]} for r in missed}
    save(out,"comparison",{"maps":results,"inventory_changes":changes,"region_257":local,
                            "lost_archived_constraints":lost_constraints,
                            "archived_region_257_incidence":matrices["A"]["by_region"]["257"]})
    routes=movement(study,maps,read(DEST/CASE/"movement.json"))
    save(out,"movement",routes)
    render(out,atlas,polygons,matrices,maps,results,routes,local)
    print({n:{"structure":r["structure"],"cross_cover":{k:v["covered"] for k,v in r["coverage"].items()},
              "retains_1509":r["candidate_1509"]["retained"]} for n,r in results.items()},flush=True)


if __name__=="__main__":
    main()
