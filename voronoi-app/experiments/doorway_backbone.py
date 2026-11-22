"""Reproduce the experimental Y doorway-to-doorway visibility analysis."""

import argparse
import gzip
import json
import math
import resource
import time
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.stats import spearmanr
from shapely.ops import unary_union
from shapely.strtree import STRtree

from experiments.connectivity_backbone import load_gzip, validate_inputs
from experiments.shortest_path_backbone import (
    matching_candidates, path_segments, plot_background, save_figure, summarize,
)
from experiments.shortest_path_routes import graph_from_dict
from experiments.shortest_path_visibility import exact_point, sha256
from voronoi_app.angular import (
    LineClearance, _exact_point, _inside_prepared, _intersections, _on_segment, _prepare_polygon,
)
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.core import ExperimentPipeline
from voronoi_app.experimental_visibility import (
    IndexedClearance, _distance, _outward_bounds, component_for_point,
    visible_connections,
)
from voronoi_app.orchestrator import ExperimentOrchestrator
from voronoi_app.registry import get_registry


STRUCTURAL_SHA = "42a27781612440f6f20088b770f08e415d6ea2f4caf249befe751fbdb3743be5"


def shared_faces(left, right):
    """Return exact positive-length overlaps of polygon boundary edges."""
    a = tuple(map(_exact_point, left.exterior.coords))
    b = tuple(map(_exact_point, right.exterior.coords))
    overlaps = set()
    for p, q in zip(a, a[1:]):
        for r, s in zip(b, b[1:]):
            points = sorted(_intersections(p, q, r, s))
            if len(points) >= 2 and points[0] != points[-1]:
                overlaps.add((points[0], points[-1]))
    return sorted(overlaps)


def doorway_records(doors, opened, buildings, labels, graph, clearance):
    """Extract face midpoints; retain invalid or ambiguous dyads explicitly."""
    records = []
    prepared = [_prepare_polygon(component) for component in graph.components]
    for door_id, (open_id, building_id) in enumerate(doors):
        open_id, building_id = int(open_id), int(building_id)
        record = {"door_id": door_id, "open_id": open_id, "building_id": building_id,
                  "building_label": int(labels[building_id])}
        faces = shared_faces(opened[open_id], buildings[building_id])
        record["faces"] = [[exact_point(a), exact_point(b)] for a, b in faces]
        if len(faces) != 1:
            record.update(status="missing-face" if not faces else "ambiguous-faces")
            records.append(record)
            continue
        start, end = faces[0]
        point = tuple((start[i] + end[i]) / 2 for i in range(2))
        record["point"] = exact_point(point)
        if not clearance.permits(point, point):
            record["status"] = "blocked-point"
            records.append(record)
            continue
        try:
            component = component_for_point(point, graph.components)
        except ValueError as error:
            record.update(status="ambiguous-component", reason=str(error))
            records.append(record)
            continue
        connections = visible_connections(point, component, graph, clearance)
        record.update(component=component, connections=list(connections))
        interior_connections = [
            i for i in connections
            if _inside_prepared(tuple((point[j] + graph.vertices[i].point[j]) / 2
                                      for j in range(2)), prepared[component])
        ]
        record["interior_connections"] = interior_connections
        record["status"] = "valid" if interior_connections else "no-interior-connection"
        records.append(record)
    return records


def reconstruct(snapshot, opened, buildings, paired, labels):
    pipeline = ExperimentPipeline.from_dict(snapshot["configuration"])
    registry = get_registry()
    terrain = registry.get_terrain(pipeline.terrain_provider, pipeline.terrain_params)
    extent = (0, 0, pipeline.canvas_size, pipeline.canvas_size)
    grid = registry.get_grid(pipeline.grid_generator, pipeline.grid_params).generate(
        terrain=terrain, extent=extent, seed=pipeline.seed,
    )
    grid.metadata["extent"] = extent
    aggregation = registry.get_aggregation(
        pipeline.aggregation_strategy, pipeline.aggregation_params,
    ).aggregate(terrain=terrain, grid=grid, form=pipeline.urban_form, seed=pipeline.seed)
    polygons = ExperimentOrchestrator(pipeline)._space_polygons(grid)
    if aggregation.buildings != set(buildings) or aggregation.open_spaces != paired:
        raise ValueError("Reconstructed cell identities differ from the snapshot")
    if any(not polygons[cell].equals_exact(polygon, 0)
           for cell, polygon in {**opened, **buildings}.items()):
        raise ValueError("Reconstructed polygons differ from the snapshot")
    if aggregation.building_labels != labels:
        raise ValueError("Reconstructed labels differ from the preserved settlement")
    return aggregation


def routes_from_connections(graph, terminals, links, clearance, tolerance=1e-10):
    """Run one single-source tree per terminal, reusing certified connectors."""
    count = len(graph.vertices)
    rows, cols, weights = [], [], []
    neighbors = [[] for _ in graph.vertices]
    for edge in graph.edges:
        rows.extend((edge.start, edge.end))
        cols.extend((edge.end, edge.start))
        weights.extend((edge.length, edge.length))
        neighbors[edge.start].append((edge.end, edge.length))
        neighbors[edge.end].append((edge.start, edge.length))
    results = []
    direct_cache = {}
    for source, (start, component) in enumerate(terminals):
        source_links = links[source]
        extra_weights = [_distance(start, graph.vertices[i].point) for i in source_links]
        matrix = coo_matrix(
            (weights + extra_weights,
             (rows + [count] * len(source_links), cols + list(source_links))),
            shape=(count + 1, count + 1),
        ).tocsr()
        distances, predecessors = dijkstra(matrix, directed=True, indices=count,
                                           return_predecessors=True)
        for destination, (end, destination_component) in enumerate(terminals):
            if source == destination:
                continue
            result = {"source": source, "destination": destination}
            if component != destination_component:
                result["status"] = "different-component"
                results.append(result)
                continue
            key = tuple(sorted((source, destination)))
            if key not in direct_cache:
                direct_cache[key] = (
                    not any(_on_segment(point, start, end) for point in graph.ambiguous_vertices)
                    and clearance.permits(start, end)
                )
            if direct_cache[key]:
                result.update(status="direct", length=_distance(start, end),
                              vertices=[], near_tie=False)
                results.append(result)
                continue
            options = sorted((float(distances[i]) + _distance(graph.vertices[i].point, end), i)
                             for i in links[destination] if math.isfinite(distances[i]))
            if not options:
                result["status"] = "unreachable"
                results.append(result)
                continue
            length, current = options[0]
            margin = tolerance * max(1.0, length)
            near_tie = len(options) > 1 and options[1][0] - length <= margin
            path = []
            while current != count:
                if current < 0 or current >= count or len(path) > count:
                    raise ValueError("Invalid metric shortest-path predecessor")
                path.append(current)
                alternatives = sum(
                    abs(float(distances[other]) + weight - float(distances[current])) <= margin
                    for other, weight in neighbors[current] if math.isfinite(distances[other])
                )
                if current in source_links:
                    alternatives += abs(_distance(start, graph.vertices[current].point)
                                        - float(distances[current])) <= margin
                near_tie |= alternatives > 1
                current = int(predecessors[current])
            result.update(status="occluded", length=length, vertices=list(reversed(path)),
                          near_tie=bool(near_tie))
            results.append(result)
    return results


def analyse_paths(valid, paths, graph, candidates, candidate_tree, spatial, baseline_summary):
    tree = STRtree([_outward_bounds(v.point, v.point) for v in graph.vertices])
    graph_edges = {(e.start, e.end): e for e in graph.edges}
    usage = {}
    statuses = Counter()
    journeys = 0
    stored = []
    for path in paths:
        source, destination = path["source"], path["destination"]
        if source >= destination:
            continue
        left, right = valid[source], valid[destination]
        if left["building_id"] == right["building_id"]:
            continue
        statuses[path["status"]] += 1
        stored.append(path)
        if path["status"] not in ("direct", "occluded"):
            continue
        journeys += 1
        statuses["near_tie"] += int(path["near_tie"])
        start = tuple(map(Fraction, left["point"]))
        end = tuple(map(Fraction, right["point"]))
        for key in set(path_segments(start, end, path["vertices"], graph, tree)):
            edge = graph_edges.get(key)
            if edge is None:
                raise ValueError(f"Noded segment absent from saved visibility graph: {key}")
            if not graph.vertices[key[0]].buildings or not graph.vertices[key[1]].buildings:
                continue
            item = usage.setdefault(key, {"start": key[0], "end": key[1],
                                          "usage": 0, "building_pairs": set()})
            item["usage"] += 1
            item["building_pairs"].add(tuple(sorted((left["building_id"], right["building_id"]))))
    spatial_by_edge = {(e["start"], e["end"]): e["usage"] for e in spatial}
    baseline_journeys = baseline_summary["journeys"]
    baseline_status = baseline_summary["status"]
    spatial_journeys = baseline_status["spatial:direct"] + baseline_status["spatial:occluded"]
    boundary_journeys = baseline_status["boundary:direct"] + baseline_status["boundary:occluded"]
    if not baseline_journeys or spatial_journeys + boundary_journeys != baseline_journeys:
        raise ValueError("Saved baseline journey counts are inconsistent")
    result = []
    for key, item in sorted(usage.items()):
        edge = graph_edges[key]
        start, end = (graph.vertices[i].point for i in key)
        item.update(start_point=exact_point(start), end_point=exact_point(end),
                    start_buildings=graph.vertices[key[0]].buildings,
                    end_buildings=graph.vertices[key[1]].buildings,
                    boundary_following=edge.boundary_following,
                    tangent_supported=edge.tangent_supported, length=edge.length,
                    candidates=matching_candidates(start, end, candidates, candidate_tree),
                    spatial_usage=spatial_by_edge.get(key, 0),
                    building_pairs=sorted(item["building_pairs"]))
        result.append(item)
    result.sort(key=lambda item: (-item["usage"], item["start"], item["end"]))
    uses = sum(item["usage"] for item in result)
    for item in result:
        item["journey_share"] = item["usage"] / journeys if journeys else None
        item["edge_use_share"] = item["usage"] / uses if uses else None
    common = sorted(set(usage) & set(spatial_by_edge))
    correlation = None
    if len(common) >= 2:
        value = float(spearmanr([usage[k]["usage"] for k in common],
                                [spatial_by_edge[k] for k in common]).statistic)
        if math.isfinite(value):
            correlation = value
    comparison = {
        "common_edges": len(common), "doorway_only": len(usage.keys() - spatial_by_edge.keys()),
        "spatial_only": len(spatial_by_edge.keys() - usage.keys()),
        "spearman_common": correlation,
        "doorway_top10_use_share": sum(e["usage"] for e in result[:10]) / uses if uses else None,
        "spatial_top10_use_share": (sum(sorted(spatial_by_edge.values(), reverse=True)[:10])
                                    / sum(spatial_by_edge.values()) if spatial_by_edge else None),
        "baseline_journeys": baseline_journeys,
        "baseline_spatial_journeys": spatial_journeys,
        "baseline_boundary_journeys": boundary_journeys,
        "doorway_prominent_spatial_rare": [
            {"edge": [e["start"], e["end"]], "doorway_usage": e["usage"],
             "spatial_usage": e["spatial_usage"]}
            for e in result
            if e["usage"] / journeys >= .01 and e["spatial_usage"] / baseline_journeys < .001
        ] if journeys else [],
        "spatial_prominent_doorway_rare": [
            {"edge": list(key), "spatial_usage": spatial_by_edge[key],
             "doorway_usage": usage.get(key, {}).get("usage", 0)}
            for key in sorted(spatial_by_edge, key=lambda k: (-spatial_by_edge[k], k))
            if spatial_by_edge[key] / baseline_journeys >= .01
            and (usage.get(key, {}).get("usage", 0) / journeys if journeys else 0) < .001
        ],
    }
    return stored, result, dict(statuses), journeys, uses, comparison


def figures(directory, opened, buildings, labels, graph, doors, edges, spatial, maps):
    points = [tuple(map(float, v.point)) for v in graph.vertices]
    valid = [item for item in doors if item["status"] == "valid"]

    def base(title):
        fig, ax = plt.subplots(figsize=(11, 10))
        plot_background(ax, opened, buildings, labels)
        ax.set(xlim=(0, 100), ylim=(0, 100), title=title)
        return fig, ax

    fig, ax = base("Reconstructed dyad face-midpoint entrances")
    ax.scatter([float(Fraction(d["point"][0])) for d in valid],
               [float(Fraction(d["point"][1])) for d in valid], s=15, color="#e23b25", zorder=6)
    fig.tight_layout()
    save_figure(fig, directory / "01-doorways.png")

    fig, ax = base("Saved visibility graph and doorway connections")
    ax.add_collection(LineCollection([(points[e.start], points[e.end]) for e in graph.edges],
                                     colors="#587aa0", alpha=.08, linewidths=.25))
    links = [(tuple(float(Fraction(x)) for x in d["point"]), points[i])
             for d in valid for i in d["connections"]]
    ax.add_collection(LineCollection(links, colors="#d22e19", alpha=.07, linewidths=.3))
    fig.tight_layout()
    save_figure(fig, directory / "02-doorway-visibility.png")

    maximum = max((e["usage"] for e in edges), default=1)
    fig, ax = base("Doorway shortest-path obstacle-supported segments")
    collection = LineCollection([(points[e["start"]], points[e["end"]]) for e in edges],
                                cmap="plasma",
                                linewidths=[.5 + 3 * math.sqrt(e["usage"] / maximum) for e in edges])
    collection.set_array([e["usage"] for e in edges])
    ax.add_collection(collection)
    fig.colorbar(collection, ax=ax, label="Unordered journeys using segment")
    fig.tight_layout()
    save_figure(fig, directory / "03-doorway-tangents.png")

    fig, ax = base("Doorway vs spatial-and-boundary sampled segments")
    door_keys = {(e["start"], e["end"]) for e in edges}
    spatial_keys = {(e["start"], e["end"]) for e in spatial}
    for keys, color, label in ((door_keys & spatial_keys, "#7045a0", "both"),
                               (door_keys - spatial_keys, "#db4120", "doorway only"),
                               (spatial_keys - door_keys, "#268aaf", "sampled only")):
        ax.add_collection(LineCollection([(points[a], points[b]) for a, b in sorted(keys)],
                                         colors=color, linewidths=1.2, label=label))
    ax.legend()
    fig.tight_layout()
    save_figure(fig, directory / "04-distribution-comparison.png")

    fig, ax = base("Doorway segments absent from 29-line connectivity map")
    omitted = [e for e in edges if not set(e["candidates"]) & maps["connectivity 29"]]
    ax.add_collection(LineCollection([(points[e["start"]], points[e["end"]]) for e in omitted],
                                     colors="#dc321a",
                                     linewidths=[.5 + 3 * math.sqrt(e["usage"] / maximum)
                                                 for e in omitted]))
    fig.tight_layout()
    save_figure(fig, directory / "05-omitted-connectivity.png")


def main():
    parser = argparse.ArgumentParser()
    for name in ("archive", "snapshot", "data-dir", "selection-dir", "visibility-dir",
                 "structural-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    hashes = validate_inputs(args)
    structural_path = args.structural_dir / "results.json.gz"
    if sha256(structural_path) != STRUCTURAL_SHA:
        raise ValueError("Structural result differs from the recorded SHA-256")
    hashes["structural-results.json.gz"] = STRUCTURAL_SHA
    raw_graph = load_gzip(args.visibility_dir / "visibility-graph.json.gz")
    spatial = load_gzip(args.visibility_dir / "backbone-records.json.gz")
    snapshot = json.loads(args.snapshot.read_text())
    opened, buildings, _, _, paired = load_axial_snapshot(snapshot)
    labels = {int(k): int(v) for k, v in
              json.loads((args.data_dir / "settlement.json").read_text())["building_labels"].items()}
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    graph = graph_from_dict(raw_graph, accessible)
    if len(graph.vertices) != 462 or len(graph.edges) != 6532:
        raise ValueError("Saved visibility graph counts differ from the reference")
    clearance = IndexedClearance(LineClearance(accessible, occupied, original_obstacles=buildings.values()))
    for edge in graph.edges:
        if not clearance.permits(graph.vertices[edge.start].point, graph.vertices[edge.end].point):
            raise ValueError(f"Saved visibility edge fails exact clearance: {edge.start}, {edge.end}")
    aggregation = reconstruct(snapshot, opened, buildings, paired, labels)
    doors = doorway_records(aggregation.doors, opened, buildings, labels, graph, clearance)
    valid = [d for d in doors if d["status"] == "valid"]
    points = [(tuple(map(Fraction, d["point"])), d["component"]) for d in valid]
    print("doors", len(doors), "valid", len(valid), "pairs", len(valid) * (len(valid) - 1) // 2,
          "connections", sum(len(d["connections"]) for d in valid), flush=True)
    print("running deterministic pilot", flush=True)
    pilot_points = points[:min(8, len(points))]
    links = [d["connections"] for d in valid]
    pilot = routes_from_connections(graph, pilot_points, links[:len(pilot_points)], clearance)
    print("pilot ordered routes", len(pilot), flush=True)
    print("running all-to-all routes", flush=True)
    paths = routes_from_connections(graph, points, links, clearance)
    if any(path != paths[path["source"] * (len(points) - 1) + path["destination"]
                                - (path["destination"] > path["source"])] for path in pilot):
        raise ValueError("Pilot routes do not reproduce the all-to-all result")
    prepared = json.loads((args.data_dir / "prepared.json").read_text())
    candidates = []
    for record in prepared["records"]:
        entry = record["baseline"] or record["boundary"][0]
        interval = tuple(tuple(map(Fraction, entry[key])) for key in ("start", "end"))
        if not clearance.permits(*interval):
            raise ValueError("A certified candidate fails exact clearance")
        candidates.append(interval)
    if len(candidates) != 3214:
        raise ValueError("Preserved candidate count differs from the reference")
    candidate_tree = STRtree([_outward_bounds(a, b) for a, b in candidates])
    chosen_paths, edges, status, journeys, uses, comparison = analyse_paths(
        valid, paths, graph, candidates, candidate_tree, spatial["edges"], spatial["summary"])
    selection = json.loads((args.selection_dir / "selection-results.json").read_text())
    structural = load_gzip(structural_path)["maps"]
    maps = {"full pool": set(range(len(candidates))),
            "greedy 29": set(selection["greedy"]["selected"]),
            "connectivity 29": set(selection["connectivity"]["selected"]),
            "structural 66": set(structural["gain-0.25%-completed"]["selected"]),
            "structural 35": set(structural["gain-0.25%-reduced"]["selected"])}
    for edge in edges:
        edge["represented_in"] = {name: bool(set(edge["candidates"]) & selected)
                                  for name, selected in maps.items()}
    same = sum(1 for a, b in combinations(valid, 2) if a["building_id"] == b["building_id"])
    components = sum(1 for a, b in combinations(valid, 2) if a["component"] == b["component"])
    summary = {
        "building_count": len(buildings), "conceptual_doors": len(doors),
        "door_status": dict(Counter(d["status"] for d in doors)),
        "valid_doors": len(valid), "distinct_valid_positions": len(set(p[0] for p in points)),
        "buildings_without_conceptual_doors": sorted(set(buildings) - {d["building_id"] for d in doors}),
        "buildings_without_valid_doors": sorted(set(buildings) - {d["building_id"] for d in valid}),
        "same_building_pairs": same, "within_component_pairs": components,
        "journeys": journeys, "status": status, "used_segments": len(edges),
        "tangent_supported_segments": sum(e["tangent_supported"] for e in edges),
        "journey_edge_uses": uses, "comparison": comparison,
        "coverage": {name: summarize(edges, selected, uses) for name, selected in maps.items()},
        "elapsed_seconds": time.monotonic() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "metric_tolerance": 1e-10, "input_sha256": hashes,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    figures(args.output_dir, opened, buildings, labels, graph, doors, edges, spatial["edges"], maps)
    summary["elapsed_seconds_including_figures"] = time.monotonic() - started
    summary["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output = {"summary": summary, "doors": doors, "valid_door_ids": [d["door_id"] for d in valid],
              "paths": chosen_paths, "segments": edges, "pilot": pilot,
              "maps": {name: sorted(selected) for name, selected in maps.items()}}
    with gzip.open(args.output_dir / "doorway-results.json.gz", "xt") as file:
        json.dump(output, file, allow_nan=False)
    with (args.output_dir / "summary.json").open("x") as file:
        json.dump(summary, file, indent=2, allow_nan=False)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
