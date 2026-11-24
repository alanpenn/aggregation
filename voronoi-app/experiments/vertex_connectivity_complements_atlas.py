"""Draw numbered Flat 40 complementary tangent choices and individual vertices."""
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


def atlas():
    result = read(OUTPUT / "flat-40-connectivity-complements.json")
    saved = read(OUTPUT / "flat-40.json")
    inputs, _, _ = load("flat-40")
    cells, _, _ = _settlement(inputs)
    buildings = {label: list(cells[int(cell)].exterior.coords)[:-1]
                 for cell, label in inputs["settlement"]["building_labels"].items()}
    centres = {label: tuple(map(mean, zip(*ring))) for label, ring in buildings.items()}
    bounds = {label: (min(x for x,y in ring), min(y for x,y in ring),
                      max(x for x,y in ring), max(y for x,y in ring))
              for label, ring in buildings.items()}
    segments = [[xy(row["start"]), xy(row["end"])] for row in saved["lines"]]
    vertices = {v["id"]: v for v in saved["vertices"]}
    locations = {i: xy(v["point"]) for i,v in vertices.items()}
    rows = result["pairs"]
    colors = ("#196b92", "#bd5135")

    def draw(ax, chosen, extent, title, *, detail=False, provisional=()):
        x0,y0,x1,y1 = extent
        visible = [label for label,(a,b,c,d) in bounds.items() if a<=x1 and c>=x0 and b<=y1 and d>=y0]
        ax.add_collection(PolyCollection([buildings[label] for label in visible], facecolor="#e9eeec",
                                         edgecolor="#788b8d",linewidth=.4))
        for label in visible:
            ax.text(*centres[label],str(label),ha="center",va="center",fontsize=5 if detail else 6,
                    clip_on=True,zorder=5)
        first = {row["first"] for row in chosen}
        second = {row["second"] for row in chosen if "second" in row}
        for ids,color,alpha,width in ((provisional,"#8d9696",.34,.45),
                                      (first-second,colors[0],.72,.75),
                                      (second-first,colors[1],.72,.75),
                                      (first&second,"#70458d",.78,.85)):
            ax.add_collection(LineCollection([segments[i] for i in sorted(ids)],colors=color,
                                             alpha=alpha,linewidths=width,zorder=3))
        if chosen:
            ax.scatter(*zip(*(locations[row["vertex"]] for row in chosen)),
                       color="#242729",s=8 if detail else 6,zorder=4)
        ax.set(xlim=(x0,x1),ylim=(y0,y1),aspect="equal",title=title)
        ax.title.set_fontsize(8 if detail else 12)
        ax.set_axis_off()

    with PdfPages(OUTPUT / "flat-40-connectivity-complements.pdf") as pdf:
        fig,ax=plt.subplots(figsize=(10,10))
        draw(ax,rows,(-1,-1,101,101),"Flat 40 · Complementary tangents",provisional=result["provisional"])
        fig.text(.5,.04,"Blue Higher degree · Red Lower degree · Purple Both roles at different vertices · Grey Provisional",
                 ha="center",fontsize=9)
        pdf.savefig(fig,bbox_inches="tight"); plt.close(fig)

        for labels in ((15,25),(6,5),(41,43)):
            x,y=zip(*(p for label in labels for p in buildings[label]))
            extent=(min(x)-5,min(y)-5,max(x)+5,max(y)+5)
            local=[row for row in rows if extent[0]<=locations[row["vertex"]][0]<=extent[2]
                   and extent[1]<=locations[row["vertex"]][1]<=extent[3]]
            fig,ax=plt.subplots(figsize=(9,8))
            draw(ax,local,extent,f"Buildings {labels[0]} and {labels[1]} · Choices at visible vertices")
            for row in local:
                i=row["vertex"]
                if any(m["label"] in labels for m in vertices[i]["members"]):
                    ax.annotate(f"v{i}",locations[i],xytext=(3,4),textcoords="offset points",fontsize=7,zorder=6)
            fig.text(.5,.06,"Vertex panels in the appendix identify both selected candidate IDs.",ha="center",fontsize=9)
            pdf.savefig(fig,bbox_inches="tight"); plt.close(fig)

        per_page=24
        for start in range(0,len(rows),per_page):
            fig,axes=plt.subplots(4,6,figsize=(17,11))
            fig.suptitle("Flat 40 · Individual convex vertices · Blue higher degree · Red lower degree")
            for ax,row in zip(axes.flat,rows[start:start+per_page]):
                i=row["vertex"]
                x,y=locations[i]
                labels="/".join(str(m["label"]) for m in vertices[i]["members"])
                second=row.get("second","—")
                draw(ax,[row],(x-4,y-4,x+4,y+4),f'v{i} · B{labels}\n{row["first"]} / {second}',detail=True)
            for ax in list(axes.flat)[len(rows[start:start+per_page]):]:
                ax.set_axis_off()
            fig.tight_layout()
            pdf.savefig(fig,bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    atlas()
