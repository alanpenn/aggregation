"""Reproduce the tangent-constrained Y seed-42 reduction experiment."""

import argparse
import gzip
import json
import time
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import networkx as nx
from shapely.ops import unary_union
from shapely.strtree import STRtree

from experiments.connectivity_backbone import load_gzip, map_summary, route_summary, validate_inputs
from experiments.shortest_path_backbone import matching_candidates, plot_background, save_figure
from experiments.shortest_path_visibility import sha256
from voronoi_app.angular import LineClearance, SampleAttachment
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import ExactCandidate, region_coverage
from voronoi_app.experimental_connectivity_selection import connectivity_order, structural_failure
from voronoi_app.experimental_structural_routes import evaluate_routes
from voronoi_app.experimental_tangent_reduction import (
    augment_weighted, minimum_cover, reduce_tangent, represented, tangent_masks, weight,
)
from voronoi_app.experimental_visibility import IndexedClearance, _outward_bounds


STRUCTURAL_SHA256 = "42a27781612440f6f20088b770f08e415d6ea2f4caf249befe751fbdb3743be5"


def tangent_ok(selected, masks, weights, required, minimum):
    coverage = represented(selected, masks)
    return coverage & required == required and weight(coverage, weights) >= minimum


def figures(output, opened, buildings, labels, lines, top, initial, selected, critical,
            samples, route_changes):
    fig, axes = plt.subplots(2, 2, figsize=(16, 15), sharex=True, sharey=True)
    panels = [
        ("Ten most-used tangent segments", None),
        ("All containing maximal candidates", {i for edge in top for i in edge["candidates"]}),
        ("Tangent-constrained reduced map", selected),
        ("Original lines removed during reduction", initial - selected),
    ]
    for ax, (title, ids) in zip(axes.flat, panels):
        plot_background(ax, opened, buildings, labels)
        if ids is None:
            segments = [[tuple(float(Fraction(x)) for x in edge[key])
                         for key in ("start_point", "end_point")] for edge in top]
            ax.add_collection(LineCollection(segments, colors="#d42a1d", linewidths=2))
        else:
            normal = ids - critical if title == "Tangent-constrained reduced map" else ids
            for subset, color, width in ((normal, "#198746", .8),
                                          (ids & critical if title == "Tangent-constrained reduced map"
                                           else set(), "#df5615", 1.8)):
                segments = [[tuple(map(float, lines[i].start)), tuple(map(float, lines[i].end))]
                            for i in sorted(subset)]
                ax.add_collection(LineCollection(segments, colors=color, linewidths=width, alpha=.85))
        ax.set(xlim=(0, 100), ylim=(0, 100), title=title)
    fig.suptitle("Y seed 42: orange lines are individually essential to the top-ten constraint")
    fig.tight_layout()
    save_figure(fig, output / "tangent-reduction-maps.png")

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharex=True, sharey=True)
    for ax, key, label in zip(axes, ("metric", "angular"),
                              ("Mean detour-ratio change", "Mean angular-depth change")):
        plot_background(ax, opened, buildings, labels)
        values = [item[key] for item in route_changes]
        limit = max((abs(value) for value in values if value is not None), default=0) or 1
        indices = [i for i, value in enumerate(values) if value is not None]
        scatter = ax.scatter([float(samples[i][0]) for i in indices],
                             [float(samples[i][1]) for i in indices],
                             c=[values[i] for i in indices], cmap="coolwarm", vmin=-limit,
                             vmax=limit, edgecolors="black", linewidths=.3, s=55, zorder=6)
        missing = [i for i, value in enumerate(values) if value is None]
        ax.scatter([float(samples[i][0]) for i in missing],
                   [float(samples[i][1]) for i in missing], marker="x", c="#333333",
                   s=45, zorder=6, label="no comparable occluded pairs")
        if missing:
            ax.legend(loc="lower right", fontsize=7)
        ax.set(xlim=(0, 100), ylim=(0, 100), title=label + "\n(reduced top-ten minus completed 66)")
        fig.colorbar(scatter, ax=ax, shrink=.75, label="negative = improvement")
    fig.tight_layout()
    save_figure(fig, output / "route-changes.png")


def main():
    parser = argparse.ArgumentParser()
    for name in ("archive", "snapshot", "data-dir", "selection-dir", "visibility-dir",
                 "structural-dir", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    hashes = validate_inputs(args)
    prior_path = args.structural_dir / "results.json.gz"
    if sha256(prior_path) != STRUCTURAL_SHA256:
        raise ValueError("Structural result differs from the recorded SHA-256")
    hashes["structural-results.json.gz"] = STRUCTURAL_SHA256
    prior = load_gzip(prior_path)
    data = json.loads((args.data_dir / "prepared.json").read_text())
    settlement = json.loads((args.data_dir / "settlement.json").read_text())
    tangent = load_gzip(args.visibility_dir / "backbone-records.json.gz")["edges"]
    tangent.sort(key=lambda edge: (-edge["usage"], edge["start"], edge["end"]))
    paths = load_gzip(args.visibility_dir / "shortest-paths.json.gz")
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
            raise ValueError(f"Candidate {i} fails exact clearance")
        lines.append(ExactCandidate(i, start, end, start, end, "preserved-unified-pool"))
    if len(lines) != 3214 or len(tangent) != 187:
        raise ValueError("Preserved input counts changed")
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from(raw_graph["edges"])
    if graph.number_of_edges() != 412106 or [graph.degree[i] for i in range(len(lines))] != raw_graph["degrees"]:
        raise ValueError("Saved graph and degrees do not match")
    covers = [set(values) for values in data["covers"]]
    regions = convex_regions(accessible)
    targets = set(regions)
    if len(targets) != 267 or region_coverage(lines, regions) != covers:
        raise ValueError("Recomputed region coverage differs from preserved data")
    groups = [{i for i, value in enumerate(data["components"]) if value == component}
              for component in range(len(set(data["components"])))]
    candidates = [(line.start, line.end) for line in lines]
    tree = STRtree([_outward_bounds(a, b) for a, b in candidates])
    for edge in tangent:
        start, end = (tuple(map(Fraction, edge[key])) for key in ("start_point", "end_point"))
        if matching_candidates(start, end, candidates, tree) != edge["candidates"]:
            raise ValueError("Saved tangent containment differs from exact geometry")
    masks = tangent_masks(len(lines), tangent)
    weights = [edge["usage"] for edge in tangent]
    if sum(weights) != 245126:
        raise ValueError("Saved tangent utilisation differs from the reference")
    order = connectivity_order(lines, graph)
    initial = set(prior["maps"]["gain-0.25%-completed"]["selected"])
    if len(initial) != 66 or structural_failure(lines, covers, targets, groups, graph,
                                                 data["obstacles"], initial):
        raise ValueError("Saved completed backbone is not the expected feasible map")
    required = (1 << 10) - 1
    global_cover = minimum_cover(masks, required)
    additions = minimum_cover(masks, required, represented(initial, masks))
    augmented = initial | set(additions)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    print("minimum top-ten cover", global_cover, "added", additions, flush=True)
    maps = {name: set(prior["maps"][name]["selected"]) for name in (
        "unified-greedy", "coverage-connectivity", "gain-0.25%-completed", "gain-0.25%-reduced")}
    maps["top-ten-augmented"] = augmented
    details = {}
    for name, start, required_bits, minimum in [
        ("top-ten", augmented, required, 0),
        *[(f"weighted-{percent}", None, 0, (sum(weights) * percent + 99) // 100)
          for percent in (25, 50, 75, 90)],
    ]:
        started = time.monotonic()
        if start is None:
            start, added = augment_weighted(initial, masks, weights, minimum, order)
        else:
            added = list(additions)
        selected, exchanges, attempts = reduce_tangent(
            lines, covers, targets, groups, graph, data["obstacles"], start, clearance,
            masks, weights, required_bits, minimum)
        critical = [i for i in sorted(selected)
                    if not tangent_ok(selected - {i}, masks, weights, required_bits, minimum)]
        if structural_failure(lines, covers, targets, groups, graph, data["obstacles"], selected):
            raise ValueError(f"{name} fails a structural constraint")
        if not tangent_ok(selected, masks, weights, required_bits, minimum):
            raise ValueError(f"{name} fails its tangent constraint")
        details[name] = {"added": added, "augmented": sorted(start), "selected": sorted(selected),
                         "tangent_essential": critical, "removed_original": sorted(initial - selected),
                         "exchanges": exchanges, "search": attempts,
                         "required_uses": minimum, "seconds": time.monotonic() - started}
        maps[name] = selected
        with (args.output_dir / f"{name}-stages.json").open("x") as file:
            json.dump(details[name], file, indent=2)
        print(name, "added", len(added), "final", len(selected), "uses",
              weight(represented(selected, masks), weights), "exchanges", len(exchanges), flush=True)
    top_support = []
    for index, edge in enumerate(tangent[:10]):
        choices = [{"id": i, "length": lines[i].length, "degree": graph.degree[i],
                    "regions": sorted(covers[i]), "already_selected": i in initial,
                    "start": [str(v) for v in lines[i].start],
                    "end": [str(v) for v in lines[i].end]} for i in edge["candidates"]]
        top_support.append({"rank": index + 1, "usage": edge["usage"],
                            "start_building_labels": edge["start_building_labels"],
                            "end_building_labels": edge["end_building_labels"],
                            "start_point": edge["start_point"], "end_point": edge["end_point"],
                            "candidates": choices})

    sample_indexes = prior["sample_indexes"]
    samples = [tuple(map(Fraction, paths["spatial_samples"][i]["point"])) for i in sample_indexes]
    components = [paths["spatial_samples"][i]["component"] for i in sample_indexes]
    fixed = [[SampleAttachment(samples[i], tuple(map(Fraction, item["point"])), item["line_id"])
              for item in options] for i, options in enumerate(prior["fixed_options"])]
    lookup = {(item["source"], item["destination"]): item for item in paths["spatial_paths"]}
    references = {(i, j): lookup[a, b] for i, a in enumerate(sample_indexes)
                  for j, b in enumerate(sample_indexes) if i != j}
    results, routes = {}, {}
    for name, selected in maps.items():
        pairs, network = evaluate_routes([lines[i] for i in sorted(selected)], fixed, components,
                                         references)
        if name in prior["route_pairs"] and pairs != prior["route_pairs"][name]:
            raise ValueError(f"Saved fixed-terminal route replay differs for {name}")
        results[name] = map_summary(selected, lines, covers, groups, graph, data["obstacles"], tangent)
        results[name]["routes"] = route_summary(pairs, network)
        routes[name] = pairs
        print(name, "routes", results[name]["routes"]["statuses"], flush=True)
    common = set.intersection(*(
        {(item["source"], item["destination"]) for item in pairs if item["status"] == "routed"}
        for pairs in routes.values()))
    for name, pairs in routes.items():
        shared = [item for item in pairs if (item["source"], item["destination"]) in common]
        results[name]["routes"]["common_occluded_count"] = len(shared)
        results[name]["routes"]["common_occluded_metric_detour"] = (
            sum(item["metric"] / item["reference"] for item in shared) / len(shared) if shared else None)
        results[name]["routes"]["common_occluded_angular"] = (
            sum(item["angular"] for item in shared) / len(shared) if shared else None)
    augmented_pairs = {(item["source"], item["destination"]): item
                       for item in routes["top-ten-augmented"]}
    ablations, ablation_routes = [], {}
    for candidate in additions:
        pairs, _ = evaluate_routes([lines[i] for i in sorted(augmented - {candidate})], fixed,
                                   components, references)
        ablation_routes[str(candidate)] = pairs
        metric_improved = angular_improved = newly_reachable = 0
        for item in pairs:
            augmented_item = augmented_pairs[item["source"], item["destination"]]
            reachable = item["status"] in ("direct", "routed")
            full_reachable = augmented_item["status"] in ("direct", "routed")
            if full_reachable and not reachable:
                newly_reachable += 1
            elif reachable and full_reachable:
                metric_improved += augmented_item["metric"] < item["metric"] - 1e-9
                angular_improved += augmented_item["angular"] < item["angular"] - 1e-9
        ablations.append({"candidate": candidate, "metric_improved_pairs": metric_improved,
                          "angular_improved_pairs": angular_improved,
                          "newly_reachable_pairs": newly_reachable})
        print("ablation", candidate, metric_improved, angular_improved, newly_reachable, flush=True)
    base = {(p["source"], p["destination"]): p for p in routes["gain-0.25%-completed"]}
    reduced = {(p["source"], p["destination"]): p for p in routes["top-ten"]}
    changes = []
    for i in range(len(samples)):
        pairs = [(base[key], reduced[key]) for key in base if key[0] == i
                 and base[key]["status"] == reduced[key]["status"] == "routed"]
        changes.append({"origin": i, "pairs": len(pairs),
                        "metric": sum(b["metric"] / b["reference"] - a["metric"] / a["reference"]
                                      for a, b in pairs) / len(pairs) if pairs else None,
                        "angular": sum(b["angular"] - a["angular"] for a, b in pairs) / len(pairs)
                        if pairs else None})
    output = {"input_sha256": hashes, "top_ten_support": top_support,
              "minimum_top_ten_cover": global_cover, "details": details, "maps": results,
              "sample_indexes": sample_indexes, "route_pairs": routes, "route_changes": changes,
              "ablations": ablations, "ablation_routes": ablation_routes}
    with gzip.open(args.output_dir / "results.json.gz", "xt") as file:
        json.dump(output, file, allow_nan=False)
    with (args.output_dir / "summary.json").open("x") as file:
        json.dump({key: value for key, value in output.items()
                   if key not in ("route_pairs", "ablation_routes")},
                  file, indent=2, allow_nan=False)
    labels = {int(k): int(v) for k, v in settlement["building_labels"].items()}
    figures(args.output_dir, opened, buildings, labels, lines, tangent[:10], initial,
            maps["top-ten"], set(details["top-ten"]["tangent_essential"]), samples, changes)
    print("saved results", args.output_dir, flush=True)


if __name__ == "__main__":
    main()
