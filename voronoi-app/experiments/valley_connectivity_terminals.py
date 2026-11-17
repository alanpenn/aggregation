"""Evaluate sparse maps with a common, precomputed multi-attachment terminal set."""

import argparse
import gzip
import json
import math
import time
from fractions import Fraction
from pathlib import Path

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, SampleAttachment, _exact_point
from voronoi_app.axial_generator import _closed_routes
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import ExactCandidate, candidate_graph, closed_routes, region_coverage
from voronoi_app.experimental_angular_selection import angular_reference


def fixed_terminal_attachments(samples, lines, clearance, limit):
    """Fix up to ``limit`` nearest visible perpendicular attachments per sample."""
    if limit <= 0:
        raise ValueError("Attachment limit must be positive")
    result = []
    for number, sample in enumerate(samples):
        ranked = []
        for line in lines:
            vector = tuple(line.end[k] - line.start[k] for k in range(2))
            distance = sum(value * value for value in vector)
            t = sum((sample[k] - line.start[k]) * vector[k] for k in range(2)) / distance
            t = min(Fraction(1), max(Fraction(0), t))
            point = tuple(line.start[k] + t * vector[k] for k in range(2))
            squared = sum((point[k] - sample[k]) ** 2 for k in range(2))
            ranked.append((squared, line.line_id, point))
        chosen = []
        for _, line_id, point in sorted(ranked):
            if clearance.permits_exact(sample, point):
                chosen.append(SampleAttachment(sample, point, line_id))
                if len(chosen) == limit:
                    break
        if not chosen:
            raise ValueError(f"No fixed visible attachments for sample {number}")
        result.append(chosen)
    return result


def map_depths(lines, fixed, components):
    """Use only surviving fixed connectors; excluded lines make connectors unavailable."""
    retained = {line.line_id for line in lines}
    attachments, sample_ids, terminal_components = [], [], []
    for sample, options in enumerate(fixed):
        for attachment in options:
            if attachment.line_id in retained:
                attachments.append(attachment)
                sample_ids.append(sample)
                terminal_components.append(components[sample])
    pairs = {(i, j): math.inf for i in range(len(fixed)) for j in range(len(fixed))
             if i != j and components[i] == components[j]}
    if attachments:
        depths = angular_reference(lines, attachments, terminal_components).depths
        for (i, j), depth in depths.items():
            pair = (sample_ids[i], sample_ids[j])
            if pair in pairs and depth < pairs[pair]:
                pairs[pair] = depth
    available = len(set(sample_ids))
    return pairs, available


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--terminal-attachments", type=int, default=128)
    parser.add_argument("--reuse-terminals", action="store_true")
    args = parser.parse_args()
    data = json.loads((args.data_dir / "prepared.json").read_text())
    maps = json.loads((args.output_dir / "selection-results.json").read_text())
    live = json.loads((args.data_dir / "live-selection.json").read_text())
    opened, buildings, generated, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    live_lines = []
    for line in generated.candidate_lines:
        if line.line_id in live["selected"]:
            start, end = _exact_point(line.start), _exact_point(line.end)
            live_lines.append(ExactCandidate(len(lines) + line.line_id, start, end, start, end,
                                             "legacy-float"))
    samples = [tuple(map(Fraction, item["sample"])) for item in data["attachments"]]
    components = [item["component"] for item in data["attachments"]]
    started = time.monotonic()
    if args.reuse_terminals:
        with gzip.open(args.output_dir / "fixed-terminals.json.gz", "rt") as file:
            raw = json.load(file)
        fixed = [[SampleAttachment(tuple(map(Fraction, a["sample"])),
                                   tuple(map(Fraction, a["point"])), a["line_id"])
                  for a in options] for options in raw]
        if (len(fixed) != len(samples) or any(
                not options or any(a.sample != sample for a in options)
                for sample, options in zip(samples, fixed, strict=True))):
            raise ValueError("Saved fixed terminals do not match the sample set")
    else:
        fixed = fixed_terminal_attachments(samples, lines + live_lines, clearance,
                                           args.terminal_attachments)
        with gzip.open(args.output_dir / "fixed-terminals.json.gz", "xt") as file:
            json.dump([[{"sample": [str(v) for v in a.sample], "point": [str(v) for v in a.point],
                         "line_id": a.line_id} for a in options] for options in fixed], file)
    terminal_seconds = time.monotonic() - started
    print("fixed terminals", len(fixed), "options", sum(map(len, fixed)),
          "seconds", round(terminal_seconds, 2), flush=True)
    legacy_graph = candidate_graph(live_lines)
    regions = convex_regions(accessible)
    legacy = {
        "selected": [line.line_id - len(lines) for line in live_lines],
        "length": sum(line.length for line in live_lines),
        "coverage": len(set().union(*region_coverage(live_lines, regions))),
        "components": nx.number_connected_components(legacy_graph),
        "graph_edges": legacy_graph.number_of_edges(),
        "rings": len(closed_routes(live_lines, data["obstacles"])),
        "geos_rings": len(_closed_routes(
            [LineString((tuple(map(float, line.start)), tuple(map(float, line.end))))
             for line in live_lines], [Point(point) for point in data["obstacles"]]
        )),
        "exact_clearance_failures": sum(
            not clearance.permits_exact(line.start, line.end) for line in live_lines
        ),
        "seconds": live["seconds"],
    }
    results = {"legacy": legacy}
    all_depths = {}
    for name in ("legacy", "greedy", "greedy_exchange", "connectivity",
                 "connectivity_exchange"):
        selected = live_lines if name == "legacy" else [lines[i] for i in maps[name]["selected"]]
        started = time.monotonic()
        depths, available = map_depths(selected, fixed, components)
        finite = [depth for depth in depths.values() if math.isfinite(depth)]
        if name != "legacy":
            results[name] = dict(maps[name])
        results[name].update({
            "samples_available": available, "pairs": len(depths),
            "reachable_pairs": len(finite), "unreachable_pairs": len(depths) - len(finite),
            "mean_depth": sum(finite) / len(finite) if finite else None,
            "max_depth": max(finite) if finite else None,
            "evaluation_seconds": time.monotonic() - started,
        })
        all_depths[name] = depths
        print(name, "available", available, "reachable", len(finite),
              "mean", results[name]["mean_depth"], "max", results[name]["max_depth"], flush=True)
    common = set.intersection(*(set(pair for pair, value in depths.items() if math.isfinite(value))
                                for depths in all_depths.values()))
    for name, depths in all_depths.items():
        results[name]["common_pair_mean"] = (
            sum(depths[pair] for pair in common) / len(common) if common else None
        )
    results["metadata"] = {"samples": len(samples), "fixed_options": sum(map(len, fixed)),
                           "max_options_per_sample": args.terminal_attachments,
                           "terminal_preparation_seconds": terminal_seconds,
                           "common_reachable_pairs": len(common)}
    filename = "angular-results-recheck.json" if args.reuse_terminals else "angular-results.json"
    with (args.output_dir / filename).open("x") as file:
        json.dump(results, file, allow_nan=False)


if __name__ == "__main__":
    main()
