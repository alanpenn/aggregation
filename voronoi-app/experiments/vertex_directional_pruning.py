"""Eliminate directional duplicates from the archived Flat 40 certified pool."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from math import atan2, degrees, sqrt
from pathlib import Path
from statistics import median

import networkx as nx
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from voronoi_app.angular import _cross, _direction, _exact_point, _on_segment
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import _vertices
from voronoi_app.experimental_circulation_topology import _contact_graph, _ordered_components

ROOT = Path("diagnostics/strict-generalisation")
TOLERANCES = (3, 5, 10)


def point(values):
    return tuple(map(Fraction, values))


def occupied_boundary(vertices):
    cells = defaultdict(dict)
    for vertex in vertices:
        for member in vertex["members"]:
            cells[member["cell"]][member["vertex_index"]] = point(vertex["point"])
    polygons = {cell: Polygon([p for _, p in sorted(ring.items())])
                for cell, ring in cells.items()}
    constituent_vertices, _ = _vertices(polygons)
    components = _ordered_components(_contact_graph(polygons, polygons))
    branches = defaultdict(list)
    faces = set()
    for block_id, component in enumerate(components):
        geometry = unary_union([polygons[cell] for cell in sorted(component)])
        parts = [geometry] if geometry.geom_type == "Polygon" else geometry.geoms
        for part in parts:
            polygon = orient(part)
            for ring_index, ring in enumerate((polygon.exterior, *polygon.interiors)):
                points = list(map(_exact_point, ring.coords[:-1]))
                for index, current in enumerate(points):
                    previous, following = points[index - 1], points[(index + 1) % len(points)]
                    rays = _direction(current, previous), _direction(current, following)
                    turn = -_cross(*rays)
                    branches[current].append((block_id, ring_index > 0, rays, turn))
                    faces.add(tuple(sorted((current, following))))
    if not branches.keys() <= {point(v["point"]) for v in vertices}:
        raise ValueError("The block union introduced vertices outside the archived cell geometry.")
    return components, branches, sorted(faces), constituent_vertices


def families(ids, angles, lengths, tolerance):
    """Cut at the largest circular gap, then greedily cap each family's span."""
    ordered = sorted(ids, key=lambda i: (angles[i], i))
    if not ordered:
        return []
    gaps = [(angles[b] - angles[a] + (180 if j == len(ordered) - 1 else 0))
            for j, (a, b) in enumerate(zip(ordered, ordered[1:] + ordered[:1]))]
    cut = (max(range(len(gaps)), key=gaps.__getitem__) + 1) % len(ordered)
    groups = []
    for position in range(cut, cut + len(ordered)):
        candidate = ordered[position % len(ordered)]
        angle = angles[candidate] + (180 if position >= len(ordered) else 0)
        if not groups or angle - groups[-1][0][0] > tolerance:
            groups.append([])
        groups[-1].append((angle, candidate))
    result = []
    for group in groups:
        members = [i for _, i in group]
        result.append({"candidate_ids": members, "count": len(members),
                       "spread_degrees": group[-1][0] - group[0][0],
                       "representative": min(members, key=lambda i: (-lengths[i], i))})
    return result


def experiment(root):
    paths = {
        "vertices": root / "vertex-axial-1/vertices.json",
        "vertex_source": root / "vertex-axial-1/source.json",
        "measures": root / "constructive-axial-3/flat-40/geometry.json",
        "measure_source": root / "constructive-axial-3/flat-40/source.json",
        "benchmark": root / "extended-terrain-1/visual-index.json",
    }
    raw = {key: path.read_bytes() for key, path in paths.items()}
    hashes = {key: sha256(content).hexdigest() for key, content in raw.items()}
    for directory, manifest, keys in (
        ("vertex-axial-1", "export-checksums.json", ("vertices", "vertex_source")),
        ("constructive-axial-3", "export-checksums.json", ("measures", "measure_source")),
        ("extended-terrain-1", "export-record.json", ("benchmark",)),
    ):
        archive = root / directory
        checksums = json.loads((archive / manifest).read_bytes())
        for key in keys:
            if checksums[paths[key].relative_to(archive).as_posix()] != hashes[key]:
                raise ValueError(f"Archive checksum mismatch for {paths[key]}.")
    data = {key: json.loads(value) for key, value in raw.items()}
    source = data["vertex_source"]
    case = next(case for case in data["benchmark"]["cases"] if case["case"] == "flat-40")
    if source != data["measure_source"] or any(
        case["records"][key] != row["id"] for key, row in source.items()
    ):
        raise ValueError("Flat 40 input archives have different lineage.")
    full = case["methods"]["full_pool"]
    intervals, measures = full["selected_intervals"], data["measures"]["candidates"]
    if [row["id"] for row in intervals] != list(range(1534)) or [
        row["id"] for row in measures
    ] != list(range(1534)) or not full["result"]["constraints"]["valid"]:
        raise ValueError("Expected the complete certified Flat 40 candidate pool.")

    vertices = data["vertices"]["vertices"]
    blocks, branches, faces, constituent_vertices = occupied_boundary(vertices)
    incident = defaultdict(list)
    audit = []
    endpoints = [(point(row["start"]), point(row["end"])) for row in intervals]
    directions = [_direction(*pair) for pair in endpoints]
    lengths = [dx * dx + dy * dy for dx, dy in directions]
    angles = [degrees(atan2(float(dy), float(dx))) % 180 for dx, dy in directions]
    for vertex in vertices:
        identifier = vertex["id"]
        coord = point(vertex["point"])
        local = branches[coord]
        convex = [rays for _, _, rays, turn in local if turn > 0]
        convex_members = {(v.reference.building_id, v.reference.vertex_index)
                          for v in constituent_vertices[coord] if v.convex}
        supports, rejected = [], []
        if convex:
            for i, ((start, end), direction) in enumerate(zip(endpoints, directions, strict=True)):
                if all(min(a, b) <= p <= max(a, b) for a, b, p in zip(start, end, coord)) and _on_segment(coord, start, end):
                    if any(_cross(direction, left) * _cross(direction, right) >= 0
                           for left, right in convex):
                        supports.append(i)
                        incident[i].append(identifier)
                    else:
                        rejected.append(i)
        audit.append({"id": identifier, "point": vertex["point"],
                      "members": [m | {"constituent_convex": (m["cell"], m["vertex_index"]) in convex_members}
                                  for m in vertex["members"]],
                      "boundary_status": ("convex" if convex else "nonconvex_or_flat" if local else "interior"),
                      "boundary_branches": [{"block": block, "hole": hole,
                                             "incident_rays": [list(map(str, ray)) for ray in rays],
                                             "turn_sign": (turn > 0) - (turn < 0)}
                                            for block, hole, rays, turn in local],
                      "candidate_ids": supports, "incidental_candidate_ids": rejected})

    unindexed = {}
    line_rows = []
    for row, measure, direction, squared, angle in zip(intervals, measures, directions, lengths, angles, strict=True):
        i = row["id"]
        if i not in incident:
            constituent = data["vertices"]["candidate_supports"][i]
            start, end = endpoints[i]
            aligned_faces = [[list(map(str, a)), list(map(str, b))] for a, b in faces
                             if _on_segment(a, start, end) and _on_segment(b, start, end)]
            unindexed[i] = {"constituent_support_vertex_ids": constituent,
                            "constituent_support_boundary_status": {
                                v: audit[v]["boundary_status"] for v in constituent},
                            "coincident_block_boundary_edges": aligned_faces}
        line_rows.append(row | {"axial_direction": list(map(str, _direction(*sorted(endpoints[i])))),
                                "orientation_degrees": angle, "squared_length": str(squared),
                                "length": sqrt(squared), "support_vertex_ids": incident.get(i, []),
                                "regions": measure["regions"], "intersections": measure["intersections"]})

    indexed = [v for v in audit if v["boundary_status"] == "convex"]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(intervals)))
    graph.add_edges_from((line["id"], j) for line in line_rows for j in line["intersections"])
    if graph.number_of_edges() != full["result"]["intersections"]:
        raise ValueError("Archived intersection count does not match the certified pool.")

    results = {}
    all_ids = set(graph)
    for tolerance in TOLERANCES:
        groups = {v["id"]: families(v["candidate_ids"], angles, lengths, tolerance) for v in indexed}
        representatives = {family["representative"] for group in groups.values() for family in group}
        retained = representatives | unindexed.keys()
        eliminated = all_ids - retained
        subgraph = graph.subgraph(retained)
        results[tolerance] = {"families_by_vertex": groups,
                              "family_count_distribution": Counter(map(len, groups.values())),
                              "family_counts_by_vertex": {i: len(g) for i, g in groups.items()},
                              "family_count": sum(map(len, groups.values())),
                              "singleton_families": sum(f["count"] == 1 for g in groups.values() for f in g),
                              "retained_candidate_ids": sorted(retained),
                              "eliminated_candidate_ids": sorted(eliminated),
                              "retained_count": len(retained),
                              "eliminated_count": len(eliminated),
                              "retained_median_length": median(line_rows[i]["length"] for i in retained),
                              "eliminated_median_length": median(line_rows[i]["length"] for i in eliminated),
                              "reduction_percent": 100 * len(eliminated) / len(all_ids),
                              "retained_intersection_pairs": subgraph.number_of_edges(),
                              "retained_graph_components": nx.number_connected_components(subgraph),
                              "retained_regions": sorted({r for i in retained for r in measures[i]["regions"]})}
    return {"input_hashes": {str(paths[key]): value for key, value in hashes.items()},
            "input_records": source, "blocks": [sorted(block) for block in blocks],
            "original_count": len(intervals), "convex_vertices": len(indexed),
            "vertices_with_support": sum(bool(v["candidate_ids"]) for v in indexed),
            "vertex_line_incidences": sum(len(v["candidate_ids"]) for v in indexed),
            "tangent_count_distribution": Counter(len(v["candidate_ids"]) for v in indexed),
            "vertices": audit, "candidates": line_rows, "unindexed_candidates": unindexed,
            "original_regions": sorted({r for m in measures for r in m["regions"]}),
            "original_intersection_pairs": graph.number_of_edges(), "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "vertex-directional-pruning-1/results.json")
    args = parser.parse_args()
    result = experiment(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(args.output, encode(result))


if __name__ == "__main__":
    main()
