"""Four complete pair scans of diverse 30-line controls with exact winding-ray screening."""
import argparse
from pathlib import Path
import sys

from experiments.flat40_maximal_convex_axial import load_experiment, save, variant
from experiments.flat40_maximal_convex_minimum import Search, valid_exchanges
from experiments.flat40_maximal_convex_minimum_report import ray_bound
from experiments.occupied_vertex_pruning import read


def main():
    sys.set_int_max_str_digits(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ("manifest","source","reference","output"):
        parser.add_argument("--"+n,type=Path,required=True)
    a=parser.parse_args()
    frozen,_,_,_,_=load_experiment(a.manifest,a.source)
    matrix=read(a.reference/"incidence-B.json")
    study=variant(frozen,matrix)
    search=Search(study,matrix)
    parents=[]
    for name in ("B-C-H","B-C-S"):
        base=frozenset(read(a.reference/f"{name}.json")["ids"])
        rows=read(a.output/f"{name}-two-for-one.json")
        by_pair={}
        for ids, removed, added in valid_exchanges(base,rows):
            by_pair.setdefault(tuple(removed),(ids,removed,added))
        for ids,removed,added in list(by_pair.values())[:2]:
            parents.append({"name":f"followup-{len(parents)+1:02d}","ids":sorted(ids),
                            "from":name,"removed":removed,"added":added})
    bound=ray_bound(study,matrix,[set(p["ids"]) for p in parents])
    save(a.output,"winding-ray-bound",bound)
    rays=[(k,v["candidates"]) for k,v in bound["ray_requirements"].items()]
    smaller={}
    for p in parents:
        ids=frozenset(p["ids"])
        direct=search.direct(ids)
        save(a.output,f'{p["name"]}-direct',direct)
        for row in direct:
            if not row["failures"]:
                smaller.setdefault(ids-{row["removed"]},[]).append(
                    {"origin":p["name"],"removed":[row["removed"]],"added":[]})
        rows=search.one(ids,2,extra_groups=rays)
        save(a.output,f'{p["name"]}-two-for-one',rows)
        hits=list(valid_exchanges(ids,rows))
        for trial,removed,added in hits:
            smaller.setdefault(trial,[]).append({"origin":p["name"],"removed":removed,"added":added})
        print(p["name"],len(hits),"accepted pair proposals",flush=True)
    save(a.output,"followup",{"parents":parents,"smaller":[
        {"ids":sorted(ids),"origins":paths,"certificate":search.certificates[ids]}
        for ids,paths in sorted(smaller.items(),key=lambda r:(len(r[0]),tuple(sorted(r[0]))))]})
    print("Winding-ray bound",bound["bound"],"; smaller maps",len(smaller),flush=True)


if __name__=="__main__":
    main()
