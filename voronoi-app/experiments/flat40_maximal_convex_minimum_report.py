"""Winding-ray lower bound, fixed doorway movement and vector diagnostics."""
import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys

import numpy as np
import pymupdf

from experiments.cross_terrain_axial_routes import evaluate_active_union
from experiments.flat40_exchange_atlas import combine, foot, page, plot_pdf
from experiments.flat40_face_extension import draw_polygons
from experiments.flat40_maximal_convex_axial import load_experiment, save, variant
from experiments.flat40_maximal_convex_minimum import Search, lower_bound
from experiments.flat40_region257_inspection import packed
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _cross, _direction


def ray_hits(p, d, a, b):
    """Closed segment intersects the strictly forward half of an exact ray."""
    u,v = _direction(p,a),_direction(p,b)
    x,y = _cross(d,u),_cross(d,v)
    dot_a,dot_b = sum(i*j for i,j in zip(d,u)),sum(i*j for i,j in zip(d,v))
    if not x and not y:
        return max(dot_a,dot_b)>0
    if min(x,y)>0 or max(x,y)<0:
        return False
    return (x*dot_b-y*dot_a)*(x-y)>0


def ray_bound(study, matrix, controls):
    search = Search(study,matrix)
    directions = [(a,b) for a in range(-2,3) for b in range(-2,3)
                  if max(abs(a),abs(b))==2]
    rays = {}
    extra = [[] for _ in study.lines]
    for block,p in sorted(study.geometry.block_witnesses.items()):
        for direction in directions:
            key = f"ray:{block}:{direction[0]}:{direction[1]}"
            owners = frozenset(i for i,line in enumerate(study.lines)
                               if ray_hits(p,direction,line.start,line.end))
            if not owners or any(ids.isdisjoint(owners) for ids in controls):
                raise ValueError(f"Certified reference fails winding ray {key}.")
            rays[key] = {"block":block,"witness":packed((p,))[0],"direction":direction,"candidates":sorted(owners)}
            j = len(search.groups)
            search.keys.append(key)
            search.groups.append(owners)
            for i in owners:
                extra[i].append(j)
    original = study.by_line
    try:
        study.by_line = [g|set(v) for g,v in zip(original,extra,strict=True)]
        bound = lower_bound(search)
    finally:
        study.by_line = original
    bound["ray_requirements"] = rays
    bound["necessity"] = ("The exact winding validator requires an enclosing bounded face for every internal "
                         "block witness. Each forward ray from the interior exits that face across its boundary. "
                         "At least one selected axial interval therefore intersects that ray.")
    return bound


def verify_integer_weights(sets, weights, population, denominator):
    if sets.keys()!=weights.keys() or any(type(q) is not int or q<0 for q in weights.values()):
        raise ValueError("Missing or negative exact dual weights.")
    charges = [0]*population
    for key, group in sets.items():
        for c in group:
            charges[c] += weights[key]
    if max(charges)>denominator:
        raise ValueError("A candidate violates the certified capacity.")
    return {"verified_bound":(sum(weights.values())+denominator-1)//denominator,
            "maximum_charge":max(charges),"candidates_checked":len(charges),
            "nonzero_weights":sum(bool(q) for q in weights.values())}


def movement(study, maps, reference):
    out = evaluate_active_union(study.inputs,study.lines,study.clearance,study.reference,
                                {k:{"maps":{"final":v}} for k,v in maps.items()})
    baseline = out["methods"]["B-C-H"]["final"]
    pairs = study.inputs["analysis"]["pairs"]
    comparison = read(reference/"movement.json")["methods"]
    for k, method in out["methods"].items():
        r = method["final"]
        if not r["valid"] or len(r["angular_routes"])!=4950 or len(r["metric_routes"])!=4950:
            raise ValueError(f"Incomplete frozen doorway routing for {k}.")
        r["paired_vs_maximal_CH"]={}
        for mode in ("angular","metric"):
            route_mode=f"{mode}_routes"
            values=r[route_mode]
            if k in comparison and max(abs(a-b) for a,b in zip(
                    values,comparison[k]["final"][route_mode],strict=True))>1e-8:
                raise ValueError(f"Reference movement replay changed for {k}.")
            delta=np.subtract(values,baseline[route_mode])
            i=int(np.argmax(delta))
            r["paired_vs_maximal_CH"][mode]={"improved":int(np.sum(delta < -1e-9)),
                "worsened":int(np.sum(delta > 1e-9)),"unchanged":int(np.sum(abs(delta)<=1e-9)),
                "mean_difference":float(np.mean(delta)),"worst_deterioration":max(0,float(delta[i])),
                "worst_pair":pairs[i] if delta[i]>1e-9 else None}
    return out|{"pairs":pairs}


def render(out, atlas, polygons, results, routes, dependencies):
    sources=[]
    blue,red,grey="#2177a4","#b44531","#5d6269"
    def save_page(name,fig):
        p=out/f"{len(sources)+1:03d}.pdf"
        plot_pdf(p,[fig])
        sources.append((name,p))

    def panels(title,subtitle,n):
        fig,axes=page(title,subtitle,n)
        for ax in axes: atlas.base(ax)
        return fig,axes

    def net(ax,ids,colour=blue,width=.9):
        for i in sorted(ids): atlas.line(ax,i,colour,width=width,z=7)

    def shapes(ax,ids):
        draw_polygons(ax,[{"vertices":packed(polygons[i])} for i in ids],
                      facecolors=red,edgecolors=red,alpha=.23,linewidths=.5,zorder=4)

    for name,ids in results["controls"].items():
        fig,(ax,)=panels(f"{name[2:]} | 31-line control","Exact candidate intervals and original numbered footprints",1)
        net(ax,ids)
        save_page(f"{name[2:]} control",fig)
    fig,(ax,)=panels("The two 31-line controls",
                   "Grey shared · Blue 1278 (C-H) · Red 1422 (C-S)",1)
    net(ax,results["common"],grey)
    net(ax,[1278],blue,1.8)
    net(ax,[1422],red,1.8)
    save_page("Common and alternative axial lines",fig)

    for name, rows in dependencies.items():
        fig,axes=panels(f"{name[2:]} | Direct-deletion dependencies",
                       "Red marks the removed line and any lost polygons",4)
        for ax,category in zip(axes,("convex","doorway","connectivity","winding")):
            row=next((r for r in rows if category in r["failures"]),None)
            if row is None:
                ax.set_title(f"No {category} failure",loc="left")
                continue
            net(ax,set(results["controls"][name])-{row["removed"]},grey)
            shapes(ax,[i for i in row["missing"] if i in polygons])
            net(ax,[row["removed"]],red,1.8)
            ax.set_title(f'{row["removed"]} · {", ".join(row["failures"])}',loc="left",fontsize=9)
        save_page(f"{name[2:]} direct-deletion diagnoses",fig)
    for serial,row in enumerate(results["smaller"],1):
        new=set(row["ids"])
        for origin in row["origins"]:
            name=origin["origin"]
            old=set(results["controls"].get(name,[]))
            if name.startswith("plateau-"):
                old=set(results["tested_plateau_maps"][int(name.split("-")[1])-1])
            elif name.startswith(("followup-","descent-")):
                old=set(next(p["ids"] for p in results["followup_parents"] if p["name"]==name))
            title=f'{len(new)} lines · map {serial} from {name}'
            fig,axes=panels(title,"Grey shared · Red removed · Blue incoming",2)
            net(axes[0],old&new,grey)
            net(axes[0],old-new,red,1.7)
            net(axes[1],new&old,grey)
            net(axes[1],new-old,blue,1.7)
            foot(fig,f'Removed {origin["removed"]} · Added {origin["added"]}')
            save_page(title,fig)

    if results["alternatives"]:
        fig,axes=panels("Example 31-line substitutions",
                       "Grey shared with original C-H · Blue incoming · Red original only",3)
        for ax,row in zip(axes,results["alternatives"][:3]):
            baseline=set(results["controls"]["B-C-H"])
            ids=set(row["ids"])
            net(ax,baseline&ids,grey)
            net(ax,baseline-ids,red,1.5)
            net(ax,ids-baseline,blue,1.5)
        save_page("Examples on the 31-line plateau",fig)
    fig,axes=page("Doorway movement","Paired mean differences from the maximal-cover C-H control",2)
    for ax,mode in zip(axes,("angular","metric")):
        points=[(k,v["final"]["paired_vs_maximal_CH"][mode]["mean_difference"])
                for k,v in routes["methods"].items() if k!="B-C-H"]
        if len(points)<=24:
            ax.bar(range(len(points)),[v for _,v in points],color=blue)
            ax.set_xticks(range(len(points)),[k for k,_ in points],rotation=60)
        else:
            ax.hist([v for _,v in points],color=blue,bins=16)
            ax.set_xlabel("Paired mean difference")
        ax.set_title(mode.capitalize())
        ax.axhline(0,color=grey,lw=.7)
    save_page("Paired doorway routing",fig)
    atlas_path=out/"flat40-maximal-convex-minimum-atlas.pdf"
    combine(atlas_path,sources)
    with pymupdf.open(atlas_path) as pdf:
        if len(pdf)!=len(sources) or any(p.get_images() for p in pdf):
            raise ValueError("Vector atlas verification failed.")


def main():
    sys.set_int_max_str_digits(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ("manifest","source","reference","output"):
        parser.add_argument("--"+n,type=Path,required=True)
    a=parser.parse_args()
    frozen,atlas,_,new,_=load_experiment(a.manifest,a.source)
    results=read(a.output/"results.json")
    extra=read(a.output/"followup.json")
    descent=read(a.output/"descent.json")
    results["followup_parents"]=extra["parents"]+descent["parents"]
    combined={tuple(row["ids"]):row for row in results["smaller"]}
    for row in extra["smaller"]+descent["smaller"]:
        key=tuple(row["ids"])
        if key in combined:
            combined[key]["origins"].extend(row["origins"])
        else:
            combined[key]=row
    results["smaller"]=sorted(combined.values(),key=lambda r:(len(r["ids"]),r["ids"]))
    save(a.output,"combined-results",results)
    save(a.output,"configuration",{
        "reference_two_for_one":"all 465 removed pairs and all 1,503 unselected replacements per original control",
        "reference_plateau_neighbourhood":"all one-for-one replacements from either control",
        "additional_31_line_pair_scans":len(results["tested_plateau_maps"]),
        "additional_30_line_direct_and_pair_scans":len(extra["parents"]),
        "additional_29_line_direct_and_pair_scans":len(descent["parents"]),
        "descent_three_for_two_structural_trial_limit":12000,
        "search_source_hashes":{p.name: sha256(p.read_bytes()).hexdigest() for p in
                                Path(__file__).parent.glob("flat40_maximal_convex_minimum*.py")}})
    maps=results["controls"]|{f"smaller-{i:02d}":r["ids"] for i,r in enumerate(results["smaller"],1)}
    dual=read(a.output/"winding-ray-bound.json")
    matrix=read(a.reference/"incidence-B.json")
    doors={f"door:{i}":sorted(g) for i,g in enumerate(frozen.doors)}
    groups=matrix["by_region"]|doors
    rays={k:r["candidates"] for k,r in dual["ray_requirements"].items()}
    no_rays=read(a.output/"lower-bound.json")
    checks = {name:verify_integer_weights(requirements,w["integer_weights"],len(frozen.lines),w["denominator"])
              for name,requirements,w in (("coverage_and_doors",groups,no_rays),
                                           ("with_winding_rays",groups|rays,dual))}
    if any(set(ids).isdisjoint(g) for ids in maps.values() for g in rays.values()):
        raise ValueError("A certified map violates a winding-ray requirement.")
    save(a.output,"dual-verification",checks|{"frozen_doorway_incidence":doors})
    routes=movement(frozen,maps,a.reference)
    save(a.output,"movement",routes)
    dependencies={name:read(a.output/f"{name}-direct.json") for name in results["controls"]}
    render(a.output,atlas,new,results,routes,dependencies)
    print("Certified lower bound",dual["bound"],"routed",len(maps),"maps",flush=True)


if __name__=="__main__":
    main()
