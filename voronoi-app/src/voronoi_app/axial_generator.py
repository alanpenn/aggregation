"""Greedy axial-line approximation for polygonal open space."""

from dataclasses import dataclass
from itertools import combinations
from math import hypot
from typing import Dict, List, Set

import networkx as nx
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union

from .axial import AxialLine, AxialMap
from .convex_coverage import convex_regions, line_region_coverage


@dataclass
class DominanceDecision:
    dominated: int
    dominator: int
    accepted: bool
    reason: str


@dataclass
class RedundancyDecision:
    candidate: int
    accepted: bool
    reason: str


@dataclass
class AxialGeneration:
    axial_map: AxialMap
    candidates: int
    candidate_lines: List[AxialLine]
    covered_cells: Set[int]
    open_cells: int
    preserved_rings: int
    required_rings: int
    axial_components: int
    open_components: int
    ambiguous_pairs: List[tuple]
    source_counts: Dict[str, int]
    pre_dominance_lines: int
    dominance_decisions: List[DominanceDecision]
    mean_depth_before: float | None
    mean_depth_after: float | None
    depth_pairs: int
    pre_collective_lines: int
    collective_decisions: List[RedundancyDecision]
    coverage_model: str
    coverage_regions: Dict[int, Polygon]
    covered_regions: Set[int]


class _CoverageSelectionError(ValueError):
    def __init__(self, message, selected, covered):
        super().__init__(message)
        self.selected = selected.copy()
        self.covered = covered.copy()


class ConvexCoverageError(ValueError):
    """A failed convex selection with its partial coverage diagnostic."""

    def __init__(self, message, regions, covered, lines, polygons):
        super().__init__(message)
        self.coverage_regions = regions
        self.covered_regions = covered
        self.axial_map = AxialMap(lines)
        self.polygons = polygons


def _parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type in ("Polygon", "LineString"):
        return [geometry]
    if hasattr(geometry, "geoms"):
        return [part for item in geometry.geoms for part in _parts(item)]
    return []


def _maximal_interval(accessible, start, end, tolerance, *, ambiguities=None):
    """Clip the supporting line to the connected interval containing the seed."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    if length <= tolerance:
        raise ValueError("A candidate direction must have non-zero length")
    ux, uy = dx / length, dy / length
    bounds = accessible.bounds
    reach = max(hypot(bounds[2] - bounds[0], bounds[3] - bounds[1]) * 3, length * 3)
    supporting = LineString([
        (start[0] - reach * ux, start[1] - reach * uy),
        (start[0] + reach * ux, start[1] + reach * uy),
    ])
    clipped = _parts(accessible.intersection(supporting))
    seed = LineString([start, end])
    intervals = []
    for segment in clipped:
        if not isinstance(segment, LineString) or segment.length <= tolerance:
            continue
        coordinates = list(segment.coords)
        projections = [
            (point[0] - start[0]) * ux + (point[1] - start[1]) * uy
            for point in (coordinates[0], coordinates[-1])
        ]
        intervals.append((min(projections), max(projections)))
    if accessible.covers(seed):
        intervals.append((0.0, length))
    intervals.sort()
    merged = []
    for low, high in intervals:
        gap = None
        if merged and low > merged[-1][1]:
            gap = LineString([
                (start[0] + merged[-1][1] * ux, start[1] + merged[-1][1] * uy),
                (start[0] + low * ux, start[1] + low * uy),
            ])
        if merged and (low <= merged[-1][1] or
                       (low <= merged[-1][1] + tolerance and accessible.covers(gap))):
            merged[-1] = (merged[-1][0], max(merged[-1][1], high))
        else:
            merged.append((low, high))
    for index, (low, high) in enumerate(merged):
        if low <= tolerance and high >= length - tolerance:
            if ambiguities is not None:
                if index and low - merged[index - 1][1] <= tolerance:
                    ambiguities.append("uncovered gap before interval within tolerance")
                if index + 1 < len(merged) and merged[index + 1][0] - high <= tolerance:
                    ambiguities.append("uncovered gap after interval within tolerance")
            return LineString([
                (start[0] + low * ux, start[1] + low * uy),
                (start[0] + high * ux, start[1] + high * uy),
            ])
    return None


def _occludes(previous, vertex, following, other, tolerance):
    dx, dy = other[0] - vertex[0], other[1] - vertex[1]
    length = hypot(dx, dy)
    if length <= tolerance:
        return False
    sides = [
        (dx * (point[1] - vertex[1]) - dy * (point[0] - vertex[0])) / length
        for point in (previous, following)
    ]
    return not (min(sides) < -tolerance and max(sides) > tolerance)


def _closed_routes(lines, obstacles):
    """Find obstacle points enclosed by a polygonized, connected line route."""
    if not lines or not obstacles:
        return set()
    faces = list(polygonize(unary_union(lines)))
    return {
        index for index, obstacle in enumerate(obstacles)
        if any(face.covers(obstacle) for face in faces)
    }


def _candidate_graph(candidates, accessible):
    """Build exact line intersections, including overlaps in accessible space."""
    graph = nx.Graph()
    graph.add_nodes_from(range(len(candidates)))
    bounds = [line.bounds for line in candidates]
    for i, left in enumerate(candidates):
        ax, ay, bx, by = bounds[i]
        for j in range(i + 1, len(candidates)):
            cx, cy, dx, dy = bounds[j]
            if bx < cx or dx < ax or by < cy or dy < ay:
                continue
            intersection = left.intersection(candidates[j])
            if not intersection.is_empty and accessible.intersects(intersection):
                graph.add_edge(i, j)
    return graph


def _connect_selected(graph, selected, groups):
    """Connect selected nodes per open component using available candidates."""
    selected = set(selected)
    for group in groups:
        group_selected = selected & group
        if not group_selected:
            raise ValueError("An open-space component has no selected axial lines")
        allowed = graph.subgraph(group)
        while True:
            components = list(nx.connected_components(allowed.subgraph(group_selected)))
            if len(components) <= 1:
                break
            component_of = {node: i for i, component in enumerate(components) for node in component}
            choices = []
            for candidate in group - selected:
                touched = {component_of[n] for n in graph[candidate] if n in component_of}
                if len(touched) > 1:
                    choices.append((-len(touched), candidate))
            if choices:
                selected.add(min(choices)[1])
            else:
                # Some bridges need several lines before they touch both groups.
                best_path = None
                for component in components:
                    distances, paths = nx.multi_source_dijkstra(
                        allowed, component,
                        weight=lambda _u, v, _data: 0 if v in selected else 1,
                    )
                    for target in group_selected - component:
                        if target not in distances:
                            continue
                        path = paths[target]
                        key = (distances[target], len(path), tuple(path))
                        if best_path is None or key < best_path[0]:
                            best_path = (key, path)
                if best_path is None:
                    raise ValueError(
                        f"Axial connectivity cannot be achieved with available candidates: "
                        f"{len(components)} line groups in an open-space component"
                    )
                selected.update(best_path[1])
            group_selected = selected & group
    return selected


def _removal_rejection(candidates, graph, remaining, covers, cells, groups, obstacles,
                       coverage_reason="open-cell coverage"):
    remaining_coverage = set().union(*(covers[i] for i in remaining)) if remaining else set()
    if remaining_coverage != cells:
        return coverage_reason
    if any(not (remaining & group) or
           not nx.is_connected(graph.subgraph(remaining & group)) for group in groups):
        return "open-space connectivity"
    if len(_closed_routes([candidates[i] for i in sorted(remaining)],
                          obstacles)) != len(obstacles):
        return "obstacle circulation ring"
    return None


def _reduce_dominated(candidates, graph, selected, covers, cells, groups, obstacles,
                      coverage_reason="open-cell coverage"):
    """Iteratively remove dominated lines without weakening existing invariants."""
    selected = set(selected)
    decisions = []
    while True:
        removed = False
        current = graph.subgraph(selected)
        for dominated in sorted(selected):
            neighbors = set(current[dominated])
            for dominator in sorted(selected - {dominated}):
                other_neighbors = set(current[dominator])
                if not neighbors - {dominator} <= other_neighbors - {dominated}:
                    continue
                remaining = selected - {dominated}
                rejection = _removal_rejection(
                    candidates, graph, remaining, covers, cells, groups, obstacles, coverage_reason,
                )
                accepted = rejection is None
                reason = rejection or "coverage, connectivity and obstacle rings preserved"
                decisions.append(DominanceDecision(dominated, dominator, accepted, reason))
                if accepted:
                    selected = remaining
                    removed = True
                    break
            if removed:
                break
        if not removed:
            return selected, decisions


def _reduce_collectively_redundant(candidates, graph, selected, covers, cells, groups, obstacles,
                                   coverage_reason="open-cell coverage"):
    """Remove individually dispensable lines until every remaining line is essential."""
    selected = set(selected)
    decisions = []
    while True:
        for candidate in sorted(selected):
            remaining = selected - {candidate}
            rejection = _removal_rejection(
                candidates, graph, remaining, covers, cells, groups, obstacles, coverage_reason,
            )
            accepted = rejection is None
            decisions.append(RedundancyDecision(
                candidate, accepted, rejection or "coverage, connectivity and obstacle rings preserved",
            ))
            if accepted:
                selected = remaining
                break
        else:
            return selected, decisions


def _comparable_mean_depths(graph, before, after):
    """Compare topological distances for the same retained line pairs."""
    before_graph = graph.subgraph(before)
    after_graph = graph.subgraph(after)
    before_total = after_total = count = 0
    for source in sorted(after):
        before_lengths = nx.single_source_shortest_path_length(before_graph, source)
        after_lengths = nx.single_source_shortest_path_length(after_graph, source)
        for target in after:
            if target <= source or target not in before_lengths:
                continue
            if target not in after_lengths:
                raise ValueError("Dominance reduction disconnected previously connected lines")
            before_total += before_lengths[target]
            after_total += after_lengths[target]
            count += 1
    if not count:
        return None, None, 0
    return before_total / count, after_total / count, count


@dataclass
class _SelectionResult:
    selected: Set[int]
    graph: nx.Graph
    groups: List[Set[int]]
    before_dominance: Set[int]
    dominance_decisions: List[DominanceDecision]
    before_collective: Set[int]
    collective_decisions: List[RedundancyDecision]
    mean_depth_before: float | None
    mean_depth_after: float | None
    depth_pairs: int


def _select_axial_candidates(candidates, covers, targets, ring_candidates, accessible,
                             obstacles, tolerance, *, coverage_model="cells"):
    """Apply the existing selector to precomputed coverage requirements."""
    target_label = "open cells" if coverage_model == "cells" else "convex regions"
    coverage_reason = "open-cell coverage" if coverage_model == "cells" else "convex-region coverage"
    selected = set(ring_candidates)
    covered = set().union(*(covers[i] for i in selected)) if selected else set()
    while covered != targets:
        available = set(range(len(candidates))) - selected
        if not available:
            break
        best = max(available, key=lambda i: (len(covers[i] - covered), candidates[i].length, -i))
        if not covers[best] - covered:
            break
        selected.add(best)
        covered.update(covers[best])
    if covered != targets:
        message = f"Axial candidates could not cover {target_label}: {sorted(targets - covered)}"
        if coverage_model == "convex":
            raise _CoverageSelectionError(message, selected, covered)
        raise ValueError(message)
    rings = _closed_routes([candidates[i] for i in sorted(selected)], obstacles)
    if len(rings) != len(obstacles):
        raise ValueError(f"Axial candidates preserve {len(rings)} of {len(obstacles)} occupied obstacle rings")

    parts = [part for part in _parts(accessible) if isinstance(part, Polygon)]
    part_graph = nx.Graph()
    part_graph.add_nodes_from(range(len(parts)))
    for i, part in enumerate(parts):
        for j in range(i + 1, len(parts)):
            if part.intersects(parts[j]):
                part_graph.add_edge(i, j)
    component_geometries = [
        unary_union([parts[i] for i in component])
        for component in nx.connected_components(part_graph)
    ]
    groups = [set() for _ in component_geometries]
    for index, line in enumerate(candidates):
        midpoint = line.interpolate(0.5, normalized=True)
        distances = [component.distance(midpoint) for component in component_geometries]
        group_index = min(range(len(distances)), key=distances.__getitem__)
        if distances[group_index] > tolerance:
            raise ValueError(f"Axial candidate {index} lies outside accessible open space")
        groups[group_index].add(index)
    selected_indices = sorted(selected)
    graph = _candidate_graph([candidates[i] for i in selected_indices], accessible)
    graph = nx.relabel_nodes(graph, dict(enumerate(selected_indices)))
    graph.add_nodes_from(range(len(candidates)))
    if any(not (selected & group) or
           not nx.is_connected(graph.subgraph(selected & group)) for group in groups):
        graph = _candidate_graph(candidates, accessible)
    selected = _connect_selected(graph, selected, groups)

    for index in sorted(selected, key=lambda i: (candidates[i].length, i)):
        remaining = selected - {index}
        remaining_coverage = set().union(*(covers[i] for i in remaining)) if remaining else set()
        if remaining_coverage != targets:
            continue
        if any(not (remaining & group) or
               not nx.is_connected(graph.subgraph(remaining & group)) for group in groups):
            continue
        if len(_closed_routes([candidates[i] for i in sorted(remaining)], obstacles)) != len(obstacles):
            continue
        selected = remaining

    before_dominance = selected.copy()
    selected, dominance_decisions = _reduce_dominated(
        candidates, graph, selected, covers, targets, groups, obstacles, coverage_reason,
    )
    mean_before, mean_after, depth_pairs = _comparable_mean_depths(
        graph, before_dominance, selected,
    )
    before_collective = selected.copy()
    selected, collective_decisions = _reduce_collectively_redundant(
        candidates, graph, selected, covers, targets, groups, obstacles, coverage_reason,
    )
    return _SelectionResult(
        selected, graph, groups, before_dominance, dominance_decisions,
        before_collective, collective_decisions, mean_before, mean_after, depth_pairs,
    )


def generate_axial_map(
    open_polygons: Dict[int, Polygon],
    occupied_polygons: Dict[int, Polygon],
    *,
    include_centroid_candidates: bool = True,
    coverage_model: str = "cells",
) -> AxialGeneration:
    """Generate an approximate axial map or raise if required checks fail.

    Coverage requires a line to enter a cell's interior. A ring is represented
    when the noded linework polygonizes into a closed route around an occupied
    hole of the open-space union.
    """
    if coverage_model not in ("cells", "convex"):
        raise ValueError(f"Unknown axial coverage model: {coverage_model}")
    if not open_polygons:
        raise ValueError("Cannot generate an axial map without open-space polygons")
    for cell, polygon in open_polygons.items():
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError(f"Open cell {cell} has invalid polygon geometry")

    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    if not accessible.is_valid:
        raise ValueError("The union of open-space polygons is invalid")
    if accessible.is_empty:
        raise ValueError("Occupied polygons leave no accessible open space")
    min_x, min_y, max_x, max_y = accessible.bounds
    scale = hypot(max_x - min_x, max_y - min_y)
    tolerance = max(scale * 1e-9, 1e-12)
    boundary_edges = []
    building_corners = []
    obstacles = []
    obstacle_edges = []
    for part in _parts(accessible):
        if not isinstance(part, Polygon):
            continue
        part = orient(part, sign=1.0)
        for ring_index, ring in enumerate([part.exterior, *part.interiors]):
            vertices = list(ring.coords)[:-1]
            edges = [(vertices[i], vertices[(i + 1) % len(vertices)]) for i in range(len(vertices))]
            boundary_edges.extend(edges)
            if ring_index:
                hole = Polygon(ring)
                occupied_part = hole.intersection(occupied)
                enclosed = [
                    component for component in _parts(occupied_part)
                    if isinstance(component, Polygon) and component.area > tolerance * tolerance
                ]
                if enclosed:
                    obstacles.extend(component.representative_point() for component in enclosed)
                    obstacle_edges.append(edges)
            for i, current in enumerate(vertices):
                previous = vertices[i - 1]
                following = vertices[(i + 1) % len(vertices)]
                cross = ((current[0] - previous[0]) * (following[1] - current[1])
                         - (current[1] - previous[1]) * (following[0] - current[0]))
                if cross < -tolerance * tolerance:
                    if not occupied.is_empty and all(
                        occupied.boundary.distance(Point(
                            (current[0] + point[0]) / 2,
                            (current[1] + point[1]) / 2,
                        )) <= tolerance
                        for point in (previous, following)
                    ):
                        building_corners.append((previous, current, following))

    candidates: List[LineString] = []
    candidate_bounds = []
    candidate_sources = []
    candidate_supports = []
    ambiguous_pairs = []

    def add_extended(start, end, source):
        if hypot(end[0] - start[0], end[1] - start[1]) <= tolerance:
            return None
        issues = []
        line = _maximal_interval(accessible, start, end, tolerance, ambiguities=issues)
        if source == "vertex" and issues:
            ambiguous_pairs.append((start, end, "; ".join(issues)))
            return None
        if line is None:
            return None
        bounds = line.bounds
        for index, existing in enumerate(candidates):
            if any(abs(a - b) > tolerance for a, b in zip(bounds, candidate_bounds[index])):
                continue
            if existing.hausdorff_distance(line) <= tolerance:
                candidate_sources[index].add(source)
                candidate_supports[index].add((source, tuple(start), tuple(end)))
                return index
        candidates.append(line)
        candidate_bounds.append(bounds)
        candidate_sources.append({source})
        candidate_supports.append({(source, tuple(start), tuple(end))})
        return len(candidates) - 1

    ring_candidates = set()
    for start, end in boundary_edges:
        add_extended(start, end, "boundary")
    for edges in obstacle_edges:
        for start, end in edges:
            index = add_extended(start, end, "boundary")
            if index is not None:
                ring_candidates.add(index)

    visibility_geometry = accessible.buffer(tolerance)
    for left, right in combinations(building_corners, 2):
        previous, start, following = left
        other_previous, end, other_following = right
        if not (_occludes(previous, start, following, end, tolerance) and
                _occludes(other_previous, end, other_following, start, tolerance)):
            continue
        segment = LineString((start, end))
        if not visibility_geometry.covers(segment):
            continue
        if not accessible.covers(segment):
            ambiguous_pairs.append((start, end, "visible only within tolerance"))
            continue
        before = len(ambiguous_pairs)
        if add_extended(start, end, "vertex") is None and len(ambiguous_pairs) == before:
            ambiguous_pairs.append((start, end, "maximal clipping failed"))

    if include_centroid_candidates:
        centres = []
        for cell in sorted(open_polygons):
            centroid = open_polygons[cell].centroid
            if not open_polygons[cell].contains(centroid):
                centroid = open_polygons[cell].representative_point()
            if accessible.covers(centroid):
                centres.append((centroid.x, centroid.y))
        pairs = sorted(
            combinations(centres, 2),
            key=lambda pair: -hypot(pair[1][0] - pair[0][0], pair[1][1] - pair[0][1]),
        )
        for start, end in pairs:
            if accessible.covers(LineString((start, end))):
                add_extended(start, end, "centroid")

    def coverage(line):
        return {
            cell for cell, polygon in open_polygons.items()
            if line.relate_pattern(polygon, "T********")
        }

    covers = [coverage(line) for line in candidates]
    uncovered = set(open_polygons) - set().union(*covers) if covers else set(open_polygons)
    for cell in sorted(uncovered):
        centre = open_polygons[cell].centroid
        if not open_polygons[cell].contains(centre):
            centre = open_polygons[cell].representative_point()
        step = centre.distance(accessible.boundary) / 2
        if step <= tolerance:
            continue
        for dx, dy in ((1.0, 0.0), (0.0, 1.0)):
            before = len(candidates)
            add_extended((centre.x - step * dx, centre.y - step * dy),
                         (centre.x + step * dx, centre.y + step * dy), "fallback")
            if len(candidates) > before:
                covers.append(coverage(candidates[-1]))

    cell_covers = covers
    regions = convex_regions(accessible) if coverage_model == "convex" else {}
    if regions:
        covers = line_region_coverage(candidates, regions)
    targets = set(regions) if coverage_model == "convex" else set(open_polygons)
    try:
        selection = _select_axial_candidates(
            candidates, covers, targets, ring_candidates, accessible, obstacles, tolerance,
            coverage_model=coverage_model,
        )
    except _CoverageSelectionError as error:
        partial_lines = [
            AxialLine(number, tuple(candidates[index].coords[0]),
                      tuple(candidates[index].coords[-1]))
            for number, index in enumerate(sorted(error.selected))
        ]
        raise ConvexCoverageError(
            str(error), regions, error.covered, partial_lines,
            {**open_polygons, **occupied_polygons},
        ) from error
    selected, graph, groups = selection.selected, selection.graph, selection.groups
    lines = [
        AxialLine(number, tuple(candidates[index].coords[0]), tuple(candidates[index].coords[-1]),
                  {"covered_cells": sorted(cell_covers[index]), "candidate_id": index,
                   **({"covered_regions": sorted(covers[index])} if regions else {})})
        for number, index in enumerate(sorted(selected))
    ]
    axial_components = nx.number_connected_components(graph.subgraph(selected))
    return AxialGeneration(
        axial_map=AxialMap(lines, metadata={
            "source": "greedy_open_space_geometry",
            "axial_components": axial_components,
            "open_components": len(groups),
        }),
        candidates=len(candidates),
        candidate_lines=[
            AxialLine(index, tuple(line.coords[0]), tuple(line.coords[-1]),
                      {"sources": sorted(candidate_sources[index]),
                       "supports": [
                           {"source": source, "start": list(start), "end": list(end)}
                           for source, start, end in sorted(candidate_supports[index])
                       ]})
            for index, line in enumerate(candidates)
        ],
        covered_cells=set().union(*(cell_covers[i] for i in selected)),
        open_cells=len(open_polygons),
        preserved_rings=len(_closed_routes([candidates[i] for i in sorted(selected)], obstacles)),
        required_rings=len(obstacles),
        axial_components=axial_components,
        open_components=len(groups),
        ambiguous_pairs=ambiguous_pairs,
        source_counts={source: sum(source in sources for sources in candidate_sources)
                       for source in ("boundary", "vertex", "centroid", "fallback")},
        pre_dominance_lines=len(selection.before_dominance),
        dominance_decisions=selection.dominance_decisions,
        mean_depth_before=selection.mean_depth_before,
        mean_depth_after=selection.mean_depth_after,
        depth_pairs=selection.depth_pairs,
        pre_collective_lines=len(selection.before_collective),
        collective_decisions=selection.collective_decisions,
        coverage_model=coverage_model,
        coverage_regions=regions,
        covered_regions=set().union(*(covers[i] for i in selected)) if regions else set(),
    )
