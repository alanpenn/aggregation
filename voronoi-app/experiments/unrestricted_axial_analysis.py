"""Summarize structural blockers and corridor geometry across Flat 40 results."""
from collections import Counter
from itertools import combinations

from experiments.occupied_vertex_pruning import read
from experiments.unrestricted_axial_reduction import DEST, ORDERS, Study
from voronoi_app.batch_store import atomic_write, encode


def main():
    study=Study()
    cases={o:read(DEST/f"{o}.json") for o in ORDERS}
    best=min(ORDERS[:-1],key=lambda o:(len(cases[o]["final_ids"]),o))
    target_ids={957,1244,1355,865,1189,1190,1208,1354}
    data=read(DEST.parent/"occupied-vertex-pruning-1/flat-40.json")
    long={i for i,l in enumerate(study.length) if l>=data["long_threshold"]}
    high_degree=sorted(study.graph,key=lambda i:(-len(study.neighbors[i]),i))[:len(study.lines)//4]
    full_degree_blocks={}
    for region, ids in study.regions.items():
        if len(ids)==1:
            full_degree_blocks.setdefault(next(iter(ids)),[]).append(region)
    summaries={}
    for order,result in cases.items():
        ids=set(result["final_ids"])
        pairs=list(combinations(sorted(ids),2))
        summaries[order]={"direct":len(result["direct_ids"]),"final":len(ids),
                          "accepted_exchanges":sum(bool(r["accepted"]) for r in result["exchanges"]),
                          "length":sum(study.length[i] for i in sorted(ids)),
                          "long_lines":sorted(ids&long),"high_degree_lines":sorted(ids&set(high_degree)),
                          "intersection_pairs":sum(j in study.neighbors[i] for i,j in pairs),
                          "transverse_pairs":sum(j in study.transverse[i] for i,j in pairs),
                          "long_transverse_pairs":sum(i in long and j in long and j in study.transverse[i] for i,j in pairs),
                          "target_lines":sorted(ids&target_ids),
                          "old_witness_lines_removed":len(set(study.previous["protected_winding_lines"])-ids),
                          "blocker_counts":dict(Counter(result["final_blockers"].values()))}
    ids=set(cases[best]["final_ids"])
    blockers={}
    for i in sorted(ids):
        trial=ids-{i}
        row={"strict_regions":[r for r,c in study.regions.items() if c&ids=={i}],
             "doorway_building_labels":[study.inputs["settlement"]["building_labels"][str(door["building_cell"])]
                                      for door,c in zip(study.inputs["analysis"]["doorways"],study.doors,strict=True)
                                      if c&ids=={i}],
             "disconnects":not study.connected(trial)}
        if not row["disconnects"]:
            rank=study.winding.rank(trial)
            if rank is None:
                rank=study.geometry.geometry(frozenset(trial))["independent_circulation_rank"]
            row["winding_rank"]=rank
        blockers[i]=row
    common=set.intersection(*(set(cases[o]["final_ids"]) for o in ORDERS[:-1]))
    atomic_write(DEST/"structural-summary.json",encode({"best_order":best,"orders":summaries,
                 "best_indispensability":blockers,"common_lines":sorted(common),
                 "full_pool_singleton_regions":full_degree_blocks}))


if __name__=="__main__":
    main()
