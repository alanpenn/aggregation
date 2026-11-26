"""Flat 40 directed-wall pilot with an independent exact coverage overlay."""
import argparse
from collections import defaultdict, deque
from fractions import Fraction as F
from hashlib import sha256
from itertools import pairwise
from pathlib import Path
import sys

from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm
import pymupdf
from shapely.geometry.polygon import orient

from experiments.directed_boundary_cover import Crawler, validate_obstacles
from experiments.directed_boundary_reference import L_ROOM, LOW, UP
from experiments.face_extension_cover import arrangement, crawl, edge, rings
from experiments.flat40_enlarged_cover import coalesce_collinear
from experiments.flat40_exchange_atlas import Atlas, combine, foot, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, lines, load_inputs, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed, ring
from voronoi_app.angular import _cross, _intersections
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes
from voronoi_app.research_data import sha256_file


def exact_coverage(domain, polygons):
    """Overlay completed polygons only after generation; permit exact gaps."""
    records=defaultdict(set)
    values={}
    outer,*holes=rings(orient(domain,sign=1))
    # Auxiliary lines connect otherwise disjoint boundary rings solely for
    # the overlay. They have zero winding jump and never enter the crawler.
    lo=min(point[0] for point in outer)-1
    hi=max(point[0] for point in outer)+1
    for h in holes:
        y=h[0][1]
        records[edge((lo,y),(hi,y))].add("overlay-zero")
    for axis,families in enumerate(([p[:-1] for p in [outer,*holes]],list(polygons))):
        for i,shape in enumerate(families):
            shape=list(shape)
            for j,(a,b) in enumerate(pairwise(shape+shape[:1])):
                key=(axis,i,j)
                records[edge(a,b)].add(key)
                values[key]=(axis,1 if a<b else -1)
    graph=arrangement(coalesce_collinear(records))
    walks,indices,_=crawl(graph)
    index=indices["right"]
    areas={i:sum((_cross(a,b) for a,b in path),F(0))/2
           for i,(kind,path,closed) in walks.items() if kind=="right" and closed}
    outside=[i for i,a in areas.items() if a<0]
    if len(outside)!=1:
        raise ValueError("Exact overlay has no unique exterior orbit.")
    arcs=defaultdict(list)
    for a,b,row in graph.edges(data=True):
        a,b=edge(a,b)
        left,right=index[a,b],index[b,a]
        delta=[0,0]
        for tag in row["sources"]-{"overlay-zero"}:
            axis,sign=values[tag]
            delta[axis]+=sign
        arcs[right].append((left,*delta))
        arcs[left].append((right,-delta[0],-delta[1]))
    labels={outside[0]:(0,0)}
    pending=deque(outside)
    while pending:
        i=pending.popleft()
        for j,dx,dy in arcs[i]:
            label=labels[i][0]+dx,labels[i][1]+dy
            if j not in labels:
                labels[j]=label
                pending.append(j)
            elif labels[j]!=label:
                raise ValueError("Inconsistent domain or overlap labels.")
    if set(labels)!=set(areas):
        raise ValueError("Overlay has an unreached face.")
    total=defaultdict(F)
    faces=[]
    for i,(inside,count) in labels.items():
        if inside not in (0,1) or count<0 or (not inside and count):
            raise ValueError("A generated polygon extends outside accessible space.")
        if inside:
            if areas[i]<=0:
                raise ValueError("Degenerate accessible face.")
            total[count]+=areas[i]
            faces.append({"vertices":packed([a for a,b in walks[i][1]]),
                          "area":str(areas[i]),"multiplicity":count})
    expected=exact_area(outer)-sum(exact_area(h) for h in holes)
    if sum(total.values())!=expected:
        raise ValueError("Overlay does not reproduce the rational accessible area.")
    if sum(m*area for m,area in total.items())!=sum(exact_area(list(p)) for p in polygons):
        raise ValueError("Multiplicity-weighted area does not match the region area sum.")
    uncovered=total[0]
    return {"domain_area":str(expected),"covered_area":str(expected-uncovered),
            "uncovered_area":str(uncovered),"covered_percent":float(100*(expected-uncovered)/expected),
            "full_coverage":not uncovered,"area_by_count":{str(k):str(v) for k,v in total.items()},
            "faces":faces}


def atlas_files(out,atlas,regions,attempts,coverage,local):
    records=[]
    def save(title,fig):
        p=out/f"{len(records)+1:02d}.pdf"
        plot_pdf(p,[fig])
        records.append((title,p))
    fig,(ax,)=page("Corrected Flat 40","Archived building footprints and accessible open space")
    atlas.base(ax)
    save("Original Flat 40",fig)

    items=list(regions.values())
    fig,axes=page("Directed boundary crawl  |  Generated polygons",
                  "Exact wall walks only. No arrangement atoms used for construction.",2)
    for ax in axes:
        atlas.base(ax)
    draw_polygons(axes[0],items,facecolors="none",edgecolors="#215c83",linewidths=1.1,zorder=5)
    draw_polygons(axes[1],items,facecolors="#287ea7",edgecolors="none",alpha=.10,zorder=3)
    axes[0].set_title(f"{len(items)} distinct rational outlines",loc="left")
    axes[1].set_title("Same fill and opacity for every polygon",loc="left")
    save("Generated regions and translucent overlap",fig)

    fig,axes=page("Exact overlap and coverage check","Counts are computed after the polygons have closed",2)
    for ax in axes:
        atlas.base(ax)
    faces=coverage["faces"]
    top=max(record["multiplicity"] for record in faces)
    collection=PolyCollection([list(map(xy,r["vertices"])) for r in faces],cmap="Blues",
        norm=BoundaryNorm([k-.5 for k in range(top+2)],256),edgecolors="none",zorder=2)
    collection.set_array([r["multiplicity"] for r in faces])
    axes[0].add_collection(collection)
    fig.colorbar(collection,ax=axes[0],fraction=.032,ticks=range(top+1),pad=.02,
                 label="Number of overlapping convex regions")
    draw_polygons(axes[1],[r for r in faces if not r["multiplicity"]],
                  facecolors="#e49a71",edgecolors="none",alpha=.68,zorder=2)
    axes[0].set_title("Exact integer multiplicity",loc="left")
    axes[1].set_title("Uncovered accessible space in orange",loc="left")
    foot(fig,f"Exact cover validation · {coverage['covered_percent']:.5f}% of accessible area covered")
    save("Exact overlap and uncovered area",fig)

    fig,axes=page("Archived region 257  |  Local comparison","Both panels share the same extent",2)
    p=atlas.regions[257]
    x,y,X,Y=p.bounds
    view=(x-4,X+4,y-4,Y+4)
    for ax in axes:
        atlas.base(ax,view)
        draw_polygons(ax,[{"vertices":list(p.exterior.coords)}],facecolors="none",
                      edgecolors="#ab6c30",linewidths=1.5,zorder=7)
        atlas.line(ax,1435,"#185997",width=1.2,z=8)
        atlas.line(ax,1509,"#bd384a",width=1.2,z=8)
    draw_polygons(axes[0],items,facecolors="#70b7d0",edgecolors="#296987",alpha=.28,zorder=4)
    draw_polygons(axes[1],[r for r in faces if not r["multiplicity"]],
                  facecolors="#e49a71",edgecolors="none",alpha=.58,zorder=3)
    axes[0].set_title(f"Completed regions · {len(local['interior_overlapping_region_ids'])} overlap 257",loc="left")
    axes[1].set_title("Exact uncovered-space overlay",loc="left")
    foot(fig,"Amber outline archived 257 · Blue 1435 · Red 1509")
    save("Local region 257 geometry",fig)

    if items:
        detail=max(items,key=lambda r:F(r["area"]))
        attempt=attempts[detail["generating_attempts"][0]]
        fig,(ax,)=page("Representative completed Flat 40 walk",
                        f"Source face {attempt['face']} · {attempt['direction']} · {attempt['hand']} hand on wall")
        atlas.base(ax)
        draw_polygons(ax,[detail],facecolors="#80c79e",edgecolors="#286c55",alpha=.42,zorder=3)
        for event in attempt["path"]:
            if event["type"] in {"physical_face","straight_extension"}:
                artificial=event["type"]=="straight_extension"
                lines(ax,[event["interval"]],colors="#bb532b" if artificial else "#235c85",
                      linewidths=1.4,linestyles="dashed" if artificial else "solid",zorder=6)
        foot(fig,"Blue physical faces · Dashed orange straight extensions · Exact ordered paths in generation.json")
        save("Representative exact directed path",fig)
    if direct:=local["physical_face_endpoint_attempts"]:
        fig,axes=page("Region 257  |  Directed walks that could not close",
                      "Starts on the occupied faces that touch the archived region",len(direct))
        positions=[xy(p) for i in direct for event in attempts[i]["path"]
                   if "interval" in event for p in event["interval"]]
        x,y=map(min,zip(*positions))
        X,Y=map(max,zip(*positions))
        for ax,i in zip(axes,direct):
            a=attempts[i]
            atlas.base(ax,(x-2,X+2,y-2,Y+2))
            draw_polygons(ax,[{"vertices":list(p.exterior.coords)}],facecolors="none",
                          edgecolors="#927432",linewidths=1.,zorder=7)
            for event in a["path"]:
                if event["type"] in {"physical_face","straight_extension"}:
                    ex=event["type"]=="straight_extension"
                    lines(ax,[event["interval"]],colors="#b04b2c" if ex else "#215f8d",
                          linestyle="dashed" if ex else "solid",linewidths=1.35,zorder=8)
            ax.set_title(f"Face {a['face']} · {a['direction']}",loc="left",fontsize=9)
        foot(fig,"Blue physical travel · Orange straight extensions · Ochre archived region 257 · No convex departure at the last boundary hit")
        save("Region 257 originating-wall failures",fig)
    destination=out/"flat40_directed_boundary_atlas.pdf"
    combine(destination,records)
    with pymupdf.open(destination) as doc:
        if len(doc)!=len(records) or any(p.get_images() for p in doc):
            raise ValueError("Unexpected non-vector atlas export.")


def main(manifest,reference,output):
    fixture,_,_=Crawler(L_ROOM).construct()
    if set(fixture)!={LOW,UP}:
        raise ValueError("L-room reference failed. Flat 40 was not attempted.")
    study,ch,_,provenance,occupied,domain,blocks=load_inputs(manifest)
    builder=Crawler(domain,blocks)
    complete,attempts,status=builder.construct()
    regions={}
    for shape,starts in complete.items():
        if rejected:=validate_obstacles(shape,occupied):
            raise ValueError(f"Independent occupied-cell intersection: {rejected}.")
        vertices=packed(shape)
        key=sha256(encode(vertices)).hexdigest()[:16]
        regions[key]={"vertices":vertices,"generating_attempts":starts,
                      "area":str(exact_area(list(shape)))}
    # Strict inclusion within the traced family is the only pruning rule.
    for key,r in list(regions.items()):
        p=points(r)
        for k,q in regions.items():
            if k==key or F(q["area"])<=F(r["area"]):
                continue
            v=points(q)
            planes=halfplanes(v+v[:1])
            if exact_area(convex_intersection(p,planes))==F(r["area"]):
                r["contained_in"]=k
                break
    retained={k:r for k,r in regions.items() if "contained_in" not in r}
    coverage=exact_coverage(domain,[points(r) for r in retained.values()])
    atlas=Atlas(study,ch)
    p=ring(atlas.regions[257])
    planes=halfplanes(p)
    wall_ids={f.identifier for f in builder.faces if f.blocks and
              any(len(_intersections(f.a,f.b,a,b))==2 for a,b in pairwise(p))}
    wall_attempts=[i for i,a in enumerate(attempts) if a["face"] in wall_ids
                   and a["start_point"]==packed([builder.faces[a["face"]].a if a["hand"]=="right"
                                                else builder.faces[a["face"]].b])[0]]
    local={"archived_region":257,"interior_overlapping_region_ids":
        [k for k,r in retained.items() if exact_area(convex_intersection(points(r),planes))],
        "uncovered_area_within_257":str(sum(
            exact_area(convex_intersection(points(r),planes)) for r in coverage["faces"]
            if not r["multiplicity"])),
           "physical_face_endpoint_attempts":wall_attempts}
    output.mkdir(parents=True,exist_ok=False)
    (output/"generation.json").write_bytes(encode({"faces":builder.face_records(),
        "attempts":attempts,"statuses":dict(status),"regions":regions,"retained_ids":sorted(retained),
        "input_provenance":provenance|{"reference_sha256":sha256_file(reference),
            "crawler_sha256":sha256_file(Path(__file__).with_name("directed_boundary_cover.py"))}}))
    (output/"coverage.json").write_bytes(encode(coverage|{"local_257":local}))
    atlas_files(output,atlas,retained,attempts,coverage,local)
    print("Flat 40",len(retained),"regions",coverage["covered_percent"],"% coverage",status,local)


if __name__=="__main__":
    sys.set_int_max_str_digits(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","reference","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    main(args.manifest,args.reference,args.output)
