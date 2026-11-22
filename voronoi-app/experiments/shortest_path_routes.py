"""Sample fixed Y-settlement terminals and compute metric visibility paths."""

import argparse
import gzip
import json
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from voronoi_app.angular import LineClearance, _exact_point, _inside_prepared, _intersections, _prepare_polygon
from voronoi_app.axial_generator import _parts
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.experimental_visibility import (
    IndexedClearance, VisibilityEdge, VisibilityGraph, VisibilityVertex, _outward_bounds,
    component_for_point, shortest_paths,
)
from experiments.shortest_path_visibility import exact_point, sha256


def graph_from_dict(data, accessible):
    vertices = tuple(VisibilityVertex(tuple(map(Fraction, v["point"])), v["component"],
                                      tuple(tuple(ref) for ref in v["buildings"]))
                     for v in data["vertices"])
    edges = tuple(VisibilityEdge(e["start"], e["end"], e["length"],
                                 e["boundary_following"], e["tangent_supported"])
                  for e in data["edges"])
    components = tuple(part for part in _parts(accessible) if isinstance(part, Polygon))
    if len(components) != data["component_count"]:
        raise ValueError("Accessible components changed since graph construction")
    return VisibilityGraph(vertices, edges, components,
                           tuple(tuple(map(Fraction, p)) for p in data["ambiguous_vertices"]),
                           data["blocked_edges"], data["ambiguous_edges"])


def grid_samples(accessible, graph, clearance, resolution=16):
    bounds = tuple(Fraction.from_float(value) for value in accessible.bounds)
    samples = []
    skipped = 0
    prepared = [_prepare_polygon(polygon) for polygon in graph.components]
    for x in range(resolution):
        for y in range(resolution):
            point = (bounds[0] + Fraction(2 * x + 1, 2 * resolution) * (bounds[2] - bounds[0]),
                     bounds[1] + Fraction(2 * y + 1, 2 * resolution) * (bounds[3] - bounds[1]))
            matches = [i for i, rings in enumerate(prepared) if _inside_prepared(point, rings)]
            if len(matches) == 1 and clearance.permits(point, point):
                samples.append({"point": exact_point(point), "component": matches[0],
                                "grid": [x, y]})
            else:
                skipped += 1
    for component, polygon in enumerate(graph.components):
        if not any(item["component"] == component for item in samples):
            representative = _exact_point(polygon.representative_point().coords[0])
            if not _inside_prepared(representative, prepared[component]) or not clearance.permits(
                representative, representative
            ):
                raise ValueError(f"No certified spatial sample in component {component}")
            samples.append({"point": exact_point(representative), "component": component,
                            "grid": None})
    return samples, skipped


def boundary_samples(buildings, labels, graph, clearance, limit=32):
    if limit <= 0:
        raise ValueError("Boundary interval sample limit must be positive")
    edges = []
    for component, polygon in enumerate(graph.components):
        for ring in (polygon.exterior, *polygon.interiors):
            points = tuple(map(_exact_point, ring.coords))
            edges.extend((component, a, b) for a, b in zip(points, points[1:]) if a != b)
    tree = STRtree([_outward_bounds(a, b) for _, a, b in edges])
    intervals = defaultdict(set)
    for building, polygon in sorted(buildings.items()):
        points = tuple(map(_exact_point, polygon.exterior.coords))
        for edge_index, (a, b) in enumerate(zip(points, points[1:])):
            for raw in tree.query(_outward_bounds(a, b)):
                component, c, d = edges[int(raw)]
                shared = sorted(_intersections(a, b, c, d))
                if len(shared) >= 2 and shared[0] != shared[-1]:
                    intervals[(component, shared[0], shared[-1])].add(
                        (int(building), int(labels[building]), edge_index)
                    )
    ordered = sorted(intervals)
    if not ordered:
        raise ValueError("No accessible occupied-building boundary intervals were found")
    chosen = [ordered[i * len(ordered) // min(limit, len(ordered))]
              for i in range(min(limit, len(ordered)))]
    origins, destinations = [], []
    for component, start, end in chosen:
        for numerator, target in ((1, origins), (2, destinations)):
            point = tuple(start[k] + Fraction(numerator, 3) * (end[k] - start[k])
                          for k in range(2))
            if not clearance.permits(point, point):
                raise ValueError("A boundary terminal fails exact point clearance")
            if component_for_point(point, graph.components) != component:
                raise ValueError("A boundary terminal has an ambiguous component")
            target.append({"point": exact_point(point), "component": component,
                           "interval": [exact_point(start), exact_point(end)],
                           "building_faces": sorted(intervals[(component, start, end)])})
    return origins, destinations, len(ordered)


def terminal_pairs(samples):
    return [(tuple(map(Fraction, item["point"])), item["component"]) for item in samples]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--boundary-intervals", type=int, default=32)
    parser.add_argument("--metric-tolerance", type=float, default=1e-10)
    args = parser.parse_args()
    with gzip.open(args.output_dir / "visibility-graph.json.gz", "rt") as file:
        data = json.load(file)
    if sha256(args.snapshot) != data["input_sha256"]["home/Downloads/axial-diagnostic.json"]:
        raise ValueError("Snapshot differs from graph construction input")
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    graph = graph_from_dict(data, accessible)
    indexed = IndexedClearance(LineClearance(accessible, occupied, original_obstacles=buildings.values()))
    settlement = json.loads((args.data_dir / "settlement.json").read_text())
    if sha256(args.data_dir / "settlement.json") != data["input_sha256"]["valley42-exchange-2026-11-17/settlement.json"]:
        raise ValueError("Settlement labels differ from graph construction input")
    labels = {int(k): int(v) for k, v in settlement["building_labels"].items()}
    spatial, skipped = grid_samples(accessible, graph, indexed)
    origins, destinations, eligible = boundary_samples(
        buildings, labels, graph, indexed, limit=args.boundary_intervals
    )
    print("spatial", len(spatial), "skipped grid", skipped, "boundary pairs",
          len(origins), "of", eligible, "eligible intervals", flush=True)
    started = time.monotonic()
    spatial_pairs = terminal_pairs(spatial)
    spatial_paths = shortest_paths(graph, spatial_pairs, spatial_pairs, indexed, same_set=True,
                                   tolerance=args.metric_tolerance)
    print("spatial paths", len(spatial_paths), "seconds", round(time.monotonic() - started, 2),
          flush=True)
    started = time.monotonic()
    boundary_paths = shortest_paths(graph, terminal_pairs(origins), terminal_pairs(destinations),
                                    indexed, tolerance=args.metric_tolerance)
    output = {"spatial_samples": spatial, "boundary_origins": origins,
              "boundary_destinations": destinations, "spatial_paths": spatial_paths,
              "boundary_paths": boundary_paths, "grid_resolution": 16,
              "skipped_grid_points": skipped, "eligible_boundary_intervals": eligible,
              "sampled_boundary_intervals": len(origins), "metric_tolerance": args.metric_tolerance,
              "boundary_routing_seconds": time.monotonic() - started}
    with gzip.open(args.output_dir / "shortest-paths.json.gz", "xt") as file:
        json.dump(output, file, allow_nan=False)
    print("boundary paths", len(boundary_paths), "seconds",
          round(output["boundary_routing_seconds"], 2), flush=True)


if __name__ == "__main__":
    main()
