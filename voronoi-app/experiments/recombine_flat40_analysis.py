"""Check the exact parent inventory and factor the minimum-map choices."""
from itertools import combinations, product
from hashlib import sha256

from experiments.constructive_axial import ROOT
from experiments.controlled_preselection import Study
from experiments.frozen_preselection import DEST as PARENTS
from experiments.occupied_vertex_pruning import read
from experiments.recombine_flat40 import DEST
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.sheaf_experiment import overlap, similarity


def main():
    result=read(DEST/"results.json")
    archived=read(PARENTS/"inventory.json")
    study=Study()
    certified=study.inputs["candidates"]["pool"]
    if archived["source"]!=study.source or archived["certified_pool"]!=certified:
        raise ValueError("Exact certified endpoints or provenance changed since the parent experiment.")
    minima=[frozenset(row["ids"]) for row in result["minimum_maps"]]
    mandatory=set(map(int,result["mandatory"]))
    observed=set(minima)
    alternative_pairs=[(i,j) for i,j in combinations(result["optional_ids"],2)
                       if all((i in ids)!=(j in ids) for ids in minima)]
    if sorted(i for pair in alternative_pairs for i in pair)!=result["optional_ids"]:
        raise ValueError("Minimum maps do not decompose into disjoint alternative pairs.")
    predicted={frozenset(mandatory|set(choice)) for choice in product(*alternative_pairs)}
    if predicted!=observed:
        raise ValueError("The choices are not independently interchangeable.")
    records=[]
    for i,j in alternative_pairs:
        angle,fraction,gap=overlap(study.segments[i],study.segments[j])
        records.append({"ids":[i,j],"angle":angle,"projected_overlap":fraction,"lateral_gap":gap,
                        "region_jaccard":similarity(study.cover[i],study.cover[j]),
                        "lengths":[study.length[i],study.length[j]]})
    parent_ids={frozenset(row["ids"]) for row in result["parents"].values()}
    shortest_novel=next(row for row in result["minimum_maps"] if frozenset(row["ids"]) not in parent_ids)
    reference_d=read(ROOT/"flat-40/D.json")["maps"]["exchanged"]
    output={"source":study.source,"pool_sha256":sha256(encode(certified)).hexdigest(),
            "exact_union_inventory":[certified["candidates"][i] for i in result["union_ids"]],
            "interchangeable_pairs":records,"distinct_parent_maps":len(parent_ids),
            "novel_minimum_maps":len(minima)-len(parent_ids),
            "shortest_novel":shortest_novel,
            "archived_algorithm_d_count":len(reference_d),
            "archived_algorithm_d_outside_union":sorted(set(reference_d)-set(result["union_ids"]))}
    atomic_write(DEST/"analysis.json",encode(output))


if __name__=="__main__":
    main()
