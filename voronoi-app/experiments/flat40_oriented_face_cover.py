"""Oriented-support replay and vector diagnostics for Flat 40."""
import argparse
from fractions import Fraction as F
from pathlib import Path
import sys
from math import hypot

from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm
import pymupdf

from experiments.flat40_exchange_atlas import Atlas, combine, foot, label, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, incidence, lines, load_inputs
from experiments.flat40_oriented_face_audit import audit, coordinates
from experiments.occupied_vertex_pruning import read
from experiments.oriented_face_extension_cover import checked_cover
from voronoi_app.batch_store import encode
from voronoi_app.research_data import sha256_file

GREEN="#08734d"
RED="#b62e47"


def arrow(ax,record,color,scale,caption=None):
    a,b=map(xy,record["face"])
    x,y=map(lambda t:sum(t)/2,zip(a,b))
    u,v=map(float,map(F,record["outward_normal"]))
    norm=hypot(u,v)
    ax.annotate("",xy=(x+scale*u/norm,y+scale*v/norm),xytext=(x,y),
                arrowprops={"arrowstyle":"-|>","color":color,"lw":1.15},zorder=12,
                annotation_clip=True)
    ax.plot(*zip(a,b),color=color,lw=1.25,zorder=9)
    if caption:
        label(ax,(x+scale*u/norm,y+scale*v/norm),caption,color,size=7)


def extent(geometry,margin):
    x,y,X,Y=geometry.bounds
    return x-margin,X+margin,y-margin,Y+margin


def visual(output,atlas,before,after,analysis):
    sources=[]
    local=analysis["local"]
    view=extent(atlas.regions[257],5)
    local_shapes=[before["regions"][key] for key in local]
    region257={"vertices":list(atlas.regions[257].exterior.coords)}
    local_ids=set(local)
    green_faces={row["face"] for key in local_ids for row in after["regions"][key]["physical_supports"]}
    red_faces={row["face"] for key in local_ids
               for row in after["regions"][key]["artificial_boundary_context"]
               if row["classification"]=="backward_extension_context"}

    def stress_shapes(ax,records):
        draw_polygons(ax,records,facecolors="#62afd2",edgecolors="#337490",
                      linewidths=.48,alpha=.19,zorder=4)
        draw_polygons(ax,[region257],facecolors="none",edgecolors="#df9a31",linewidths=2,zorder=7)
        atlas.line(ax,1435,"#245cb0",width=1.65,z=8)
        atlas.line(ax,1509,"#c83e2c",width=1.65,z=8)

    def save(name,title,fig):
        path=output/name
        plot_pdf(path,[fig])
        sources.append((title,path))

    fig,axes=page("Region 257  |  Outward-facing support audit",
                  "Same archived frame and extent. Normals belong to physical faces.",2)
    for ax in axes:
        atlas.base(ax,view)
    stress_shapes(axes[0],local_shapes)
    stress_shapes(axes[1],[after["regions"][k] for k in local])
    for key in sorted(red_faces):
        arrow(axes[0],analysis["faces"][key],RED,.56)
    for key in sorted(green_faces):
        arrow(axes[1],analysis["faces"][key],GREEN,.56)
    axes[0].set_title("Before · disputed parent normals shown in red",loc="left")
    axes[1].set_title("After · valid physical supports shown in green",loc="left")
    foot(fig,"Amber archived 257 · Blue candidate 1435 · Red candidate 1509 · Arrows point toward physical open space")
    save("01_region257_before_after.pdf","Before and after",fig)

    for number,(key,record) in enumerate(local.items(),2):
        p=after["regions"][key]
        rows=p["physical_supports"]+p["artificial_boundary_context"]
        fig,axes=page(f"Region {key}  |  Generating paths and support provenance",
                      "Arrow geometry starts on the original occupied face",2)
        atlas.base(axes[0],view)
        atlas.base(axes[1])
        rejected=[r for r in rows if r["classification"]=="backward_extension_context"]
        support=[r for r in rows if r["classification"]=="valid_physical_support"]
        for walk in record["walks"].values():
            path=walk["path"]
            lines(axes[0],[path+path[:1]],colors="#814b9a",linewidths=.8,zorder=5)
        for ax in axes:
            draw_polygons(ax,[p],facecolors="#83cbdb",edgecolors="#286b86",linewidths=1.1,alpha=.62,zorder=4)
            for j,r in enumerate(support+rejected,1):
                c=GREEN if r in support else RED
                arrow(ax,analysis["faces"][r["face"]],c,.68 if ax is axes[0] else 1.9,f"F{j}")
                for eid in r["extension_boundary_segments"]:
                    lines(ax,[analysis["extensions"][eid]["interval"]],colors=c,linewidths=.85,
                          linestyles="dashed",zorder=6)
        axes[0].set_title(f"Local · {len(record['walks'])} exact directed seed paths in purple",loc="left")
        axes[1].set_title("Full view · includes remote generating faces",loc="left")
        foot(fig,";  ".join(f"F{j}  {r['face']} · min signed {float(F(r['min_signed'])):.4g}"
                           for j,r in enumerate(support+rejected,1))[:195])
        save(f"{number:02d}_{key}.pdf",f"Region {key}",fig)

    fig,axes=page("Corrected overlap  |  Transparent cover and integer multiplicity",
                  "The semantic support correction preserves the exact cover",2)
    for ax in axes:
        atlas.base(ax)
    draw_polygons(axes[0],after["regions"].values(),facecolors="#2279ae",edgecolors="none",alpha=.10,zorder=2)
    atoms=after["atoms"]
    top=max(x["multiplicity"] for x in atoms)
    norm=BoundaryNorm([i-.5 for i in range(top+2)],256)
    collection=PolyCollection([list(map(xy,a["vertices"])) for a in atoms],cmap="Blues",
                              norm=norm,edgecolors="none",zorder=2)
    collection.set_array([a["multiplicity"] for a in atoms])
    axes[1].add_collection(collection)
    bar=fig.colorbar(collection,ax=axes[1],fraction=.040,ticks=range(top+1),pad=.025)
    bar.set_label("Number of overlapping convex regions")
    axes[0].set_title("Same blue at α = 0.10",loc="left")
    axes[1].set_title("Exact arrangement-face counts",loc="left")
    save("25_corrected_overlap.pdf","Corrected overlap",fig)
    target=output/"flat40_oriented_face_atlas.pdf"
    combine(target,sources)
    with pymupdf.open(target) as document:
        if len(document)!=25 or any(p.get_images() for p in document):
            raise ValueError("Unexpected orientation atlas export.")


def main():
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","arrangement","coverage","output"):
        p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args()
    study,ch,_,provenance,occupied,domain,blocks=load_inputs(args.manifest)
    archived=read(args.arrangement)
    if archived["provenance"]["lineage"]!=study.source or len(archived["components"])!=1:
        raise ValueError("The arrangement is from a different Flat 40 source.")
    component=archived["components"][0]
    atlas=Atlas(study,ch)
    analysis=audit(component,blocks,atlas.regions[257])
    corrected=checked_cover(component,analysis,domain,occupied)
    if F(corrected["exact_uncovered_area"]) or corrected["rejected"]:
        raise ValueError("The oriented family failed geometric validation.")
    for i in (1435,1509):
        if not study.clear(i):
            raise ValueError(f"Archived line {i} failed independent clearance.")
    matrix=incidence(study,corrected["regions"])
    old=read(args.coverage)
    if matrix!=old["incidence"]:
        raise ValueError("Replayed frozen coverage differs.")
    local=set(analysis["local"])
    effects={str(i):sorted(key for key,row in matrix.items() if i in row["line_ids"]) for i in (1435,1509)}
    unique=sorted(key for key,row in matrix.items() if set(row["line_ids"]).intersection(ch)=={1509})
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/"orientation-audit.json").write_bytes(encode(analysis|{
        "arrangement_sha256":sha256_file(args.arrangement),"coverage_sha256":sha256_file(args.coverage),
        "lineage":provenance["lineage"]}))
    (args.output/"oriented-cover.json").write_bytes(encode(corrected|{
        "coverage_by_candidate":effects,"unique_1509_in_archived_CH":unique,
        "unique_1509_in_local_CH":sorted(local.intersection(unique)),
        "local_coverage_by_candidate":{i:sorted(local.intersection(keys)) for i,keys in effects.items()},
        "same_region_ids":set(corrected["regions"])==set(component["regions"])}))
    visual(args.output,atlas,component,corrected,analysis)
    print(analysis["counts"],corrected["support_classification_counts"],
          {i:len(v) for i,v in effects.items()},len(unique),len(local.intersection(unique)),flush=True)


if __name__=="__main__":
    main()
