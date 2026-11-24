"""Numbered maps and paired difference overlays for the frozen experiment."""
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import load
from experiments.frozen_preselection import CASES, DEST, save
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.occupied_vertex_pruning_atlas import xy
from voronoi_app.batch_methods import _settlement


def main():
    inputs,_,_=load("flat-40")
    cells,_,_=_settlement(inputs)
    buildings={label:list(cells[int(i)].exterior.coords)[:-1]
               for i,label in inputs["settlement"]["building_labels"].items()}
    segments=[[xy(line["start"]),xy(line["end"])] for line in read(OUTPUT/"flat-40.json")["lines"]]
    maps=DEST/"numbered-maps"
    maps.mkdir(exist_ok=True)
    index=[]
    with PdfPages(DEST/"flat-40-numbered-atlas.pdf") as pdf:
        def draw(name,title,layers,zoom=()):
            fig,ax=plt.subplots(figsize=(10,9))
            ax.add_collection(PolyCollection(list(buildings.values()),facecolor="#e8eeea",
                                             edgecolor="#738587",linewidth=.48))
            for label,ring in buildings.items():
                x,y=map(mean,zip(*ring))
                ax.text(x,y,str(label),ha="center",va="center",fontsize=6,clip_on=True,zorder=5)
            for label,color,ids in layers:
                ax.add_collection(LineCollection([segments[i] for i in sorted(ids)],colors=color,
                                                 alpha=.23 if len(ids)>500 else .78,linewidths=.78))
                ax.plot([],[],color=color,label=f"{label} ({len(ids)})")
            if zoom:
                x,y=zip(*(p for label in zoom for p in buildings[label]))
                ax.set(xlim=(min(x)-7,max(x)+7),ylim=(min(y)-7,max(y)+7))
            else:
                ax.set(xlim=(-1,101),ylim=(-1,101))
            ax.set(aspect="equal",title=title)
            ax.set_axis_off()
            ax.legend(loc="upper center",bbox_to_anchor=(.5,0),frameon=False,ncol=3)
            files={ext:f"numbered-maps/{name}.{ext}" for ext in ("pdf","png")}
            for ext,path in files.items():
                fig.savefig(DEST/path,bbox_inches="tight",dpi=450)
            pdf.savefig(fig,bbox_inches="tight")
            plt.close(fig)
            index.append({"page":len(index)+1,"title":title,"files":files,"building_closeup":list(zoom),
                          "layers":[{"label":label,"color":color,"ids":sorted(ids)}
                                    for label,color,ids in layers]})

        for p,title in (("F","Full certified pool"),("C","Repaired complementary pool")):
            draw(f"{p}-start",f"Flat 40 · {title}",[(title,"#176690",read(DEST/f"{p}-start.json")["ids"])])
        for phase in ("direct","exchange"):
            for case in CASES:
                ids=read(DEST/f"{case}-{phase}.json")["ids"]
                draw(f"{case}-{phase}",f"Flat 40 · {case} {phase}",[("Retained","#176690",ids)])
            for order in ("S","H"):
                f,c=(set(read(DEST/f"{p}-{order}-{phase}.json")["ids"]) for p in ("F","C"))
                layers=[("Shared","#176690",f&c),("Full only","#d76d2b",f-c),
                        ("Complementary only","#8245a0",c-f)]
                draw(f"compare-{order}-{phase}",f"Flat 40 · {order} {phase} comparison",layers)
                for a,b in ((15,25),(6,5),(41,43)):
                    draw(f"{order}-{phase}-buildings-{a}-{b}",f"Flat 40 · {order} {phase} · Buildings {a} and {b}",
                         layers,(a,b))
    save("visual-index",{"atlas":"flat-40-numbered-atlas.pdf","pages":index})


if __name__=="__main__":
    main()
