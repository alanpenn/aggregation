"""Plot legacy and unified-pool Valley selections on identical numbered geometry."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

from voronoi_app.axial_snapshot import load_axial_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--targeted-continuation", action="store_true")
    args = parser.parse_args()
    data = json.loads((args.data_dir / "prepared.json").read_text())
    settlement = json.loads((args.data_dir / "settlement.json").read_text())
    live = json.loads((args.data_dir / "live-selection.json").read_text())
    result = json.loads((args.output_dir / "selection-results.json").read_text())
    opened, buildings, generated, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    labels = {int(cell): int(label) for cell, label in settlement["building_labels"].items()}
    lines = []
    for record in data["records"]:
        source = record["baseline"] or record["boundary"][0]
        lines.append([tuple(float(Fraction(x)) for x in source[key]) for key in ("start", "end")])
    live_by_id = {line.line_id: line for line in generated.candidate_lines}
    final_title = "Connectivity order after exchanges"
    final_selection = result["connectivity_exchange"]["selected"]
    if args.targeted_continuation:
        targeted = json.loads((args.output_dir / "targeted-evaluated.json").read_text())
        final_selection = targeted["connectivity_exchange:1391"]["selected"]
        final_title = "Connectivity exchanges plus targeted 1391 continuation"
    maps = [
        ("Original live-pool greedy replay (32)", [
            (live_by_id[i].start, live_by_id[i].end) for i in live["selected"]
        ]),
        ("Unified-pool coverage greedy", [lines[i] for i in result["greedy"]["selected"]]),
        ("Unified-pool connectivity order", [lines[i] for i in result["connectivity"]["selected"]]),
        (final_title, [lines[i] for i in final_selection]),
    ]
    bounds = unary_bounds([*opened.values(), *buildings.values()])
    colors = {1: "#d44816", 50: "#d44816", 49: "#b72498", 54: "#d49000", 23: "#206cd4"}
    fig, axes = plt.subplots(2, 2, figsize=(18, 18), sharex=True, sharey=True)
    for ax, (title, segments) in zip(axes.flat, maps):
        for cell, polygon in {**opened, **buildings}.items():
            label = labels.get(cell)
            ax.fill(*polygon.exterior.xy, facecolor="#8c9097" if cell in buildings else "#f8f6ef",
                    edgecolor=colors.get(label, "#d8d8d3"),
                    linewidth=1.5 if label in colors else .25, zorder=0)
            if label is not None:
                point = polygon.representative_point()
                ax.text(point.x, point.y, str(label), fontsize=7 if label in colors else 4,
                        fontweight="bold" if label in colors else "normal",
                        color=colors.get(label, "black"), ha="center", va="center", zorder=4)
        ax.add_collection(LineCollection(segments, colors="#16853c", linewidths=.9, alpha=.7,
                                         zorder=2))
        ax.set(xlim=(bounds[0], bounds[2]), ylim=(bounds[1], bounds[3]),
               title=f"{title} — {len(segments)} lines", xlabel="x", ylabel="y")
        ax.set_aspect("equal")
    fig.legend(handles=[
        Line2D([0], [0], color="#d44816", label="Buildings 1 and 50"),
        Line2D([0], [0], color="#b72498", label="Building 49 (both pairs)"),
        Line2D([0], [0], color="#d49000", label="Building 54"),
        Line2D([0], [0], color="#206cd4", label="Building 23"),
    ], loc="lower center", ncol=4)
    fig.suptitle("Converging Valleys/Y seed 42 — common settlement and plot extents")
    fig.tight_layout(rect=(0, .03, 1, .98))
    destination = args.output_dir / (
        "connectivity-comparison-targeted.png" if args.targeted_continuation
        else "connectivity-comparison.png"
    )
    if destination.exists():
        raise FileExistsError(destination)
    fig.savefig(destination, dpi=180)
    plt.close(fig)
    print("saved", destination)


def unary_bounds(polygons):
    bounds = [polygon.bounds for polygon in polygons]
    return min(b[0] for b in bounds), min(b[1] for b in bounds), \
        max(b[2] for b in bounds), max(b[3] for b in bounds)


if __name__ == "__main__":
    main()
