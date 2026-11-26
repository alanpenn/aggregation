"""Run and depict the Flat 40 face-extension convex-cover experiment."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from fractions import Fraction as F
from pathlib import Path
import sys

from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import BoundaryNorm
from matplotlib import pyplot as plt
from shapely import from_wkb
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from experiments.face_extension_cover import bounds, examine_component
from experiments.flat40_exchange_atlas import Atlas, BLUE, RED, FRAME, combine, foot, page, parts, plot_pdf, xy
from experiments.flat40_region257_inspection import convex_intersection, exact_area, ring
from experiments.near_collinear_consolidation import certificate, verified_study
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _ring_location
from voronoi_app.batch_methods import _domain
from voronoi_app.batch_store import encode
from voronoi_app.complementary_axial import ComplementaryStudy
from voronoi_app.region_incidence_angular import halfplanes, positive_interior
from voronoi_app.research_data import sha256_file


def points(record):
    return [tuple(map(F,p)) for p in record["vertices"]]


def draw_polygons(ax, items, **options):
    ax.add_collection(PolyCollection([list(map(xy,item["vertices"])) for item in items],**options))


def lines(ax, rows, **options):
    ax.add_collection(LineCollection([[xy(p) for p in row] for row in rows],**options))


def axes_outline(ax):
    ax.set(xlim=FRAME[:2],ylim=FRAME[2:],aspect="equal")
    ax.set_axis_off()


def stats(components):
    partition=all(c["partition_certified"] for c in components)
    areas=defaultdict(F)
    for component in components:
        for m,a in component["area_by_multiplicity"].items():
            areas[int(m)]+=F(a)
    total=sum(F(x["domain_area"]) for x in components)
    covered=sum(a for m,a in areas.items() if m)
    cumulative=F(0)
    median=None
    for m,a in sorted(areas.items()):
        cumulative+=a
        if cumulative>=total/2:
            median=m
            break
    return {"partition_certified":partition,"accessible_area":str(total),
            "covered_area":str(covered),"uncovered_area":str(total-covered),
            "covered_pct":float(100*covered/total),
            "minimum":min(areas) if partition else None,"maximum":max(areas),
            "mean":float(sum(m*a for m,a in areas.items())/total),
            "median":median,"area_by_count":{str(m):str(a) for m,a in areas.items()},
            "uncovered_or_unclassified_area_approx":float(total-covered),
            "bands_approx":{str(m):float(areas[m]) for m in (0,1,2,3)}|
                            {"4+":float(sum(a for m,a in areas.items() if m>=4))}}


def incidence(study, regions):
    def locate(poly):
        vertices=points(poly)
        return vertices+[vertices[0]]
    matrix={}
    endpoints=[(line.start,line.end) for line in study.lines]
    index=STRtree([bounds(seg) for seg in endpoints])
    door_points=[tuple(map(F,door["point"])) for door in study.inputs["analysis"]["incidence"]["doorways"]]
    for key,record in sorted(regions.items()):
        vertices=locate(record)
        minp,maxp=tuple(map(min,zip(*vertices))),tuple(map(max,zip(*vertices)))
        planes=halfplanes(vertices)
        ids=sorted(int(i) for i in index.query(bounds((minp,maxp))) if positive_interior(*endpoints[i],planes))
        doors=[j for j,p in enumerate(door_points) if _ring_location(vertices,p)>=0]
        matrix[key]={"line_ids":ids,"doorways":doors}
    return matrix


def select(study,regions,coverage,old):
    if any(not row["line_ids"] for row in coverage.values()):
        return {"status":"infeasible_with_frozen_candidates",
                "regions_without_candidate":[k for k,row in coverage.items() if not row["line_ids"]]}
    ids=sorted(regions)
    region_lines={str(i):coverage[k]["line_ids"] for i,k in enumerate(ids)}
    original=study.inputs
    doors=original["analysis"]["incidence"]["doorways"]
    door_regions=[[i for i,k in enumerate(ids) if j in coverage[k]["doorways"]] for j in range(len(doors))]
    if any(not values for values in door_regions):
        return {"status":"missing_doorway_region_incidence",
                "unrepresented_doorways":[j for j,r in enumerate(door_regions) if not r]}
    pool=dict(original["candidates"]["pool"])
    by_line=defaultdict(list)
    for i,k in enumerate(ids):
        for j in coverage[k]["line_ids"]:
            by_line[j].append(i)
    pool["candidates"]=[row|{"regions":by_line[row["id"]]} for row in pool["candidates"]]
    prepared_regions={str(i):Polygon([xy(v) for v in regions[k]["vertices"]]).wkb_hex for i,k in enumerate(ids)}
    records=original|{
        "candidates":original["candidates"]|{"pool":pool,"regions_wkb":prepared_regions},
        "analysis":original["analysis"]|{"incidence":{"region_lines":region_lines,
                "doorways":doors,"doorway_regions":door_regions}}}
    adapter=ComplementaryStudy(records,graph=study.graph)
    baseline=adapter.summary(old,independent=True)
    deleted=adapter.summary(set(old)-{1509},independent=True)
    prepared=adapter.prepare(lambda a,b=None:print(a,b or "",flush=True))
    result=adapter.reduce_prepared(prepared,"sheaf") if not prepared.failure else None
    return {"status":"certified" if result and result.certified else "incomplete",
            "region_id_order":ids,"CH_test":baseline,"CH_without_1509_test":deleted,
            "prepare_failure":prepared.failure,"stages":prepared.stages,
            "C-H":asdict(result) if result else None}


def atlas_files(output,atlas,components,regions,local_records,summary):
    sources=[]
    all_atoms=[a for c in components for a in c["atoms"]]
    all_regions=list(regions.values())
    raw_faces=[r["face"] for c in components for r in c["faces"].values()]
    extended=[r["interval"] for c in components for r in c["extensions"].values()]
    edges=[r["edge"] for c in components for r in c["edges"]]
    zero=[a for a in all_atoms if a["multiplicity"]==0]
    def one(title,subtitle,draw,n=1):
        fig,axes=page(title,subtitle,n)
        for ax in axes:
            atlas.base(ax)
        draw(fig,axes)
        file=output/f"{len(sources)+1:02d}.pdf"
        plot_pdf(file,[fig])
        sources.append((title,file))

    one("Corrected Flat 40","Archived numbered footprints and accessible domain",lambda f,a:None)
    one("Archived 292-region convex cover","Each region is drawn independently with the same opacity",
        lambda f,a:draw_polygons(a[0],[{"vertices":list(p.exterior.coords)} for p in atlas.regions.values()],
                                  facecolors="#2c74a8",edgecolors="#4986aa",linewidths=.25,alpha=.10,zorder=2))
    def exposed(f,a):
        lines(a[0],extended,colors="#4988b7",linewidths=.38,zorder=4)
        lines(a[0],raw_faces,colors="#bb5136",linewidths=.8,zorder=5)
        foot(f,"Red  Exposed occupied faces   ·   Blue  Extensions, terminated at the first boundary event")
    one("Exposed faces and extensions","Original boundary faces are distinct from their extensions",exposed)
    def planar(f,a):
        lines(a[0],edges,colors="#5691a7",linewidths=.35,zorder=4)
        vertices={tuple(p) for e in edges for p in e}
        a[0].scatter(*zip(*(xy(x) for x in vertices)),s=.65,c="#003d64",zorder=5)
        foot(f,"Nodes mark rational intersections. Directed states and CCW incident order are in arrangement.json.")
    one("Noded planar arrangement",f"{len(edges):,} embedded edges",planar)
    one("Generated convex polygons",f"{len(regions):,} convex polygons within the tested growth construction",
        lambda f,a:draw_polygons(a[0],all_regions,facecolors="none",edgecolors="#24658c",linewidths=.4,alpha=.42,zorder=4))
    one("Transparent overlap map","All convex polygons use the same blue and opacity 0.10",
        lambda f,a:draw_polygons(a[0],all_regions,facecolors="#1565a0",edgecolors="none",alpha=.10,zorder=2))
    def overlay(a,atoms):
        top=summary["maximum"]
        norm=BoundaryNorm([i-.5 for i in range(top+2)],256)
        collection=PolyCollection([list(map(xy,x["vertices"])) for x in atoms],
                                  cmap="Blues",norm=norm,edgecolors="none",zorder=2)
        collection.set_array([x["multiplicity"] for x in atoms])
        a.add_collection(collection)
        return collection
    def counts(f,a):
        collection=overlay(a[0],all_atoms)
        bar=f.colorbar(collection,ax=a[0],fraction=.035,pad=.02,
                       ticks=range(summary["maximum"]+1))
        bar.set_label("Number of overlapping convex regions")
        foot(f,"Area by multiplicity in model units  ·  " +
             "    ".join(f"{k}: {v:.2f}" for k,v in summary["bands_approx"].items()))
    one("Exact overlap multiplicity","Counts come from rational arrangement atoms",counts)
    def diagnostic(f,a):
        c=components[0]
        face_id=max(c["face_starts"],key=lambda k:len({v["atom"] for v in c["face_starts"][k] if v["atom"] is not None}))
        face=c["faces"][face_id]
        for ax,hand in zip(a,("left","right")):
            lines(ax,edges,colors="#9eb7c0",linewidths=.16,zorder=3)
            starts=[s for s in c["face_starts"][face_id] if s["hand"]==hand]
            hit={s["atom"] for s in starts if s["atom"] is not None}
            draw_polygons(ax,[c["atoms"][i] for i in hit],facecolors="#abeea9",edgecolors="#167752",zorder=4)
            lines(ax,[face["face"]],colors="#c32b27",linewidths=2.1,zorder=6)
            ax.set_title(f"{hand.capitalize()}-handed · {len(starts)} directed starts · {len(hit)} accessible atoms",loc="left")
        foot(f,f"Physical face {face_id} · Red originating face · Green reachable arrangement faces")
    one("Face starts and handedness","Opposite signed walks are kept in the provenance",diagnostic,2)
    def gaps(f,a):
        draw_polygons(a[0],zero,facecolors="#df5039",edgecolors="#b72d1e",linewidths=.7,zorder=4)
        foot(f,f"Coverage {summary['covered_pct']:.9f}% · Uncovered exact atom area {summary['uncovered_or_unclassified_area_approx']:.6g}")
    one("Uncovered-space check","Exact partition checked against the archived accessible area",gaps)
    def compare(f,a):
        draw_polygons(a[0],[{"vertices":list(p.exterior.coords)} for p in atlas.regions.values()],
                      facecolors="none",edgecolors="#b47c3d",linewidths=.43,alpha=.5,zorder=4)
        draw_polygons(a[0],all_regions,facecolors="none",edgecolors="#21779e",linewidths=.32,alpha=.53,zorder=5)
        foot(f,"Amber  Archived cover outlines   ·   Blue  Face-extension polygons")
    one("Comparison with archived convex cover","Same coordinates and scale",compare)
    local=atlas.regions[257]
    x,y,X,Y=local.bounds
    def views(f,a):
        local_ids=set(local_records["regions_touching_257"])
        for ax in a:
            ax.set(xlim=(x-3,X+3),ylim=(y-3,Y+3))
        draw_polygons(a[0],[{"vertices":list(p.exterior.coords)} for p in atlas.regions.values()],
                      facecolors="none",edgecolors="#bb7c26",linewidths=.7,zorder=3)
        lines(a[0],extended,colors="#91b7c5",linewidths=.5,zorder=4)
        draw_polygons(a[1],[regions[i] for i in local_ids],facecolors="#37a6cc",edgecolors="#0e6c91",
                      linewidths=.55,alpha=.17,zorder=4)
        overlay(a[2],all_atoms)
        for ax in a:
            draw_polygons(ax,[{"vertices":list(local.exterior.coords)}],facecolors="none",
                          edgecolors="#d38b28",linewidths=2,zorder=7)
            atlas.line(ax,1435,BLUE,width=1.65,z=8)
            atlas.line(ax,1509,RED,width=1.65,z=8)
        for ax,title in zip(a,("Archived outlines and extensions","New polygons overlapping 257","Local integer overlap")):
            ax.set_title(title,loc="left")
        foot(f,"Amber  Region 257   ·   Blue  1435   ·   Red  1509")
    one("Region 257  |  Local boundary and overlap comparison","Three matched views",views,3)
    combine(output/"face_extension_cover_atlas.pdf",sources)


def load_inputs(manifest):
    study,ch,d,provenance=verified_study(manifest)
    _,occupied,accessible,_=_domain(study.inputs)
    blocks=[(name,p) for name,wkb in study.inputs["topology"]["blocks_wkb"].items() for p in parts(from_wkb(wkb))]
    return study,ch,d,provenance,occupied,accessible,blocks


def replay_archived_cover(study):
    adapter=ComplementaryStudy(study.inputs,graph=study.graph)
    prepared=adapter.prepare(lambda a,b=None:print(a,b or "",flush=True))
    result=adapter.reduce_prepared(prepared,"sheaf") if not prepared.failure else None
    return {"stage_counts":{k:len(v) for k,v in prepared.stages.items()},
            "failure":prepared.failure,"C-H":asdict(result) if result else None}


def main():
    sys.set_int_max_str_digits(0)
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--manifest",required=True,type=Path)
    cli.add_argument("--output",required=True,type=Path)
    cli.add_argument("--checkpoint",type=Path)
    cli.add_argument("--replay-archived-cover",action="store_true")
    args=cli.parse_args()
    study,ch,d,provenance,occupied,accessible,blocks=load_inputs(args.manifest)
    checkpoint_identity={"source":study.source,
                         "geometry_code_sha256":sha256_file(Path(__file__).with_name("face_extension_cover.py"))}
    args.output.mkdir(parents=True,exist_ok=False)
    atlas=Atlas(study,ch)

    def preview(graph, faces, extensions):
        fig,(ax,)=page("Arrangement before convex growth",
                       "Exact noded geometry from the archived accessible domain")
        atlas.base(ax)
        lines(ax,[(a,b) for a,b in graph.edges],colors="#538497",linewidths=.36,zorder=4)
        lines(ax,[row["face"] for row in faces.values()],colors="#b95033",linewidths=.65,zorder=5)
        target=args.output/"arrangement_before_growth.pdf"
        plot_pdf(target,[fig])

    if args.checkpoint and args.checkpoint.exists():
        checkpoint=read(args.checkpoint)
        if checkpoint["identity"]!=checkpoint_identity:
            raise ValueError("Arrangement checkpoint is from different geometry inputs or code.")
        components=checkpoint["components"]
    else:
        components=[examine_component(p,blocks,occupied,arrangement_observer=preview) for p in parts(accessible)]
        if args.checkpoint:
            with args.checkpoint.open("xb") as stream:
                stream.write(encode({"identity":checkpoint_identity,"components":components}))
    summary=stats(components)
    regions={k:r for c in components for k,r in c["regions"].items()}
    matrix=incidence(study,regions)
    ch_set=set(ch)
    near=ring(atlas.regions[257])
    local={"regions_touching_257":[k for k,r in regions.items()
           if exact_area(convex_intersection(near,halfplanes(points(r)+points(r)[:1])))],
           "regions_covered_by_1435":[k for k,row in matrix.items() if 1435 in row["line_ids"]],
           "regions_covered_by_1509":[k for k,row in matrix.items() if 1509 in row["line_ids"]],
           "only_1509_in_CH":[k for k,row in matrix.items() if ch_set.intersection(row["line_ids"])=={1509}]}
    with (args.output/"arrangement.json").open("xb") as stream:
        stream.write(encode({"provenance":provenance|checkpoint_identity,"components":components}))
    with (args.output/"coverage.json").open("xb") as stream:
        stream.write(encode({"summary":summary,"regions":len(regions),"incidence":matrix,"local_257":local}))
    atlas_files(args.output,atlas,components,regions,local,summary)
    experiment={"mode_A":{"C-H":certificate(study,ch_set),"D":certificate(study,set(d))}}
    experiment["mode_B"]=(select(study,regions,matrix,ch) if summary["partition_certified"] and
                          not F(summary["uncovered_area"]) else {"status":"incomplete_open_space_cover"})
    with (args.output/"selection.json").open("xb") as stream:
        stream.write(encode(experiment))
    if args.replay_archived_cover:
        with (args.output/"matched-mode-A-replay.json").open("xb") as stream:
            stream.write(encode(replay_archived_cover(study)))


if __name__=="__main__":
    main()
