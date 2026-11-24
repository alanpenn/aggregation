"""Exact incidence and winding explanation for the 1278/1422 factor."""
import networkx as nx

from experiments.controlled_preselection import Study
from experiments.flat40_factorial_routes import DEST, save
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _on_segment
from voronoi_app.sheaf_experiment import interval


def main():
    inventory=read(DEST/"inventory.json")
    index=inventory["pairs"].index([1278,1422])
    study=Study()
    common_contexts=[]
    for source in inventory["maps"]:
        if source["bits"][index]:
            continue
        common=set(source["ids"])-{1278}
        row={"other_choices":source["id"],"common_ids":sorted(common),
             "missing_regions_without_either":{r:[i for i in (1278,1422) if i in ids]
                   for r,ids in study.regions.items() if common.isdisjoint(ids)},
             "missing_doors_without_either":{j:[i for i in (1278,1422) if i in ids]
                   for j,ids in enumerate(study.doors) if common.isdisjoint(ids)},
             "compensation":{}}
        for chosen,other in ((1278,1422),(1422,1278)):
            row["compensation"][chosen]={
                r:sorted(common & study.regions[r])
                for r in sorted(study.cover[other]-study.cover[chosen])}
        topology=study.geometry.geometry(frozenset(common))
        row["without_either"]={"rank":topology["independent_circulation_rank"],
            "components":nx.number_connected_components(study.graph.subgraph(common)),
            "lost_enclosures":topology["missing_axial_rings"],
            "merged_block_classes":[c["enclosed_blocks"] for c in topology["circulation_cycles"]
                                    if len(c["enclosed_blocks"])>1]}
        common_contexts.append(row)
    example=common_contexts[0]
    common=set(example["common_ids"])
    shared_topology=study.geometry.geometry(frozenset(common))
    candidates={}
    for chosen in (1278,1422):
        ids=common|{chosen}
        topology=study.full(ids,faces=True)
        rings=[]
        for cycle in topology["circulation_cycles"]:
            ring=topology["witness_faces"][cycle["face_index"]]
            line=study.lines[chosen]
            uses_line=any(_on_segment(a,*interval(line)) and _on_segment(b,*interval(line))
                          for a,b in zip(ring,ring[1:]))
            if uses_line:
                rings.append({"blocks":cycle["enclosed_blocks"],"ring":[list(map(str,p)) for p in ring]})
        candidates[chosen]={"regions":sorted(study.cover[chosen]),"winding_rank":topology["independent_circulation_rank"],
                            "winding_faces_using_line":rings,
                            "selected_intersections":sorted(study.neighbors[chosen]&common)}
    save("dissimilar-pair",{"factor":index+1,"line_ids":[1278,1422],"contexts":common_contexts,
                            "zero_context_without_either":{"rank":shared_topology["independent_circulation_rank"],
                                "lost_enclosures":shared_topology["missing_axial_rings"],
                                "merged_block_classes":[cycle["enclosed_blocks"] for cycle in shared_topology["circulation_cycles"]
                                                        if len(cycle["enclosed_blocks"])>1]},
                            "zero_context_candidates":candidates})


if __name__=="__main__":
    main()
