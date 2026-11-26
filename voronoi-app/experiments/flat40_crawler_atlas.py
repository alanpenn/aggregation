"""Diagnostic atlas for a complete or checkpointed Flat 40 crawler replay."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
from itertools import pairwise
import gzip
import json
from math import hypot
from pathlib import Path
import sys

import networkx as nx
from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from experiments.flat40_oriented_crawler import Replay, geometry
from experiments.flat40_convex_enlargement import Checker, edge_attempts, edges
from experiments.flat40_enlarged_cover import blocked_facets
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_exchange_atlas import Atlas, combine, foot, label, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, lines, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, ring
from voronoi_app.angular import _inside_prepared, _intersections
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes, positive_interior


def read(path):
    with path.open("rb") as stream:
        return json.load(stream)


def targeted(replay, region, budget):
    original=replay.crawler.starts
    x,y,X,Y=map(F,region.bounds)
    vertices=ring(region)
    ranked=[]
    for sign,t in original():
        i,a,b=t
        face=replay.crawler.faces[replay.crawler.tracks[i].face]
        contact=any(len(_intersections(face.a,face.b,p,q))==2 for p,q in pairwise(vertices))
        if contact or (x-3<=a[0]<=X+3 and y-3<=a[1]<=Y+3):
            ranked.append((not contact,sign,t))
    starts=[(sign,t) for _,sign,t in sorted(ranked)]
    out=replay.out/"local-257-schedule"
    out.mkdir(exist_ok=True)
    schedule={str(sign):[replay.ids[t] for k,t in starts if k==sign] for sign in (1,-1)}
    file=out/"start-schedule.json"
    if file.exists() and read(file)!=schedule:
        raise ValueError("Local start order differs from checkpoint.")
    if not file.exists():
        file.write_bytes(encode(schedule))
    replay.crawler.starts=lambda:starts
    try:
        work=Replay(replay.crawler,replay.occupied,out)
        for _ in range(0,budget,1000):
            for sign in (1,-1):
                result=work.batch(sign,min(1000,budget-_))
                print("local",sign,result["origin"],"/",result["total_origins"],result["popped"],flush=True)
    finally:
        replay.crawler.starts=original


def collect(out):
    regions={}
    paths=set()
    rejection=Counter()
    progress={}
    options_admitted=0
    example=None
    for name,directory in [("global",out),("local",out/"local-257-schedule")]:
        for sign,side in ((1,"right"),(-1,"left")):
            last=None
            for file in sorted((directory/side).glob("*.json.gz")):
                with gzip.open(file,"rb") as stream:
                    data=json.load(stream)
                for row in data["records"]:
                    rejection.update(row["rejections"])
                    options_admitted+=sum(status in {"straight","follow_physical_face",
                        "straight_extension_from_wall","turn_towards_originating_face"}
                        for _,status in row["outgoing"])
                    if example is None and any(s=="turn_towards_originating_face" for _,s in row["outgoing"]):
                        example=row
                    for record in row["closed"]:
                        key=sign,tuple(row["path"])
                        if key in paths:
                            continue
                        paths.add(key)
                        r=regions.setdefault(record["id"],{"vertices":record["vertices"],"paths":[]})
                        if r["vertices"]!=record["vertices"]:
                            raise ValueError("Region ID collision.")
                        r["paths"].append(record|{"hand":side,"ordered_directed_edges":row["path"]})
                last=data["after"]
            if last is not None:
                progress[f"{name}-{side}"]=last
    return regions,{"checkpoints":progress,"rejected_options":dict(rejection),
                     "accepted_outgoing_options":options_admitted,
                     "unique_closed_directed_paths":len(paths)},example


def uncovered_components(overlay):
    gaps=[r for r in overlay["faces"] if not r["multiplicity"]]
    graph=nx.Graph()
    graph.add_nodes_from(range(len(gaps)))
    owners=defaultdict(list)
    for i,r in enumerate(gaps):
        for a,b in edges(points(r)):
            owners[tuple(sorted((a,b)))].append(i)
    for group in owners.values():
        if len(group)==2:
            graph.add_edge(*group)
    return [{"atom_ids":sorted(g),"area":str(sum(F(gaps[i]["area"]) for i in g))}
            for g in nx.connected_components(graph)]


def stats(c):
    area=F(c["domain_area"])
    bands={int(k):F(v) for k,v in c["area_by_count"].items()}
    cumul=F(0)
    median=None
    for m,v in sorted(bands.items()):
        cumul+=v
        if cumul>=area/2:
            median=m
            break
    return {"covered_pct":c["covered_percent"],"domain_area":str(area),
            "covered_area":c["covered_area"],"uncovered_area":c["uncovered_area"],
            "maximum":max(bands),"minimum_nonzero":min((m for m,v in bands.items() if m and v),default=None),
            "mean":float(sum(m*v for m,v in bands.items())/area),"median":median,
            "bands_approx":{str(m):float(v) for m,v in bands.items()}}


def validate(regions,runner,domain,old257,study):
    checker=Checker(domain,runner.occupied)
    local=[]
    for key,r in regions.items():
        p=points(r)
        cert=checker.witness([],p,independent=True)
        if cert is None:
            raise ValueError(f"Independent convexity/domain/occupied check failed for {key}")
        supports={runner.crawler.tracks[runner.states[i][0]].face
                  for a in r["paths"] for i in a["ordered_directed_edges"]}
        if any(runner.crawler.faces[f].signed(v)<0 for f in supports for v in p):
            raise ValueError(f"An oriented support faces away from {key}.")
        r.update(area=str(exact_area(p)),perimeter_approx=sum(hypot(float(a[0]-b[0]),float(a[1]-b[1]))
                  for a,b in edges(p)),physical_support_faces=sorted(supports),
                 validation={"convex":True,"contained":True,"occupied_interior_or_island":False,
                             "outward_support":True})
        facet_proof=blocked_facets(checker,p)
        trial=None
        if not facet_proof:
            for a,b in edges(p):
                if probe:=edge_attempts(p,a,b,checker):
                    trial=checker.witness(p,points(probe),independent=True)
                    if trial:
                        trial|={"crossed_edge":probe["edge"]}
                        break
        r["maximality"]={"status":"proved_global" if facet_proof else
                        "counterexample" if trial else "unresolved","facet_certificate":facet_proof,
                        "enlargement":trial}
        planes=halfplanes(p+p[:1])
        if exact_area(convex_intersection(old257,planes)):
            local.append(key)
            r["strict_local_incidence"]=[i for i in (1435,1509)
                     if positive_interior(study.lines[i].start,study.lines[i].end,planes)]
    return local


def draw(out,atlas,runner,regions,coverage,local,example,previous):
    g=runner.crawler
    items=list(regions.values())
    old=[{"vertices":list(p.exterior.coords)} for p in atlas.regions.values()]
    numbered=[]
    def save(title,fig):
        file=out/f"{len(numbered)+1:02d}.pdf"
        plot_pdf(file,[fig])
        numbered.append((title,file))
    def start(title,subtitle,n=1,view=None):
        fig,axes=page(title,subtitle,n)
        for ax in axes:
            atlas.base(ax) if view is None else atlas.base(ax,view)
        return fig,axes
    def paths(ax,record,numbered=False):
        for j,i in enumerate(record["ordered_directed_edges"]):
            t,a,b=runner.states[i]
            track=g.tracks[t]
            lines(ax,[(a,b)],colors="#205a8b" if track.wall else "#bf6326",
                  linestyles="solid" if track.wall else "dashed",linewidths=1.25,zorder=7)
            if numbered and (j==0 or j%4==0):
                label(ax,xy(b),j+1,"#784126",size=6)
    def normals(ax,faces,length=.7):
        for i in faces:
            f=g.faces[i]
            a,b=xy(f.a),xy(f.b)
            mid=tuple((x+y)/2 for x,y in zip(a,b))
            d=(-(b[1]-a[1]),b[0]-a[0]);n=hypot(*d)
            endpoint=tuple(x+length*y/n for x,y in zip(mid,d))
            ax.annotate("",xy=endpoint,xytext=mid,arrowprops={"arrowstyle":"-|>","color":"#168a52",
                        "lw":1.0},zorder=8)
    def shape(ax,rows,alpha=.10,fill="#377fa8",outline="none"):
        draw_polygons(ax,rows,facecolors=fill,edgecolors=outline,linewidths=.47,alpha=alpha,zorder=3)
    fig,_=start("Corrected Flat 40","Archived numbered footprints and accessible geometry")
    save("Occupied and accessible geometry",fig)
    fig,(ax,)=start("Outward-oriented exposed faces","Normals are fixed by the accessible side of the physical face")
    normals(ax,[f.identifier for f in g.faces if f.blocks],.9)
    save("Outward-facing supports",fig)
    fig,(ax,)=start("Whole face-extension network","Blue extensions · Red occupied source faces")
    lines(ax,[(t.a,t.b) for t in g.tracks if not t.wall],colors="#4486af",linewidths=.35,zorder=4)
    lines(ax,[(f.a,f.b) for f in g.faces if f.blocks],colors="#b14932",linewidths=.7,zorder=5)
    save("Face-extension network",fig)
    fig,axes=start("Exact extension junctions","An exact intersection does not force a turn",2)
    ax=axes[0]
    nodes=[a for a,rows in g.outgoing.items() if len({r[0] for r in rows if not g.tracks[r[0]].wall})>1]
    if nodes:
        ax.scatter(*zip(*map(xy,nodes)),s=1.6,color="#286c8f",zorder=6)
    if example:
        ids=example["path"][-1:]
        node=runner.states[ids[0]][2]
        x,y=xy(node)
        ax=axes[1]
        ax.set(xlim=(x-3,x+3),ylim=(y-3,y+3))
        for i,reason in example["outgoing"]:
            t,a,b=runner.states[i]
            lines(ax,[(a,b)],colors="#078951" if reason=="turn_towards_originating_face" else "#9d9c9b",
                  linewidths=1.8,zorder=7)
        ax.scatter(x,y,s=25,c="#c67d25",zorder=9)
    save("Extension intersections and alternatives",fig)
    for hand in ("right","left"):
        fig,axes=start(f"{hand.capitalize()}-hand completed crawls","Numbered junctions follow saved exact directed paths",3)
        result=[(r,p) for r in items for p in r["paths"] if p["hand"]==hand]
        result=sorted(result,key=lambda row:-row[1]["turns_at_extensions"])
        chosen=[]
        for r,p in result:
            if r["vertices"] not in [v["vertices"] for v,_ in chosen]:
                chosen.append((r,p))
            if len(chosen)==3:
                break
        for ax,(r,p) in zip(axes,chosen):
            shape(ax,[r],.30)
            paths(ax,p,True)
            ax.set_title(f"{p['turns_at_extensions']} extension turns",fontsize=9,loc="left")
        save(f"{hand.capitalize()}-hand directed paths",fig)
    fig,(ax,)=start("New convex outlines",f"{len(items)} validated distinct polygons in the explored portion")
    shape(ax,items,1.,fill="none",outline="#206387")
    save("New convex outlines",fig)
    fig,axes=start("Transparent cover comparison","Identical map frame, one fill at α = 0.09 per polygon",3)
    for ax,rows,title in zip(axes,(old,previous,items),("Archived 292","Previous 2,201","Directed crawl · checkpoint")):
        shape(ax,rows,.09)
        ax.set_title(title,loc="left",fontsize=9)
    save("Three transparent covers at identical scale",fig)
    fig,(ax,)=start("Exact integer overlap","Polygon boundaries noded after generation")
    faces=coverage["faces"]
    top=max(p["multiplicity"] for p in faces)
    pcs=PolyCollection([list(map(xy,p["vertices"])) for p in faces],cmap="Blues",edgecolors="none",
                       norm=BoundaryNorm([p-.5 for p in range(top+2)],256),zorder=2)
    pcs.set_array([p["multiplicity"] for p in faces])
    ax.add_collection(pcs)
    ticks=sorted(set(range(0,top+1,max(1,(top+1)//12)))|{top})
    bar=fig.colorbar(pcs,ax=ax,ticks=ticks,pad=.025,label="Number of overlapping convex polygons")
    bar.solids.set_rasterized(False)
    save("Exact integer overlap",fig)
    fig,(ax,)=start("Exact uncovered accessible space","An incomplete enumeration cannot establish that the gaps are intrinsic")
    shape(ax,[p for p in faces if not p["multiplicity"]],.78,fill="#e58f5c")
    foot(fig,f"Covered {coverage['covered_percent']:.5f}% · orange marks exact gaps in the explored output")
    save("Uncovered-space overlay",fig)
    r=atlas.regions[257]
    x,y,X,Y=r.bounds
    fig,axes=start("Region 257  |  Cover and oriented supports","Exact original building plans and frozen axial intervals",2,
                   (x-4,X+4,y-4,Y+4))
    for ax in axes:
        shape(ax,[{"vertices":list(r.exterior.coords)}],1.,fill="none",outline="#cd8731")
        atlas.line(ax,1435,"#1f5b99",width=1.3,z=9)
        atlas.line(ax,1509,"#bb3940",width=1.3,z=9)
    shape(axes[0],[regions[k] for k in local],.16)
    axes[0].set_title(f"{len(local)} directed polygons overlap 257",loc="left")
    if local:
        record=regions[local[0]]
        shape(axes[1],[record],.24)
        paths(axes[1],record["paths"][0])
        normals(axes[1],record["physical_support_faces"])
    axes[1].set_title("Sample exact path and fixed normals",loc="left")
    foot(fig,"Gold archived 257 · Blue candidate 1435 · Red candidate 1509 · Green outward normals")
    save("Region 257 views",fig)
    candidate=next((regions[k] for k in local if regions[k]["maximality"]["enlargement"]),None)
    if candidate:
        growth=candidate["maximality"]["enlargement"]
        f=Polygon([xy(p) for p in growth["vertices"]])
        x,y,X,Y=f.bounds
        fig,axes=start("Region 257  |  A non-maximal completed polygon",
                       "The enlarged convex set was independently checked against physical boundaries and occupied cells",
                       2,(x-2,X+2,y-2,Y+2))
        for ax in axes:
            shape(ax,[candidate],1.,fill="none",outline="#336eab")
            lines(ax,[growth["crossed_edge"]],colors="#ad4728",linestyles="dashed",linewidths=1.6,zorder=6)
        shape(axes[1],[growth],.29,fill="#5ba476",outline="#18754e")
        axes[0].set_title("Completed directed polygon",loc="left")
        axes[1].set_title("Strict convex superset with exact clearance",loc="left")
        foot(fig,"Blue original boundary · Orange crossed facet · Green enlargement witness")
        save("Local non-maximality witness",fig)
    path=out/"flat40_directed_face_convex_atlas.pdf"
    tmp=out/".flat40_directed_face_convex_atlas.pdf"
    combine(tmp,numbered)
    import pymupdf
    with pymupdf.open(tmp) as pdf:
        if len(pdf)!=len(numbered) or any(p.get_images() for p in pdf):
            raise ValueError("The consolidated atlas is not entirely vector.")
    tmp.replace(path)


def main():
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("manifest","output","previous","archived-overlap"):
        p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--local-budget",type=int,default=0)
    p.add_argument("--render-only",action="store_true")
    a=p.parse_args()
    study,ch,_,domain,runner=geometry(a.manifest,a.output)
    atlas=Atlas(study,ch)
    if a.local_budget:
        targeted(runner,atlas.regions[257],a.local_budget)
    if a.render_only:
        saved=read(a.output/"regions.json")
        previous=read(a.previous)["components"][0]
        draw(a.output,atlas,runner,saved["regions"],read(a.output/"coverage.json"),
             saved["local_257"],collect(a.output)[2],list(previous["regions"].values()))
        return
    regions,search,example=collect(a.output)
    local=validate(regions,runner,domain,ring(atlas.regions[257]),study)
    overlay=exact_coverage(domain,[tuple(points(r)) for r in regions.values()])
    overlay["statistics"]=stats(overlay)
    overlay["uncovered_components"]=uncovered_components(overlay)
    previous=read(a.previous)["components"][0]
    archived=read(a.archived_overlap)
    comparison={"archived":stats(archived),"new":overlay["statistics"],"previous":{"maximum":11,
        "covered_pct":100.0,"mean":float(sum(int(k)*F(v) for k,v in previous["area_by_multiplicity"].items())/
                                              F(previous["domain_area"]))}}
    (a.output/"regions.json").write_bytes(encode({"regions":regions,"search":search,"local_257":local}))
    (a.output/"coverage.json").write_bytes(encode(overlay))
    (a.output/"comparison.json").write_bytes(encode(comparison))
    draw(a.output,atlas,runner,regions,overlay,local,example,list(previous["regions"].values()))
    print(len(regions),len(local),overlay["statistics"],len(overlay["uncovered_components"]),flush=True)


if __name__=="__main__":
    main()
