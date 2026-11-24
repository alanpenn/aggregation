"""Numbered vector and raster maps for the unrestricted Flat 40 study."""
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import ROOT
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.occupied_vertex_pruning_atlas import xy
from experiments.unrestricted_axial_reduction import DEST, ORDERS, Study
from voronoi_app.batch_methods import _settlement


def main():
    study=Study()
    cases={o:read(DEST/f"{o}.json") for o in ORDERS}
    best_order=min(ORDERS[:-1],key=lambda o:(len(cases[o]["final_ids"]),o))
    best=set(cases[best_order]["final_ids"])
    removed=set(study.previous["protected_winding_lines"])-best
    topology=study.full(best,faces=True)
    alternative=[(cycle["enclosed_blocks"], topology["witness_faces"][cycle["face_index"]])
                 for cycle in topology["circulation_cycles"]]
    polygons,_,_=_settlement(study.inputs)
    buildings={label:list(polygons[int(cell)].exterior.coords)[:-1]
               for cell,label in study.inputs["settlement"]["building_labels"].items()}
    segments=[[xy(row["start"]),xy(row["end"])] for row in read(OUTPUT/"flat-40.json")["lines"]]
    maps=DEST/"numbered-maps"
    maps.mkdir(exist_ok=True)
    index=[]

    def draw(pdf,key,title,ids,*,zoom=(),removed_lines=(),cycles=()):
        fig,ax=plt.subplots(figsize=(10,9))
        ax.add_collection(PolyCollection(list(buildings.values()),facecolor="#e8eeeb",
                                         edgecolor="#778b89",linewidth=.5))
        for label,ring in buildings.items():
            x,y=map(mean,zip(*ring))
            ax.text(x,y,str(label),ha="center",va="center",fontsize=6,clip_on=True,zorder=5)
        for members,color,alpha,label,width in (
            (ids,"#176891",.68,f"Retained ({len(ids)})",.8),
            (removed_lines,"#be543b",.64,f"Removed from original witnesses ({len(removed_lines)})",.8)):
            if members:
                ax.add_collection(LineCollection([segments[i] for i in sorted(members)],colors=color,
                                                 alpha=alpha,linewidths=width))
                ax.plot([],[],color=color,label=label)
        if cycles:
            ax.add_collection(LineCollection([[tuple(map(float,p)) for p in ring] for _,ring in cycles],
                                             colors="#74439a",alpha=.86,linewidths=1.5,zorder=4))
            ax.plot([],[],color="#74439a",label=f"Exact winding faces ({len(cycles)})")
        if zoom:
            x,y=zip(*(p for label in zoom for p in buildings[label]))
            ax.set(xlim=(min(x)-8,max(x)+8),ylim=(min(y)-8,max(y)+8))
        else:
            ax.set(xlim=(-1,101),ylim=(-1,101))
        ax.set(aspect="equal",title=title)
        ax.set_axis_off()
        ax.legend(loc="upper center",bbox_to_anchor=(.5,0),frameon=False)
        files={ext:f"numbered-maps/{key}.{ext}" for ext in ("pdf","png")}
        for ext,name in files.items():
            fig.savefig(DEST/name,bbox_inches="tight",dpi=330)
        pdf.savefig(fig,bbox_inches="tight")
        plt.close(fig)
        index.append({"title":title,"files":files,"candidate_ids":sorted(ids),
                      "removed_witness_ids":sorted(removed_lines),"building_closeup":list(zoom),
                      "winding_face_blocks":[blocks for blocks,_ in cycles]})

    with PdfPages(DEST/"flat-40-numbered-atlas.pdf") as pdf:
        draw(pdf,"repaired","Flat 40 · Repaired complementary pool",study.previous["repaired_ids"])
        draw(pdf,"conservative","Flat 40 · Conservative sheaf reduction",study.previous["retained"])
        for order,row in cases.items():
            draw(pdf,order,f"Flat 40 · {order.replace('-',' ').title()} standalone reduction",row["direct_ids"])
            if row["final_ids"]!=row["direct_ids"]:
                draw(pdf,f"{order}-exchange",f"Flat 40 · {order.replace('-',' ').title()} after exchanges",
                     row["final_ids"])
        draw(pdf,"strict-backward","Flat 40 · Archived strict backward",
             study.inputs["analysis"]["maps"]["strict_backward"]["line_ids"])
        draw(pdf,"constructive-d","Flat 40 · Constructive Algorithm D",
             read(ROOT/"flat-40/D.json")["maps"]["exchanged"])
        draw(pdf,"best-witnesses",f"Flat 40 · {best_order.replace('-',' ').title()} winding witnesses",
             best,removed_lines=removed,cycles=alternative)
        for zoom in ((15,25),(6,5),(41,43)):
            draw(pdf,f"buildings-{zoom[0]}-{zoom[1]}",f"Flat 40 · Buildings {zoom[0]} and {zoom[1]}",
                 best,zoom=zoom,removed_lines=removed,cycles=alternative)
    from voronoi_app.batch_store import atomic_write, encode
    atomic_write(DEST/"visual-index.json",encode({"pages":index,"best_order":best_order,
                 "winding_faces":[{"blocks":blocks,"ring":[list(map(str,p)) for p in ring]}
                                  for blocks,ring in alternative]}))


if __name__=="__main__":
    main()
