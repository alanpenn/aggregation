"""Draw the numbered Flat 40 sheaf reduction audit."""
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import load
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.occupied_vertex_pruning_atlas import xy
from voronoi_app.batch_methods import _settlement


def main():
    destination = OUTPUT.parent / "complementary-sheaf-reduction-1"
    result = read(destination / "flat-40.json")
    inputs, _, _ = load("flat-40")
    polygons, _, _ = _settlement(inputs)
    footprints = {label: list(polygons[int(cell)].exterior.coords)[:-1]
                  for cell, label in inputs["settlement"]["building_labels"].items()}
    segments = [[xy(row["start"]), xy(row["end"])] for row in read(OUTPUT/"flat-40.json")["lines"]]
    repair = result["repair"]["candidate"]
    palette = {"Baseline":"#557484","Retained":"#176891","Removed":"#b74a32","Coverage repair":"#653a88"}

    def draw(ax, title, layers):
        ax.add_collection(PolyCollection(list(footprints.values()),facecolor="#e8ecea",
                                         edgecolor="#7c8b8c",linewidth=.45))
        for label,ids in layers:
            ax.add_collection(LineCollection([segments[i] for i in ids],colors=palette[label],
                                             linewidths=1.3 if label=="Coverage repair" else .63,
                                             alpha=.86 if label in ("Removed","Coverage repair") else .38))
            ax.plot([],[],color=palette[label],label=f"{label} ({len(ids)})")
        for label,ring in footprints.items():
            x,y=map(mean,zip(*ring))
            ax.text(x,y,str(label),ha="center",va="center",fontsize=6,zorder=5)
        ax.set(xlim=(-1,101),ylim=(-1,101),aspect="equal",title=title)
        ax.set_axis_off()
        ax.legend(loc="upper center",bbox_to_anchor=(.5,0),frameon=False)

    keep=[i for i in result["retained"] if i!=repair]
    with PdfPages(destination/"flat-40-numbered-maps.pdf") as pdf:
        fig,axes=plt.subplots(1,2,figsize=(15,8))
        fig.suptitle("Flat 40 · Complementary tangent sheaf reduction")
        draw(axes[0],"Saved complementary pool",[("Baseline",result["baseline_ids"])])
        draw(axes[1],"Validated reduction",[("Retained",keep),("Coverage repair",[repair])])
        pdf.savefig(fig,bbox_inches="tight")
        plt.close(fig)
        fig,ax=plt.subplots(figsize=(9,9))
        draw(ax,"Eliminated lines over the retained pool",
             [("Retained",keep),("Removed",result["eliminated"]),("Coverage repair",[repair])])
        pdf.savefig(fig,bbox_inches="tight")
        plt.close(fig)


if __name__=="__main__":
    main()
