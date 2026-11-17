"""Report and plot certified pair candidates and bounded Valley exchanges."""

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from shapely.ops import unary_union

from voronoi_app.angular import (
    LineClearance, SampleAttachment, _exact_point, _intersections, _on_segment,
)
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.exact_axial import ExactCandidate, candidate_graph
from voronoi_app.experimental_angular_selection import angular_reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    state = args.data_dir
    data = json.loads((state / "prepared.json").read_text())
    result = json.loads((state / "exchange-result.json").read_text())
    reference = json.loads((state / "reference.json").read_text())
    settlement = json.loads((state / "settlement.json").read_text())
    live_selection = json.loads((state / "live-selection.json").read_text())
    snapshot = json.loads(args.snapshot.read_text())
    opened, buildings, generated, _, _ = load_axial_snapshot(snapshot)
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    labels = {int(cell): int(label) for cell, label in settlement["building_labels"].items()}
    cells = {label: cell for cell, label in labels.items()}
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    live_by_id = {line.line_id: line for line in generated.candidate_lines}
    live_selected = set(live_selection["selected"])
    building_edges = {}
    for cell, polygon in buildings.items():
        points = list(map(_exact_point, polygon.exterior.coords))
        building_edges[cell] = list(zip(points, points[1:]))
    pair_data = {}
    for pair, identifiers in result["pair_candidates"].items():
        entries = []
        for i in identifiers:
            line = lines[i]
            live_matches = []
            for candidate in generated.candidate_lines:
                for support in candidate.attributes.get("supports", ()):
                    start, end = map(_exact_point, (support["start"], support["end"]))
                    if start != end and _on_segment(start, line.start, line.end) and _on_segment(
                        end, line.start, line.end
                    ):
                        live_matches.append({
                            "id": candidate.line_id,
                            "selected": candidate.line_id in live_selected,
                            "stored_interval_exact_clear": clearance.permits_exact(
                                candidate.start, candidate.end),
                        })
                        break
            ambiguous = []
            for item in snapshot["ambiguous_pairs"]:
                start, end = map(_exact_point, (item["start"], item["end"]))
                if start != end and _on_segment(start, line.start, line.end) and _on_segment(
                    end, line.start, line.end
                ):
                    ambiguous.append(item["reason"])
            unresolved = []
            for item in snapshot["audit"]["unresolved"]:
                start, end = map(_exact_point, (item["start"], item["end"]))
                if start != end and _on_segment(start, line.start, line.end) and _on_segment(
                    end, line.start, line.end
                ):
                    unresolved.append({"status": item["status"], "reason": item["reason"]})
            limiting = [
                sorted(labels[cell] for cell, edges in building_edges.items()
                       if any(_on_segment(point, a, b) for a, b in edges))
                for point in (line.start, line.end)
            ]
            intersections = sum(
                bool(_intersections(line.start, line.end, other.start, other.end))
                for j, other in enumerate(lines) if j != i
            )
            entries.append({
                "candidate": i, "length": line.length,
                "start": [str(v) for v in line.start], "end": [str(v) for v in line.end],
                "baseline": data["records"][i]["baseline"] is not None,
                "boundary": bool(data["records"][i]["boundary"]),
                "exact_clear": clearance.permits_exact(line.start, line.end),
                "live": live_matches, "ambiguous": ambiguous, "unresolved": unresolved,
                "limiting_building_labels": limiting,
                "exact_candidate_intersections": intersections,
                "initially_selected": i in result["initial"],
                "finally_selected": i in result["selected"],
            })
        pair_data[pair] = sorted(entries, key=lambda item: -item["length"])
    attachments = [SampleAttachment(tuple(map(Fraction, item["sample"])),
                                    tuple(map(Fraction, item["point"])), item["line_id"])
                   for item in data["attachments"]]
    components = [item["component"] for item in data["attachments"]]
    full = {(a, b): d for a, b, d in reference["depths"]}
    selected = set(result["initial"])
    checkpoints = {0, 1, 2}
    pair_49_23 = set(result["pair_candidates"]["49-23"])
    checkpoints.update(
        index for index, (removed, _) in enumerate(result["exchanges"], 1)
        if pair_49_23.intersection(removed)
    )
    checkpoints.update({index - 1 for index in checkpoints if index > 2})
    step_metrics = {}
    for step in range(max(checkpoints) + 1):
        if step:
            removed, added = result["exchanges"][step - 1]
            selected.difference_update(removed)
            selected.update(added)
        if step not in checkpoints:
            continue
        selected_lines = [lines[i] for i in sorted(selected)]
        depths = angular_reference(selected_lines, attachments, components).depths
        changes = [depths[pair] - depth for pair, depth in full.items() if math.isfinite(depth)]
        step_metrics[step] = {
            "lines": len(selected),
            "length": sum(line.length for line in selected_lines),
            "intersections": candidate_graph(selected_lines).number_of_edges(),
            "mean_increase": sum(changes) / len(changes),
            "max_increase": max(changes),
            "increased_pairs": sum(value > 1e-10 for value in changes),
        }
        print("validated step", step, step_metrics[step], flush=True)

    def background(ax, bounds):
        for cell, polygon in {**opened, **buildings}.items():
            if not polygon.intersects(bounds):
                continue
            ax.fill(*polygon.exterior.xy, facecolor="#8c9097" if cell in buildings else "#f8f6ef",
                    edgecolor="#dddddc", linewidth=.3, zorder=0)
            if cell in labels:
                point = polygon.representative_point()
                ax.text(point.x, point.y, str(labels[cell]), fontsize=6, ha="center",
                        va="center", color="black", clip_on=True, zorder=6)
        ax.set_aspect("equal")

    from shapely.geometry import box

    for pair, entries in pair_data.items():
        left, right = map(int, pair.split("-"))
        a, b = buildings[cells[left]], buildings[cells[right]]
        min_x, min_y, max_x, max_y = a.union(b).bounds
        margin = 6
        bounds = box(min_x - margin, min_y - margin, max_x + margin, max_y + margin)
        fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharex=True, sharey=True)
        live_segments = [(live_by_id[i].start, live_by_id[i].end) for i in sorted(live_selected)]
        for ax in axes:
            background(ax, bounds)
            ax.add_collection(LineCollection(live_segments, colors="#16853c", linewidths=.9,
                                             alpha=.7, zorder=2))
            ax.set(xlim=(bounds.bounds[0], bounds.bounds[2]),
                   ylim=(bounds.bounds[1], bounds.bounds[3]), xlabel="x", ylabel="y")
        axes[0].set_title("Replayed live convex selection (32 lines)")
        candidate = lines[entries[0]["candidate"]]
        axes[1].plot(*zip(*[(float(x), float(y)) for x, y in (candidate.start, candidate.end)]),
                     color="#d37300", linewidth=2.2, zorder=4)
        axes[1].set_title(f"Overlay: exact candidate {candidate.line_id} "
                          f"({candidate.length:.2f}); not a live exchange")
        fig.suptitle(f"Displayed buildings {pair}; orange line is exact-clear")
        fig.tight_layout()
        destination = state / f"pair-{pair}.png"
        if destination.exists():
            raise FileExistsError(destination)
        fig.savefig(destination, dpi=160)
        plt.close(fig)

    exchange_results = [("49-54", result)]
    revisit_path = state / "exchange-revisit-49-23.json"
    if revisit_path.exists():
        exchange_results.append(("49-23", json.loads(revisit_path.read_text())))
    for pair, exchange in exchange_results:
        if not exchange["exchanges"]:
            continue
        removed, added = exchange["exchanges"][0]
        before = set(exchange["initial"])
        after = before.difference(removed).union(added)
        fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharex=True, sharey=True)
        first, second = map(int, pair.split("-"))
        a, b = buildings[cells[first]], buildings[cells[second]]
        min_x, min_y, max_x, max_y = a.union(b).bounds
        bounds = box(min_x - 8, min_y - 8, max_x + 8, max_y + 8)
        for ax, chosen, title in zip(axes, (before, after), ("Before exchange", "After exchange")):
            background(ax, bounds)
            segments = [[tuple(map(float, lines[i].start)), tuple(map(float, lines[i].end))]
                        for i in sorted(chosen)]
            ax.add_collection(LineCollection(segments, colors="#16853c", linewidths=.45,
                                             alpha=.25, zorder=2))
            highlights = ([(i, "#b63b3b", "--") for i in removed] if chosen is before
                          else [(i, "#d37300", "-") for i in added])
            for i, colour, style in highlights:
                ax.plot(*zip(*[tuple(map(float, p)) for p in (lines[i].start, lines[i].end)]),
                        color=colour, linestyle=style, linewidth=1.6, zorder=4)
            ax.set(xlim=(bounds.bounds[0], bounds.bounds[2]),
                   ylim=(bounds.bounds[1], bounds.bounds[3]), title=title)
        fig.suptitle(f"Fixed-sample experiment: remove {removed}, add {added}; red removed, orange added")
        fig.tight_layout()
        destination = state / f"pair-{pair}-exchange.png"
        if destination.exists():
            raise FileExistsError(destination)
        fig.savefig(destination, dpi=160)
        plt.close(fig)
    report = {"pairs": pair_data, "step_metrics": step_metrics}
    with (state / "pair-diagnostics.json").open("x") as file:
        json.dump(report, file, allow_nan=False)
    print("pair diagnostics", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
