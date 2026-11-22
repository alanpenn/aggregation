import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Polygon, box

from .engine import SimulationResult

UNASSIGNED_OPEN_COLOR = "#f2e4bc"


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
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=UNASSIGNED_OPEN_COLOR, edgecolor="gray",
                             label="Unassigned open (traversable)")],
              loc="upper right", fontsize="small")
    ax.axis("off")
    fig.tight_layout()
    return fig


def _render_voronoi_aggregation(ax, result, voronoi, cmap, norm, mean_depth, canvas_size):
    """Render aggregation using Voronoi diagram."""
    regions = _finite_voronoi_regions(voronoi, canvas_size)
    for region_index in set(regions) - set(result.buildings) - set(result.open_spaces):
        x, y = zip(*regions[region_index])
        ax.fill(x, y, color=UNASSIGNED_OPEN_COLOR)
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
        else:
            rect = plt.Rectangle((cell_x, cell_y), cell_size, cell_size,
                                 facecolor=UNASSIGNED_OPEN_COLOR, edgecolor="gray", linewidth=0.5)
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
        else:
            ax.plot(x, y, 'o', color=UNASSIGNED_OPEN_COLOR, markersize=8)
    
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


def fig_axial_map(result):
    """Render approximate axial sightlines over the experiment aggregation."""
    fig = fig_aggregation(result)
    ax = fig.axes[0]
    for line in result.axial_map.lines:
        ax.plot(
            [line.start[0], line.end[0]],
            [line.start[1], line.end[1]],
            color="#00d4ff",
            linewidth=2,
            alpha=0.9,
        )
    ax.set_title("Axial sightline approximation")
    return fig


def fig_certified_axial_map(open_polygons, occupied_polygons, paired_open_cells, lines):
    """Render saved research geometry; float conversion is for this figure only."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import LineCollection
    from matplotlib.figure import Figure

    fig = Figure(figsize=(10, 10))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    for cell, polygon in open_polygons.items():
        x, y = polygon.exterior.xy
        color = "white" if cell in paired_open_cells else UNASSIGNED_OPEN_COLOR
        ax.fill(x, y, facecolor=color, edgecolor="lightgrey", linewidth=0.4)
    for polygon in occupied_polygons.values():
        x, y = polygon.exterior.xy
        ax.fill(x, y, facecolor="grey", edgecolor="dimgray", linewidth=0.4)
    segments = [
        (tuple(float(value) for value in line.start),
         tuple(float(value) for value in line.end))
        for line in lines
    ]
    ax.add_collection(LineCollection(segments, colors="#2659a0", linewidths=1.5))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_title("Certified exact research map (display approximation)")
    ax.axis("off")
    fig.tight_layout()
    return fig


def fig_entrance_axial_map(polygons, building_labels, analysis):
    """Show selected lines on an axial mean-depth scale with labelled buildings."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D

    fig = Figure(figsize=(9, 8), layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    excluded = set(analysis["excluded_cells"])
    for cell, polygon in polygons.items():
        x, y = polygon.exterior.xy
        color = "#313946" if cell in building_labels else (
            "#d1a15a" if cell in excluded else "#f4f2ec"
        )
        ax.fill(x, y, facecolor=color, edgecolor="#d6d3cb", linewidth=0.35)
        if cell in building_labels:
            point = polygon.representative_point()
            ax.text(point.x, point.y, str(building_labels[cell]), color="white",
                    fontsize=7, ha="center", va="center", zorder=5)

    lines = analysis["lines"]
    depths = [analysis["axial_depths"][line.line_id] for line in lines]
    low, high = min(depths), max(depths)
    norm = Normalize(low, high) if low != high else Normalize(low - 0.5, high + 0.5)
    collection = LineCollection(
        [[tuple(map(float, line.start)), tuple(map(float, line.end))] for line in lines],
        cmap="RdYlBu", norm=norm, linewidths=1.35, zorder=3,
    )
    collection.set_array(depths)
    ax.add_collection(collection)
    colorbar = fig.colorbar(collection, ax=ax, shrink=0.76)
    colorbar.set_label("Axial mean depth (line changes)")
    if low == high:
        colorbar.set_ticks([low])
    entrances = [tuple(map(float, point)) for point in analysis["entrances"]]
    if entrances:
        ax.scatter(*zip(*entrances), color="#302049", edgecolor="white",
                   s=17, linewidth=0.55, zorder=4)
        ax.legend(handles=[Line2D([], [], marker="o", color="#302049",
                                  linestyle="", label="Building entrance")],
                  loc="upper right")
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_axis_off()
    return fig


def fig_generated_axial_map(result, generated, polygons, show_candidates=False):
    """Render the generated lines on the same cell polygons used for analysis."""
    fig, ax = plt.subplots(figsize=(10, 10))
    for cell in set(polygons) - set(result.buildings):
        x, y = polygons[cell].exterior.xy
        color = "white" if cell in result.open_spaces else UNASSIGNED_OPEN_COLOR
        ax.fill(x, y, facecolor=color, edgecolor="lightgrey", linewidth=0.5)
    for cell in result.buildings:
        x, y = polygons[cell].exterior.xy
        ax.fill(x, y, facecolor="grey", edgecolor="dimgray", linewidth=0.5)
    if show_candidates:
        from matplotlib.collections import LineCollection
        segments = [(line.start, line.end) for line in generated.candidate_lines]
        ax.add_collection(LineCollection(segments, colors="#2659a0", linewidths=0.6, alpha=0.3))
    else:
        colors = plt.get_cmap("tab10")
        for index, line in enumerate(generated.axial_map.lines):
            ax.plot([line.start[0], line.end[0]], [line.start[1], line.end[1]],
                    color=colors(index % 10), linewidth=1.5)
    ax.set_xlim(0, result.config.canvas_size)
    ax.set_ylim(0, result.config.canvas_size)
    ax.set_aspect("equal")
    ax.set_title("All axial candidates" if show_candidates else "Greedy axial map approximation")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=UNASSIGNED_OPEN_COLOR, edgecolor="lightgrey",
                             label="Unassigned open (traversable)")],
              loc="upper right", fontsize="small")
    ax.axis("off")
    fig.tight_layout()
    return fig


def fig_convex_coverage(result, generated, polygons):
    """Show experimental convex regions and which ones selected lines enter."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    fig, ax = plt.subplots(figsize=(10, 10))
    for cell in set(polygons) - set(result.buildings):
        x, y = polygons[cell].exterior.xy
        ax.fill(x, y, facecolor="white", edgecolor="none")
    for cell in result.buildings:
        x, y = polygons[cell].exterior.xy
        ax.fill(x, y, facecolor="grey", edgecolor="dimgray", linewidth=0.4)
    for index, region in sorted(
        generated.coverage_regions.items(),
        key=lambda item: item[0] not in generated.covered_regions,
    ):
        x, y = region.exterior.xy
        covered = index in generated.covered_regions
        ax.fill(x, y, facecolor="#66aadd" if covered else "#e54848",
                edgecolor="#3572a0" if covered else "#b00020",
                linewidth=0.4 if covered else 1.0, alpha=0.12 if covered else 0.55)
    for line in generated.axial_map.lines:
        ax.plot([line.start[0], line.end[0]], [line.start[1], line.end[1]],
                color="#006b3c", linewidth=1.2)
    ax.set_xlim(0, result.config.canvas_size)
    ax.set_ylim(0, result.config.canvas_size)
    ax.set_aspect("equal")
    ax.set_title("Experimental convex-region coverage")
    ax.axis("off")
    ax.legend(handles=[
        Patch(facecolor="#66aadd", edgecolor="#3572a0", label="Covered convex region"),
        Patch(facecolor="#e54848", edgecolor="#b00020", label="Uncovered convex region"),
        Line2D([0], [0], color="#006b3c", label="Selected axial line"),
    ], loc="upper right", fontsize="small")
    fig.tight_layout()
    return fig


def fig_angular_comparison(result, polygons, candidates, greedy_ids, angular, samples, depths):
    """Compare selected lines and show mean angular depth from the fixed samples."""
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(10, 10))
    for cell, polygon in polygons.items():
        color = "grey" if cell in result.buildings else "white"
        ax.fill(*polygon.exterior.xy, facecolor=color, edgecolor="lightgrey", linewidth=0.4)
    angular_ids = {line.line_id for line in angular}
    for line in candidates:
        greedy, optimised = line.line_id in greedy_ids, line.line_id in angular_ids
        if not (greedy or optimised):
            continue
        color = "#7450a0" if greedy and optimised else "#ca5343" if greedy else "#007d58"
        ax.plot([line.start[0], line.end[0]], [line.start[1], line.end[1]],
                color=color, linewidth=1.6, alpha=0.9)
    sample_depths = [[depths[i, j] for j in range(len(samples)) if (i, j) in depths]
                     for i in range(len(samples))]
    means = [sum(values) / len(values) if values else np.nan for values in sample_depths]
    vmax = max((value for value in means if np.isfinite(value)), default=0) or 1
    points = ax.scatter([point[0] for point in samples], [point[1] for point in samples],
                        c=means, cmap="inferno", vmin=0, vmax=vmax,
                        s=45, edgecolor="white", zorder=5)
    fig.colorbar(points, ax=ax, label="Mean angular depth from sample")
    ax.legend(handles=[
        Line2D([0], [0], color="#ca5343", label="Greedy only"),
        Line2D([0], [0], color="#007d58", label="Angular only"),
        Line2D([0], [0], color="#7450a0", label="Both"),
    ], loc="upper right", fontsize="small")
    ax.set_xlim(0, result.config.canvas_size)
    ax.set_ylim(0, result.config.canvas_size)
    ax.set_aspect("equal")
    ax.set_title("Angular and greedy selection comparison")
    ax.axis("off")
    fig.tight_layout()
    return fig


def fig_axial_diagnostics(result, generated, polygons, audit):
    """Show candidate provenance and independently identified missing tangents."""
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(10, 10))
    for cell in set(polygons) - set(result.buildings):
        x, y = polygons[cell].exterior.xy
        color = "white" if cell in result.open_spaces else UNASSIGNED_OPEN_COLOR
        ax.fill(x, y, facecolor=color, edgecolor="lightgrey", linewidth=0.5)
    for cell in result.buildings:
        x, y = polygons[cell].exterior.xy
        ax.fill(x, y, facecolor="grey", edgecolor="dimgray", linewidth=0.5)
    styles = [
        ("occluding", "Mutual tangent present", "#1a9850"),
        ("vertex", "Other vertex candidates", "#8073ac"),
        ("centroid", "Centroid candidates", "#377eb8"),
        ("fallback", "Fallback candidates", "#ff9f1c"),
        ("boundary", "Other boundary candidates", "#999999"),
    ]
    assigned = set()
    from matplotlib.patches import Patch
    legend = [Patch(facecolor=UNASSIGNED_OPEN_COLOR, edgecolor="lightgrey",
                    label="Unassigned open (traversable)")]
    for source, label, color in styles:
        indices = audit.source_indices[source] - assigned
        assigned.update(indices)
        segments = [(generated.candidate_lines[i].start, generated.candidate_lines[i].end)
                    for i in sorted(indices)]
        if segments:
            ax.add_collection(LineCollection(segments, colors=color, linewidths=0.8, alpha=0.65))
            legend.append(Line2D([0], [0], color=color, label=label))
    missing = [list(pair.maximal.coords) for pair in audit.pairs
               if pair.status == "missing"]
    if missing:
        ax.add_collection(LineCollection(missing, colors="#e31a1c", linewidths=1.6,
                                         linestyles="dashed"))
        legend.append(Line2D([0], [0], color="#e31a1c", linestyle="--",
                             label="Missing mutual tangent"))
    indeterminate = [(pair.start, pair.end) for pair in audit.pairs
                     if pair.status == "indeterminate clipping"]
    if indeterminate:
        ax.add_collection(LineCollection(indeterminate, colors="#e6ab02", linewidths=1.5,
                                         linestyles="dotted"))
        legend.append(Line2D([0], [0], color="#e6ab02", linestyle=":",
                             label="Clipping indeterminate (seed)"))
    ax.set_xlim(0, result.config.canvas_size)
    ax.set_ylim(0, result.config.canvas_size)
    ax.set_aspect("equal")
    ax.set_title("Axial candidate audit")
    ax.axis("off")
    if legend:
        ax.legend(handles=legend, loc="upper right", fontsize="small")
    fig.tight_layout()
    return fig


def fig_unresolved_tangents(open_polygons, occupied_polygons, audit):
    """Highlight unresolved seed segments and their independently clipped intervals."""
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(10, 10))
    for polygon in open_polygons.values():
        x, y = polygon.exterior.xy
        ax.fill(x, y, facecolor="white", edgecolor="lightgrey", linewidth=0.4)
    for polygon in occupied_polygons.values():
        x, y = polygon.exterior.xy
        ax.fill(x, y, facecolor="grey", edgecolor="dimgray", linewidth=0.4)
    unresolved = [pair for pair in audit.pairs if pair.status != "present"]
    intervals = [list(pair.maximal.coords) for pair in unresolved if pair.maximal is not None]
    if intervals:
        ax.add_collection(LineCollection(intervals, colors="#377eb8", linewidths=1, alpha=0.65))
    if unresolved:
        ax.add_collection(LineCollection(
            [(pair.start, pair.end) for pair in unresolved],
            colors="#e31a1c", linewidths=2, linestyles="dashed",
        ))
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_title(f"Unresolved mutual tangents ({len(unresolved)})")
    ax.legend(handles=[
        Line2D([0], [0], color="#e31a1c", linestyle="--", label="Unresolved seed"),
        Line2D([0], [0], color="#377eb8", label="Independent clipped interval (if available)"),
    ], loc="upper right", fontsize="small")
    ax.axis("off")
    fig.tight_layout()
    return fig
