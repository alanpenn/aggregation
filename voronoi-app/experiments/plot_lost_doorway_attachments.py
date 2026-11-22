"""Show the exact fixed connectors lost and recovered in the Y 42 corridor tests."""

import json

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import numpy as np
from shapely import from_wkb
from shapely.geometry import box

from voronoi_app.batch_routing_reference import point
from voronoi_app.batch_store import BatchStore

from .extreme_diagonals import ROOT


def plot(data, number, directory):
    corridor = data["corridors"][number - 1]
    variants = corridor["variants"]
    original, pair, repaired = (set(variants[k]["representatives"]) for k in "ABC")
    exterior = set(corridor["exterior"])
    lost = [door for door in data["doorways"]
            if any(i in original | exterior for i, _ in door["connectors"])
            and not any(i in pair | exterior for i, _ in door["connectors"])]
    assert len(lost) == variants["B"]["constraints"]["unattached_doors"]
    lines = [np.array([point(p) for p in interval], dtype=float) for interval in data["intervals"]]
    labels = data["settlement"]["building_labels"]
    buildings = [(label, from_wkb(data["settlement"]["polygons_wkb"][cell]))
                 for cell, label in labels.items()]
    points = [p for i in pair | (repaired - pair) for p in lines[i]]
    for door in lost:
        points.append(point(door["point"]))
        points.extend(point(stop) for i, stop in door["connectors"] if i in original | repaired)
    bounds = np.array(points, dtype=float)
    low, high = bounds.min(axis=0) - 7, bounds.max(axis=0) + 7
    crop = box(*low, *high)

    fig, axes = plt.subplots(1, 3, figsize=(14, 7), sharex=True, sharey=True)
    fig.subplots_adjust(left=.015, right=.985, bottom=.13, top=.85, wspace=.035)
    for ax, title, active, colour in zip(
        axes, ("Original sheaf", f"Extreme pair · {len(lost)} doors detached", "Repaired pair"),
        (original, pair, repaired), ("#b83252", "#b83252", "#087c6a"), strict=True,
    ):
        for label, building in buildings:
            if building.intersects(crop):
                ax.fill(*building.exterior.xy, color="#363e48", zorder=1)
                p = building.representative_point()
                ax.text(p.x, p.y, label, color="white", fontsize=7, ha="center",
                        va="center", clip_on=True, zorder=2)
        ax.add_collection(LineCollection([lines[i] for i in sorted(exterior)], colors="#909ca6",
                                         alpha=.20, linewidths=.65, zorder=3))
        ax.add_collection(LineCollection([lines[i] for i in sorted(active - pair)], colors=(
            "#087c6a" if active == repaired else "#547fa7"), linewidths=1.65, zorder=4))
        ax.add_collection(LineCollection([lines[i] for i in sorted(active & pair)],
                                         colors="#df841b", linewidths=2.35, zorder=5))
        for door in lost:
            p = np.array(point(door["point"]), dtype=float)
            connectors = [(i, stop) for i, stop in door["connectors"] if i in active]
            if active == pair:
                connectors = [(i, stop) for i, stop in door["connectors"] if i in original]
            for _, stop in connectors:
                q = np.array(point(stop), dtype=float)
                ax.plot(*np.array([p, q]).T, color=colour, lw=1.1,
                        linestyle="--" if active == pair else "-", zorder=6)
                if active != pair:
                    ax.scatter(*q, s=10, color=colour, zorder=7)
            ax.scatter(*p, s=53, facecolors="white", edgecolors=colour, linewidths=1.65, zorder=9)
            if active == pair:
                ax.scatter(*p, s=24, marker="x", color=colour, linewidths=1.15, zorder=10)
            # The numbered marker follows the actual doorway position, not the building centroid.
            label = labels[str(door["building_cell"])]
            ax.annotate(label, p, xytext=(6, 6), textcoords="offset points", color=colour,
                        fontsize=8, weight="bold", zorder=11,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1})
        ax.set(xlim=(low[0], high[0]), ylim=(low[1], high[1]), aspect="equal", title=title)
        ax.axis("off")

    fig.suptitle(f"Y 42 | Corridor {number}", x=.035, ha="left", fontsize=22, weight="bold")
    count = len(variants["B"]["transverse_connections"])
    pairs = len(variants["B"]["affected_pairs"]["unreachable"])
    assert count == len(variants["A"]["transverse_connections"])
    fig.text(.035, .897, f"{count} transverse line contacts in both the original and extreme-pair maps. "
             f"The pair disconnects {pairs} doorway pairs.", fontsize=11)
    handles = [
        Line2D([], [], color="#547fa7", label="Original sheaf line"),
        Line2D([], [], color="#df841b", label="Extreme diagonal"),
        Line2D([], [], color="#b83252", linestyle="--", label="Removed fixed connector"),
        Line2D([], [], color="#087c6a", label="Repair line and restored connector"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .045),
               ncol=4, frameon=False)
    for extension in ("png", "pdf"):
        path = directory / f"Y-42-{number}-lost-doorway-attachments.{extension}"
        with path.open("xb") as stream:
            fig.savefig(stream, format=extension, dpi=180)
    plt.close(fig)
    print(number, sorted(int(labels[str(d["building_cell"])]) for d in lost), count, pairs)


def main():
    directory = ROOT / "extreme-diagonals" / "pilot-3"
    journal = json.loads((directory / "Y-42.json").read_text())
    _, data, _ = BatchStore(ROOT).load(journal["record"])
    for number in (2, 3):
        plot(data, number, directory)


if __name__ == "__main__":
    main()
