"""Resume the eight plateau pair scans from intact per-origin checkpoints."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
import sys
from time import monotonic

from experiments.flat40_maximal_convex_axial import load_experiment, save, variant
from experiments.flat40_maximal_convex_minimum import Search, valid_exchanges
from experiments.occupied_vertex_pruning import read
from voronoi_app.research_data import sha256_file


def replay_study(manifest, source, reference):
    sys.set_int_max_str_digits(0)
    frozen,_,_,_,_=load_experiment(manifest,source)
    matrix=read(reference/"incidence-B.json")
    return Search(variant(frozen,matrix),matrix)


def scan(manifest, source, reference, out, name, ids):
    search=replay_study(manifest,source,reference)
    bound=read(out/"winding-ray-bound.json")
    rays=[(k,v["candidates"]) for k,v in bound["ray_requirements"].items()]
    started=monotonic()
    rows=search.one(ids,2,extra_groups=rays)
    save(out,f"{name}-two-for-one",rows)
    return {"scan":name,"elapsed_seconds":monotonic()-started,
            "accepted":sum(r["counts"].get("accepted",0) for r in rows)}


def main():
    sys.set_int_max_str_digits(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ("manifest","source","reference","output"):
        parser.add_argument("--"+k,type=Path,required=True)
    a=parser.parse_args()
    out=a.output
    controls={n:frozenset(read(a.reference/f"{n}.json")["ids"]) for n in ("B-C-H","B-C-S")}
    neighbours={ids:[] for ids in controls.values()}
    successful={}
    def register(name, ids, remove, add):
        successful.setdefault(ids,[]).append({"origin":name,"removed":remove,"added":add})
    for name,ids in controls.items():
        for trial,remove,add in valid_exchanges(ids,read(out/f"{name}-one-for-one.json")):
            neighbours.setdefault(trial,[]).append({"origin":name,"removed":remove,"added":add})
        for trial,remove,add in valid_exchanges(ids,read(out/f"{name}-two-for-one.json")):
            register(name,trial,remove,add)
    alternatives=sorted(set(neighbours)-set(controls.values()),key=lambda s:tuple(sorted(s)))
    chosen={f"plateau-{i:02d}":ids for i,ids in enumerate(alternatives[:8],1)}
    pending={n:ids for n,ids in chosen.items() if not (out/f"{n}-two-for-one.json").exists()}
    with ProcessPoolExecutor(max_workers=4,mp_context=get_context("spawn")) as executor:
        work=[executor.submit(scan,a.manifest,a.source,a.reference,out,n,ids) for n,ids in pending.items()]
        stats=[job.result() for job in work]
    for name,ids in chosen.items():
        for trial,remove,add in valid_exchanges(ids,read(out/f"{name}-two-for-one.json")):
            register(name,trial,remove,add)
    search=replay_study(a.manifest,a.source,a.reference)
    smaller=[]
    for ids,paths in sorted(successful.items(),key=lambda r:(len(r[0]),tuple(sorted(r[0])))):
        smaller.append({"ids":sorted(ids),"origins":paths,"certificate":search.independent(ids)})
    save(out,"plateau-resume",{"configuration_sha256":sha256_file(__file__),
                             "completed_before_resume":sorted(set(chosen)-set(pending)),
                             "parallel_scans":stats})
    save(out,"results",{"controls":{k:sorted(v) for k,v in controls.items()},
          "common":sorted(set.intersection(*(set(v) for v in controls.values()))),
          "union":sorted(set.union(*(set(v) for v in controls.values()))),
          "alternatives":[{"ids":sorted(ids),"paths":neighbours[ids]} for ids in alternatives],
          "tested_plateau_maps":[sorted(ids) for ids in chosen.values()],
          "in_all_31_neighbourhood_maps":sorted(set.intersection(*(set(v) for v in neighbours))),
          "smaller":smaller})
    print("Finished",len(alternatives),"other 31-line maps;",len(smaller),"distinct 30-line maps",flush=True)


if __name__=="__main__":
    main()
