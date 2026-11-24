"""Compare full-pool intersection degree and length as family winner criteria."""
from fractions import Fraction

import networkx as nx

from experiments.constructive_axial import ROOT, load
from experiments.occupied_vertex_pruning import OUTPUT, TARGETS, read
from voronoi_app.angular import LineClearance
from voronoi_app.batch_methods import _domain
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import Geometry


def main():
    case = "flat-40"
    saved = read(OUTPUT / f"{case}.json")
    inputs, source, _ = load(case)
    if source != saved["source"]:
        raise ValueError("The pruning and candidate records have different lineage.")
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    measures = read(ROOT / case / "geometry.json")["candidates"]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from((r["id"], i) for r in measures for i in r["intersections"])
    lengths = [Fraction(r["squared_length"]) for r in saved["lines"]]
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible, obstacles, original_obstacles=occupied.values()))
    geometry = Geometry(inputs, lines, graph, clearance)
    regions, doors = incidence_sets(inputs["analysis"]["incidence"])
    long = {i for i, line in enumerate(lines) if line.length >= saved["long_threshold"]}
    transverse = [(i, int(j), tuple(point)) for i in long for j, point in measures[i]["transverse"].items()
                  if i < int(j) and int(j) in long]

    def compare(ids):
        subgraph = graph.subgraph(ids)
        crossings = [(i, j, p) for i, j, p in transverse if i in ids and j in ids]
        return {"count": len(ids), "reduction_percent": 100 * (1 - len(ids) / len(lines)),
                "intersection_pairs": subgraph.number_of_edges(),
                "components": nx.number_connected_components(subgraph),
                "missing_regions": sorted(i for i, candidates in regions.items() if ids.isdisjoint(candidates)),
                "missing_doorways": [i for i, candidates in enumerate(doors) if ids.isdisjoint(candidates)],
                "long_crossing_pairs": len(crossings), "long_crossing_sites": len({p for _, _, p in crossings}),
                "targets": sorted(ids.intersection(TARGETS))}

    results = {}
    for tolerance, old in saved["results"].items():
        length_ids = set(old["retained"])
        degree_ids = set(map(int, saved["unindexed"]))
        changed_families = 0
        for groups in old["vertex_families"].values():
            for group in groups:
                winner = min(group["candidate_ids"], key=lambda i: (-graph.degree[i], -lengths[i], i))
                changed_families += winner != group["representative"]
                degree_ids.add(winner)
        result = compare(degree_ids)
        print(tolerance, result, flush=True)
        winding = geometry.geometry(frozenset(degree_ids))
        results[tolerance] = {
            "length": compare(length_ids) | {"winding_rank": old["winding_rank"]},
            "connectivity": result | {"winding_rank": winding["independent_circulation_rank"],
                                      "required_rank": winding["required_circulation_rank"],
                                      "missing_rings": winding["missing_axial_rings"],
                                      "clearance_rejections": winding["lines_crossing_effective_occupied_space"]},
            "changed_families": changed_families,
            "connectivity_only": sorted(degree_ids - length_ids),
            "length_only": sorted(length_ids - degree_ids),
            "connectivity_retained": sorted(degree_ids),
            "connectivity_eliminated": sorted(set(graph) - degree_ids),
        }
        atomic_write(OUTPUT / "flat-40-connectivity-comparison.json", encode({
            "criterion": "full certified pool degree, then exact length, then canonical ID",
            "source": source, "results": results}))


if __name__ == "__main__":
    main()
