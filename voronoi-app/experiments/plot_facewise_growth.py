"""Plot confirmed archived growth defects with original building labels."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely import from_wkb

from voronoi_app.batch_store import BatchStore


OUT=Path("diagnostics/facewise-growth-audit")
ROOT=Path("diagnostics/strict-generalisation/pilot-1")


def plot(ax, data, rows, marked, title):
    polys={int(i):from_wkb(wkb) for i,wkb in data["polygons_wkb"].items()}
    formed={r["open_cell"] for r in rows}
    occupied={r["building_cell"]:r["building"] for r in rows}
    affected={r["building_cell"] for r in marked}
    parents={r["parent_open_cell"] for r in marked}
    paired={r["open_cell"] for r in marked}
    for i,p in polys.items():
        color=("#ab3651" if i in affected else "#4b535f") if i in occupied else (
            "#79b79c" if i in paired else "#d6c283" if i in parents else
            "#d4eee4" if i in formed else "#f8f8f5")
        ax.fill(*p.exterior.xy,color=color,edgecolor="#b4b7b5",linewidth=.28,zorder=1)
        if i in occupied:
            c=p.representative_point()
            ax.text(c.x,c.y,str(occupied[i]),color="white",ha="center",va="center",fontsize=5,zorder=5)
    for r in marked:
        center=polys[r["open_cell"]].representative_point()
        ax.text(center.x,center.y,f"O{r['open_cell']}",fontsize=5,ha="center",va="center",zorder=5)
        for key in ("parent_open_cell","building_cell"):
            other=r[key]
            if other is None:
                continue
            boundary=polys[other].boundary.intersection(polys[r["open_cell"]].boundary)
            if boundary.length==0:
                q=polys[other].representative_point()
                ax.plot([q.x,center.x],[q.y,center.y],color="#c3294c",linestyle="--",
                        linewidth=1.15,zorder=4)
            else:
                segments=boundary.geoms if hasattr(boundary,"geoms") else (boundary,)
                for line in segments:
                    if line.length>0:
                        ax.plot(*line.xy,color="#084b5b",linewidth=2.2,zorder=4)
    ax.set_aspect("equal")
    xmin,ymin,xmax,ymax=data["grid"]["extent"]
    ax.set(xlim=(xmin,xmax),ylim=(ymin,ymax),title=title)
    ax.axis("off")


def save(fig,name):
    handles=[Patch(color="#4b535f",label="Buildings"),Patch(color="#ab3651",label="Affected building"),
             Patch(color="#d4eee4",label="Assigned open cell"),Patch(color="#f8f8f5",label="Unassigned"),
             Patch(color="#79b79c",label="Paired open cell"),Patch(color="#d6c283",label="Recorded parent"),
             Line2D([],[],color="#084b5b",label="Shared face"),
             Line2D([],[],color="#c3294c",linestyle="--",label="Growth or dyad link without a face")]
    fig.legend(handles=handles,loc="lower center",ncol=4,frameon=False,fontsize=8)
    fig.subplots_adjust(bottom=.12,top=.88)
    for suffix in ("png","pdf"):
        with (OUT/f"{name}.{suffix}").open("xb") as f:
            fig.savefig(f,format=suffix,dpi=250)
    plt.close(fig)


def main():
    store=BatchStore(ROOT)
    for seed in (40,41):
        audit=json.loads((OUT/f"converging_valleys-{seed}.json").read_text())
        _,data,_=store.load(audit["settlement"])
        rows=audit["placements"]
        marked=[r for r in rows if r["parent_face_length"]==0 or r["pair_face_length"]==0]
        fig,ax=plt.subplots(figsize=(9,9))
        plot(ax,data,rows,marked,f"Y seed {seed} · Full settlement")
        save(fig,f"Y-{seed}-face-audit")
        first=next(i for i,r in enumerate(rows) if r["components"]>1)
        fig,axes=plt.subplots(1,2,figsize=(12,7))
        plot(axes[0],data,rows[:first],[],f"After building {rows[first-1]['building']} · 1 open component")
        plot(axes[1],data,rows[:first+1],[rows[first]],
             f"After building {rows[first]['building']} · {rows[first]['components']} open components")
        fig.suptitle(f"Y seed {seed} · First disconnect",fontsize=14)
        save(fig,f"Y-{seed}-first-disconnect")


if __name__=="__main__":
    main()
