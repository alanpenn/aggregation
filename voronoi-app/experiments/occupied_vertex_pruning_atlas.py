"""Draw the numbered Flat 40 pruning atlas from saved rational intervals."""
from fractions import Fraction
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.lines import Line2D
import numpy as np
from shapely.geometry import LineString, box

from experiments.constructive_axial import load
from experiments.occupied_vertex_pruning import OUTPUT, read
from voronoi_app.batch_methods import _settlement


def xy(coordinates):
    return tuple(float(Fraction(value)) for value in coordinates)


def atlas(directory=OUTPUT):
    data = read(directory / "flat-40.json")
    inputs, _, _ = load("flat-40")
    polygons, _, _ = _settlement(inputs)
    buildings = {label: list(polygons[int(cell)].exterior.coords)
                 for cell, label in inputs["settlement"]["building_labels"].items()}
    intervals = [[xy(line["start"]), xy(line["end"])] for line in data["lines"]]
    coordinates = [xy(v["point"]) for v in data["vertices"]]
    degrees = [len(v["supported"]) for v in data["vertices"]]
    highest = sorted(data["vertices"], key=lambda v: (-len(v["supported"]), v["id"]))[:8]
    colors = {"Original":"#365b6b", "Retained":"#176891", "Eliminated":"#bc4b36"}

    with PdfPages(directory / "flat-40-atlas.pdf") as pdf:
        def draw(title, layers=(), show_vertices=False, zoom=None, highlighted=()):
            fig, ax = plt.subplots(figsize=(10, 9))
            ax.add_collection(PolyCollection(list(buildings.values()), facecolor="#e8ebea",
                                             edgecolor="#6a797b", linewidth=.5, zorder=1))
            for label, ring in buildings.items():
                x,y = map(mean,zip(*ring[:-1]))
                ax.text(x,y,str(label),ha="center",va="center",fontsize=6,clip_on=True,zorder=5)
            handles = []
            for kind, ids, alpha in layers:
                ax.add_collection(LineCollection([intervals[i] for i in ids],
                                                 colors=colors[kind], linewidths=.55, alpha=alpha, zorder=2))
                handles.append(Line2D([],[],label=f"{kind} ({len(ids):,})",color=colors[kind]))
            if show_vertices:
                scatter = ax.scatter(*zip(*coordinates),c=degrees,s=[10+3*n for n in degrees],
                                     cmap="viridis",edgecolors="#2b3335",linewidths=.3,zorder=4)
                fig.colorbar(scatter,ax=ax,shrink=.68,label="Certified tangents at vertex")
                for v in highest:
                    i=v["id"]
                    ax.annotate(f"v{i}",coordinates[i],xytext=(4,5),textcoords="offset points",fontsize=7,zorder=6)
            if highlighted:
                result = data["results"]["10"]
                kept=set(result["retained"])
                for i in highlighted:
                    color=colors["Retained" if i in kept else "Eliminated"]
                    ax.add_collection(LineCollection([intervals[i]],colors=color,linewidths=1.45,zorder=3))
            if zoom:
                x,y=zip(*(p for label in zoom for p in buildings[label]))
                ax.set(xlim=(min(x)-7,max(x)+7),ylim=(min(y)-7,max(y)+7))
                for n,i in enumerate(highlighted):
                    lo, hi = ax.get_xlim()
                    bottom, top = ax.get_ylim()
                    part=LineString(intervals[i]).intersection(box(lo,bottom,hi,top))
                    if part.length:
                        p=part.interpolate((n+1)/(len(highlighted)+1),normalized=True)
                        ax.text(p.x,p.y,str(i),fontsize=8,zorder=6,
                                bbox={"facecolor":"white","edgecolor":"none","alpha":.87})
            else:
                ax.set(xlim=(-1,101),ylim=(-1,101))
            if handles:
                ax.legend(handles=handles,loc="upper center",bbox_to_anchor=(.5,-.015),
                          frameon=False,ncol=len(handles))
            ax.set_aspect("equal")
            ax.set_axis_off()
            ax.set_title(title)
            pdf.savefig(fig,bbox_inches="tight")
            plt.close(fig)

        draw("Flat 40 · Original certified pool", [("Original",range(len(intervals)),.18)])
        draw("Flat 40 · Convex occupied-block vertices and tangent counts", show_vertices=True)
        fig, axes = plt.subplots(2,4,subplot_kw={"projection":"polar"},figsize=(13,7))
        fig.suptitle("Flat 40 · Axial orientations at the eight highest-degree vertices")
        for ax,v in zip(axes.flat,highest):
            samples=np.radians([data["lines"][i]["angle"] for i in v["supported"]])
            bins=np.linspace(0,np.pi,37)
            counts,edges=np.histogram(samples,bins=bins)
            ax.bar(edges[:-1],counts,width=np.diff(edges),align="edge",color="#3281a4",alpha=.8)
            for family in data["results"]["5"]["vertex_families"][str(v["id"])]:
                angle=np.radians(data["lines"][family["representative"]]["angle"])
                ax.plot([angle,angle],[0,max(counts)+.4],color="#b74c39",linewidth=.8)
            ax.set_thetamin(0)
            ax.set_thetamax(180)
            ax.set_thetagrids([0,45,90,135,180])
            labels=", ".join(str(m["label"]) for m in v["members"])
            ax.set_title(f'v{v["id"]} · Buildings {labels or "—"}\n{len(samples)} tangents',fontsize=9)
            ax.set_yticks(range(1,max(counts)+1))
        fig.text(.5,.06,"Bars show 5° orientation bins. Red marks show the 5° family representatives.",ha="center")
        fig.subplots_adjust(wspace=.45,hspace=.6)
        pdf.savefig(fig,bbox_inches="tight")
        plt.close(fig)
        for tolerance,r in sorted(data["results"].items(),key=lambda item:int(item[0])):
            keep,drop=r["retained"],r["eliminated"]
            draw(f"Flat 40 · {tolerance}° retained lines",[("Retained",keep,.24)])
            draw(f"Flat 40 · {tolerance}° eliminated lines",[("Eliminated",drop,.55)])
            draw(f"Flat 40 · {tolerance}° comparison",[("Retained",keep,.15),("Eliminated",drop,.55)])
        for zoom,ids in (((15,25),(957,865)),((6,5),(1244,1189,1190,1208)),((41,43),(1355,1354))):
            r=data["results"]["10"]
            draw(f"Buildings {zoom[0]} and {zoom[1]} · 10° target detail",
                 [("Retained",r["retained"],.10),("Eliminated",r["eliminated"],.18)],
                 zoom=zoom,highlighted=ids)


if __name__ == "__main__":
    atlas()
