"""Advance the bounded search below the first certified 29-line map."""
import argparse
from pathlib import Path
import sys

from experiments.flat40_maximal_convex_axial import load_experiment, save, variant
from experiments.flat40_maximal_convex_minimum import Search, valid_exchanges
from experiments.occupied_vertex_pruning import read


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    for n in ("manifest","source","reference","output"):
        parser.add_argument("--"+n,type=Path,required=True)
    a = parser.parse_args()
    frozen,_,_,_,_=load_experiment(a.manifest,a.source)
    matrix=read(a.reference/"incidence-B.json")
    study=variant(frozen,matrix)
    search=Search(study,matrix)
    bound=read(a.output/"winding-ray-bound.json")
    rays=[(k,v["candidates"]) for k,v in bound["ray_requirements"].items()]
    followup=read(a.output/"followup.json")
    if not followup["smaller"]:
        save(a.output,"descent",{"parents":[],"smaller":[]})
        return
    parent=followup["smaller"][0]
    ids=frozenset(parent["ids"])
    name=f"descent-{len(ids)}"
    cert=search.independent(ids)
    if cert!=parent["certificate"]:
        raise ValueError("Parent failed exact certificate replay.")
    discovered={}
    def register(trial,removed,added):
        discovered.setdefault(trial,[]).append({"origin":name,"removed":removed,"added":added})
    direct=search.direct(ids)
    save(a.output,f"{name}-direct",direct)
    for row in direct:
        if not row["failures"]:
            register(ids-{row["removed"]},[row["removed"]],[])
    pairs=search.one(ids,2,extra_groups=rays)
    save(a.output,f"{name}-two-for-one",pairs)
    for trial,removed,added in valid_exchanges(ids,pairs):
        register(trial,removed,added)
    print(name,"direct and pair successors",len(discovered),flush=True)
    if not discovered:
        triples,hits=search.two(ids,12000,extra_groups=rays)
        save(a.output,f"{name}-three-for-two",triples)
        for removed,added in hits:
            register(ids-set(removed)|set(added),removed,added)
        print(name,"triple search complete",triples["complete"],"structural checks",
              triples["checked"],"accepted",len(hits),flush=True)
    save(a.output,"descent",{"parents":[{"name":name,"ids":sorted(ids)}],
         "smaller":[{"ids":sorted(trial),"origins":origins,"certificate":search.certificates[trial]}
                    for trial,origins in sorted(discovered.items(),key=lambda r:tuple(sorted(r[0])))]})


if __name__=="__main__":
    main()
