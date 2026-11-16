"""Plot saved Hill angular-fidelity experiment results."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from shapely import wkt


parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
args = parser.parse_args()
state = args.data_dir
prepared = json.loads((state / "angular-hill-prepared.json").read_text())
results = json.loads((state / "angular-hill-final-results.json").read_text())
settlement = json.loads((state / "hill42-corridor-pool.json").read_text())
polygons = {int(i): wkt.loads(p) for i, p in settlement["polygons"].items()}
labels = {int(i): label for i, label in settlement["building_labels"].items()}
segments = []
for record in prepared["records"]:
    item = record["baseline"] or record["boundary"][0]
    segments.append(tuple(tuple(float(Fraction(x)) for x in item[key])
                          for key in ("start", "end")))


def background(ax, *, labels_visible=False):
    for cell, polygon in polygons.items():
        ax.fill(*polygon.exterior.xy,
                facecolor="#8c9097" if cell in labels else "#f8f6ef",
                edgecolor="#dddddc", linewidth=.3, zorder=0)
        if labels_visible and cell in labels:
            point = polygon.representative_point()
            ax.text(point.x, point.y, str(labels[cell]), fontsize=7, ha="center",
                    va="center", color="black", clip_on=True, zorder=6)
    ax.set_aspect("equal")


fig, ax = plt.subplots(figsize=(7, 4))
ax.plot([item["epsilon"] for item in results],
        [len(item["best"]["selected"]) for item in results], marker="o")
ax.set(xlabel="Angular tolerance ε (normalised right-angle units)",
       ylabel="Selected lines", title="Empirical complexity–fidelity results")
ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(state / "angular-hill-complexity.png", dpi=180)
plt.close(fig)

chosen = [results[min(range(len(results)),
                      key=lambda i: abs(results[i]["epsilon"] - target))]
          for target in (0, .1, .5)]
fig, axes = plt.subplots(2, 2, figsize=(12, 12))
background(axes[0, 0])
axes[0, 0].add_collection(LineCollection(segments, colors="#305985", linewidths=.25, alpha=.45))
axes[0, 0].set_title(f"Full certified pool: {len(segments)} lines")
for ax, entry in zip(axes.flat[1:], chosen):
    background(ax)
    selected = entry["best"]["selected"]
    ax.add_collection(LineCollection([segments[i] for i in selected],
                                     colors="#1d5ca7", linewidths=.5, alpha=.7))
    ax.set_title(f"ε = {entry['epsilon']:g}: {len(selected)} lines")
for ax in axes.flat:
    ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="x", ylabel="y")
fig.suptitle("Hill seed 42 — identical settlement and extents")
fig.tight_layout()
fig.savefig(state / "angular-hill-maps.png", dpi=180)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(15, 7))
for ax, entry in zip(axes, (chosen[0], chosen[-1])):
    background(ax, labels_visible=True)
    selected = entry["best"]["selected"]
    ax.add_collection(LineCollection([segments[i] for i in selected], colors="#1764b0",
                                     linewidths=.8, alpha=.7, zorder=2))
    for index, colour, style in ((555, "#d47700", "--"), (592, "#b21a80", "-.")):
        ax.plot(*zip(*segments[index]), color=colour, linestyle=style, linewidth=2.5, zorder=4)
        for point in (prepared["records"][index]["baseline"]["seed_start"],
                      prepared["records"][index]["baseline"]["seed_end"]):
            x, y = (float(Fraction(value)) for value in point)
            ax.scatter(x, y, s=25, color=colour, edgecolor="white", zorder=5)
    ax.set(xlim=(27, 51), ylim=(40, 68), xlabel="x", ylabel="y",
           title=f"ε={entry['epsilon']:g}: corridor line "
                 f"{'selected' if entry['best']['corridor_555'] else 'not selected'}")
fig.legend(handles=[
    Line2D([], [], color="#1764b0", label="Selected finite segments"),
    Line2D([], [], color="#d47700", ls="--", label="21.0679 corridor candidate (555)"),
    Line2D([], [], color="#b21a80", ls="-.", label="19.1286 candidate (592)"),
    Line2D([], [], marker="o", color="none", markerfacecolor="#d47700",
           label="Defining support vertices"),
], loc="lower center", ncol=2)
fig.suptitle("Building 2–15 corridor; exact intervals shown as float display segments")
fig.tight_layout(rect=(0, .08, 1, .95))
fig.savefig(state / "angular-hill-corridor.png", dpi=180)
plt.close(fig)

fig, axes = plt.subplots(2, 3, figsize=(13, 7))
for ax, entry in zip(axes.flat, results):
    changes = [row[2] for row in entry["best"]["differences"]]
    ax.hist(changes, bins=20, color="#1d5ca7")
    ax.set_title(f"ε={entry['epsilon']:g}; max Δ={max(changes):.3g}")
    ax.set_xlabel("Angular-depth change")
    ax.set_ylabel("Ordered pairs")
fig.suptitle("Fixed-attachment angular-depth changes")
fig.tight_layout()
fig.savefig(state / "angular-hill-angular-errors.png", dpi=180)
plt.close(fig)
