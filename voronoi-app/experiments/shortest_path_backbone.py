"""Analyse obstacle-supported path segments against saved certified axial maps."""

import argparse
import gzip
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from shapely.ops import unary_union
from shapely.strtree import STRtree

from voronoi_app.angular import LineClearance, _direction, _on_segment
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.experimental_visibility import IndexedClearance, _outward_bounds
from experiments.shortest_path_routes import graph_from_dict
from experiments.shortest_path_visibility import exact_point, sha256


def path_segments(start, end, vertex_ids, graph, tree):
    """Split every path leg at any exact boundary vertex lying on it."""
    points = [start, *(graph.vertices[i].point for i in vertex_ids), end]
    segments = []
    for a, b in zip(points, points[1:]):
        if a == b:
            continue
        axis = 0 if a[0] != b[0] else 1
        direction = _direction(a, b)
        nodes = [int(i) for i in tree.query(_outward_bounds(a, b))
                 if _on_segment(graph.vertices[int(i)].point, a, b)]
        nodes.sort(key=lambda i: (graph.vertices[i].point[axis] - a[axis]) / direction[axis])
        segments.extend(tuple(sorted((left, right))) for left, right in zip(nodes, nodes[1:]))
    return segments


def matching_candidates(start, end, candidates, tree):
    return sorted(int(i) for i in tree.query(_outward_bounds(start, end))
                  if _on_segment(start, *candidates[int(i)])
                  and _on_segment(end, *candidates[int(i)]))


def summarize(backbone, selected, total_uses):
    covered = [item for item in backbone if any(i in selected for i in item["candidates"])]
    usage = sum(item["usage"] for item in covered)
    return {"covered_edges": len(covered), "edges": len(backbone),
            "edge_percent": 100 * len(covered) / len(backbone) if backbone else None,
            "covered_uses": usage, "uses": total_uses,
            "usage_percent": 100 * usage / total_uses if total_uses else None}


def plot_background(ax, opened, buildings, labels):
    for cell, polygon in {**opened, **buildings}.items():
        ax.fill(*polygon.exterior.xy, facecolor="#8c9097" if cell in buildings else "#f8f6ef",
                edgecolor="#e2e2de", linewidth=.25, zorder=0)
        if cell in labels:
            point = polygon.representative_point()
            ax.text(point.x, point.y, str(labels[cell]), fontsize=4.5, ha="center",
                    va="center", color="black", zorder=5)
    ax.set_aspect("equal")


def save_figure(fig, destination):
    with destination.open("xb") as file:
        fig.savefig(file, format="png", dpi=170)
    plt.close(fig)


def save_figures(directory, opened, buildings, labels, graph, backbone, maps, candidates):
    points = [tuple(map(float, vertex.point)) for vertex in graph.vertices]
    bounds = unary_union([*opened.values(), *buildings.values()]).bounds
    settings = ((bounds[0], bounds[2]), (bounds[1], bounds[3]))
    fig, ax = plt.subplots(figsize=(11, 10))
    plot_background(ax, opened, buildings, labels)
    lines = [(points[e.start], points[e.end]) for e in graph.edges]
    ax.add_collection(LineCollection(lines, colors="#5475a2", alpha=.13, linewidths=.25))
    ax.scatter(*zip(*points), s=2, color="#193f7c", zorder=4)
    ax.set(xlim=settings[0], ylim=settings[1], title="Exact-predicate boundary visibility graph")
    fig.tight_layout()
    save_figure(fig, directory / "visibility-network.png")

    max_usage = max((item["usage"] for item in backbone), default=1)
    fig, ax = plt.subplots(figsize=(11, 10))
    plot_background(ax, opened, buildings, labels)
    lines = [(points[item["start"]], points[item["end"]]) for item in backbone]
    counts = [item["usage"] for item in backbone]
    if lines:
        collection = LineCollection(lines, cmap="plasma",
                                    linewidths=[.5 + 3 * math.sqrt(c / max_usage) for c in counts],
                                    zorder=3)
        collection.set_array(counts)
        ax.add_collection(collection)
        fig.colorbar(collection, ax=ax, label="Sampled journeys using edge")
    ax.set(xlim=settings[0], ylim=settings[1], title="Obstacle-supported shortest-path backbone")
    fig.tight_layout()
    save_figure(fig, directory / "tangent-backbone.png")

    chosen = maps["connectivity"]
    missing = [item for item in backbone if not any(i in chosen for i in item["candidates"])]
    fig, ax = plt.subplots(figsize=(11, 10))
    plot_background(ax, opened, buildings, labels)
    chosen_lines = [[tuple(map(float, p)) for p in candidates[i]] for i in sorted(chosen)]
    ax.add_collection(LineCollection(chosen_lines, colors="#1a9140", linewidths=.8, alpha=.7))
    missing_lines = [(points[item["start"]], points[item["end"]]) for item in missing]
    if missing_lines:
        ax.add_collection(LineCollection(missing_lines, colors="#dd3d19",
                                         linewidths=[.5 + 3 * math.sqrt(item["usage"] / max_usage)
                                                     for item in missing], zorder=4))
    ax.set(xlim=settings[0], ylim=settings[1],
           title="Red: used obstacle segments absent from 29-line connectivity map")
    fig.tight_layout()
    save_figure(fig, directory / "missing-backbone.png")

    counts = [summarize(backbone, selected, sum(item["usage"] for item in backbone))
              for selected in maps.values()]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(maps))
    ax.bar([i - .18 for i in x],
           [item["edge_percent"] if item["edge_percent"] is not None else math.nan for item in counts],
           width=.36, label="Distinct edges")
    ax.bar([i + .18 for i in x],
           [item["usage_percent"] if item["usage_percent"] is not None else math.nan for item in counts],
           width=.36, label="Journey-edge uses")
    ax.set_xticks(list(x), list(maps), rotation=25, ha="right")
    ax.set(ylim=(0, 100), ylabel="Geometrically contained (%)",
           title="Coverage of used obstacle-supported segments")
    ax.legend()
    fig.tight_layout()
    save_figure(fig, directory / "axial-tangent-coverage.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.output_dir / "visibility-graph.json.gz", "rt") as file:
        raw_graph = json.load(file)
    with gzip.open(args.output_dir / "shortest-paths.json.gz", "rt") as file:
        paths = json.load(file)
    for suffix, path in (
        ("home/Downloads/axial-diagnostic.json", args.snapshot),
        ("valley42-exchange-2026-11-17/prepared.json", args.data_dir / "prepared.json"),
        ("valley42-exchange-2026-11-17/settlement.json", args.data_dir / "settlement.json"),
        ("valley-connectivity-2026-11-17/selection-results.json",
         args.selection_dir / "selection-results.json"),
        ("valley-connectivity-2026-11-17/targeted-evaluated.json",
         args.selection_dir / "targeted-evaluated.json"),
    ):
        if sha256(path) != raw_graph["input_sha256"][suffix]:
            raise ValueError(f"Preserved input changed after graph construction: {path}")
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = IndexedClearance(LineClearance(accessible, occupied, original_obstacles=buildings.values()))
    graph = graph_from_dict(raw_graph, accessible)
    vertex_tree = STRtree([_outward_bounds(v.point, v.point) for v in graph.vertices])
    graph_edges = {(e.start, e.end): e for e in graph.edges}
    data = json.loads((args.data_dir / "prepared.json").read_text())
    candidates = []
    for record in data["records"]:
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        if not clearance.permits(start, end):
            raise ValueError("A preserved candidate fails exact clearance")
        candidates.append((start, end))
    if len(candidates) != len(set(tuple(sorted(interval)) for interval in candidates)):
        raise ValueError("Preserved candidate pool contains duplicate intervals")
    candidate_tree = STRtree([_outward_bounds(a, b) for a, b in candidates])
    selection = json.loads((args.selection_dir / "selection-results.json").read_text())
    targeted = json.loads((args.selection_dir / "targeted-evaluated.json").read_text())
    settlement = json.loads((args.data_dir / "settlement.json").read_text())
    labels = {int(k): int(v) for k, v in settlement["building_labels"].items()}
    maps = {"full pool": set(range(len(candidates))),
            "greedy 29": set(selection["greedy"]["selected"]),
            "connectivity": set(selection["connectivity"]["selected"]),
            "connectivity 24": set(selection["connectivity_exchange"]["selected"]),
            "targeted 23": set(targeted["connectivity_exchange:1391"]["selected"])}
    if any(not selected <= set(range(len(candidates))) for selected in maps.values()):
        raise ValueError("A saved selection references an absent certified candidate")
    usage = {}
    status = Counter()
    total_journeys = 0
    for kind, source_samples, destination_samples, records in (
        ("spatial", paths["spatial_samples"], paths["spatial_samples"], paths["spatial_paths"]),
        ("boundary", paths["boundary_origins"], paths["boundary_destinations"], paths["boundary_paths"]),
    ):
        for result in records:
            status[f"{kind}:{result['status']}"] += 1
            if result["status"] not in ("direct", "occluded"):
                continue
            total_journeys += 1
            if result["near_tie"]:
                status[f"{kind}:near_tie"] += 1
            start = tuple(map(Fraction, source_samples[result["source"]]["point"]))
            end = tuple(map(Fraction, destination_samples[result["destination"]]["point"]))
            segments = set(path_segments(start, end, result["vertices"], graph, vertex_tree))
            for key in segments:
                edge = graph_edges.get(key)
                if edge is None:
                    raise ValueError(f"Noded shortest-path segment missing from visibility graph: {key}")
                if not graph.vertices[key[0]].buildings or not graph.vertices[key[1]].buildings:
                    continue
                entry = usage.setdefault(key, {"start": key[0], "end": key[1],
                    "usage": 0, "total_journey_length": 0.0, "pairs": []})
                entry["usage"] += 1
                entry["total_journey_length"] += result["length"]
                entry["pairs"].append([kind, result["source"], result["destination"]])
    backbone = []
    for key, entry in sorted(usage.items()):
        edge = graph_edges[key]
        start, end = (graph.vertices[i].point for i in key)
        entry.update({"start_point": exact_point(start), "end_point": exact_point(end),
                      "start_buildings": graph.vertices[key[0]].buildings,
                      "end_buildings": graph.vertices[key[1]].buildings,
                      "start_building_labels": sorted(
                          {labels[cell] for cell, _ in graph.vertices[key[0]].buildings}),
                      "end_building_labels": sorted(
                          {labels[cell] for cell, _ in graph.vertices[key[1]].buildings}),
                      "length": edge.length, "boundary_following": edge.boundary_following,
                      "tangent_supported": edge.tangent_supported,
                      "journey_share": entry["usage"] / total_journeys if total_journeys else None,
                      "traversed_length": entry["usage"] * edge.length,
                      "candidates": matching_candidates(start, end, candidates, candidate_tree)})
        backbone.append(entry)
    backbone.sort(key=lambda item: (-item["usage"], item["start"], item["end"]))
    tangent = [item for item in backbone if item["tangent_supported"]]
    total_uses = sum(item["usage"] for item in backbone)
    tangent_uses = sum(item["usage"] for item in tangent)
    ranked_usage = sorted((item["usage"] for item in backbone), reverse=True)
    summary = {"status": dict(status), "journeys": total_journeys,
               "backbone_edges": len(backbone), "backbone_uses": total_uses,
               "mutual_tangent_edges": len(tangent), "mutual_tangent_uses": tangent_uses,
               "utilization_histogram": dict(sorted(Counter(item["usage"] for item in backbone).items())),
               "top_10_use_share_percent": (
                   100 * sum(ranked_usage[:10]) / total_uses if total_uses else None
               ),
               "max_edge_uses": ranked_usage[0] if ranked_usage else 0,
               "all_coverage": {name: summarize(backbone, selected, total_uses)
                                for name, selected in maps.items()},
               "tangent_coverage": {name: summarize(tangent, selected, tangent_uses)
                                    for name, selected in maps.items()}}
    with gzip.open(args.output_dir / "backbone-records.json.gz", "xt") as file:
        json.dump({"summary": summary, "edges": backbone}, file, allow_nan=False)
    with (args.output_dir / "backbone-summary.json").open("x") as file:
        json.dump(summary, file, indent=2, allow_nan=False)
    save_figures(args.output_dir, opened, buildings, labels, graph, backbone, maps, candidates)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
