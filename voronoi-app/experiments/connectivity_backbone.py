"""Reproduce the connectivity-first structural-backbone comparison."""

import argparse
import gzip
import json
import math
import tarfile
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import networkx as nx
from shapely.ops import unary_union
from shapely.strtree import STRtree

from experiments.shortest_path_backbone import matching_candidates, plot_background, save_figure, summarize
from experiments.shortest_path_visibility import sha256, verified_inputs
from experiments.valley_connectivity_terminals import fixed_terminal_attachments
from voronoi_app.angular import LineClearance, _intersections
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import ExactCandidate, closed_routes, region_coverage
from voronoi_app.experimental_connectivity_selection import connectivity_order, structural_failure
from voronoi_app.experimental_structural_backbone import (
    complete_coverage, footprint, grow_backbone, reach_masks, reduce_selection,
)
from voronoi_app.experimental_structural_routes import evaluate_routes
from voronoi_app.experimental_visibility import IndexedClearance, _outward_bounds


VISIBILITY_HASHES = {
    "backbone-records.json.gz": "15c3e1d1f6f5b8fd9cfbf63d6a44abbfcaf1e69438f7ea2b70d0059b18522fba",
    "shortest-paths.json.gz": "2879c6530d861edd4d3cd0f3c8a4d34cefecc420cbc62f08b9f6e975d8f82973",
    "visibility-graph.json.gz": "31749ca148830cf25b15149fb52d020da2d77a5c928d72c11df31a0b7047445e",
}


def load_gzip(path):
    with gzip.open(path, "rt") as file:
        return json.load(file)


def validate_inputs(args):
    hashes = verified_inputs(args.archive, args.snapshot, args.data_dir, args.selection_dir)
    graph_path = args.selection_dir / "candidate-graph.json.gz"
    suffix = "valley-connectivity-2026-11-17/candidate-graph.json.gz"
    with tarfile.open(args.archive, "r:gz") as archive:
        manifest_file = archive.extractfile("MANIFEST.json")
        if manifest_file is None:
            raise ValueError("Research archive has no manifest")
        manifest = json.load(manifest_file)["files"]
    matches = [item for item in manifest if item["path"].endswith(suffix)]
    if len(matches) != 1 or sha256(graph_path) != matches[0]["sha256"] or (
        graph_path.stat().st_size != matches[0]["bytes"]
    ):
        raise ValueError("Saved candidate graph differs from its archive manifest")
    hashes[suffix] = sha256(graph_path)
    for name, expected in VISIBILITY_HASHES.items():
        path = args.visibility_dir / name
        if sha256(path) != expected:
            raise ValueError(f"Saved independent visibility result has changed: {path}")
        hashes[name] = expected
    raw_visibility = load_gzip(args.visibility_dir / "visibility-graph.json.gz")
    for key, value in raw_visibility["input_sha256"].items():
        if key in hashes and hashes[key] != value:
            raise ValueError(f"Visibility results used a different input: {key}")
    return hashes


def map_summary(selected, lines, covers, groups, graph, obstacles, tangent):
    selected = set(selected)
    covered = set().union(*(covers[i] for i in selected)) if selected else set()
    components = [nx.number_connected_components(graph.subgraph(selected & group))
                  if selected & group else 0 for group in groups]
    tangent_stats = summarize(tangent, selected, sum(item["usage"] for item in tangent))
    top = sorted(tangent, key=lambda item: (-item["usage"], item["start"], item["end"]))[:10]
    return {"selected": sorted(selected), "lines": len(selected),
            "length": sum(lines[i].length for i in selected),
            "coverage": len(covered), "components_per_accessible_component": components,
            "intersection_edges": graph.subgraph(selected).number_of_edges(),
            "rings": len(closed_routes([lines[i] for i in sorted(selected)], obstacles)),
            "tangent": tangent_stats,
            "top_ten_contained": sum(any(i in selected for i in edge["candidates"]) for edge in top)}


def route_summary(pairs, network):
    counts = Counter(pair["status"] for pair in pairs)
    for status in ("direct", "routed", "attachment-failure", "network-disconnected",
                   "different-component"):
        counts.setdefault(status, 0)
    reachable = [pair for pair in pairs if pair["status"] in ("direct", "routed")]
    ratios = [pair["metric"] / pair["reference"] for pair in reachable if pair["reference"]]
    angular = [pair["angular"] for pair in reachable]
    return {"statuses": dict(counts), "pairs": len(pairs),
            "mean_metric_detour": sum(ratios) / len(ratios) if ratios else None,
            "max_metric_detour": max(ratios) if ratios else None,
            "mean_angular": sum(angular) / len(angular) if angular else None,
            "max_angular": max(angular) if angular else None, **network}


def plot_results(output, opened, buildings, labels, lines, order, tangent, maps, results):
    fig, axes = plt.subplots(2, 3, figsize=(19, 13), sharex=True, sharey=True)
    primary = maps["gain-0.5%-backbone"]
    panels = [
        ("20 highest fixed full-pool degrees", set(order[:20]), set()),
        ("Structural backbone", primary, set()),
        ("After coverage and repair", maps["gain-0.5%-completed"], primary),
        ("After bounded reductions", maps["gain-0.5%-reduced"], primary),
    ]
    for ax, (title, selected, backbone) in zip(axes.flat, panels):
        plot_background(ax, opened, buildings, labels)
        for ids, color in ((selected & backbone if backbone else selected, "#16853c"),
                           (selected - backbone if backbone else set(), "#df8317")):
            segments = [[tuple(map(float, lines[i].start)), tuple(map(float, lines[i].end))]
                        for i in sorted(ids)]
            ax.add_collection(LineCollection(segments, colors=color, linewidths=1, alpha=.8))
        ax.set(xlim=(0, 100), ylim=(0, 100), title=f"{title} ({len(selected)})")
    ax = axes.flat[4]
    plot_background(ax, opened, buildings, labels)
    selected = maps["gain-0.5%-reduced"]
    max_use = max(edge["usage"] for edge in tangent)
    for represented, color in ((True, "#148246"), (False, "#d8371b")):
        items = [edge for edge in tangent
                 if any(i in selected for i in edge["candidates"]) == represented]
        segments = [[tuple(float(Fraction(x)) for x in edge[key])
                     for key in ("start_point", "end_point")] for edge in items]
        ax.add_collection(LineCollection(segments, colors=color,
            linewidths=[.4 + 3 * math.sqrt(edge["usage"] / max_use) for edge in items]))
    ax.set(xlim=(0, 100), ylim=(0, 100),
           title="Used tangents: represented green, omitted red")
    axes.flat[5].axis("off")
    fig.suptitle("Y seed 42: green backbone; orange additions or replacement lines")
    fig.tight_layout()
    save_figure(fig, output / "structural-maps.png")

    names = list(results)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    values = [
        ("Selected lines", [results[n]["lines"] for n in names]),
        ("Tangent journey-edge uses (%)",
         [results[n]["tangent"]["usage_percent"] for n in names]),
        ("Mean metric detour", [results[n]["routes"]["common_occluded_metric_detour"] for n in names]),
        ("Mean angular depth", [results[n]["routes"]["common_occluded_angular"] for n in names]),
    ]
    for ax, (title, values_for_axis) in zip(axes.flat, values):
        ax.bar(range(len(names)), [v if v is not None else math.nan for v in values_for_axis])
        ax.set_xticks(range(len(names)), names, rotation=45, ha="right", fontsize=7)
        ax.set_title(title + (" (same reachable occluded pairs)" if "Mean " in title else ""))
    fig.tight_layout()
    save_figure(fig, output / "comparison.png")


def main():
    parser = argparse.ArgumentParser()
    for name in ("archive", "snapshot", "data-dir", "selection-dir", "visibility-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    hashes = validate_inputs(args)
    data = json.loads((args.data_dir / "prepared.json").read_text())
    selections = json.loads((args.selection_dir / "selection-results.json").read_text())
    settlement = json.loads((args.data_dir / "settlement.json").read_text())
    paths = load_gzip(args.visibility_dir / "shortest-paths.json.gz")
    tangent = load_gzip(args.visibility_dir / "backbone-records.json.gz")["edges"]
    raw_graph = load_gzip(args.selection_dir / "candidate-graph.json.gz")
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    indexed = IndexedClearance(clearance)
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        if not indexed.permits(start, end):
            raise ValueError(f"Saved candidate {i} fails exact clearance")
        lines.append(ExactCandidate(i, start, end, start, end, "preserved-unified-pool"))
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from(raw_graph["edges"])
    if (len(lines) != 3214 or graph.number_of_edges() != 412106
            or list(dict(graph.degree()).values()) != raw_graph["degrees"]):
        raise ValueError("Saved full-pool graph does not match the candidate pool")
    groups = [{i for i, value in enumerate(data["components"]) if value == component}
              for component in range(len(set(data["components"])))]
    covers = [set(values) for values in data["covers"]]
    regions = convex_regions(accessible)
    targets = set(regions)
    if len(targets) != 267 or region_coverage(lines, regions) != covers:
        raise ValueError("Saved and exact recomputed convex-region coverage differ")
    candidates = [(line.start, line.end) for line in lines]
    tree = STRtree([_outward_bounds(a, b) for a, b in candidates])
    if len(tangent) != 187:
        raise ValueError("Independent tangent data do not contain 187 segments")
    for edge in tangent:
        a, b = (tuple(map(Fraction, edge[key])) for key in ("start_point", "end_point"))
        if matching_candidates(a, b, candidates, tree) != edge["candidates"]:
            raise ValueError("Saved tangent-to-candidate containment no longer matches")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    order = connectivity_order(lines, graph)
    masks = reach_masks(graph, len(lines))
    maps = {"unified-greedy": set(selections["greedy"]["selected"]),
            "coverage-connectivity": set(selections["connectivity"]["selected"])}
    details = {}
    for label, fraction in (("gain-1%", .01), ("gain-0.5%", .005), ("gain-0.25%", .0025)):
        started = time.monotonic()
        threshold = math.ceil(fraction * len(lines))
        backbone, reasons = grow_backbone(lines, graph, groups, data["obstacles"],
                                           set(data["ring_candidates"]), threshold)
        print(label, "backbone", len(backbone), "seconds", round(time.monotonic() - started, 2),
              flush=True)
        required = footprint(lines, masks, backbone)
        completed, added, repairs, repair_stats = complete_coverage(
            lines, covers, targets, groups, graph, data["obstacles"], backbone,
            set(data["ring_candidates"]))
        print(label, "completed", len(completed), "coverage additions", len(added),
              "repairs", len(repairs), flush=True)
        reduced, exchanges, attempts = reduce_selection(
            lines, covers, targets, groups, graph, data["obstacles"], completed, clearance,
            required, addition_limit=30, pair_limit=10, removal_limit=400, check_limit=30, rounds=5)
        print(label, "reduced", len(reduced), "exchanges", len(exchanges), flush=True)
        maps.update({f"{label}-backbone": backbone, f"{label}-completed": completed,
                     f"{label}-reduced": reduced})
        details[label] = {"minimum_new_network_neighbors": threshold,
                          "reasons": {str(k): v for k, v in reasons.items()},
                          "backbone_reach": required.reach.bit_count(),
                          "backbone_directions": sorted(required.directions),
                          "backbone_bounds": [str(v) for v in required.bounds],
                          "coverage_additions": added, "repair_lines": repairs,
                          "repair": repair_stats, "exchanges": exchanges,
                          "search": attempts, "seconds": time.monotonic() - started}
        with (args.output_dir / f"{label}-stages.json").open("x") as file:
            json.dump({"backbone": sorted(backbone), "completed": sorted(completed),
                       "reduced": sorted(reduced), "details": details[label]}, file,
                      indent=2, allow_nan=False)
        for name in (f"{label}-completed", f"{label}-reduced"):
            failure = structural_failure(lines, covers, targets, groups, graph, data["obstacles"],
                                         maps[name])
            if failure:
                raise ValueError(f"{name} fails {failure}")
    sample_indexes = [i * len(paths["spatial_samples"]) // 32 for i in range(32)]
    samples = [tuple(map(Fraction, paths["spatial_samples"][i]["point"])) for i in sample_indexes]
    components = [paths["spatial_samples"][i]["component"] for i in sample_indexes]
    lookup = {(item["source"], item["destination"]): item for item in paths["spatial_paths"]}
    references = {(i, j): lookup[a, b] for i, a in enumerate(sample_indexes)
                  for j, b in enumerate(sample_indexes) if i != j}
    fixed = fixed_terminal_attachments(samples, lines, clearance, limit=128)
    print("fixed terminals", len(fixed), "options", sum(map(len, fixed)), flush=True)
    results, route_records, cached = {}, {}, {}
    for name, selected in maps.items():
        key = frozenset(selected)
        if key not in cached:
            pairs, network = evaluate_routes([lines[i] for i in sorted(selected)], fixed,
                                             components, references)
            cached[key] = pairs, network
        pairs, network = cached[key]
        results[name] = map_summary(selected, lines, covers, groups, graph, data["obstacles"], tangent)
        results[name]["routes"] = route_summary(pairs, network)
        route_records[name] = pairs
        print(name, "lines", len(selected), "routes", results[name]["routes"]["statuses"],
              "tangent", results[name]["tangent"]["usage_percent"], flush=True)
    common = set.intersection(*(
        {(item["source"], item["destination"]) for item in pairs
         if item["status"] in ("direct", "routed")} for pairs in route_records.values()
    ))
    for name, pairs in route_records.items():
        shared = [item for item in pairs if (item["source"], item["destination"]) in common]
        occluded = [item for item in shared if item["status"] == "routed"]
        results[name]["routes"]["common_metric_detour"] = (
            sum(item["metric"] / item["reference"] for item in shared) / len(shared)
            if shared else None)
        results[name]["routes"]["common_angular"] = (
            sum(item["angular"] for item in shared) / len(shared) if shared else None)
        results[name]["routes"]["common_pair_count"] = len(shared)
        results[name]["routes"]["common_occluded_count"] = len(occluded)
        results[name]["routes"]["common_occluded_metric_detour"] = (
            sum(item["metric"] / item["reference"] for item in occluded) / len(occluded)
            if occluded else None)
        results[name]["routes"]["common_occluded_angular"] = (
            sum(item["angular"] for item in occluded) / len(occluded) if occluded else None)
    intersection_cache = {}
    intersection_provenance = {}
    for name, selected in maps.items():
        records = []
        for a, b in sorted(tuple(sorted(pair)) for pair in graph.subgraph(selected).edges):
            if (a, b) not in intersection_cache:
                points = _intersections(lines[a].start, lines[a].end, lines[b].start, lines[b].end)
                if not points:
                    raise ValueError(f"Saved graph intersection is absent for {(a, b)}")
                intersection_cache[a, b] = [[str(value) for value in p] for p in sorted(points)]
            records.append({"candidates": [a, b], "points": intersection_cache[a, b]})
        intersection_provenance[name] = records
    output = {"input_sha256": hashes, "methods": details, "maps": results,
              "candidate_intervals": [
                  [[str(value) for value in line.start], [str(value) for value in line.end]]
                  for line in lines],
              "intersection_provenance": intersection_provenance,
              "sample_indexes": sample_indexes, "fixed_options": [
                  [{"line_id": a.line_id, "point": [str(v) for v in a.point]} for a in options]
                  for options in fixed],
              "route_pairs": route_records}
    with gzip.open(args.output_dir / "results.json.gz", "xt") as file:
        json.dump(output, file, allow_nan=False)
    with (args.output_dir / "summary.json").open("x") as file:
        json.dump({"methods": details, "maps": results, "sample_indexes": sample_indexes},
                  file, indent=2, allow_nan=False)
    labels = {int(k): int(v) for k, v in settlement["building_labels"].items()}
    plot_results(args.output_dir, opened, buildings, labels, lines, order, tangent, maps, results)
    print("saved results", args.output_dir, flush=True)


if __name__ == "__main__":
    main()
