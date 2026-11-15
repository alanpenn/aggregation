"""Bounded experimental angular selection, independent of the greedy selector."""

from dataclasses import dataclass
from itertools import zip_longest
from math import hypot, isfinite
from random import Random

import networkx as nx
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .angular import (
    AngularAttachmentError, AngularConnectivityError, LineClearance, _exact_point, _intersections,
    angular_attachment_depths, attach_spatial_samples,
)
from .axial import AxialLine
from .axial_generator import (
    _candidate_graph, _closed_routes, _parts, _removal_rejection, _select_axial_candidates,
)
from .convex_coverage import line_region_coverage


@dataclass
class AngularSelection:
    lines: list[AxialLine]
    samples: list[tuple]
    attachments: list
    depths: dict
    objective: float
    initial_objective: float
    initial_ids: set[int]
    iterations: int
    pool_size: int
    safe_candidates: int
    repaired_seed: bool
    attachment_rejections: int
    covered_regions: int
    preserved_rings: int
    required_rings: int
    components: int
    sample_components: list[int]
    excluded_pairs: int
    accepted_moves: dict[str, int]


def _obstacles(accessible, occupied, tolerance):
    obstacles = []
    boundaries = []
    for part in _parts(accessible):
        if not isinstance(part, Polygon):
            continue
        for ring in part.interiors:
            components = _parts(Polygon(ring).intersection(occupied))
            found = [component for component in components
                     if isinstance(component, Polygon) and component.area > tolerance * tolerance]
            if found:
                obstacles.extend(component.representative_point() for component in found)
                boundaries.append(LineString(ring.coords))
    return obstacles, boundaries


def _component_geometries(accessible):
    parts = [part for part in _parts(accessible) if isinstance(part, Polygon)]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(parts)))
    for i, part in enumerate(parts):
        for j in range(i + 1, len(parts)):
            if part.intersects(parts[j]):
                graph.add_edge(i, j)
    return [unary_union([parts[i] for i in group])
            for group in nx.connected_components(graph)]


def _groups(accessible, candidates, tolerance):
    components = _component_geometries(accessible)
    groups = [set() for _ in components]
    for index, line in enumerate(candidates):
        midpoint = line.interpolate(0.5, normalized=True)
        distances = [component.distance(midpoint) for component in components]
        component = min(range(len(distances)), key=distances.__getitem__)
        if distances[component] > tolerance:
            raise ValueError(f"Candidate {index} lies outside the accessible components")
        groups[component].add(index)
    return groups


def sample_component_ids(accessible, samples):
    components = _component_geometries(accessible)
    result = []
    for sample in samples:
        point = Point(sample)
        matches = [index for index, component in enumerate(components) if component.covers(point)]
        if not matches:
            raise ValueError(f"Spatial sample is outside accessible components: {sample}")
        result.append(matches[0])
    return result


def spatial_samples(regions, count=12):
    """Choose deterministic, dispersed points from the same convex-region geometry."""
    points = set()
    for region in regions.values():
        centre = region.representative_point()
        points.add((centre.x, centre.y))
        for x, y in region.exterior.coords[:-1]:
            points.add(((centre.x + x) / 2, (centre.y + y) / 2))
    points = sorted(points)
    if len(points) < 2:
        raise ValueError("Angular comparison requires at least two distinct spatial samples")
    selected = [points.pop(0)]
    while points and len(selected) < count:
        point = max(points, key=lambda p: (
            min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in selected),
            -p[0], -p[1],
        ))
        selected.append(point)
        points.remove(point)
    return selected


def optimise_angular_map(
    candidates: list[AxialLine], initial_ids: set[int], regions, accessible, occupied,
    samples, *, mode="fewest", penalty=0.1, iterations=100, seed=42, max_pool=192,
):
    """Search bounded feasible exchanges; no global optimum is implied."""
    if mode not in ("fewest", "penalty"):
        raise ValueError(f"Unknown angular optimisation mode: {mode}")
    if not isfinite(penalty) or penalty < 0 or iterations < 0 or max_pool < 1:
        raise ValueError("Penalty and iterations must be non-negative and pool size positive")
    if len(samples) < 2:
        raise ValueError("Angular comparison requires at least two spatial samples")
    sample_components = sample_component_ids(accessible, samples)
    if not any(sample_components.count(component) > 1 for component in sample_components):
        raise ValueError("No spatial sample pairs are in the same accessible component")
    by_id = {line.line_id: line for line in candidates}
    if len(by_id) != len(candidates) or not initial_ids <= set(by_id):
        raise ValueError("Candidate IDs must be unique and include the initial selection")
    clearance = LineClearance(accessible, occupied)
    safe = [line for line in candidates
            if clearance.permits(LineString((line.start, line.end)))]
    geometries = [LineString((line.start, line.end)) for line in safe]
    covers = line_region_coverage(geometries, regions)
    targets = set(regions)
    covered = set().union(*covers) if covers else set()
    if covered != targets:
        raise ValueError(
            "The conservative safety screen cannot cover convex regions: "
            f"{sorted(targets - covered)}"
        )
    min_x, min_y, max_x, max_y = accessible.bounds
    tolerance = max(hypot(max_x - min_x, max_y - min_y) * 1e-9, 1e-12)
    obstacles, boundaries = _obstacles(accessible, occupied, tolerance)
    safe_initial = {i for i, line in enumerate(safe) if line.line_id in initial_ids}
    boundary_indices = {
        i for i, line in enumerate(safe)
        if "boundary" in line.attributes.get("sources", ())
        and any(geometries[i].intersection(boundary).length > tolerance for boundary in boundaries)
    }

    pool = set(safe_initial) | boundary_indices
    if len(pool) > max_pool:
        raise ValueError(
            f"The angular pool limit {max_pool} is smaller than the "
            f"{len(pool)} required initial and boundary candidates"
        )
    uncovered = targets - (set().union(*(covers[i] for i in pool)) if pool else set())
    while uncovered and len(pool) < max_pool:
        remaining = set(range(len(safe))) - pool
        best = max(remaining, key=lambda i: (len(covers[i] & uncovered), geometries[i].length, -i))
        if not covers[best] & uncovered:
            break
        pool.add(best)
        uncovered -= covers[best]
    remaining = set(range(len(safe))) - pool
    ordering = lambda i: (-geometries[i].length, safe[i].line_id)
    ranked = [
        sorted((i for i in remaining if source in safe[i].attributes.get("sources", ())),
               key=ordering)
        for source in ("vertex", "boundary", "centroid")
    ]
    ranked.append(sorted(remaining, key=ordering))
    for row in zip_longest(*ranked):
        for index in row:
            if index is not None and len(pool) < max_pool:
                pool.add(index)
        if len(pool) >= max_pool:
            break
    if uncovered:
        raise ValueError(f"Bounded angular candidate pool cannot cover regions: {sorted(uncovered)}")
    ordered = sorted(pool)
    pool_lines = [safe[i] for i in ordered]
    pool_geometry = [geometries[i] for i in ordered]
    pool_covers = [covers[i] for i in ordered]
    index_of = {line.line_id: i for i, line in enumerate(pool_lines)}
    selected = {index_of[line_id] for line_id in initial_ids if line_id in index_of}
    graph = _candidate_graph(pool_geometry, accessible)
    endpoints = [(_exact_point(line.start), _exact_point(line.end)) for line in pool_lines]
    graph.remove_edges_from(
        (i, j) for i, j in list(graph.edges) if not _intersections(*endpoints[i], *endpoints[j])
    )
    groups = _groups(accessible, pool_geometry, tolerance)
    baseline_safe = len(selected) == len(initial_ids)
    rejection = _removal_rejection(
        pool_geometry, graph, selected, pool_covers, targets, groups, obstacles,
        "convex-region coverage",
    )
    repaired = not baseline_safe or rejection is not None
    if repaired:
        rings = {index_of[safe[i].line_id] for i in boundary_indices if safe[i].line_id in index_of}
        selection = _select_axial_candidates(
            pool_geometry, pool_covers, targets, rings, accessible, obstacles, tolerance,
            coverage_model="convex",
        )
        selected = selection.selected
        rejection = _removal_rejection(
            pool_geometry, graph, selected, pool_covers, targets, groups, obstacles,
            "convex-region coverage",
        )
        if rejection is not None:
            raise ValueError(f"Repaired angular seed fails exact checks: {rejection}")

    attachment_cache = {}

    def evaluate(chosen):
        lines = [pool_lines[i] for i in sorted(chosen)]
        attachments = []
        for sample_index, sample in enumerate(samples):
            choices = []
            for candidate_index in sorted(chosen):
                cache_key = (sample_index, candidate_index)
                if cache_key not in attachment_cache:
                    try:
                        attachment_cache[cache_key] = attach_spatial_samples(
                            [sample], [pool_lines[candidate_index]], clearance,
                        )[0]
                    except AngularAttachmentError:
                        attachment_cache[cache_key] = None
                attachment = attachment_cache[cache_key]
                if attachment is not None:
                    distance = sum((attachment.point[i] - attachment.sample[i]) ** 2 for i in range(2))
                    choices.append((distance, attachment.line_id, attachment))
            if not choices:
                raise AngularAttachmentError(f"No visible axial attachment for spatial sample: {sample}")
            attachments.append(min(choices, key=lambda item: (item[0], item[1]))[2])
        depths = angular_attachment_depths(lines, attachments, components=sample_components)
        mean = sum(depths.values()) / len(depths)
        value = mean + penalty * len(chosen) if mode == "penalty" else mean
        key = (len(chosen), mean) if mode == "fewest" else (value, len(chosen), mean)
        return key, value, attachments, depths

    key, objective, attachments, depths = evaluate(selected)
    first_objective = objective
    first_ids = {pool_lines[i].line_id for i in selected}
    rng = Random(seed)
    attachment_rejections = 0
    moves = (("addition", 1, 0), ("removal", 0, 1), ("one-for-one", 1, 1),
             ("two-for-two", 2, 2), ("two-for-one", 1, 2), ("three-for-two", 2, 3))
    accepted_moves = {name: 0 for name, _, _ in moves}
    for iteration in range(iterations):
        move, add_count, remove_count = moves[iteration % len(moves)]
        available = sorted(set(range(len(pool_lines))) - selected)
        if len(available) < add_count or len(selected) < remove_count:
            continue
        proposal = ((selected - set(rng.sample(sorted(selected), remove_count)))
                    | set(rng.sample(available, add_count)))
        if _removal_rejection(
            pool_geometry, graph, proposal, pool_covers, targets, groups, obstacles,
            "convex-region coverage",
        ) is not None:
            continue
        try:
            candidate_key, candidate_value, candidate_attachments, candidate_depths = evaluate(proposal)
        except (AngularAttachmentError, AngularConnectivityError):
            attachment_rejections += 1
            continue
        if candidate_key < key:
            selected = proposal
            accepted_moves[move] += 1
            key, objective, attachments, depths = (
                candidate_key, candidate_value, candidate_attachments, candidate_depths,
            )
    return AngularSelection(
        [pool_lines[i] for i in sorted(selected)], list(samples), attachments, depths,
        objective, first_objective, first_ids, iterations, len(pool_lines), len(safe), repaired,
        attachment_rejections,
        len(set().union(*(pool_covers[i] for i in selected))),
        len(_closed_routes([pool_geometry[i] for i in sorted(selected)], obstacles)),
        len(obstacles), nx.number_connected_components(graph.subgraph(selected)),
        sample_components, len(samples) * (len(samples) - 1) - len(depths),
        accepted_moves,
    )
