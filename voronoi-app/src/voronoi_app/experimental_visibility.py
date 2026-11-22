"""Exact-predicate visibility graph and sampled metric paths for research."""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import hypot, inf, isfinite, nextafter

from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import Polygon, box
from shapely.strtree import STRtree

from .angular import (
    LineClearance, _cross, _crosses_prepared, _direction, _exact_point, _inside_prepared,
    _intersections, _on_segment, _prepare_polygon,
)
from .axial_generator import _parts
from .exact_enumeration import _supports, _vertices


Point = tuple[Fraction, Fraction]


def _outward_bounds(start, end):
    return box(nextafter(float(min(start[0], end[0])), -inf),
               nextafter(float(min(start[1], end[1])), -inf),
               nextafter(float(max(start[0], end[0])), inf),
               nextafter(float(max(start[1], end[1])), inf))


class IndexedClearance:
    """Apply LineClearance's exact predicates after an outward-rounded index filter."""

    def __init__(self, clearance: LineClearance):
        self.clearance = clearance
        self.forbidden = clearance._forbidden
        self.frame = tuple(Fraction.from_float(value) for value in clearance.frame.bounds)
        self.tree = STRtree([
            _outward_bounds((rings[0][1][0], rings[0][1][1]),
                            (rings[0][1][2], rings[0][1][3]))
            for rings in self.forbidden
        ])

    def permits(self, start: Point, end: Point) -> bool:
        if any(not (self.frame[0] < point[0] < self.frame[2]
                    and self.frame[1] < point[1] < self.frame[3]) for point in (start, end)):
            return False
        candidates = sorted(int(i) for i in self.tree.query(_outward_bounds(start, end)))
        if start == end:
            return not any(_inside_prepared(start, self.forbidden[i]) for i in candidates)
        return not any(_crosses_prepared(start, end, self.forbidden[i]) for i in candidates)


@dataclass(frozen=True)
class VisibilityVertex:
    point: Point
    component: int
    buildings: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class VisibilityEdge:
    start: int
    end: int
    length: float
    boundary_following: bool
    tangent_supported: bool


@dataclass(frozen=True)
class VisibilityGraph:
    vertices: tuple[VisibilityVertex, ...]
    edges: tuple[VisibilityEdge, ...]
    components: tuple
    ambiguous_vertices: tuple[Point, ...]
    blocked_edges: int
    ambiguous_edges: int


def _boundary_rings(accessible):
    parts = [part for part in _parts(accessible) if isinstance(part, Polygon)]
    if not parts:
        raise ValueError("Accessible geometry has no polygonal components")
    rings = []
    for component, polygon in enumerate(parts):
        for ring_index, ring in enumerate((polygon.exterior, *polygon.interiors)):
            points = tuple(_exact_point(p) for p in ring.coords)
            rings.append((component, ring_index, points))
    return tuple(parts), rings


def _face_covers_segment(start, end, edges):
    """Exact coverage by a union of collinear boundary intervals."""
    direction = _direction(start, end)
    axis = 0 if direction[0] else 1
    intervals = []
    for a, b in edges:
        if _cross(direction, _direction(start, a)) or _cross(direction, _direction(start, b)):
            continue
        left, right = sorted(((a[axis] - start[axis]) / direction[axis],
                              (b[axis] - start[axis]) / direction[axis]))
        if right >= 0 and left <= 1:
            intervals.append((max(Fraction(0), left), min(Fraction(1), right)))
    reach = Fraction(0)
    for low, high in sorted(intervals):
        if low > reach:
            return False
        reach = max(reach, high)
        if reach >= 1:
            return True
    return False


def build_visibility_graph(accessible, occupied_polygons, *, progress=None):
    """Build the full same-component boundary-vertex graph with exact clearance."""
    from shapely.ops import unary_union

    occupied = unary_union(list(occupied_polygons.values()))
    clearance = LineClearance(accessible, occupied, original_obstacles=occupied_polygons.values())
    indexed = IndexedClearance(clearance)
    components, rings = _boundary_rings(accessible)
    originals, _ = _vertices(occupied_polygons)
    positions = defaultdict(set)
    boundary_edges = []
    for component, ring_index, points in rings:
        for point in points[:-1]:
            positions[point].add((component, ring_index))
        boundary_edges.extend((a, b) for a, b in zip(points, points[1:]) if a != b)
    for point in originals:
        for component, ring_index, points in rings:
            if any(_on_segment(point, a, b) for a, b in zip(points, points[1:])):
                positions[point].add((component, ring_index))
    ambiguous = {point for point, memberships in positions.items() if len(memberships) > 1}
    vertices = []
    for point, memberships in sorted(positions.items()):
        references = tuple(sorted((v.reference.building_id, v.reference.vertex_index)
                                  for v in originals.get(point, ())))
        vertices.append(VisibilityVertex(point, min(memberships)[0], references))
    edge_tree = STRtree([_outward_bounds(a, b) for a, b in boundary_edges])
    edges = []
    blocked = ambiguous_count = 0
    for i, j in combinations(range(len(vertices)), 2):
        left, right = vertices[i], vertices[j]
        if left.component != right.component:
            continue
        if any(_on_segment(point, left.point, right.point) for point in ambiguous):
            ambiguous_count += 1
            continue
        if not indexed.permits(left.point, right.point):
            blocked += 1
            continue
        possible = [boundary_edges[int(k)]
                    for k in edge_tree.query(_outward_bounds(left.point, right.point))]
        follows = _face_covers_segment(left.point, right.point, possible)
        tangent = (
            any(v.convex and _supports(v, right.point) for v in originals.get(left.point, ()))
            and any(v.convex and _supports(v, left.point) for v in originals.get(right.point, ()))
        )
        length = hypot(float(right.point[0] - left.point[0]),
                       float(right.point[1] - left.point[1]))
        edges.append(VisibilityEdge(i, j, length, follows, tangent))
        if progress and len(edges) % 5000 == 0:
            progress(len(edges), blocked)
    return VisibilityGraph(tuple(vertices), tuple(edges), components, tuple(sorted(ambiguous)),
                           blocked, ambiguous_count)


def component_for_point(point, components, *, interior=False):
    matches = []
    for index, polygon in enumerate(components):
        rings = _prepare_polygon(polygon)
        if _inside_prepared(point, rings):
            matches.append(index)
        elif not interior and any(
            _on_segment(point, a, b) for points, _, _ in rings for a, b in zip(points, points[1:])
        ):
            matches.append(index)
    if len(matches) != 1:
        raise ValueError(f"Point has {len(matches)} accessible component matches: {point}")
    return matches[0]


def visible_connections(point, component, graph, clearance):
    """Fix the visible graph-vertex connections of one terminal."""
    if not clearance.permits(point, point):
        raise ValueError("A terminal lies outside the constructed accessible domain")
    return tuple(
        i for i, vertex in enumerate(graph.vertices)
        if vertex.component == component
        and not any(_on_segment(ambiguous, point, vertex.point)
                    for ambiguous in graph.ambiguous_vertices)
        and clearance.permits(point, vertex.point)
    )


def _distance(start, end):
    return hypot(float(end[0] - start[0]), float(end[1] - start[1]))


def shortest_paths(graph, sources, destinations, clearance, *, same_set=False, tolerance=1e-10):
    """Return one deterministic float-metric witness and report possible ties.

    Terminals are (point, component) pairs. Distances are floating-point sums
    of Euclidean lengths; only visibility and interval predicates are exact.
    """
    if not isfinite(tolerance) or tolerance < 0:
        raise ValueError("Metric tie tolerance must be finite and non-negative")
    count = len(graph.vertices)
    rows, cols, weights = [], [], []
    neighbors = [[] for _ in range(count)]
    for edge in graph.edges:
        rows.extend((edge.start, edge.end))
        cols.extend((edge.end, edge.start))
        weights.extend((edge.length, edge.length))
        neighbors[edge.start].append((edge.end, edge.length))
        neighbors[edge.end].append((edge.start, edge.length))
    source_links = [visible_connections(point, component, graph, clearance)
                    for point, component in sources]
    destination_links = source_links if same_set else [
        visible_connections(point, component, graph, clearance) for point, component in destinations
    ]
    results = []
    direct_cache = {}
    for source_id, (start, component) in enumerate(sources):
        links = source_links[source_id]
        extra_rows = [count] * len(links)
        extra_weights = [_distance(start, graph.vertices[i].point) for i in links]
        matrix = coo_matrix(
            (weights + extra_weights, (rows + extra_rows, cols + list(links))),
            shape=(count + 1, count + 1),
        ).tocsr()
        distances, predecessors = dijkstra(matrix, directed=True, indices=count,
                                           return_predecessors=True)
        for destination_id, (end, destination_component) in enumerate(destinations):
            if same_set and source_id == destination_id:
                continue
            if component != destination_component:
                results.append({"source": source_id, "destination": destination_id,
                                "status": "different-component"})
                continue
            key = tuple(sorted((source_id, destination_id))) if same_set else None
            if key is not None and key in direct_cache:
                direct = direct_cache[key]
            else:
                direct = (not any(_on_segment(point, start, end)
                                  for point in graph.ambiguous_vertices)
                          and clearance.permits(start, end))
                if key is not None:
                    direct_cache[key] = direct
            if direct:
                results.append({"source": source_id, "destination": destination_id,
                                "status": "direct", "length": _distance(start, end),
                                "vertices": [], "near_tie": False})
                continue
            options = sorted((float(distances[i]) + _distance(graph.vertices[i].point, end), i)
                             for i in destination_links[destination_id]
                             if isfinite(distances[i]))
            if not options:
                results.append({"source": source_id, "destination": destination_id,
                                "status": "unreachable"})
                continue
            length, current = options[0]
            margin = tolerance * max(1.0, length)
            near_tie = len(options) > 1 and options[1][0] - length <= margin
            path = []
            while current != count:
                if current < 0 or current >= count or len(path) > count:
                    raise ValueError("Invalid metric shortest-path predecessor")
                path.append(current)
                alternatives = sum(
                    abs(float(distances[other]) + weight - float(distances[current])) <= margin
                    for other, weight in neighbors[current] if isfinite(distances[other])
                )
                if current in links:
                    alternatives += abs(_distance(start, graph.vertices[current].point)
                                        - float(distances[current])) <= margin
                near_tie |= alternatives > 1
                current = int(predecessors[current])
            results.append({"source": source_id, "destination": destination_id,
                            "status": "occluded", "length": length,
                            "vertices": list(reversed(path)), "near_tie": bool(near_tie)})
    return results
