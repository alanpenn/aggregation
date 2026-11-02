"""Coordinated visualisations for cellular morphology and axial analysis."""

from typing import Dict, Iterable, List, Optional, Sequence

import matplotlib.pyplot as plt
from matplotlib import cm, colors
import numpy as np
from shapely.geometry import Polygon, MultiPolygon

from .axial import AxialRepresentation
from .axial_experiment import AxialExperimentRun, AxialSnapshot
from .carrier import Carrier
from .report import draw_morphology


LINE_MEASURES = ("length", "connectivity", "global_integration_rra", "local_integration_rra")


def _polygon_parts(geometry):
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if hasattr(geometry, "geoms"):
        return [part for item in geometry.geoms for part in _polygon_parts(item)]
    return []


def _line_values(representation: AxialRepresentation, metrics: Dict[str, object], measure: str):
    if measure == "length":
        return {line.id: line.length for line in representation.lines}
    values = metrics.get(measure, {})
    return values if isinstance(values, dict) else {}


def _draw_open_geometry(ax, representation: AxialRepresentation, extent):
    for polygon in _polygon_parts(representation.open_geometry):
        x, y = polygon.exterior.xy
        ax.fill(x, y, color="#efefef", edgecolor="white", linewidth=0.4)
        for hole in polygon.interiors:
            hx, hy = hole.xy
            ax.fill(hx, hy, color="white", edgecolor="white")
    min_x, min_y, max_x, max_y = extent
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_aspect("equal")
    ax.axis("off")


def _line_colors(values: Dict[int, object], cmap_name="viridis"):
    finite = {key: float(value) for key, value in values.items()
              if value is not None and np.isfinite(value)}
    if not finite:
        return {}, None
    low, high = min(finite.values()), max(finite.values())
    if low == high:
        high = low + 1
    norm = colors.Normalize(low, high)
    cmap = plt.get_cmap(cmap_name)
    return {key: cmap(norm(value)) for key, value in finite.items()}, (cmap, norm)


def fig_axial_snapshot(
    carrier: Carrier,
    snapshot: AxialSnapshot,
    target: Iterable[int] = (),
    colour_by: str = "length",
):
    """Render cellular morphology beside the sampled axial-line overlay."""
    if colour_by not in LINE_MEASURES:
        raise ValueError(f"colour_by must be one of {LINE_MEASURES}")
    representation = snapshot.representation
    metrics = snapshot.axial_metrics
    values = _line_values(representation, metrics, colour_by)
    line_colors, scale = _line_colors(values)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))

    draw_morphology(
        axes[0], carrier, snapshot.occupied, target,
        title=f"Cellular morphology - {snapshot.step} occupied",
    )

    ax = axes[1]
    _draw_open_geometry(ax, representation, carrier.extent)
    for line in representation.lines:
        x, y = line.geometry.xy
        ax.plot(x, y, color=line_colors.get(line.id, "#9a9a9a"), linewidth=2)
    ax.set_title(f"Sampled axial lines (colour: {colour_by})\n"
                 f"{representation.method}; {len(representation.lines)} lines")
    if scale:
        mappable = cm.ScalarMappable(norm=scale[1], cmap=scale[0])
        fig.colorbar(mappable, ax=ax, fraction=0.046, pad=0.04, label=colour_by)

    fig.tight_layout()
    return fig


def fig_axial_graph_diagnostics(snapshot: AxialSnapshot):
    """Show graph, intelligibility scatter and length/integration distributions."""
    representation = snapshot.representation
    metrics = snapshot.axial_metrics
    fig, axes = plt.subplots(1, 7, figsize=(24, 4))

    graph_ax = axes[0]
    positions = {}
    for line in representation.lines:
        point = line.geometry.interpolate(0.5, normalized=True)
        positions[line.id] = (point.x, point.y)
    if positions:
        for left, right in representation.graph.edges():
            graph_ax.plot(
                [positions[left][0], positions[right][0]],
                [positions[left][1], positions[right][1]],
                color="#888888", linewidth=0.8, zorder=1,
            )
        integration = metrics["global_integration_rra"]
        finite = [value for value in integration.values() if value is not None]
        low, high = (min(finite), max(finite)) if finite else (0.0, 1.0)
        if low == high:
            high = low + 1
        cmap = plt.get_cmap("viridis")
        norm = colors.Normalize(low, high)
        for node, (x, y) in positions.items():
            value = integration[node]
            graph_ax.scatter(
                x, y, color=cmap(norm(value)) if value is not None else "#aaaaaa",
                edgecolor="black", s=32, zorder=2,
            )
        graph_ax.set_title(
            f"Axial graph\n{metrics['component_count']} components; "
            f"{metrics['cycle_rank']} cycles"
        )
        graph_ax.set_aspect("equal")
        graph_ax.axis("off")
    else:
        graph_ax.set_title("Axial graph (no lines)")
        graph_ax.axis("off")

    connectivity = metrics["connectivity"]
    integration = metrics["global_integration_rra"]
    valid = [(connectivity[node], value) for node, value in integration.items()
             if value is not None]
    scatter_ax = axes[1]
    if valid:
        scatter_ax.scatter([item[0] for item in valid], [item[1] for item in valid], alpha=0.8)
    scatter_ax.set_xlabel("Axial connectivity")
    scatter_ax.set_ylabel("Global integration (RRA)")
    r_squared = metrics["intelligibility_r_squared"]
    r_text = "undefined" if r_squared is None else f"{r_squared:.3f}"
    scatter_ax.set_title(f"Intelligibility R²={r_text}\nn={metrics['intelligibility_n']}")

    distribution_ax = axes[2]
    lengths = metrics["line_lengths"]
    if lengths:
        distribution_ax.hist(lengths, bins=min(15, max(3, len(lengths))), alpha=0.6,
                             color="#4776a8")
    distribution_ax.set_title("Line length")
    distribution_ax.set_xlabel("Geometry units")

    connectivity_ax = axes[3]
    connectivity_values = list(connectivity.values())
    if connectivity_values:
        connectivity_ax.hist(connectivity_values, bins=min(12, max(3, len(set(connectivity_values)))),
                             color="#6a9f58")
    connectivity_ax.set_title("Connectivity")

    integration_ax = axes[4]
    integrations = metrics["global_integration_distribution"]
    if integrations:
        integration_ax.hist(integrations, bins=min(15, max(3, len(integrations))),
                            color="#8f6bb3")
    integration_ax.set_title("Global integration (RRA)")

    local_ax = axes[5]
    local_integrations = metrics["local_integration_distribution"]
    if local_integrations:
        local_ax.hist(local_integrations, bins=min(15, max(3, len(local_integrations))),
                      color="#b27c47")
    local_ax.set_title("Local integration (RRA)")

    depth_ax = axes[6]
    depths = metrics["mean_depth_distribution"]
    if depths:
        depth_ax.hist(depths, bins=min(15, max(3, len(depths))), color="#558b8b")
    depth_ax.set_title("Mean depth")

    fig.tight_layout()
    return fig


def summarise_axial_runs(runs: Sequence[AxialExperimentRun]) -> List[Dict[str, object]]:
    """Aggregate trajectory diagnostics by mode and occupied-cell stage."""
    groups = {}
    for run in runs:
        for snapshot in run.snapshots:
            groups.setdefault((run.config.mode, snapshot.step), []).append(snapshot)
    rows = []
    fields = (
        "axial_line_count", "intersection_count", "component_count", "cycle_rank",
        "intelligibility_pearson", "intelligibility_r_squared", "intelligibility_n",
        "sample_coverage_fraction",
    )
    for (mode, step), snapshots in sorted(groups.items()):
        row: Dict[str, object] = {"mode": mode, "occupied_cells": step, "runs": len(snapshots)}
        for field in fields:
            values = [snapshot.axial_metrics[field] for snapshot in snapshots
                      if snapshot.axial_metrics[field] is not None]
            row[f"{field}_mean"] = float(np.mean(values)) if values else None
            row[f"{field}_std"] = float(np.std(values)) if values else None
            row[f"{field}_n"] = len(values)
        for distribution in ("line_lengths", "global_integration_distribution",
                             "local_integration_distribution", "connectivity_distribution",
                             "mean_depth_distribution"):
            values = [
                value
                for snapshot in snapshots
                for value in snapshot.axial_metrics[distribution]
                if value is not None and np.isfinite(value)
            ]
            row[f"{distribution}_mean"] = float(np.mean(values)) if values else None
            row[f"{distribution}_std"] = float(np.std(values)) if values else None
            row[f"{distribution}_n"] = len(values)
        rows.append(row)
    return rows


def fig_axial_trajectories(runs: Sequence[AxialExperimentRun]):
    """Plot emergence trajectories and intelligibility across modes."""
    summaries = summarise_axial_runs(runs)
    modes = list(dict.fromkeys(run.config.mode for run in runs))
    charts = [
        ("axial_line_count_mean", "Axial line count"),
        ("line_lengths_mean", "Mean axial line length"),
        ("connectivity_distribution_mean", "Mean axial connectivity"),
        ("mean_depth_distribution_mean", "Mean axial depth"),
        ("global_integration_distribution_mean", "Mean global integration (RRA)"),
        ("local_integration_distribution_mean", "Mean local integration (RRA)"),
        ("intelligibility_r_squared_mean", "Intelligibility R-squared"),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))
    for ax, (field, title) in zip(axes.ravel(), charts):
        for mode in modes:
            rows = [row for row in summaries if row["mode"] == mode]
            rows.sort(key=lambda row: row["occupied_cells"])
            valid = [row for row in rows if row[field] is not None]
            ax.plot([row["occupied_cells"] for row in valid],
                    [row[field] for row in valid], marker="o", label=mode)
        ax.set_title(title)
        ax.set_xlabel("Occupied cells")
        ax.legend(fontsize=8)
    axes.ravel()[-1].set_visible(False)
    fig.tight_layout()
    return fig
