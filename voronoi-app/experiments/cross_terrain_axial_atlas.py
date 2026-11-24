"""Numbered archive-aware atlas and summary plots for the benchmark."""
from collections import defaultdict
from pathlib import Path
from shutil import copyfile
from statistics import mean
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection

from experiments.constructive_axial import load
from experiments.cross_terrain_axial import CASES, DEST, METHODS, read, save
from experiments.occupied_vertex_pruning_atlas import xy
from voronoi_app.batch_methods import _settlement

NAMES={"strict_backward":"Strict backward","D":"Constructive D","C-S":"Complementary shortest","C-H":"Complementary sheaf"}
COLORS={"full":"#537382","complementary":"#8c53a2","strict_backward":"#236b90","D":"#98632c",
        "C-S":"#277f64","C-H":"#9a4056"}


def main():
    available=read(DEST/"inputs.json")
    ledger={(r["case"],r["method"]):r for r in read(DEST/"evaluation-ledger.json")}
    maps=DEST/"numbered-maps"
    maps.mkdir(exist_ok=True)
    index=[]
    pdf_paths=[]

    def register(case,method,stem,ids,status,extra=None):
        pdf=maps/f"{stem}.pdf"
        png=maps/f"{stem}.png"
        if not png.exists():
            subprocess.run(["pdftoppm","-singlefile","-png","-scale-to","3000",str(pdf),str(png.with_suffix(""))],check=True)
        pdf_paths.append(str(pdf))
        index.append({"page":len(index)+1,"case":case,"method":method,"pdf":str(pdf.relative_to(DEST)),
                      "png":str(png.relative_to(DEST)),"candidate_ids":ids,"status":status,**(extra or {})})

    def failure_card(case,methods):
        stem=f"{case}-missing-inputs"
        fig,ax=plt.subplots(figsize=(10,7))
        ax.set_axis_off()
        ax.text(.06,.89,case.replace("_"," ").title(),fontsize=23,weight="bold",transform=ax.transAxes)
        ax.text(.06,.76,"Published geometry only",fontsize=16,transform=ax.transAxes)
        for k,(method,row) in enumerate(methods.items()):
            ax.text(.06,.63-k*.105,f"{NAMES[method]}   {row['status'].replace('_',' ')}",
                    fontsize=12,transform=ax.transAxes)
        ax.text(.06,.13,"The original exact batch payloads are required to reproduce this case.",fontsize=10,transform=ax.transAxes)
        fig.savefig(maps/f"{stem}.pdf",bbox_inches="tight")
        plt.close(fig)
        register(case,"diagnostic",stem,[],"missing_exact_payloads")

    for case in CASES:
        folder=DEST/case
        source=available[case]
        if not (folder/"structural.json").exists():
            for method,k in (("full","published_full"),("strict_backward","published_strict")):
                publication=source[k]
                stem=f"{case}-{method}-published"
                path=Path(source["root"])/publication["visual"]["pdf"]
                copyfile(path,maps/f"{stem}.pdf")
                register(case,method,stem,publication["result"].get("line_ids",[]),"published_archive_only",
                         {"archived_pdf":str(path),"archived_metrics":publication["result"].get("constraints")})
            failure_card(case,{m:ledger[case,m] for m in METHODS})
            continue
        structure=read(folder/"structural.json")
        inputs,_,_=load(case)
        cells,_,_=_settlement(inputs)
        buildings={label:list(cells[int(i)].exterior.coords)[:-1]
                   for i,label in inputs["settlement"]["building_labels"].items()}
        centers={label:tuple(map(mean,zip(*ring))) for label,ring in buildings.items()}
        segments=[[xy(row["start"]),xy(row["end"])] for row in inputs["candidates"]["pool"]["candidates"]]
        choices={"full":(structure["full_ids"],"Certified full candidate pool",None),
                 "complementary":(structure["complementary_repaired"],"Complementary starting pool",
                                  structure.get("complementary_winding"))}
        choices.update({method:(structure["methods"][method].get("ids",[]),NAMES[method],
                                structure["methods"][method].get("winding"))
                        for method in METHODS})
        extent=(-1,-1,101,101)

        def draw(ax,method,items,small=False):
            ids,title,w=items
            shade=COLORS[method]
            ax.add_collection(PolyCollection(list(buildings.values()),facecolor="#e9eeea",
                                             edgecolor="#738588",linewidth=.45))
            ax.add_collection(LineCollection([segments[i] for i in ids],colors=shade,
                           linewidths=.58 if len(ids)>150 else .91,alpha=.28 if len(ids)>150 else .86))
            for label,(x,y) in centers.items():
                ax.text(x,y,str(label),ha="center",va="center",fontsize=4 if small else 6,
                        color="#253638",clip_on=True,zorder=4)
            row=ledger.get((case,method),{})
            rank=w.get("independent_circulation_rank") if w else None
            if rank is None:
                rank=row.get("winding_rank") or structure.get("methods",{}).get(method,{}).get("deficiencies",{}).get("rank")
            if row.get("status") in ("certified_archive","independent_success"):
                covered="complete"
            else:
                problem=structure.get("methods",{}).get(method,{}).get("deficiencies",{})
                missing=problem.get("missing_regions",[])
                doors=problem.get("unattached_doors",[])
                notes=[]
                if missing:
                    notes.append(f"{len(missing)} regions missing")
                if doors:
                    notes.append(f"{len(doors)} doors missing")
                if problem.get("components",1)!=1:
                    notes.append(f"{problem['components']} components")
                covered=", ".join(notes) or "see certificate"
            label=f"{title} · {len(ids)} lines"
            status=row.get("status")
            if status:
                label+=f'\nRank {rank if rank is not None else "—"}/{structure["blocks"]} · Coverage {covered}'
                if "angular_mean" in row:
                    label+=f' · Angular {row["angular_mean"]:.3f} · Metric {row["metric_mean"]:.2f}'
                label+=f'\n{status.replace("_"," ")}'
            ax.set(xlim=(extent[0],extent[2]),ylim=(extent[1],extent[3]),aspect="equal",title=label)
            ax.title.set_fontsize(8 if small else 11)
            ax.set_axis_off()

        fig,axes=plt.subplots(2,3,figsize=(15,11))
        fig.suptitle(f"{case.replace('_',' ').title()} · Matched benchmark")
        for ax,(method,items) in zip(axes.flat,choices.items()):
            draw(ax,method,items,small=True)
        stem=f"{case}-comparison"
        fig.savefig(maps/f"{stem}.pdf",bbox_inches="tight")
        plt.close(fig)
        register(case,"comparison",stem,[],"matched")
        for method,items in choices.items():
            stem=f"{case}-{method}"
            fig,ax=plt.subplots(figsize=(10,9))
            fig.suptitle(case.replace("_"," ").title())
            draw(ax,method,items)
            fig.savefig(maps/f"{stem}.pdf",bbox_inches="tight")
            plt.close(fig)
            status=ledger.get((case,method),{}).get("status","starting geometry")
            register(case,method,stem,items[0],status)
    subprocess.run(["pdfunite",*pdf_paths,str(DEST/"numbered-cross-terrain-atlas.pdf")],check=True)
    save(DEST/"visual-index.json",{"pages":index,"recovered_cases":sum(not v["missing"] for v in available.values())})
    successful=[r for r in ledger.values() if r.get("angular_mean") is not None]
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    for ax,key,title in zip(axes,("selected","angular_excess","metric_excess"),
                            ("Retained lines","Mean angular excess","Mean metric excess")):
        by_case=defaultdict(dict)
        for r in successful:
            by_case[r["case"]][r["method"]]=r[key]
        for case,results in by_case.items():
            x=[i for i,m in enumerate(METHODS) if m in results]
            y=[results[METHODS[i]] for i in x]
            ax.plot(x,y,"o-",alpha=.60,linewidth=.8,label=case)
        ax.set(xticks=range(4),xticklabels=["Backward","D","C-S","C-H"],title=title)
    axes[-1].legend(frameon=False,fontsize=7)
    fig.suptitle("Matched recovered settlements · complete cases only")
    fig.tight_layout()
    fig.savefig(DEST/"summary-comparison.pdf",bbox_inches="tight")
    plt.close(fig)


if __name__=="__main__":
    main()
