"""Test minimum and maximum certified intersection degree at each Flat 40 corner."""
from fractions import Fraction
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
    degree = dict(graph.degree())
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
        high = min(ids, key=lambda i: (-degree[i], -squared[i], i))
        low = min((i for i in ids if i != high), key=lambda i: (degree[i], -squared[i], i), default=None)
        retained.add(high)
        row = {"vertex": v["id"], "maximum": high, "maximum_degree": degree[high]}
        if low is not None:
            retained.add(low)
            branches = [rays for _, rays, turn in corners[tuple(map(Fraction, v["point"]))] if turn > 0]
            assignments = [(axial_angle(directions[high], a), axial_angle(directions[low], b))
                           for rays in branches for a, b in (rays, rays[::-1])]
            alignment = min(assignments, key=lambda errors: (max(errors), sum(errors), errors))
            row |= {"minimum": low, "minimum_degree": degree[low], "degree_gap": degree[high]-degree[low],
                    "pair_angle": axial_angle(directions[high], directions[low]),
                    "face_errors_degrees": alignment,
                    "exact_two_face_alignment": any(
                        _cross(directions[high], a) == _cross(directions[low], b) == 0
                        for rays in branches for a, b in (rays, rays[::-1]))}
        pairs.append(row)
    paired = [r for r in pairs if "minimum" in r]
    regions, doors = incidence_sets(inputs["analysis"]["incidence"])
    subgraph = graph.subgraph(retained)
    long = {i for i,line in enumerate(lines) if line.length >= saved["long_threshold"]}
    crossings = [(i,int(j),tuple(p)) for i in long for j,p in measures[i]["transverse"].items()
                 if i < int(j) and int(j) in long]
    sites = {p for i,j,p in crossings if i in retained and j in retained}
    result = {"criterion": "extremes of degree in original exact intersection graph; length then ID for ties",
              "source": source, "original_count": len(lines), "retained": sorted(retained),
              "eliminated": sorted(set(graph)-retained), "provisional": sorted(unindexed), "pairs": pairs,
              "unique_maxima": len({r["maximum"] for r in pairs}),
              "unique_minima": len({r["minimum"] for r in paired}),
              "median_degree_gap": median(r["degree_gap"] for r in paired),
              "median_pair_angle": median(r["pair_angle"] for r in paired),
              "median_worst_face_error": median(max(r["face_errors_degrees"]) for r in paired),
              "face_alignment_counts": {t: sum(max(r["face_errors_degrees"]) <= t for r in paired)
                                        for t in (3, 5, 10, 15)},
              "exact_two_face_count": sum(r["exact_two_face_alignment"] for r in paired),
              "components": sorted(map(sorted,nx.connected_components(subgraph)),key=lambda c:(-len(c),c)),
              "intersection_pairs": subgraph.number_of_edges(),
              "missing_regions": {i: sorted(ids) for i,ids in regions.items() if retained.isdisjoint(ids)},
              "missing_doorways": {i: sorted(ids) for i,ids in enumerate(doors) if retained.isdisjoint(ids)},
              "region_count": len(regions), "doorway_count": len(doors),
              "long_sites_retained": len(sites), "long_sites_original": len({p for _,_,p in crossings})}
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible, obstacles, original_obstacles=occupied.values()))
    result["winding"] = Geometry(inputs, lines, graph, clearance).geometry(frozenset(retained))
    atomic_write(OUTPUT / "flat-40-connectivity-extremes.json", encode(result))
    return result


if __name__ == "__main__":
    run()
