"""Numbered vector atlas, every factorial cell, and detailed contrasts."""
from statistics import mean

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.lines import Line2D
from shapely import from_wkb

from experiments.constructive_axial import load
from experiments.flat40_factorial_routes import DEST, save
from experiments.occupied_vertex_pruning import read
from experiments.occupied_vertex_pruning_atlas import xy
from voronoi_app.batch_methods import _settlement

COLORS=("#a63a52","#bd6c18","#7460a3","#26856a","#9b671e","#1991a5","#416fad")
EXTENT=(-1,-1,101,101)


class Atlas:
    def __init__(self):
        self.inventory=read(DEST/"inventory.json")
        self.performance=read(DEST/"performance.json")
        self.effects=read(DEST/"doorway-effects.json")
        self.routes=read(DEST/"routing-index.json")
        inputs,_,_ = load("flat-40")
        polygons,_,_=_settlement(inputs)
        self.buildings={label:list(polygons[int(i)].exterior.coords)[:-1]
                       for i,label in inputs["settlement"]["building_labels"].items()}
        self.centres={label:tuple(map(mean,zip(*ring))) for label,ring in self.buildings.items()}
        self.regions={int(i):list(from_wkb(wkb).exterior.coords)
                      for i,wkb in inputs["candidates"]["regions_wkb"].items()}
        self.lines=[[xy(r["start"]),xy(r["end"])] for r in inputs["candidates"]["pool"]["candidates"]]
        self.doors=[xy(r["point"]) for r in self.routes["doorways"]]
        self.index=[]
        self.contact_index=[]
        self.paths={}
        self.principal=DEST/"principal"
        self.principal.mkdir(exist_ok=True)
        self.individual=DEST/"individual"
        self.individual.mkdir(exist_ok=True)

    def draw(self,ax,layers,title="",extent=EXTENT,regions=(),small=False):
        if regions:
            for ids,color in regions:
                ax.add_collection(PolyCollection([self.regions[i] for i in ids],edgecolor=color,
                                                 facecolor=color,alpha=.13,linewidth=.5))
        ax.add_collection(PolyCollection(list(self.buildings.values()),facecolor="#e7ebe7",
                                         edgecolor="#83908d",linewidth=.42,zorder=2))
        for i,(x,y) in self.centres.items():
            ax.text(x,y,str(i),ha="center",va="center",fontsize=3.8 if small else 6,
                    clip_on=True,zorder=5,color="#263638")
        for ids,color,width,alpha in layers:
            ax.add_collection(LineCollection([self.lines[i] for i in sorted(ids)],colors=color,
                                             linewidths=width,alpha=alpha,zorder=3))
        x0,y0,x1,y1=extent
        ax.set(xlim=(x0,x1),ylim=(y0,y1),aspect="equal",title=title)
        ax.title.set_fontsize(8 if small else 12)
        ax.set_axis_off()

    def export(self,pdf,fig,key,title,ids=(),maps=()):
        files={ext:f"principal/{key}.{ext}" for ext in ("pdf","png")}
        for ext,f in files.items():
            fig.savefig(DEST/f,bbox_inches="tight",dpi=380)
        pdf.savefig(fig,bbox_inches="tight")
        plt.close(fig)
        self.index.append({"page":len(self.index)+1,"title":title,"files":files,
                           "ids":sorted(ids),"maps":list(maps)})

    def layer(self,ids):
        selected=set(ids)
        layers=[(selected&set(self.inventory["core"]),"#176891",.84,.87)]
        for color,pair in zip(COLORS,self.inventory["pairs"]):
            layers.append((selected.intersection(pair),color,1.28,.97))
        extras=selected-set(self.inventory["union_ids"])
        if extras:
            layers.append((extras,"#33474a",.85,.9))
        return layers

    def caption(self,r):
        return f'{r["id"]}  |  Angular {r["angular_mean"]:.4f}  |  Metric {r["metric_mean"]:.3f}  |  Length {r["length"]:,.2f}'

    def details(self,pdf):
        dissimilar=read(DEST/"dissimilar-pair.json")
        routes=read(DEST/"alternative-routes.json")
        m={r["id"]:r for r in self.performance["rows"]}
        chosen=[1278,1422]
        x,y=zip(*(p for i in chosen for p in self.lines[i]))
        bounds=(min(x)-7,min(y)-7,max(x)+7,max(y)+7)
        fig,axes=plt.subplots(1,2,figsize=(16,8))
        for ax,i,map_id,c in zip(axes,chosen,routes["maps"],("#a33f4e","#237d65")):
            row=dissimilar["zero_context_candidates"][str(i)]
            near=set(row["selected_intersections"])
            layers=[(set(m[map_id]["ids"])-near-{i},"#859494",.63,.37),(near,"#176891",.96,.73),({i},c,2.25,1)]
            self.draw(ax,layers,f"{i} · Strict convex regions and intersecting lines",bounds,
                      regions=[(row["regions"],c)])
            for face in row["winding_faces_using_line"]:
                ax.plot(*zip(*(xy(p) for p in face["ring"])),color="#763d91",lw=1.0,linestyle="--",zorder=4)
        fig.suptitle("Flat 40 · 1278 and 1422 · Other six choices fixed at zero")
        fig.text(.5,.065,"Shaded strict regions · Dark blue intersecting lines · Dashed purple exact winding boundaries",ha="center")
        self.export(pdf,fig,"dissimilar-geometry","Dissimilar pair geometry",chosen,routes["maps"])
        fig,axes=plt.subplots(1,2,figsize=(16,8))
        for ax,i,map_id,distance in zip(axes,chosen,routes["maps"],routes["metric_costs"]):
            self.draw(ax,self.layer(m[map_id]["ids"]),f"{i} · Distance {distance:.3f}")
            path=[xy(p) for p in routes["paths"][map_id]]
            if path:
                ax.plot(*zip(*path),color="#d64032",lw=2.6,zorder=7)
                ax.scatter(*zip(path[0],path[-1]),c="#d64032",s=27,zorder=8)
        fig.suptitle(f'Certified metric alternative routes · Buildings {" and ".join(map(str,routes["buildings"]))}')
        self.export(pdf,fig,"dissimilar-routes","Dissimilar pair certified metric routes",maps=routes["maps"])

    def spatial(self,pdf):
        for metric in ("angular","metric"):
            factors=sorted(self.effects,key=lambda row:-row["costs"][metric]["maximum_absolute_change"])[:4]
            fig,axes=plt.subplots(2,2,figsize=(14,13))
            for ax,entry in zip(axes.flat,factors):
                data=entry["costs"][metric]
                ids=entry["pair"]
                self.draw(ax,[(ids,"#176891",1.0,.7)],f"{ids[0]} / {ids[1]} · {data['affected_pair_count']} affected pairs")
                for row in data["largest"][:4]:
                    a,b=self.routes["pairs"][row["index"]]
                    ax.plot(*zip(self.doors[a],self.doors[b]),color="#bb4e35",lw=.85,alpha=.77,zorder=4)
                counts=[data["affected_by_building"][str(label)] for label in self.routes["building_labels"]]
                ax.scatter(*zip(*self.doors),s=[6+v*.31 for v in counts],color="#bb4e35",alpha=.58,zorder=4)
            fig.suptitle(f"Flat 40 · Doorway pairs most affected by {metric} substitutions")
            fig.text(.5,.06,"Red links connect doorway endpoints · Dot size shows number of affected partners",ha="center")
            self.export(pdf,fig,f"doorway-{metric}",f"{metric} affected doorways")

    def run(self):
        rows=self.performance["rows"]
        with PdfPages(DEST/"flat-40-factorial-atlas.pdf") as pdf:
            fig,ax=plt.subplots(figsize=(10,9))
            self.draw(ax,self.layer(self.inventory["core"]),"Flat 40 · 27 mandatory lines")
            self.export(pdf,fig,"mandatory","Mandatory core",self.inventory["core"])
            fig,ax=plt.subplots(figsize=(10,9))
            self.draw(ax,self.layer(self.inventory["union_ids"]),"Flat 40 · Seven interchangeable pairs")
            ax.legend(handles=[Line2D([],[],color=color,label=f"{a} / {b}") for (a,b),color in
                               zip(self.inventory["pairs"],COLORS)],loc="lower center",ncol=4,fontsize=8,
                      bbox_to_anchor=(.5,-.06),frameon=False)
            self.export(pdf,fig,"pairs","Seven alternative pairs",self.inventory["union_ids"])
            principal={}
            for role,row in self.performance["best"].items():
                principal.setdefault(row["id"],[]).append(role)
            for row in self.performance["pareto"]:
                principal.setdefault(row["id"],[]).append("Pareto efficient")
            for row in rows:
                if row["id"] not in principal:
                    continue
                fig,ax=plt.subplots(figsize=(10,9))
                title=", ".join(s.replace("_"," ") for s in principal[row["id"]])
                self.draw(ax,self.layer(row["ids"]),title)
                fig.text(.5,.045,self.caption(row),ha="center")
                self.export(pdf,fig,f'map-{row["id"]}',title,row["ids"],[row["id"]])
            d=self.performance["controls"]["Algorithm D"]
            fig,ax=plt.subplots(figsize=(10,9))
            self.draw(ax,[(d["ids"],"#176891",1.0,.86)],"Flat 40 · Algorithm D · 33 lines")
            self.export(pdf,fig,"algorithm-d","Algorithm D control",d["ids"])
            self.details(pdf)
            self.spatial(pdf)
        with PdfPages(DEST/"flat-40-all-128-maps.pdf") as contact:
            for index in range(0,128,4):
                fig,axes=plt.subplots(2,2,figsize=(13,12))
                group=rows[index:index+4]
                fig.suptitle(f"Flat 40 · Binary prefix {group[0]['id'][:5]}")
                for ax,row in zip(axes.flat,group):
                    self.draw(ax,self.layer(row["ids"]),self.caption(row),small=True)
                contact.savefig(fig,bbox_inches="tight")
                plt.close(fig)
                self.contact_index.append({"page":index//4+1,"map_ids":[r["id"] for r in group]})
        for row in rows:
            fig,ax=plt.subplots(figsize=(10,9))
            name=f'individual/{row["id"]}.pdf'
            self.draw(ax,self.layer(row["ids"]),self.caption(row))
            fig.savefig(DEST/name,bbox_inches="tight")
            plt.close(fig)
            self.paths[row["id"]]={"pdf":name,"ids":row["ids"],"bits":row["bits"],
                                   "angular_mean":row["angular_mean"],"metric_mean":row["metric_mean"],
                                   "length":row["length"],"route_record":f'routes/{row["id"]}.json'}
        save("visual-index",{"principal":self.index,"contact":self.contact_index,"individual":self.paths,
                             "extent":EXTENT,"pair_colors":dict(zip(map(str,self.inventory["pairs"]),COLORS))})


if __name__=="__main__":
    Atlas().run()
