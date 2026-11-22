"""Exact rational linework for experimental axial-map certification."""

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import cmp_to_key
from heapq import heappop, heappush
from itertools import combinations
from math import hypot, inf, isfinite, nextafter
from random import Random

import networkx as nx
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .angular import (
    AngularAttachmentError, AngularConnectivityError, LineClearance,
    _angular_attachment_depths_by_origin, _cross, _crosses_prepared,
    _direction, _exact_point, _intersections, _on_segment, _prepare_polygon, _ring_location,
    attach_spatial_samples, topological_sample_depths,
)
from .angular_optimisation import _component_geometries, _obstacles, sample_component_ids
from .axial_generator import _parts
from .convex_coverage import convex_regions

Point = tuple[Fraction, Fraction]


@dataclass(frozen=True)
class VertexReference:
    """Original occupied-polygon vertex, identified by cell and exterior-ring index."""

    building_id: int
    vertex_index: int


@dataclass(frozen=True)
class ExactSupport:
    """Unrounded defining points and their original building-vertex references."""

    source: str
    start: Point
    end: Point
    start_vertices: tuple[VertexReference, ...] = ()
    end_vertices: tuple[VertexReference, ...] = ()


@dataclass(frozen=True)
class ExactCandidate:
    """A maximal interval, stored independently of its float display geometry."""

    line_id: int
    start: Point
    end: Point
    seed_start: Point
    seed_end: Point
    source: str
    aliases: tuple[tuple[str, Point, Point], ...] = ()
    provenance: tuple[ExactSupport, ...] = ()

    def __post_init__(self):
        if not isinstance(self.line_id, int) or isinstance(self.line_id, bool):
            raise ValueError("Exact candidate ID must be an integer")
        for point in (self.start, self.end, self.seed_start, self.seed_end):
            if len(point) != 2 or not all(isinstance(value, Fraction) for value in point):
                raise ValueError("Exact candidate coordinates must be rational pairs")
        if self.start == self.end or self.seed_start == self.seed_end:
            raise ValueError("Exact candidate and seed must have non-zero length")
        if not (_on_segment(self.seed_start, self.start, self.end)
                and _on_segment(self.seed_end, self.start, self.end)):
            raise ValueError("Exact candidate must contain its defining seed")
        for _, start, end in self.aliases:
            if start == end or not (_on_segment(start, self.start, self.end)
                                    and _on_segment(end, self.start, self.end)):
                raise ValueError("Exact candidate must contain every defining seed")
        for support in self.provenance:
            if (support.start == support.end
                    or not all(isinstance(value, Fraction)
                               for value in (*support.start, *support.end))
                    or not (_on_segment(support.start, self.start, self.end)
                            and _on_segment(support.end, self.start, self.end))):
                raise ValueError("Exact candidate must contain each rational provenance support")

    @classmethod
    def from_seed(cls, line_id, start, end, source, clearance: LineClearance):
        seed_start, seed_end = _exact_point(start), _exact_point(end)
        first, last = clearance.maximal_interval(seed_start, seed_end)
        return cls(line_id, first, last, seed_start, seed_end, source)

    @property
    def length(self):
        return hypot(float(self.end[0] - self.start[0]), float(self.end[1] - self.start[1]))


def _bounds(line):
    return box(
        nextafter(float(min(line.start[0], line.end[0])), -inf),
        nextafter(float(min(line.start[1], line.end[1])), -inf),
        nextafter(float(max(line.start[0], line.end[0])), inf),
        nextafter(float(max(line.start[1], line.end[1])), inf),
    )


def candidate_graph(candidates):
    """Use outward-rounded bounds only as a prefilter; certify every edge exactly."""
    graph = nx.Graph()
    graph.add_nodes_from(range(len(candidates)))
    bounds = [_bounds(line) for line in candidates]
    tree = STRtree(bounds)
    for i, line in enumerate(candidates):
        for raw in tree.query(bounds[i]):
            j = int(raw)
            if j > i and _intersections(line.start, line.end, candidates[j].start, candidates[j].end):
                graph.add_edge(i, j)
    return graph


def region_coverage(candidates, regions):
    """Count only positive-length intersections with region interiors."""
    identifiers = list(regions)
    prepared = [_prepare_polygon(regions[i]) for i in identifiers]
    tree = STRtree([regions[i].envelope for i in identifiers])
    return [
        {identifiers[int(index)] for index in tree.query(_bounds(line))
         if _crosses_prepared(line.start, line.end, prepared[int(index)])}
        for line in candidates
    ]


def _segment_graph(candidates):
    points = [{line.start, line.end} for line in candidates]
    line_graph = candidate_graph(candidates)
    for i, j in line_graph.edges:
        nodes = _intersections(candidates[i].start, candidates[i].end,
                               candidates[j].start, candidates[j].end)
        points[i].update(nodes)
        points[j].update(nodes)
    graph = nx.Graph()
    for line, nodes in zip(candidates, points):
        direction = _direction(line.start, line.end)
        axis = 0 if direction[0] else 1
        ordered = sorted(nodes, key=lambda p: (p[axis] - line.start[axis]) / direction[axis])
        graph.add_edges_from(zip(ordered, ordered[1:]))
    return graph


def _compare_directions(left, right):
    def half(vector):
        return 0 if vector[1] > 0 or (vector[1] == 0 and vector[0] >= 0) else 1

    lh, rh = half(left), half(right)
    if lh != rh:
        return -1 if lh < rh else 1
    cross = _cross(left, right)
    return -1 if cross > 0 else (1 if cross < 0 else 0)


def closed_routes(candidates, obstacles):
    """Find occupied witnesses enclosed by bounded faces of exact noded linework."""
    graph = _segment_graph(candidates)
    neighbors = {
        node: sorted(graph[node], key=cmp_to_key(
            lambda left, right: _compare_directions(
                _direction(node, left), _direction(node, right),
            )
        ))
        for node in graph
    }
    visited = set()
    faces = []
    for first, adjacent in graph.edges:
        for start in ((first, adjacent), (adjacent, first)):
            if start in visited:
                continue
            edge = start
            ring = []
            while edge not in visited:
                visited.add(edge)
                previous, current = edge
                ring.append(previous)
                order = neighbors[current]
                edge = (current, order[(order.index(previous) - 1) % len(order)])
            if edge != start:
                raise ValueError("Exact linework produced an invalid face traversal")
            ring.append(ring[0])
            area = sum(_cross(a, b) for a, b in zip(ring, ring[1:]))
            if area > 0:
                faces.append(ring)
    return {
        index for index, point in enumerate(obstacles)
        if any(_ring_location(ring, _exact_point(point)) >= 0 for ring in faces)
    }


@dataclass
class ExactCandidateSet:
    candidates: list[ExactCandidate]
    covers: list[set[int]]
    ring_candidates: set[int]
    rejected: list[tuple[str, Point, Point]]
    fallback_regions: set[int]


@dataclass
class ExactProblem:
    pool: ExactCandidateSet
    accessible: BaseGeometry
    occupied: BaseGeometry
    regions: dict[int, Polygon]
    clearance: LineClearance
    obstacles: list[tuple[float, float]]


def build_candidates(clearance, regions, ring_seeds, seeds, *, progress=None):
    """Build a safe exact pool; preserve rejected seeds and deduplicated provenance."""
    candidates = []
    index_by_interval = {}
    ring_candidates = set()
    rejected = []

    def add(source, start, end, required_ring=False, support=None):
        a, b = _exact_point(start), _exact_point(end)
        if a == b or not clearance.permits_exact(a, b):
            rejected.append((source, a, b))
            if required_ring:
                raise ValueError(f"Required ring seed {a} to {b} is not geometrically permissible")
            return
        line = ExactCandidate.from_seed(len(candidates), a, b, source, clearance)
        if support is not None:
            line = replace(line, provenance=(support,))
        key = tuple(sorted((line.start, line.end)))
        if key in index_by_interval:
            index = index_by_interval[key]
            old = candidates[index]
            provenance = (source, a, b)
            if provenance != (old.source, old.seed_start, old.seed_end) and provenance not in old.aliases:
                candidates[index] = replace(old, aliases=old.aliases + (provenance,))
            old = candidates[index]
            if support is not None and support not in old.provenance:
                candidates[index] = replace(old, provenance=old.provenance + (support,))
        else:
            index = len(candidates)
            index_by_interval[key] = index
            candidates.append(line)
        if required_ring:
            ring_candidates.add(index)

    for seed in ring_seeds:
        if isinstance(seed, ExactSupport):
            add(seed.source, seed.start, seed.end, required_ring=True, support=seed)
        else:
            start, end = seed
            add("ring-boundary", start, end, required_ring=True)
    for index, seed in enumerate(seeds, 1):
        if isinstance(seed, ExactSupport):
            add(seed.source, seed.start, seed.end, support=seed)
        else:
            source, start, end = seed
            add(source, start, end)
        if progress and (index % 16 == 0 or index == len(seeds)):
            progress(index, len(seeds))

    covers = region_coverage(candidates, regions)
    covered = set().union(*covers) if covers else set()
    fallback_regions = set()
    for identifier in sorted(set(regions) - covered):
        polygon = regions[identifier]
        centre = polygon.representative_point()
        start = _exact_point((centre.x, centre.y))
        for vertex in list(polygon.exterior.coords)[:-1]:
            point = _exact_point(vertex)
            end = tuple((start[i] + point[i]) / 2 for i in range(2))
            if (start != end and clearance.permits_exact(start, end)
                    and _crosses_prepared(start, end, _prepare_polygon(polygon))):
                source = f"region-fallback:{identifier}"
                add(source, start, end,
                    support=ExactSupport(source, start, end))
                fallback_regions.add(identifier)
                break
        else:
            raise ValueError(f"No permissible fallback seed for convex region {identifier}")
    if fallback_regions:
        covers = region_coverage(candidates, regions)
    remaining = set(regions) - (set().union(*covers) if covers else set())
    if remaining:
        raise ValueError(f"Exact candidates do not cover convex regions: {sorted(remaining)}")
    return ExactCandidateSet(candidates, covers, ring_candidates, rejected, fallback_regions)


def generate_exact_candidate_pool(open_polygons, occupied_polygons, legacy_candidates,
                                  tangent_pairs):
    """Reconstruct exact candidates, including supplied unresolved tangent seeds."""
    if not open_polygons:
        raise ValueError("Exact candidate generation requires open-space polygons")
    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=occupied_polygons.values())
    regions = convex_regions(accessible)
    min_x, min_y, max_x, max_y = accessible.bounds
    tolerance = max(hypot(max_x - min_x, max_y - min_y) * 1e-9, 1e-12)
    witnesses, _ = _obstacles(accessible, occupied, tolerance)
    ring_seeds = []
    for part in _parts(accessible):
        if not isinstance(part, Polygon):
            continue
        for ring in part.interiors:
            components = _parts(Polygon(ring).intersection(occupied))
            if any(isinstance(component, Polygon) and component.area > tolerance * tolerance
                   for component in components):
                points = list(ring.coords)
                ring_seeds.extend(zip(points[:-1], points[1:]))
    seeds = []
    for line in legacy_candidates:
        supports = line.attributes.get("supports", ())
        if supports:
            seeds.extend((f"candidate:{line.line_id}:{entry['source']}", entry["start"], entry["end"])
                         for entry in supports)
        else:
            seeds.append((f"legacy-stored:{line.line_id}", line.start, line.end))
    seeds.extend((f"recovered-tangent:{index}", start, end)
                 for index, (start, end) in enumerate(tangent_pairs))
    pool = build_candidates(clearance, regions, ring_seeds, seeds)
    return ExactProblem(pool, accessible, occupied, regions, clearance,
                        [(point.x, point.y) for point in witnesses])


def _component_groups(accessible, candidates):
    components = _component_geometries(accessible)
    if len(components) == 1:
        return [set(range(len(candidates)))]
    groups = [set() for _ in components]
    parts = [[_prepare_polygon(part) for part in _parts(component)]
             for component in components]
    for index, line in enumerate(candidates):
        point = tuple((line.start[i] + line.end[i]) / 2 for i in range(2))
        matches = []
        for component, polygons in enumerate(parts):
            if any(_inside_or_boundary(point, rings) for rings in polygons):
                matches.append(component)
        if len(matches) != 1:
            raise ValueError(f"Exact candidate {line.line_id} has ambiguous open-space component")
        groups[matches[0]].add(index)
    return groups


def _inside_or_boundary(point, rings):
    locations = [_ring_location(points, point) for points, _, _ in rings]
    return locations[0] >= 0 and all(location <= 0 for location in locations[1:])


def rejection(pool, selected, targets, groups, graph, obstacles):
    covered = set().union(*(pool.covers[i] for i in selected)) if selected else set()
    if covered != targets:
        return "convex-region coverage"
    if any(not selected.intersection(group)
           or not nx.is_connected(graph.subgraph(selected.intersection(group))) for group in groups):
        return "open-space connectivity"
    lines = [pool.candidates[i] for i in sorted(selected)]
    if len(closed_routes(lines, obstacles)) != len(obstacles):
        return "obstacle circulation ring"
    return None


def _selected_graph(candidates, selected):
    indices = sorted(selected)
    graph = candidate_graph([candidates[i] for i in indices])
    return nx.relabel_nodes(graph, dict(enumerate(indices)))


def _connect_exact_selected(candidates, selected, groups):
    """Connect selected components without materializing the full candidate graph."""
    bounds = [_bounds(line) for line in candidates]
    tree = STRtree(bounds)
    cache = {}

    def neighbors(index):
        if index not in cache:
            left = candidates[index]
            cache[index] = {
                int(raw) for raw in tree.query(bounds[index])
                if int(raw) != index and _intersections(
                    left.start, left.end, candidates[int(raw)].start, candidates[int(raw)].end,
                )
            }
        return cache[index]

    selected = set(selected)
    for group in groups:
        while True:
            group_selected = selected & group
            if not group_selected:
                raise ValueError("An open-space component has no selected axial lines")
            components = list(nx.connected_components(_selected_graph(candidates, group_selected)))
            if len(components) <= 1:
                break
            component_of = {node: number for number, component in enumerate(components)
                            for node in component}
            touched = {}
            for index in sorted(group_selected):
                for other in neighbors(index) & (group - selected):
                    touched.setdefault(other, set()).add(component_of[index])
            choices = [(-len(connected), index) for index, connected in touched.items()
                       if len(connected) > 1]
            if choices:
                selected.add(min(choices)[1])
                continue
            best_path = None
            for component in components:
                queue = [(0, 0, (index,)) for index in sorted(component)]
                best = {index: (0, 0, (index,)) for index in component}
                while queue:
                    distance, hops, path = heappop(queue)
                    node = path[-1]
                    if best.get(node) != (distance, hops, path):
                        continue
                    if node in group_selected - component:
                        key = (distance, len(path), path)
                        if best_path is None or key < best_path[0]:
                            best_path = (key, path)
                        break
                    for other in sorted(neighbors(node) & group):
                        proposal = (distance + (other not in selected), hops + 1, path + (other,))
                        if other not in best or proposal < best[other]:
                            best[other] = proposal
                            heappush(queue, proposal)
            if best_path is None:
                raise ValueError("Exact candidate pool cannot connect an open-space component")
            selected.update(best_path[1])
    return selected


def greedy_selection(pool, regions, accessible, obstacles):
    """Run the existing coverage/length greedy ordering with exact feasibility checks."""
    targets = set(regions)
    selected = set(pool.ring_candidates)
    covered = set().union(*(pool.covers[i] for i in selected)) if selected else set()
    while covered != targets:
        available = set(range(len(pool.candidates))) - selected
        if not available:
            raise ValueError(f"Exact candidates cannot cover convex regions: {sorted(targets - covered)}")
        best = max(available, key=lambda i: (
            len(pool.covers[i] - covered), pool.candidates[i].length, -i,
        ))
        if not pool.covers[best] - covered:
            raise ValueError(f"Exact candidates cannot cover convex regions: {sorted(targets - covered)}")
        selected.add(best)
        covered.update(pool.covers[best])
    groups = _component_groups(accessible, pool.candidates)
    graph = _selected_graph(pool.candidates, selected)
    if any(not selected.intersection(group)
           or not nx.is_connected(graph.subgraph(selected.intersection(group))) for group in groups):
        selected = _connect_exact_selected(pool.candidates, selected, groups)
        graph = _selected_graph(pool.candidates, selected)
    reason = rejection(pool, selected, targets, groups, graph, obstacles)
    if reason:
        raise ValueError(f"Exact greedy seed fails {reason}")
    for index in sorted(selected, key=lambda i: (pool.candidates[i].length, i)):
        remaining = selected - {index}
        if rejection(pool, remaining, targets, groups, graph, obstacles) is None:
            selected = remaining
    while True:
        current = graph.subgraph(selected)
        removed = False
        for dominated in sorted(selected):
            neighbors = set(current[dominated])
            for dominator in sorted(selected - {dominated}):
                other_neighbors = set(current[dominator])
                if not neighbors - {dominator} <= other_neighbors - {dominated}:
                    continue
                remaining = selected - {dominated}
                if rejection(pool, remaining, targets, groups, graph, obstacles) is None:
                    selected = remaining
                    removed = True
                    break
            if removed:
                break
        if not removed:
            break
    while True:
        for index in sorted(selected):
            remaining = selected - {index}
            if rejection(pool, remaining, targets, groups, graph, obstacles) is None:
                selected = remaining
                break
        else:
            clearance = LineClearance(accessible, Polygon())
            for index in selected:
                line = pool.candidates[index]
                if not clearance.permits_exact(line.start, line.end):
                    raise ValueError(f"Exact candidate {line.line_id} leaves accessible space")
            return selected, groups, graph


@dataclass
class ExactAngularResult:
    selected: set[int]
    initial_mean: float
    mean: float
    initial_topological: float
    topological: float
    initial_objective: float
    objective: float
    accepted_moves: int
    iterations: int
    attachment_rejections: int
    safety_rejections: int


def _attach_selected_samples(samples, lines, clearance, cache):
    """Find the same nearest visible attachments using exact distance bounds."""
    attachments = []
    for sample_index, sample in enumerate(samples):
        origin = _exact_point(sample)
        ranked = []
        for line in lines:
            direction = _direction(line.start, line.end)
            length_squared = sum(value * value for value in direction)
            t = sum((origin[i] - line.start[i]) * direction[i] for i in range(2)) / length_squared
            t = min(Fraction(1), max(Fraction(0), t))
            projected = tuple(line.start[i] + t * direction[i] for i in range(2))
            lower_bound = sum((projected[i] - origin[i]) ** 2 for i in range(2))
            ranked.append((lower_bound, line.line_id, line))
        best = None
        for lower_bound, line_id, line in sorted(ranked, key=lambda item: (item[0], item[1])):
            if best is not None and lower_bound > best[0][0]:
                break
            key = (sample_index, line_id)
            if key not in cache:
                try:
                    cache[key] = attach_spatial_samples([sample], [line], clearance)[0]
                except AngularAttachmentError:
                    cache[key] = None
            attachment = cache[key]
            if attachment is None:
                continue
            distance = sum((attachment.point[i] - origin[i]) ** 2 for i in range(2))
            rank = (distance, line_id)
            if best is None or rank < best[0]:
                best = (rank, attachment)
        if best is None:
            raise AngularAttachmentError(f"No visible axial attachment for spatial sample: {sample}")
        attachments.append(best[1])
    return attachments


def angular_selection(pool, initial, regions, accessible, clearance, obstacles, samples, *,
                      mode="fewest", penalty=0.1, iterations=100, seed=42):
    """Run bounded angular exchanges against the same exact candidate pool."""
    if mode not in ("fewest", "penalty") or not isfinite(penalty) or penalty < 0 or iterations < 0:
        raise ValueError("Invalid exact angular search settings")
    groups = _component_groups(accessible, pool.candidates)
    sample_components = sample_component_ids(accessible, samples)
    attachment_cache = {}

    def evaluate(selected):
        lines = [pool.candidates[i] for i in sorted(selected)]
        attachments = _attach_selected_samples(samples, lines, clearance, attachment_cache)
        depths = _angular_attachment_depths_by_origin(
            lines, attachments, components=sample_components,
        )
        topological = topological_sample_depths(lines, attachments, components=sample_components)
        mean = sum(depths.values()) / len(depths)
        topo = sum(topological.values()) / len(topological)
        value = mean + penalty * len(selected) if mode == "penalty" else mean
        key = (len(selected), mean) if mode == "fewest" else (value, len(selected), mean)
        return key, value, mean, topo

    def selection_graph(selected):
        indices = sorted(selected)
        graph = candidate_graph([pool.candidates[i] for i in indices])
        return nx.relabel_nodes(graph, dict(enumerate(indices)))

    selected = set(initial)
    if any(not clearance.permits_exact(pool.candidates[i].start, pool.candidates[i].end)
           for i in selected):
        raise ValueError("Exact angular seed contains a geometrically invalid candidate")
    reason = rejection(pool, selected, set(regions), groups, selection_graph(selected), obstacles)
    if reason:
        raise ValueError(f"Exact angular seed fails {reason}")
    key, objective, mean, topo = evaluate(selected)
    initial_objective, initial_mean, initial_topological = objective, mean, topo
    rng = Random(seed)
    moves = ((1, 0), (0, 1), (1, 1), (2, 2), (1, 2), (2, 3))
    accepted = 0
    attachment_rejections = 0
    safety_rejections = 0
    for iteration in range(iterations):
        add_count, remove_count = moves[iteration % len(moves)]
        available = sorted(set(range(len(pool.candidates))) - selected)
        if len(available) < add_count or len(selected) < remove_count:
            continue
        proposal = ((selected - set(rng.sample(sorted(selected), remove_count)))
                    | set(rng.sample(available, add_count)))
        if any(not clearance.permits_exact(pool.candidates[i].start, pool.candidates[i].end)
               for i in proposal - selected):
            safety_rejections += 1
            continue
        if rejection(pool, proposal, set(regions), groups, selection_graph(proposal), obstacles):
            continue
        try:
            new_key, new_objective, new_mean, new_topo = evaluate(proposal)
        except (AngularAttachmentError, AngularConnectivityError):
            attachment_rejections += 1
            continue
        if new_key < key:
            selected = proposal
            key, objective, mean, topo = new_key, new_objective, new_mean, new_topo
            accepted += 1
    return ExactAngularResult(selected, initial_mean, mean, initial_topological, topo,
                              initial_objective, objective, accepted, iterations,
                              attachment_rejections, safety_rejections)


@dataclass
class TwoForOneResult:
    selected: set[int]
    rounds: list[dict]


def bounded_two_for_one_selection(
    pool, initial, regions, accessible, clearance, obstacles, samples, *,
    max_candidates=300, max_feasibility_checks=300, max_feasible=12, max_rounds=5,
):
    """Explore bounded two-for-one exchanges, ranking feasible maps by angular depth."""
    if min(max_candidates, max_feasibility_checks, max_feasible, max_rounds) <= 0:
        raise ValueError("Two-for-one search limits must be positive")
    groups = _component_groups(accessible, pool.candidates)
    sample_components = sample_component_ids(accessible, samples)
    targets = set(regions)
    positions = {identifier: index for index, identifier in enumerate(sorted(targets))}
    if any(not cover <= targets for cover in pool.covers):
        raise ValueError("Candidate coverage contains an unknown region")

    def mask(identifiers):
        return sum(1 << positions[identifier] for identifier in identifiers)

    target_mask = mask(targets)
    covers = [mask(cover) for cover in pool.covers]
    current = set(initial)
    if any(not clearance.permits_exact(pool.candidates[i].start, pool.candidates[i].end)
           for i in current):
        raise ValueError("Two-for-one seed contains a geometrically invalid candidate")
    graph = _selected_graph(pool.candidates, current)
    reason = rejection(pool, current, targets, groups, graph, obstacles)
    if reason:
        raise ValueError(f"Two-for-one seed fails {reason}")
    cache = {}
    rounds = []
    for _ in range(max_rounds):
        ordered = sorted(current)
        graph = _selected_graph(pool.candidates, current)
        removals = []
        for pair in combinations(ordered, 2):
            covered = 0
            for index in current - set(pair):
                covered |= covers[index]
            removals.append((pair, target_mask & ~covered))
        ranked = sorted(set(range(len(pool.candidates))) - current,
                        key=lambda index: (-pool.candidates[index].length, index))[:max_candidates]
        best = None
        checked = 0
        feasible = 0
        attachment_rejections = 0
        for add in ranked:
            line = pool.candidates[add]
            compatible = [pair for pair, missing in removals if not missing & ~covers[add]]
            if not compatible:
                continue
            if not clearance.permits_exact(line.start, line.end):
                raise ValueError(f"Two-for-one candidate {line.line_id} is geometrically invalid")
            extended = graph.copy()
            extended.add_node(add)
            extended.add_edges_from(
                (add, index) for index in ordered
                if _intersections(line.start, line.end,
                                  pool.candidates[index].start, pool.candidates[index].end)
            )
            for pair in compatible:
                remaining = current - set(pair)
                proposal = remaining | {add}
                if any(not proposal.intersection(group)
                       or not nx.is_connected(extended.subgraph(proposal & group))
                       for group in groups):
                    continue
                checked += 1
                if rejection(pool, proposal, targets, groups, extended, obstacles) is None:
                    lines = [pool.candidates[index] for index in sorted(proposal)]
                    try:
                        attachments = _attach_selected_samples(samples, lines, clearance, cache)
                        depths = _angular_attachment_depths_by_origin(
                            lines, attachments, components=sample_components,
                        )
                        topological = topological_sample_depths(lines, attachments,
                                                                components=sample_components)
                    except (AngularAttachmentError, AngularConnectivityError):
                        attachment_rejections += 1
                    else:
                        feasible += 1
                        angular = sum(depths.values()) / len(depths)
                        topo = sum(topological.values()) / len(topological)
                        choice = (angular, topo, add, pair)
                        if best is None or choice < best:
                            best = choice
                if feasible >= max_feasible or checked >= max_feasibility_checks:
                    break
            if feasible >= max_feasible or checked >= max_feasibility_checks:
                break
        rounds.append({"ranked_candidate_limit": max_candidates, "feasibility_checks": checked,
                       "feasible_evaluated": feasible, "attachment_rejections": attachment_rejections,
                       "best": best})
        if best is None:
            break
        _, _, add, pair = best
        current.difference_update(pair)
        current.add(add)
    return TwoForOneResult(current, rounds)
