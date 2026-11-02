"""
Visualisation and summary statistics for morphic grammar experiments.

Colour scheme (categorical morphology only; space-syntax values are never
mapped onto these colours):
    occupied cells         dark grey
    exterior open cells    light grey
    enclosed open cells    blue
    designated target      thick orange outline
    aggregate boundary     black line
"""

from typing import Dict, Iterable, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np

from . import morphology as mo
from .carrier import Carrier
from .experiment import MODE_LABELS, ExperimentRun

COLOURS = {
    mo.OCCUPIED: "#4d4d4d",
    mo.EXTERIOR_OPEN: "#e3e3e3",
    mo.ENCLOSED_OPEN: "#4f9bd9",
}
TARGET_COLOUR = "#ff7f0e"


def draw_morphology(
    ax,
    carrier: Carrier,
    occupied: Sequence[int],
    target: Optional[Iterable] = None,
    show_open_graph: bool = False,
    title: str = "",
) -> None:
    categories = mo.classify_cells(carrier, occupied)
    for cell, polygon in carrier.polygons.items():
        x, y = polygon.exterior.xy
        ax.fill(x, y, facecolor=COLOURS[categories[cell]], edgecolor="white", linewidth=0.4)

    geometry = mo.aggregate_geometry(carrier, occupied)
    if geometry is not None:
        for part in getattr(geometry, "geoms", [geometry]):
            x, y = part.exterior.xy
            ax.plot(x, y, color="black", linewidth=1.4)
            for hole in part.interiors:
                hx, hy = hole.xy
                ax.plot(hx, hy, color="black", linewidth=1.4)

    for cell in (target or []):
        x, y = carrier.polygons[cell].exterior.xy
        ax.plot(x, y, color=TARGET_COLOUR, linewidth=3)

    if show_open_graph:
        open_set = mo.open_cells(carrier, occupied)
        for left, right in carrier.graph(open_set).edges():
            (x1, y1), (x2, y2) = carrier.centroid(left), carrier.centroid(right)
            ax.plot([x1, x2], [y1, y2], color="#777777", linewidth=0.4, alpha=0.7)

    min_x, min_y, max_x, max_y = carrier.extent
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=9)


def fig_comparison(
    runs: Dict[str, ExperimentRun],
    step: Optional[int] = None,
    show_open_graph: bool = False,
):
    """Side-by-side morphologies on a shared extent. ``step`` limits replay."""
    fig, axes = plt.subplots(1, len(runs), figsize=(4.5 * len(runs), 4.8), squeeze=False)
    for ax, (mode, run) in zip(axes[0], runs.items()):
        total = len(run.result.occupied)
        shown = total if step is None else min(step, total)
        occupied = run.result.occupied_at(shown)
        label = MODE_LABELS.get(mode, mode)
        draw_morphology(
            ax, run.carrier, occupied, run.result.target, show_open_graph,
            title=f"{label}\n{shown}/{total} cells - {run.result.termination}",
        )
    fig.tight_layout()
    return fig


def legend_text() -> str:
    return (
        "Dark grey = occupied; light grey = exterior open; blue = enclosed open; "
        "orange outline = enclosure target; black line = aggregate boundary."
    )


SUMMARY_FIELDS = [
    "n_occupied", "n_occupied_components", "n_open_components",
    "n_enclosed_open_components", "enclosed_open_area", "occupied_graph_cycles",
    "occupied_nontrivial_cycles", "aggregate_perimeter", "compactness",
    "open_connectivity_mean", "n_exterior_open_cells",
]


def summarise(runs: List[ExperimentRun]) -> List[Dict[str, object]]:
    """Per-mode mean/std of each measure (missing values excluded) and enclosure rates."""
    rows = []
    for mode in dict.fromkeys(run.config.mode for run in runs):
        group = [r for r in runs if r.config.mode == mode]
        row: Dict[str, object] = {"mode": mode, "runs": len(group)}
        for name in SUMMARY_FIELDS:
            values = [r.metrics[name] for r in group if r.metrics[name] is not None]
            row[f"{name}_mean"] = float(np.mean(values)) if values else None
            row[f"{name}_std"] = float(np.std(values)) if values else None
            row[f"{name}_n"] = len(values)
        row["any_enclosed_rate"] = float(np.mean(
            [r.metrics["n_enclosed_open_components"] > 0 for r in group]))
        targeted = [r for r in group if r.metrics["target_enclosed"] is not None]
        row["target_enclosed_rate"] = (
            float(np.mean([r.metrics["target_enclosed"] for r in targeted])) if targeted else None
        )
        rows.append(row)
    return rows


def fig_distributions(runs: List[ExperimentRun]):
    """Box plots of key measures by mode."""
    measures = [
        ("enclosed_open_area", "Enclosed open area"),
        ("n_enclosed_open_components", "Enclosed open components"),
        ("compactness", "Compactness (4piA/P^2)"),
        ("occupied_graph_cycles", "Occupied graph cycles (cyclomatic)"),
        ("occupied_nontrivial_cycles", "Non-trivial cycles (cyclomatic - triangles)"),
        ("n_occupied_components", "Occupied components"),
    ]
    modes = list(dict.fromkeys(run.config.mode for run in runs))
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, (key, label) in zip(axes.ravel(), measures):
        data = [[r.metrics[key] for r in runs if r.config.mode == m and r.metrics[key] is not None]
                for m in modes]
        ax.boxplot([d if d else [np.nan] for d in data])
        ax.set_xticklabels(modes)
        ax.set_title(label, fontsize=10)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8)
    fig.tight_layout()
    return fig
