import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Polygon, box

from .engine import SimulationResult


def _hill_elevation(x, y, canvas_size):
    cy = canvas_size / 2
    sigma = canvas_size / 6
    return np.exp(-(y - cy) ** 2 / (2 * sigma ** 2))


def _region_centroid(voronoi, region_index):
    region = voronoi.regions[voronoi.point_region[region_index]]
    if region is None or len(region) == 0 or -1 in region:
        return None

    polygon_vertices = [voronoi.vertices[i] for i in region if i >= 0]
    if len(polygon_vertices) < 3:
        return None

    polygon = Polygon(polygon_vertices)
    if not polygon.is_valid:
        return None

    centroid = polygon.centroid
    return np.array([centroid.x, centroid.y], dtype=float)


def _finite_voronoi_regions(voronoi, canvas_size):
    """Return Voronoi regions clipped to the experiment canvas."""
    if len(voronoi.points) < 3:
        return {}

    center = voronoi.points.mean(axis=0)
    radius = np.ptp(voronoi.points, axis=0).max() * 2
    ridge_map = {}
    for (point_a, point_b), (vertex_a, vertex_b) in zip(
        voronoi.ridge_points, voronoi.ridge_vertices
    ):
        ridge_map.setdefault(point_a, []).append((point_b, vertex_a, vertex_b))
        ridge_map.setdefault(point_b, []).append((point_a, vertex_a, vertex_b))

    vertices = voronoi.vertices.tolist()
    regions = {}
    for point_index, region_index in enumerate(voronoi.point_region):
        region = voronoi.regions[region_index]
        if not region:
            continue
        if all(vertex >= 0 for vertex in region):
            polygon_vertices = [vertices[vertex] for vertex in region]
        else:
            polygon_vertices = [vertices[vertex] for vertex in region if vertex >= 0]
            for neighbor, vertex_a, vertex_b in ridge_map.get(point_index, []):
                if vertex_a < 0 or vertex_b < 0:
                    tangent = voronoi.points[neighbor] - voronoi.points[point_index]
                    tangent /= np.linalg.norm(tangent)
                    normal = np.array([-tangent[1], tangent[0]])
                    midpoint = voronoi.points[[point_index, neighbor]].mean(axis=0)
                    direction = np.sign(np.dot(midpoint - center, normal)) * normal
                    finite_vertex = vertex_b if vertex_a < 0 else vertex_a
                    far_point = vertices[finite_vertex] + direction * radius
                    polygon_vertices.append(far_point.tolist())

        if len(polygon_vertices) < 3:
            continue
        polygon = Polygon(polygon_vertices).convex_hull
        clipped = polygon.intersection(box(0, 0, canvas_size, canvas_size))
        if not clipped.is_empty and clipped.geom_type == "Polygon":
            regions[point_index] = np.asarray(clipped.exterior.coords)
    return regions


def fig_aggregation(result: SimulationResult):
    """Render aggregation results. Supports both Voronoi and Cartesian grids."""
    voronoi = result.voronoi
    canvas_size = result.config.canvas_size
    grid = getattr(result, 'grid', None)
    grid_type = grid.metadata.get("grid_type", "voronoi") if grid else "voronoi"

    mean_depth = result.mean_depth
    if mean_depth:
        norm = plt.Normalize(min(mean_depth.values()), max(mean_depth.values()))
    else:
        norm = plt.Normalize(0, 1)
    cmap = cm.jet.reversed()

    fig, ax = plt.subplots(figsize=(10, 10))

    # Choose rendering based on grid type
    if voronoi is not None:
        # Voronoi rendering (original)
        _render_voronoi_aggregation(ax, result, voronoi, cmap, norm, mean_depth, canvas_size)
    elif grid_type == "cartesian" and grid is not None:
        # Cartesian grid rendering
        _render_cartesian_aggregation(ax, result, grid, cmap, norm, mean_depth, canvas_size)
    else:
        # Fallback: render points and edges
        _render_graph_aggregation(ax, result, grid, cmap, norm, mean_depth, canvas_size)

    ax.set_xlim(0, canvas_size)
    ax.set_ylim(0, canvas_size)
    ax.set_aspect("equal")
    ax.set_title("Aggregation with Visibility Graph")
    ax.axis("off")
    fig.tight_layout()
    return fig


def _render_voronoi_aggregation(ax, result, voronoi, cmap, norm, mean_depth, canvas_size):
    """Render aggregation using Voronoi diagram."""
    regions = _finite_voronoi_regions(voronoi, canvas_size)
    for region_index in result.buildings:
        polygon = regions.get(region_index)
        if polygon is None:
            continue
        if len(polygon) >= 3:
            x, y = zip(*polygon)
            ax.fill(x, y, color="black")
            cx, cy = np.mean(x[:-1]), np.mean(y[:-1])
            label = result.building_labels.get(region_index, "?")
            ax.text(cx, cy, str(label), color="white", ha="center", va="center", fontsize=8)

    for region_index in result.open_spaces:
        polygon = regions.get(region_index)
        if polygon is None:
            continue
        if len(polygon) >= 3:
            x, y = zip(*polygon)
            color = cmap(norm(mean_depth.get(region_index, 0)))
            ax.fill(x, y, color=color)

    for line in result.los_lines:
        x, y = line.xy
        ax.plot(x, y, linestyle=":", color="white", linewidth=0.5)

    for door in result.doors:
        try:
            open_idx, building_idx = door
            if not isinstance(open_idx, (int, np.integer)) or not isinstance(
                building_idx, (int, np.integer)
            ):
                raise TypeError
            open_centroid = _region_centroid(result.voronoi, open_idx)
            building_centroid = _region_centroid(result.voronoi, building_idx)
            if open_centroid is None or building_centroid is None:
                continue

            direction = building_centroid - open_centroid
            half_length = np.linalg.norm(direction) / 2
            if half_length == 0:
                continue

            start = open_centroid + 0.25 * direction
            end = open_centroid + 0.75 * direction

            ax.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color="black",
                linewidth=1.5,
            )
        except (TypeError, ValueError):
            if len(door) == 2 and np.asarray(door).shape == (2, 2):
                x = [door[0][0], door[1][0]]
                y = [door[0][1], door[1][1]]
                ax.plot(x, y, color="black", linewidth=1.5)


def _render_cartesian_aggregation(ax, result, grid, cmap, norm, mean_depth, canvas_size):
    """Render aggregation on Cartesian grid as cell colors."""
    # Create grid cells around each node
    nodes = np.array(grid.nodes)
    cell_size = canvas_size / (int(np.sqrt(len(nodes))) + 1)
    
    for idx, (x, y) in enumerate(nodes):
        # Create square cell around point
        cell_x = x - cell_size / 2
        cell_y = y - cell_size / 2
        
        if idx in result.buildings:
            rect = plt.Rectangle((cell_x, cell_y), cell_size, cell_size, 
                                  facecolor="black", edgecolor="gray", linewidth=0.5)
            ax.add_patch(rect)
            label = result.building_labels.get(idx, "?")
            ax.text(x, y, str(label), color="white", ha="center", va="center", fontsize=8)
        elif idx in result.open_spaces:
            color = cmap(norm(mean_depth.get(idx, 0)))
            rect = plt.Rectangle((cell_x, cell_y), cell_size, cell_size, 
                                  facecolor=color, edgecolor="gray", linewidth=0.5)
            ax.add_patch(rect)
    
    # Draw doors as lines between cell centers
    for door in result.doors:
        try:
            open_idx, building_idx = door
            open_pos = nodes[open_idx]
            building_pos = nodes[building_idx]
            ax.plot([open_pos[0], building_pos[0]], [open_pos[1], building_pos[1]], 
                   color="black", linewidth=1.5)
        except (IndexError, TypeError):
            pass


def _render_graph_aggregation(ax, result, grid, cmap, norm, mean_depth, canvas_size):
    """Render aggregation as graph with node coloring."""
    if grid is None:
        return
    
    nodes = np.array(grid.nodes)
    
    # Draw edges
    for edge in grid.edges:
        try:
            x = [nodes[edge[0]][0], nodes[edge[1]][0]]
            y = [nodes[edge[0]][1], nodes[edge[1]][1]]
            ax.plot(x, y, color="gray", linewidth=0.5, alpha=0.5)
        except (IndexError, TypeError):
            pass
    
    # Draw nodes with coloring
    for idx, (x, y) in enumerate(nodes):
        if idx in result.buildings:
            ax.plot(x, y, 'o', color='black', markersize=8)
            label = result.building_labels.get(idx, "?")
            ax.text(x + 1, y + 1, str(label), fontsize=8, color="black")
        elif idx in result.open_spaces:
            color = cmap(norm(mean_depth.get(idx, 0)))
            ax.plot(x, y, 'o', color=color, markersize=8)
    
    # Draw doors
    for door in result.doors:
        try:
            open_idx, building_idx = door
            open_pos = nodes[open_idx]
            building_pos = nodes[building_idx]
            ax.plot([open_pos[0], building_pos[0]], [open_pos[1], building_pos[1]], 
                   color="black", linewidth=1.5)
        except (IndexError, TypeError):
            pass



def fig_elevation(result: SimulationResult):
    """Render the digital elevation model for the selected terrain."""
    canvas_size = result.config.canvas_size
    terrain_name = result.config.terrain_provider
    
    # Use terrain sample from result if available
    if hasattr(result, 'terrain_sample') and result.terrain_sample:
        X = result.terrain_sample.get("x")
        Y = result.terrain_sample.get("y")
        Z = result.terrain_sample.get("elevations")
    else:
        # Fallback: generate on-the-fly (for backwards compatibility)
        grid_res = 200
        x = np.linspace(0, canvas_size, grid_res)
        y = np.linspace(0, canvas_size, grid_res)
        X, Y = np.meshgrid(x, y)
        Z = _hill_elevation(X, Y, canvas_size)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    contour = ax.contourf(X, Y, Z, cmap="terrain")
    fig.colorbar(contour, ax=ax, label="Elevation (m)")
    ax.set_title(f"Digital Elevation Model ({terrain_name.replace('_', ' ').title()})")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig
