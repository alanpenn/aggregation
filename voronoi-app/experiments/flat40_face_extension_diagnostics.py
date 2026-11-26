"""Additional audited maps for a completed Flat 40 face-extension run."""
import argparse
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
import sys

from shapely.geometry import Polygon
from shapely.strtree import STRtree

from experiments.face_extension_cover import hull
from experiments.flat40_exchange_atlas import Atlas, combine, foot, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, lines, load_inputs, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, ring
from experiments.occupied_vertex_pruning import read
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes
from voronoi_app.research_data import sha256_file


def equivalences(atlas, regions):
    names=list(regions)
    polygons=[Polygon([xy(p) for p in regions[k]["vertices"]]) for k in names]
    tree=STRtree(polygons)
    areas=[F(regions[k]["area"]) for k in names]
    canonical={hull(points(regions[k])):k for k in names}
    old_matches={}
    new_matches=set()
    for i,archived in atlas.regions.items():
        coords=ring(archived)
        area=exact_area(coords)
        matches=[]
        for j in tree.query(archived):
            if min(area,areas[j])*5 < max(area,areas[j])*4:
                continue
            r=points(regions[names[j]])
            overlap=exact_area(convex_intersection(coords,halfplanes(r+r[:1])))
            if 5*overlap>=4*(area+areas[j]-overlap):
                matches.append({"new_id":names[j],"jaccard":str(overlap/(area+areas[j]-overlap))})
                new_matches.add(names[j])
        old_matches[i]={"exact_match":canonical.get(hull(coords)),
                        "intersection_over_union_at_least_0.8":matches}
    return {"by_archived_id":old_matches,"archived_with_no_close_equivalent":[i for i,v in old_matches.items()
               if not v["intersection_over_union_at_least_0.8"]],
            "new_with_no_close_equivalent":sorted(set(names)-new_matches)}


def diagnostics(output,manifest):
    study,ch,d,provenance,*_=load_inputs(manifest)
    arrangement=read(output/"arrangement.json")
    coverage=read(output/"coverage.json")
    selection=read(output/"selection.json")
    if provenance["lineage"]!=arrangement["provenance"]["lineage"]:
        raise ValueError("The arrangement belongs to another settlement.")
    atlas=Atlas(study,ch)
    components=arrangement["components"]
    regions={k:r for c in components for k,r in c["regions"].items()}
    equivalence=equivalences(atlas,regions)
    figures=[]
    highest=max((a for c in components for a in c["atoms"]),key=lambda a:(a["multiplicity"],F(a["area"])))
    x,y,X,Y=Polygon([xy(p) for p in highest["vertices"]]).bounds
    fig,(ax,)=page("High-overlap detail",f"Peak multiplicity {highest['multiplicity']} on an exact arrangement face")
    atlas.base(ax,(x-2.6,X+2.6,y-2.6,Y+2.6))
    overlap=[r for r in regions.values() if any(
        i in r["atoms"] for i,a in enumerate(components[0]["atoms"]) if a is highest)]
    draw_polygons(ax,overlap,facecolors="#2577ab",edgecolors="#285c77",linewidths=.6,alpha=.12,zorder=4)
    draw_polygons(ax,[highest],facecolors="#f0b766",edgecolors="#a25c26",linewidths=1.45,zorder=5)
    foot(fig,"Amber marks a peak face. Blue polygons are its covering regions.")
    path=output/"12_high_overlap.pdf"
    plot_pdf(path,[fig])
    figures.append(("High-overlap detail",path))

    comp=components[0]
    seeds_to_regions=defaultdict(set)
    for key,row in comp["regions"].items():
        for start in row["starts"]:
            seeds_to_regions[start["seed"]].add(key)
    def direction_sets(starts):
        groups=defaultdict(set)
        for start in starts:
            groups[start["hand"],start["direction"]].update(seeds_to_regions.get(start["atom"],set()))
        return groups
    face,starts=max(comp["face_starts"].items(),key=lambda item:
                     len(set.union(set(),*direction_sets(item[1]).values())))
    groups=direction_sets(starts)
    shape=comp["faces"][face]["face"]
    x,y,X,Y=Polygon([xy(p) for v in set.union(set(),*groups.values())
                     for p in regions[v]["vertices"]]).bounds
    fig,axes=page("Generated regions from one physical face",
                  "Each panel uses the same orientation and scale",4)
    for ax,hand,direction in zip(axes,("right","right","left","left"),(0,1,0,1)):
        atlas.base(ax,(x-1,X+1,y-1,Y+1))
        associated=groups[hand,direction]
        draw_polygons(ax,[regions[i] for i in associated],facecolors="#67bd9b",
                      edgecolors="#12664a",linewidths=.6,alpha=.20,zorder=4)
        lines(ax,[shape],colors="#be382d",linewidths=2,zorder=7)
        ax.set_title(f"{hand} · dir {direction} · {len(associated)} regions",loc="left",fontsize=9)
    foot(fig,f"Exposed face {face} · The complementary direction and handedness reverse the boundary walk.")
    path=output/"13_directed_result_detail.pdf"
    plot_pdf(path,[fig])
    figures.append(("Directed growth detail",path))
    mode=selection["mode_B"]
    if mode["status"]=="certified":
        fig,axes=page("Axial selection comparison","Exact archived intervals with alternate region incidence",2)
        for ax,ids,title in zip(axes,(ch,mode["C-H"]["ids"]),
                              (f"Mode A · {len(ch)} lines",f"Mode B · {len(mode['C-H']['ids'])} lines")):
            atlas.base(ax)
            lines(ax,[(study.lines[i].start,study.lines[i].end) for i in ids],
                  colors="#17658b",linewidths=.7,zorder=5)
            ax.set_title(title,loc="left")
        path=output/"14_axial_maps.pdf"
        plot_pdf(path,[fig])
        figures.append(("Axial selection comparison",path))
    with (output/"geometric-comparison.json").open("xb") as stream:
        stream.write(encode({"equivalence":equivalence,
            "arrangement_sha256":sha256_file(output/"arrangement.json"),
            "representative_originating_face":face,
            "starting_state_regions":{f"{hand}:{direction}":sorted(ids) for (hand,direction),ids in groups.items()}}))
    import pymupdf
    atlas_path=output/"face_extension_cover_atlas.pdf"
    with pymupdf.open(atlas_path) as pdf:
        toc=pdf.get_toc()
    sources=[(title,output/f"{number:02d}.pdf") for _,title,number in toc]
    combine(output/"face_extension_complete_atlas.pdf",sources+figures)


if __name__=="__main__":
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    diagnostics(args.output,args.manifest)
