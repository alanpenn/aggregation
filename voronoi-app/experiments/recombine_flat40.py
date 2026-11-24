"""Exhaustively minimise the union of the saved Flat 40 exchange maps."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
from math import comb
from time import monotonic

from experiments.controlled_preselection import Study, check, metrics
from experiments.frozen_preselection import CASES, DEST as PARENTS
from experiments.occupied_vertex_pruning import OUTPUT, read
from voronoi_app.batch_store import atomic_write, encode

DEST = OUTPUT.parent / "recombined-axial-maps-1"


def run():
    started = monotonic()
    study = Study()
    parents = {}
    for name in CASES:
        path = PARENTS / f"{name}-exchange.json"
        row = read(path)
        ids = set(row["ids"])
        if row["source"] != study.source or len(ids) != 34 or len(row["ids"]) != 34:
            raise ValueError(f"Invalid parent inventory for {name}.")
        configuration = row["configuration"]
        if row["configuration_sha256"] != sha256(encode(configuration)).hexdigest():
            raise ValueError(f"Invalid configuration certificate for {name}.")
        parents[name] = {"ids": sorted(ids), "sha256": sha256(path.read_bytes()).hexdigest(),
                         "winding": check(study, ids), "metrics": metrics(study, ids)}
    roots = [set(row["ids"]) for row in parents.values()]
    union = set.union(*roots)
    shared = set.intersection(*roots)
    union_winding = check(study,union)
    if study.winding.rank(union) != study.winding.required:
        raise ValueError("The union does not have a uniform certified occupied-block cycle space.")

    # Every feasible network is a subset of the union. In its uniform cycle
    # space, deleting lines cannot create new winding signatures or incidence.
    # A failed rank or incidence check on U−{i} makes i mandatory in U.
    mandatory={}
    for i in sorted(union):
        trial=union-{i}
        regions=[r for r, candidates in study.regions.items() if trial.isdisjoint(candidates)]
        doors=[d for d, candidates in enumerate(study.doors) if trial.isdisjoint(candidates)]
        rank=study.winding.rank(trial) if study.connected(trial) else None
        if regions or doors or (rank is not None and rank < study.winding.required):
            mandatory[i]={"strict_regions":regions,"doorways":doors,"winding_rank_if_connected":rank}

    fixed=set(mandatory)
    optional=sorted(union-fixed)
    if not fixed <= shared:
        raise ValueError("A verified parent omits a supposedly mandatory candidate.")
    print(f"Verified {len(union)} union lines, {len(shared)} shared and {len(fixed)} mandatory.",flush=True)

    # Cache incidence as integer masks. The exact winding check builds a new
    # cycle basis for each surviving connected trial. A full face certificate
    # independently verifies each minimum found.
    incidence_masks=[sum(1<<i for i in ids & union) for ids in study.incidence]
    audit=[]
    minima=[]
    for count in range(len(fixed), min(map(len, roots))+1):
        count_by_status=Counter()
        for extras in combinations(optional,count-len(fixed)):
            ids=fixed|set(extras)
            mask=sum(1<<i for i in ids)
            if any(not (mask & requirement) for requirement in incidence_masks):
                count_by_status["incidence"]+=1
                continue
            if not study.connected(ids):
                count_by_status["connectivity"]+=1
                continue
            if study.winding.rank(ids)!=study.winding.required:
                count_by_status["winding"]+=1
                continue
            count_by_status["valid"]+=1
            minima.append({"ids":sorted(ids),"metrics":metrics(study,ids),"winding":check(study,ids),
                           "parent_distance":{k:len(ids^set(v["ids"])) for k,v in parents.items()}})
        expected=comb(len(optional),count-len(fixed))
        if sum(count_by_status.values())!=expected:
            raise ValueError("The exhaustive count does not match the subset inventory.")
        audit.append({"size":count,"subsets_considered":expected,"outcomes":dict(count_by_status)})
        print(count,dict(count_by_status),flush=True)
        if minima:
            break
    if not minima:
        raise ValueError("The search did not recover a known valid parent.")
    minima.sort(key=lambda row:(row["metrics"]["length"],row["ids"]))
    ids=set(minima[0]["ids"])
    for name,row in parents.items():
        ids_p=set(row["ids"])
        row["replacement_for_shortest_minimum"]={"removed":sorted(ids_p-ids),"added":sorted(ids-ids_p)}
    data={"source":study.source,"parents":parents,"union_ids":sorted(union),"shared_ids":sorted(shared),
          "union_metrics":metrics(study,union),"union_winding":union_winding,
          "mandatory":mandatory,"optional_ids":optional,"size_audit":audit,"minimum_maps":minima,
          "required_regions":sorted(study.regions),"required_doorways":len(study.doors),
          "elapsed_seconds":monotonic()-started,
          "scope":"Every subset of the parent union. Clearance inherited from the certified intervals."}
    DEST.mkdir(exist_ok=True)
    atomic_write(DEST/"results.json",encode(data))
    return data


if __name__=="__main__":
    run()
