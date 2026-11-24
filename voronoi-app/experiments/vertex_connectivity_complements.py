"""Test complementary certified intersection sets at each Flat 40 corner."""
from fractions import Fraction
from itertools import combinations
from math import atan2, degrees
from statistics import median

import networkx as nx

from experiments.constructive_axial import ROOT, load
from experiments.occupied_vertex_pruning import OUTPUT, boundary_index, read
from voronoi_app.angular import LineClearance, _cross
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import Geometry


def axial_angle(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    return degrees(atan2(float(abs(_cross(a, b))), float(abs(dot))))


def run():
    saved = read(OUTPUT / "flat-40.json")
    inputs, source, _ = load("flat-40")
    if source != saved["source"]:
        raise ValueError("The candidate and pruning records have different lineage.")
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    measures = read(ROOT / "flat-40/geometry.json")["candidates"]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from((r["id"], i) for r in measures for i in r["intersections"])
    neighbors = {i: set(graph[i]) for i in graph}
    degree = {i: len(adjacent) for i, adjacent in neighbors.items()}
    polygons, _, _ = _settlement(inputs)
    labels = {int(k): v for k, v in inputs["settlement"]["building_labels"].items()}
    vertices, _, corners = boundary_index(inputs["topology"], polygons, labels, lines)
    if vertices != saved["vertices"]:
        raise ValueError("The exact convex vertex inventory differs.")
    directions = [tuple(map(Fraction, row["direction"])) for row in saved["lines"]]
    squared = [Fraction(row["squared_length"]) for row in saved["lines"]]
    unindexed = set(map(int, saved["unindexed"]))
    retained = set(unindexed)
    pairs = []
    for v in vertices:
        ids = v["supported"]
        if not ids:
            continue
        def score_pair(i, j):
            union = neighbors[i] | neighbors[j]
            distance = Fraction(len(neighbors[i] ^ neighbors[j]), len(union)) if union else Fraction(0)
            score = min(degree[i], degree[j]) * (1 + distance) / 2
            return score, axial_angle(directions[i], directions[j]), degree[i] + degree[j], squared[i] + squared[j], -i, -j

        if len(ids) == 1:
            high, low = ids[0], None
            score = None
        else:
            high, low = max(combinations(sorted(ids), 2), key=lambda pair: score_pair(*pair))
            score = score_pair(high, low)[0]
            if (degree[low], -low) > (degree[high], -high):
                high, low = low, high
        retained.add(high)
        row = {"vertex": v["id"], "first": high, "first_degree": degree[high]}
        if low is not None:
            retained.add(low)
            union = neighbors[high] | neighbors[low]
            common = neighbors[high] & neighbors[low]
            distance = Fraction(len(union) - len(common), len(union)) if union else Fraction(0)
            branches = [rays for _, rays, turn in corners[tuple(map(Fraction, v["point"]))] if turn > 0]
            assignments = [(axial_angle(directions[high], a), axial_angle(directions[low], b))
                           for rays in branches for a, b in (rays, rays[::-1])]
            alignment = min(assignments, key=lambda errors: (max(errors), sum(errors), errors))
            row |= {"second": low, "second_degree": degree[low], "score": str(score),
                    "jaccard_distance": float(distance), "intersection_union": len(union),
                    "intersection_shared": len(common),
                    "pair_angle": axial_angle(directions[high], directions[low]),
                    "face_errors_degrees": alignment,
                    "exact_two_face_alignment": any(
                        _cross(directions[high], a) == _cross(directions[low], b) == 0
                        for rays in branches for a, b in (rays, rays[::-1]))}
        pairs.append(row)
    paired = [r for r in pairs if "second" in r]
    regions, doors = incidence_sets(inputs["analysis"]["incidence"])
    subgraph = graph.subgraph(retained)
    long = {i for i,line in enumerate(lines) if line.length >= saved["long_threshold"]}
    transverse = [(i, int(j), tuple(p)) for i, row in enumerate(measures)
                  for j, p in row["transverse"].items() if i < int(j)]

    def pool_metrics(ids):
        selected = graph.subgraph(ids)
        active_crossings = [(i, j, p) for i, j, p in transverse if i in ids and j in ids]
        return {"count": len(ids), "reduction_percent": 100*(1-len(ids)/len(lines)),
                "median_length": median(lines[i].length for i in ids),
                "total_length": sum(lines[i].length for i in sorted(ids)),
                "intersection_pairs": selected.number_of_edges(),
                "mean_degree": 2*selected.number_of_edges()/len(ids),
                "transverse_pairs": len(active_crossings),
                "distinct_transverse_sites": len({p for _, _, p in active_crossings}),
                "long_transverse_sites": len({p for i, j, p in active_crossings if i in long and j in long})}

    result = {"criterion": "min(full-pool degrees) × (1 + Jaccard distance) / 2",
              "tie_breakers": ["largest axial angle", "largest degree sum", "largest exact squared-length sum", "lowest sorted ID pair"],
              "source": source, "original_count": len(lines), "retained": sorted(retained),
              "eliminated": sorted(set(graph)-retained), "provisional": sorted(unindexed), "pairs": pairs,
              "intersection_neighbors": {i: sorted(neighbors[i]) for i in sorted(neighbors)},
              "median_jaccard_distance": median(r["jaccard_distance"] for r in paired),
              "median_first_degree": median(r["first_degree"] for r in paired),
              "median_second_degree": median(r["second_degree"] for r in paired),
              "median_pair_angle": median(r["pair_angle"] for r in paired),
              "median_worst_face_error": median(max(r["face_errors_degrees"]) for r in paired),
              "face_alignment_counts": {t: sum(max(r["face_errors_degrees"]) <= t for r in paired)
                                        for t in (3, 5, 10, 15)},
              "exact_two_face_count": sum(r["exact_two_face_alignment"] for r in paired),
              "components": sorted(map(sorted,nx.connected_components(subgraph)),key=lambda c:(-len(c),c)),
              "missing_regions": {i: sorted(ids) for i,ids in regions.items() if retained.isdisjoint(ids)},
              "missing_doorways": {i: sorted(ids) for i,ids in enumerate(doors) if retained.isdisjoint(ids)},
              "region_count": len(regions), "doorway_count": len(doors),
              "metrics": pool_metrics(retained), "original": pool_metrics(set(graph)),
              "length_rule": {t: pool_metrics(set(row["retained"])) | {"winding_rank": row["winding_rank"],
                              "missing_regions": list(row["missing_region_restorers"])}
                              for t, row in saved["results"].items()}}
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible, obstacles, original_obstacles=occupied.values()))
    result["winding"] = Geometry(inputs, lines, graph, clearance).geometry(frozenset(retained))
    atomic_write(OUTPUT / "flat-40-connectivity-complements.json", encode(result))
    return result


if __name__ == "__main__":
    run()
