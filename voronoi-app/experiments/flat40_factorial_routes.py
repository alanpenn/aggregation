"""Route every certified Flat 40 factorial cell and checkpoint route arrays."""
from functools import cache
from hashlib import sha256
from itertools import product
from time import monotonic
import argparse

from shapely import from_wkb

from experiments.constructive_axial import load
from experiments.controlled_preselection import Study
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.recombine_flat40 import DEST as PRIOR
from experiments.strict_generalisation import rss_mib
from voronoi_app.batch_routing_reference import MasterNetwork, describe
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.convex_metric_experiment import build_master_doors, worst
from voronoi_app.region_incidence_angular import angular_depth
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import RegionalNetwork

DEST = OUTPUT.parent/"flat-40-factorial-1"


def save(name, data):
    atomic_write(DEST/f"{name}.json",encode(data))


def checksum(value):
    return sha256(encode(value)).hexdigest()


def verify():
    import experiments.recombine_flat40 as enumeration
    previous = read(PRIOR/"results.json")
    analysis = read(PRIOR/"analysis.json")
    enumeration.DEST = DEST/"reproduced-enumeration"
    reproduced=enumeration.DEST/"results.json"
    if not reproduced.exists():
        enumeration.run()
    current=read(reproduced)
    keys = ("source","parents","union_ids","shared_ids","mandatory","optional_ids","size_audit","minimum_maps")
    hashes = [{k:checksum(row[k]) for k in keys} for row in (previous,current)]
    if hashes[0]!=hashes[1]:
        raise ValueError(f"Enumeration replay differs: {[k for k in keys if hashes[0][k]!=hashes[1][k]]}")
    study=Study()
    if study.source!=analysis["source"] or checksum(study.inputs["candidates"]["pool"])!=analysis["pool_sha256"]:
        raise ValueError("Exact endpoints or provenance differ.")
    pair_definitions = sorted(sorted(row["ids"]) for row in analysis["interchangeable_pairs"])
    core = sorted(map(int,current["mandatory"]))
    certified={tuple(row["ids"]):row for row in current["minimum_maps"]}
    if len(core)!=27 or len(pair_definitions)!=7 or len({i for pair in pair_definitions for i in pair})!=14:
        raise ValueError("Unexpected factorial structure.")
    rows=[]
    for binary in product((0,1),repeat=7):
        flags="".join(map(str,binary))
        choices=[pair[b] for pair,b in zip(pair_definitions,binary,strict=True)]
        ids=sorted(core+choices)
        cert=certified[tuple(ids)]
        rows.append({"id":flags,"bits":binary,"alternatives":choices,"ids":ids,
                     "length":cert["metrics"]["length"],"intersection_count":cert["metrics"]["intersection_pairs"],
                     "certificate":cert["winding"],"strict_regions":292,"doorways":100,"components":1})
    if len(rows)!=128 or len(certified)!=128:
        raise ValueError("The factorial inventory did not match the exact replay.")
    save("inventory",{"source":study.source,"enumeration_hashes":hashes[0],"pairs":pair_definitions,
                       "core":core,"maps":rows,"pool_sha256":analysis["pool_sha256"],
                       "union_ids":current["union_ids"],"size_audit":current["size_audit"]})


def route():
    started=monotonic()
    inventory=read(DEST/"inventory.json")
    study=Study()
    inputs,source,reference=load("flat-40")
    if inventory["source"]!=source:
        raise ValueError("Routing lineage differs from enumeration.")
    analysis=inputs["analysis"]
    pairs=[tuple(pair) for pair in analysis["pairs"]]
    if len(pairs)!=4950 or pairs!=[tuple(pair) for pair in reference["identity"]["pairs"]] or analysis["doorways"]!=reference["identity"]["doorways"]:
        raise ValueError("Doorway order differs from the full-pool reference.")
    labels=[inputs["settlement"]["building_labels"][str(d["building_cell"])] for d in analysis["doorways"]]
    _, links=incidence_sets(analysis["incidence"])
    regions={int(i):from_wkb(wkb) for i,wkb in inputs["candidates"]["regions_wkb"].items()}
    checkpoints=DEST/"routes"
    checkpoints.mkdir(exist_ok=True)
    route_hash=checksum({"inputs":source,"pairs":pairs,"inventory":inventory["enumeration_hashes"]})
    unfinished=[r for r in inventory["maps"] if not (checkpoints/f'{r["id"]}.json').exists()]
    if unfinished or not (DEST/"alternative-routes.json").exists():
        axial=MasterNetwork(study.lines,[])
        stops,_,_=build_master_doors(study.lines,analysis["incidence"],regions,study.clearance)
        metric=RegionalNetwork(axial,stops)
        print("Shared certified networks constructed",round(monotonic()-started,2),flush=True)
        for number,row in enumerate(unfinished,1):
            clock=monotonic()
            ids=frozenset(row["ids"])
            angles,status=angular_depth(axial,ids,[g&ids for g in links],pairs)
            distances=metric.route(ids,False)
            if not all(s=="reachable" for s in status) or any(d is None for d in distances):
                raise ValueError(f'Unreachable pair in {row["id"]}.')
            result={"id":row["id"],"ids":row["ids"],"route_hash":route_hash,
                     "angular_routes":angles,"metric_routes":distances}
            for key,costs in (("angular",angles),("metric",distances)):
                result[key]=describe(costs)
                result[f"{key}_mean_excess"]=sum(b-a for a,b in zip(reference[key],costs,strict=True))/len(pairs)
                result[f"{key}_worst_excess"]=worst(pairs,reference[key],costs,labels)
            result["seconds"]=monotonic()-clock
            atomic_write(checkpoints/f'{row["id"]}.json',encode(result))
            if number%16==0:
                print(number,"maps routed",flush=True)
        # Save an exactly certified metric path for the most affected pair in
        # the 1278/1422 comparison, with all other choices held at zero.
        index=inventory["pairs"].index([1278,1422])
        first="0"*7
        second=first[:index]+"1"+first[index+1:]
        a,b=(read(checkpoints/f"{key}.json") for key in (first,second))
        extreme=max(range(len(pairs)),key=lambda i:abs(b["metric_routes"][i]-a["metric_routes"][i]))
        selected=pairs[extreme]
        paths={}
        for row in (a,b):
            trace=metric.route(frozenset(row["ids"]),False,trace_pairs=[selected])
            line=trace[selected]
            paths[row["id"]]=[[str(v) for v in p] for p in line] if line else []
        save("alternative-routes",{"pair_index":extreme,"buildings":[labels[j] for j in selected],
                                   "paths":paths,"maps":[first,second],
                                   "metric_costs":[a["metric_routes"][extreme],b["metric_routes"][extreme]]})
    for row in inventory["maps"]:
        r=read(checkpoints/f'{row["id"]}.json')
        if r["ids"]!=row["ids"] or r["route_hash"]!=route_hash or any(len(r[f"{cost}_routes"])!=4950 for cost in ("angular","metric")):
            raise ValueError("Stale or truncated movement checkpoint.")
    save("routing-index",{"route_hash":route_hash,"doorways":analysis["doorways"],"pairs":pairs,
                          "building_labels":labels,"maps":[r["id"] for r in inventory["maps"]],
                          "reference_means":{k:sum(reference[k])/len(pairs) for k in ("angular","metric")},
                          "seconds":monotonic()-started,"peak_rss_mib":rss_mib()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("verify","route"))
    args=parser.parse_args()
    DEST.mkdir(exist_ok=True)
    {"verify":verify,"route":route}[args.phase]()


if __name__=="__main__":
    main()
