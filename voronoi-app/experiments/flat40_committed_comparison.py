"""Matched-crawler metrics and exact before/after region 257 views."""
import argparse
from collections import Counter
from fractions import Fraction as F
import gzip
import json
from pathlib import Path

import pymupdf

from experiments.flat40_crawler_atlas import read
from experiments.flat40_exchange_atlas import Atlas, combine, foot, page, plot_pdf
from experiments.flat40_face_extension import draw_polygons, load_inputs
from voronoi_app.batch_store import encode
from voronoi_app.research_data import sha256_file


def counts(root, committed=False):
    regions=read(root/"regions.json")
    cover=read(root/"coverage.json")
    search=regions["search"]
    phases=read(root/"commitment-metadata.json")["state_phases"] if committed else None
    options=Counter()
    arrived=0
    used=set()
    for path in sorted(root.rglob("*.json.gz")):
        with gzip.open(path,"rb") as f:
            rows=json.load(f)["records"]
        for r in rows:
            options.update(s for _,s in r["outgoing"])
            if committed and phases[r["path"][-1]]["phase"]=="committed":
                arrived+=sum(s=="follow_physical_face" for _,s in r["outgoing"])
            for closed in r["closed"]:
                used.add(closed["id"])
    m=Counter(r["maximality"]["status"] for r in regions["regions"].values())
    local=regions["local_257"]
    return {"prefixes":sum(s["popped"] for s in search["checkpoints"].values()),
            "completed_paths":search["unique_closed_directed_paths"],"regions":len(used),
            "maximality":dict(m),"maximal_fraction":m["proved_global"]/len(used),
            "local_257_regions":len(local),"overlap":cover["statistics"],
            "uncovered_components":len(cover["uncovered_components"]),
            "accepted_approach_transitions":options["turn_towards_originating_face"],
            "committed_approaches":options["turn_towards_originating_face"] if committed else None,
            "committed_arrivals":arrived if committed else None,
            "turns_prohibited_during_commitment":options["turn_prohibited_during_commitment"] if committed else None,
            "blocked_approach_options":sum(n for key,n in options.items() if key.startswith("blocked_approach_")) if committed else None,
            "outgoing_decisions":dict(options)}


def mapped(atlas,before,after,path):
    p=atlas.regions[257]
    x,y,X,Y=p.bounds
    view=(x-4,X+4,y-4,Y+4)
    fig,axes=page("Region 257  |  Matched-budget comparison",
                  "The same directed network, origins, handedness and explored-prefix budget",2)
    for ax,root,title in zip(axes,(before,after),("Earlier traversal","Committed approach")):
        atlas.base(ax,view)
        data=read(root/"regions.json")
        local=data["local_257"]
        draw_polygons(ax,[data["regions"][k] for k in local],
                      facecolors="#388db6",edgecolors="#317b9b",linewidths=.45,alpha=.10,zorder=4)
        draw_polygons(ax,[{"vertices":list(p.exterior.coords)}],facecolors="none",
                      edgecolors="#bc762c",linewidths=1.45,zorder=7)
        atlas.line(ax,1435,"#175a9b",width=1.4,z=9)
        atlas.line(ax,1509,"#b73643",width=1.4,z=9)
        ax.set_title(f"{title} · {len(local)} polygons overlap 257",loc="left")
    foot(fig,"Same scale and opacity · Amber archived 257 · Blue 1435 · Red 1509")
    plot_pdf(path,[fig])


def main(manifest,previous,out,fixture):
    s,ch,*_=load_inputs(manifest)
    old,new=counts(previous),counts(out,True)
    if old["prefixes"]!=new["prefixes"] or sha256_file(previous/"geometry.json")!=sha256_file(out/"geometry.json"):
        raise ValueError("The two runs do not share their geometry and prefix budget.")
    mapped(Atlas(s,ch),previous,out,out/"region257_matched_comparison.pdf")
    p=out/"flat40_commitment_comparison_atlas.pdf"
    combine(p,[("Matched region 257 comparison",out/"region257_matched_comparison.pdf"),
                ("Reference trajectories",fixture),("Flat 40 geometry and overlaps",out/"flat40_directed_face_convex_atlas.pdf")])
    with pymupdf.open(p) as f:
        if any(page.get_images() for page in f):
            raise ValueError("Unexpected raster in comparison atlas.")
    (out/"matched-comparison.json").write_bytes(encode({"before":old,"committed":new,
      "same_start_geometry_sha256":sha256_file(out/"geometry.json")}))
    for name,row in (("before",old),("committed",new)):
        print(name,{k:v for k,v in row.items() if k not in ("overlap","outgoing_decisions")},
              {k:row["overlap"][k] for k in ("covered_pct","maximum","mean","median")},flush=True)


if __name__=="__main__":
    import sys
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("manifest","previous","output","fixture"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    main(a.manifest,a.previous,a.output,a.fixture)
