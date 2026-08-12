import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np

from .engine import SimulationResult


def _hill_elevation(x, y, canvas_size):
    cy = canvas_size / 2
    sigma = canvas_size / 6
    return np.exp(-(y - cy) ** 2 / (2 * sigma ** 2))


def fig_aggregation(result: SimulationResult):
    voronoi = result.voronoi
    canvas_size = result.config.canvas_size

    mean_depth = result.mean_depth
    if mean_depth:
        norm = plt.Normalize(min(mean_depth.values()), max(mean_depth.values()))
    else:
        norm = plt.Normalize(0, 1)
    cmap = cm.jet.reversed()

    fig, ax = plt.subplots(figsize=(10, 10))

    for region_index in result.buildings:
        region = voronoi.regions[voronoi.point_region[region_index]]
        if not region or -1 in region:
            continue
        polygon = [voronoi.vertices[i] for i in region if i >= 0]
        if len(polygon) >= 3:
            polygon.append(polygon[0])
            x, y = zip(*polygon)
            ax.fill(x, y, color="black")
            cx, cy = np.mean(x[:-1]), np.mean(y[:-1])
            label = result.building_labels.get(region_index, "?")
            ax.text(cx, cy, str(label), color="white", ha="center", va="center", fontsize=8)

    for region_index in result.open_spaces:
        region = voronoi.regions[voronoi.point_region[region_index]]
        if not region or -1 in region:
            continue
        polygon = [voronoi.vertices[i] for i in region if i >= 0]
        if len(polygon) >= 3:
            polygon.append(polygon[0])
            x, y = zip(*polygon)
            color = cmap(norm(mean_depth.get(region_index, 0)))
            ax.fill(x, y, color=color)

    for line in result.los_lines:
        x, y = line.xy
        ax.plot(x, y, linestyle=":", color="white", linewidth=0.5)

    for door in result.doors:
        ax.plot(door[0], door[1], "o", color="red")

    ax.set_xlim(0, canvas_size)
    ax.set_ylim(0, canvas_size)
    ax.set_aspect("equal")
    ax.set_title("Aggregation with Visibility Graph")
    ax.axis("off")
    fig.tight_layout()
    return fig


def fig_elevation(result: SimulationResult):
    canvas_size = result.config.canvas_size
    grid_res = 200
    x = np.linspace(0, canvas_size, grid_res)
    y = np.linspace(0, canvas_size, grid_res)
    X, Y = np.meshgrid(x, y)
    Z = _hill_elevation(X, Y, canvas_size)

    fig, ax = plt.subplots(figsize=(8, 6))
    contour = ax.contourf(X, Y, Z, cmap="terrain")
    fig.colorbar(contour, ax=ax, label="Elevation")
    ax.set_title("Digital Elevation Model (Ridge)")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig
