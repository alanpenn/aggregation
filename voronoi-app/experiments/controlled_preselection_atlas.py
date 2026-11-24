"""Numbered paired maps of the matched Flat 40 preselection experiment."""
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import load
from experiments.controlled_preselection import DEST, ORDERS
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.occupied_vertex_pruning_atlas import xy
from voronoi_app.batch_methods import _settlement
from voronoi_app.batch_store import atomic_write, encode


def main():
    inputs, _, _ = load("flat-40")
    cells, _, _ = _settlement(inputs)
    buildings = {label: list(cells[int(cell)].exterior.coords)[:-1]
                 for cell, label in inputs["settlement"]["building_labels"].items()}
    intervals = [[xy(row["start"]), xy(row["end"])] for row in read(OUTPUT/"flat-40.json")["lines"]]
    index=[]
    with PdfPages(DEST/"flat-40-numbered-comparison.pdf") as pdf:
        for order in ORDERS:
            runs=[read(DEST/f"{p}-{order}.json") for p in ("F","C")]
            for phase in ("direct","final"):
                ids=[set(row[f"{phase}_ids"]) for row in runs]
                shared=ids[0] & ids[1]
                fig,axes=plt.subplots(1,2,figsize=(15,8))
                fig.suptitle(f"Flat 40 · {order.replace('-', ' ').title()} · "
                             f"{'After single deletions' if phase=='direct' else 'After exchanges'}")
                for ax,keep,title,color in zip(axes,ids,("Full certified start","Complementary start"),
                                               ("#1a6d90","#b64d37"),strict=True):
                    ax.add_collection(PolyCollection(list(buildings.values()),facecolor="#e7edeb",
                                                     edgecolor="#7d8c8c",linewidth=.45))
                    for group,tone,label in ((shared,"#636d71","Shared"),(keep-shared,color,"Only in this map")):
                        ax.add_collection(LineCollection([intervals[i] for i in sorted(group)],
                                                         colors=tone, linewidths=.86,alpha=.85))
                        ax.plot([],[],color=tone,label=f"{label} ({len(group)})")
                    for label,ring in buildings.items():
                        x,y=map(mean,zip(*ring))
                        ax.text(x,y,str(label),ha="center",va="center",fontsize=6,zorder=4)
                    ax.set(xlim=(-1,101),ylim=(-1,101),aspect="equal",title=f"{title} · {len(keep)} lines")
                    ax.set_axis_off()
                    ax.legend(loc="upper center",bbox_to_anchor=(.5,0),frameon=False)
                pdf.savefig(fig,bbox_inches="tight")
                plt.close(fig)
                index.append({"order":order,"phase":phase,"F":sorted(ids[0]),"C":sorted(ids[1]),
                              "shared":sorted(shared)})
    atomic_write(DEST/"visual-index.json",encode({"atlas":"flat-40-numbered-comparison.pdf","pages":index}))


if __name__=="__main__":
    main()
