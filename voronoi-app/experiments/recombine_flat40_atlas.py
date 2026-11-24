"""Draw the numbered parent and union comparisons for Flat 40."""
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import load
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.occupied_vertex_pruning_atlas import xy
from experiments.recombine_flat40 import DEST
from voronoi_app.batch_methods import _settlement
from voronoi_app.batch_store import atomic_write, encode


def main():
    result=read(DEST/"results.json")
    inputs,_,_=load("flat-40")
    polygons,_,_=_settlement(inputs)
    building={label:list(polygons[int(i)].exterior.coords)[:-1]
              for i,label in inputs["settlement"]["building_labels"].items()}
    intervals=[[xy(row["start"]),xy(row["end"])] for row in read(OUTPUT/"flat-40.json")["lines"]]
    union=set(result["union_ids"])
    fixed=set(map(int,result["mandatory"]))
    pages=[]
    with PdfPages(DEST/"flat-40-recombination-atlas.pdf") as pdf:
        def draw(title, layers):
            fig,ax=plt.subplots(figsize=(10,9))
            ax.add_collection(PolyCollection(list(building.values()),facecolor="#e8eeeb",
                                             edgecolor="#768887",linewidth=.5))
            for label,ring in building.items():
                x,y=map(mean,zip(*ring))
                ax.text(x,y,str(label),ha="center",va="center",fontsize=6,zorder=5)
            for kind,color,ids in layers:
                ax.add_collection(LineCollection([intervals[i] for i in sorted(ids)],colors=color,
                                                 alpha=.88,linewidths=1.0))
                ax.plot([],[],color=color,label=f"{kind} ({len(ids)})")
            ax.set(xlim=(-1,101),ylim=(-1,101),aspect="equal",title=title)
            ax.set_axis_off()
            ax.legend(loc="upper center",bbox_to_anchor=(.5,0),frameon=False,ncol=3)
            pdf.savefig(fig,bbox_inches="tight")
            plt.close(fig)
            pages.append({"title":title,"layers":[{"label":label,"ids":sorted(ids)}
                                                 for label,_,ids in layers]})
        draw("Flat 40 · Certified parent union",[("Mandatory within union","#176891",fixed),
                                                ("Alternative lines","#8b4ba1",union-fixed)])
        for name in ("F-S","C-S","C-H"):
            ids=set(result["parents"][name]["ids"])
            draw(f"Flat 40 · Parent {name}",[("Mandatory within union","#176891",fixed),
                                          ("Selected alternatives","#8b4ba1",ids-fixed)])
        known={frozenset(row["ids"]) for row in result["parents"].values()}
        novel=[row for row in result["minimum_maps"] if frozenset(row["ids"]) not in known]
        examples=(("Shortest new recombination",novel[0]),
                  ("New recombination with most intersection pairs",
                   max(novel,key=lambda row:row["metrics"]["intersection_pairs"])))
        plotted=set()
        for title,row in examples:
            ids=frozenset(row["ids"])
            if ids in plotted:
                continue
            plotted.add(ids)
            draw(f"Flat 40 · {title}",[("Mandatory within union","#176891",fixed),
                                       ("Selected alternatives","#8b4ba1",ids-fixed)])
    atomic_write(DEST/"visual-index.json",encode({"pages":pages}))


if __name__=="__main__":
    main()
