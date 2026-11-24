"""Export the complete numbered Flat 40 recombination atlas."""
from collections import defaultdict
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import ROOT, load
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.occupied_vertex_pruning_atlas import xy
from experiments.recombine_flat40_extended import DEST, ORDERS, save
from voronoi_app.batch_methods import _settlement


def main():
    inputs,source,_=load("flat-40")
    cells,_,_=_settlement(inputs)
    buildings={label:list(cells[int(i)].exterior.coords)[:-1]
               for i,label in inputs["settlement"]["building_labels"].items()}
    centers={label:tuple(map(mean,zip(*ring))) for label,ring in buildings.items()}
    segments=[[xy(r["start"]),xy(r["end"])] for r in read(OUTPUT/"flat-40.json")["lines"]]
    data=read(DEST/"unions.json")
    parent={n:set(data["parents"][n]["ids"]) for n in ("F-S","C-S","C-H")}
    common=set.intersection(*parent.values())
    union=set.union(*parent.values())
    runs={f"{u}-{o}":read(DEST/f"{u}-{o}.json") for u in data["unions"] for o in ORDERS}
    exchanged={mode:read(DEST/f"{mode}-exchanges.json") for mode in ("union","full")}
    best={mode:set(row["best"]["ids"]) for mode,row in exchanged.items()}
    algorithm_d=set(read(ROOT/"flat-40/D.json")["maps"]["exchanged"])
    mapping=defaultdict(set)
    for i in union:
        mapping[tuple(n for n,ids in parent.items() if i in ids)].add(i)
    colors=["#d47933","#7a54a1","#438b6b","#b54857","#44819f","#8a7238"]
    provenance=[("All parents","#176891",common)]
    provenance.extend((" + ".join(key),color,ids) for (key,ids),color in
                      zip([(key,mapping[key]) for key in sorted(mapping) if len(key)<3],colors))
    maps=DEST/"numbered-maps"
    maps.mkdir(exist_ok=True)
    index=[]

    def panel(ax,title,layers,extent):
        ax.add_collection(PolyCollection(list(buildings.values()),facecolor="#e9eeea",
                                         edgecolor="#75898b",linewidth=.48))
        for label,(x,y) in centers.items():
            ax.text(x,y,str(label),ha="center",va="center",fontsize=6,clip_on=True,zorder=5)
        for label,color,ids in layers:
            if not ids:
                continue
            ax.add_collection(LineCollection([segments[i] for i in sorted(ids)],colors=color,
                              linewidths=.68 if label=="Removed from U3" else .95,
                              alpha=.30 if label=="Removed from U3" else .82))
            ax.plot([],[],color=color,label=f"{label} ({len(ids)})")
        x0,y0,x1,y1=extent
        ax.set(xlim=(x0,x1),ylim=(y0,y1),aspect="equal",title=title)
        ax.set_axis_off()
        ax.legend(loc="upper center",bbox_to_anchor=(.5,0),frameon=False,ncol=2,fontsize=8)

    with PdfPages(DEST/"flat-40-numbered-atlas.pdf") as pdf:
        def draw(stem,panels,zoom=()):
            extent=(-1,-1,101,101)
            if zoom:
                x,y=zip(*(p for label in zoom for p in buildings[label]))
                extent=(min(x)-7,min(y)-7,max(x)+7,max(y)+7)
            fig,axes=plt.subplots(1,len(panels),squeeze=False,figsize=(9*len(panels),8.5))
            for ax,(title,layers) in zip(axes.flat,panels,strict=True):
                panel(ax,title,layers,extent)
            files={ext:f"numbered-maps/{stem}.{ext}" for ext in ("pdf","png")}
            for ext,path in files.items():
                fig.savefig(DEST/path,bbox_inches="tight",dpi=400)
            pdf.savefig(fig,bbox_inches="tight")
            plt.close(fig)
            index.append({"page":len(index)+1,"files":files,"closeup":list(zoom),
                          "panels":[{"title":title,"layers":[{"label":label,"ids":sorted(ids)}
                                                             for label,_,ids in layers]}
                                    for title,layers in panels]})

        for n,ids in parent.items():
            draw(n,[(f"Flat 40 · {n} parent",[("Selected","#176891",ids)])])
        draw("U3",[("Flat 40 · Complete union by parent provenance",provenance)])
        for name,row in runs.items():
            draw(name,[(f"Flat 40 · {name}",[("Retained","#176891",set(row["ids"]))])])
        for mode,ids in best.items():
            draw(f"{mode}-best",[(f"Flat 40 · Best {mode}-pool exchange · {len(ids)} lines",
                                   [("Selected","#176891",ids)])])
        draw("algorithm-d",[("Flat 40 · Algorithm D",[("Selected","#176891",algorithm_d)])])
        draw("parent-comparison",[(f"Flat 40 · {n}",[("Selected","#176891",ids)])
                                  for n,ids in parent.items()])
        def overlay(ids):
            layers=[("Removed from U3","#bd593f",union-ids)]
            layers.extend((label,color,available&ids) for label,color,available in provenance)
            layers.append(("Introduced outside U3","#e15d23",ids-union))
            return layers
        panels=[("Best union-only exchange",overlay(best["union"])),
                ("Best full-pool exchange",overlay(best["full"]))]
        draw("best-comparison",panels)
        novel=set(next(row["ids"] for row in exchanged["union"]["outcomes"] if not row["parent_identity"]))
        novel_panel=("New union-only recombination",overlay(novel))
        draw("novel-union",[novel_panel])
        for zoom in ((15,25),(6,5),(41,43)):
            draw(f"buildings-{zoom[0]}-{zoom[1]}",[novel_panel,*panels],zoom)
    save("visual-index",{"source":source,"pages":index,"palette":{label:color for label,color,_ in provenance}})
    inventories={**{name:sorted(ids) for name,ids in parent.items()},
                 **{name:row["ids"] for name,row in runs.items()},
                 **{f"{mode}-best":sorted(ids) for mode,ids in best.items()},
                 **{f"{mode}-{row['start']}":row["ids"] for mode,data in exchanged.items()
                    for row in data["outcomes"]},"Algorithm D":sorted(algorithm_d),
                 "Strict backward":inputs["analysis"]["maps"]["strict_backward"]["line_ids"]}
    all_ids=sorted(set.union(*(set(ids) for ids in inventories.values()),union))
    save("final-inventories",{"source":source,"maps":inventories,
          "intervals":[inputs["candidates"]["pool"]["candidates"][i] for i in all_ids]})


if __name__=="__main__":
    main()
