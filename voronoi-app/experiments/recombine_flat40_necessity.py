"""Compare exact deletion necessities and available alternatives across unions."""
from functools import cache

import networkx as nx

from experiments.recombine_flat40 import DEST as EXACT
from experiments.recombine_flat40_extended import DEST, Study, save
from experiments.occupied_vertex_pruning import read


def main():
    study=Study()
    unions=read(DEST/"unions.json")
    proof=read(EXACT/"results.json")
    geometry=read(EXACT/"analysis.json")
    parent_ids={k:frozenset(v["ids"]) for k,v in unions["parents"].items() if k!="F-H"}
    best=read(DEST/"union-exchanges.json")
    novel=next(row for row in best["outcomes"] if not row["parent_identity"])
    samples=parent_ids | {"bounded union novel":frozenset(novel["ids"]),
                          "shortest novel exact":frozenset(geometry["shortest_novel"]["ids"]),
                          "best full-pool":frozenset(read(DEST/"full-exchanges.json")["best"]["ids"])}

    @cache
    def delete(ids,i):
        remaining=ids-{i}
        topology=study.geometry.geometry(remaining)
        missing_regions=[r for r,options in study.regions.items() if remaining.isdisjoint(options)]
        missing_doors=[j for j,options in enumerate(study.doors) if remaining.isdisjoint(options)]
        components=nx.number_connected_components(study.graph.subgraph(remaining))
        rank=topology["independent_circulation_rank"]
        if not (missing_regions or missing_doors or components!=1 or rank<24):
            raise ValueError(f"Saved minimum has an individually removable line: {i}")
        return {"lost_regions":missing_regions,"lost_doorways":missing_doors,"components":components,
                "winding_rank":rank,"lost_simple_enclosures":topology["missing_axial_rings"],
                "merged_block_classes":[c["enclosed_blocks"] for c in topology["circulation_cycles"]
                                        if len(c["enclosed_blocks"])>1]}

    comparisons={}
    for name,ids in samples.items():
        comparisons[name]={"ids":sorted(ids),"deletion_blockers":{i:delete(ids,i) for i in sorted(ids)}}
    flexibility={}
    for name,row in unions["unions"].items():
        ids=set(row["ids"])
        minima=[m["ids"] for m in proof["minimum_maps"] if set(m["ids"])<=ids]
        flexibility[name]={"minimum_count":len(minima[0]),"number_of_minimum_maps":len(minima),
                           "alternative_pairs":[x for x in geometry["interchangeable_pairs"]
                                                if ids.issuperset(x["ids"])],
                           "fixed_across_minima":sorted(set.intersection(*(set(m) for m in minima)))}
    save("necessity",{"source":study.source,"maps":comparisons,"union_flexibility":flexibility})


if __name__=="__main__":
    main()
