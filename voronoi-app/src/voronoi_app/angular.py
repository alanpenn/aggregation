"""Direction-aware angular shortest paths on noded axial linework."""

from dataclasses import dataclass
from fractions import Fraction
from math import atan2, isfinite, pi
from typing import Protocol, Sequence

import networkx as nx
from shapely.geometry import LineString, Polygon, box

from .axial_generator import _parts

Coordinate = tuple[float | Fraction, float | Fraction]


class AngularLine(Protocol):
    @property
    def line_id(self) -> int: ...

    @property
    def start(self) -> Coordinate: ...

    @property
    def end(self) -> Coordinate: ...


class AngularAttachmentError(ValueError):
    """A sample has no permitted connector to the selected network."""


class AngularConnectivityError(ValueError):
    """Attached samples cannot reach one another on the selected network."""


def angular_turn_cost(incoming: Coordinate, outgoing: Coordinate) -> float:
    """Return angular change divided by a right angle, including reversals."""
    if not all(isinstance(value, Fraction) or isfinite(value)
               for value in (*incoming, *outgoing)):
        raise ValueError("Movement directions must be finite")
    incoming_scale = max(abs(value) for value in incoming)
    outgoing_scale = max(abs(value) for value in outgoing)
    if incoming_scale == 0 or outgoing_scale == 0:
        raise ValueError("Movement directions must have non-zero length")
    ax, ay = (float(value / incoming_scale) for value in incoming)
    bx, by = (float(value / outgoing_scale) for value in outgoing)
    cross = ax * by - ay * bx
    dot = ax * bx + ay * by
    return 2 * atan2(abs(cross), dot) / pi


def _direction(start: Coordinate, end: Coordinate) -> Coordinate:
    return end[0] - start[0], end[1] - start[1]


def _exact_point(point):
    return tuple(value if isinstance(value, Fraction) else Fraction.from_float(float(value))
                 for value in point)


def _cross(left, right):
    return left[0] * right[1] - left[1] * right[0]


def _on_segment(point, start, end):
    return (_cross(_direction(start, end), _direction(start, point)) == 0
            and all(min(start[i], end[i]) <= point[i] <= max(start[i], end[i])
                    for i in range(2)))


def _intersections(a, b, c, d):
    left = _direction(a, b)
    right = _direction(c, d)
    offset = _direction(a, c)
    denominator = _cross(left, right)
    if denominator:
        t = _cross(offset, right) / denominator
        u = _cross(offset, left) / denominator
        if 0 <= t <= 1 and 0 <= u <= 1:
            return {tuple(a[i] + t * left[i] for i in range(2))}
        return set()
    if _cross(offset, left):
        return set()
    return {point for point in (a, b, c, d)
            if _on_segment(point, a, b) and _on_segment(point, c, d)}


def _ring_location(ring, point):
    inside = False
    for start, end in zip(ring, ring[1:]):
        if (_cross(_direction(start, end), _direction(start, point)) == 0
                and min(start[0], end[0]) <= point[0] <= max(start[0], end[0])
                and min(start[1], end[1]) <= point[1] <= max(start[1], end[1])):
            return 0
        if (start[1] > point[1]) != (end[1] > point[1]):
            x = start[0] + (point[1] - start[1]) * (end[0] - start[0]) / (end[1] - start[1])
            if x > point[0]:
                inside = not inside
    return 1 if inside else -1


def _crosses_polygon_interior(line: LineString, polygon: Polygon) -> bool:
    """Test the stored float coordinates as exact rationals, permitting boundary contact."""
    start, end = [_exact_point(point) for point in line.coords]
    return _crosses_polygon_interior_exact(start, end, polygon)


def _crosses_polygon_interior_exact(start, end, polygon):
    return _crosses_prepared(start, end, _prepare_polygon(polygon))


def _prepare_polygon(polygon):
    rings = []
    for ring in (polygon.exterior, *polygon.interiors):
        points = [_exact_point(point) for point in ring.coords]
        bounds = (min(point[0] for point in points), min(point[1] for point in points),
                  max(point[0] for point in points), max(point[1] for point in points))
        edges = [(a, b, (min(a[0], b[0]), min(a[1], b[1]),
                         max(a[0], b[0]), max(a[1], b[1])))
                 for a, b in zip(points, points[1:])]
        rings.append((points, bounds, edges))
    return rings


def _overlap(left, right):
    return not (left[2] < right[0] or right[2] < left[0]
                or left[3] < right[1] or right[3] < left[1])


def _inside_prepared(point, rings):
    locations = [
        _ring_location(points, point) if (bounds[0] <= point[0] <= bounds[2]
                                          and bounds[1] <= point[1] <= bounds[3]) else -1
        for points, bounds, _ in rings
    ]
    return locations[0] == 1 and all(location == -1 for location in locations[1:])


def _crosses_prepared(start, end, rings):
    direction = _direction(start, end)
    bounds = (min(start[0], end[0]), min(start[1], end[1]),
              max(start[0], end[0]), max(start[1], end[1]))
    if not _overlap(bounds, rings[0][1]):
        return False
    events = {Fraction(0), Fraction(1)}
    for _, ring_bounds, edges in rings:
        if not _overlap(bounds, ring_bounds):
            continue
        for a, b, edge_bounds in edges:
            if not _overlap(bounds, edge_bounds):
                continue
            edge = _direction(a, b)
            relative = _direction(start, a)
            denominator = _cross(direction, edge)
            if denominator:
                t = _cross(relative, edge) / denominator
                u = _cross(relative, direction) / denominator
                if 0 < t < 1 and 0 <= u <= 1:
                    events.add(t)
            elif _cross(relative, direction) == 0:
                axis = 0 if direction[0] else 1
                for point in (a, b):
                    t = (point[axis] - start[axis]) / direction[axis]
                    if 0 < t < 1:
                        events.add(t)
    ordered = sorted(events)
    for low, high in zip(ordered, ordered[1:]):
        t = (low + high) / 2
        point = tuple(start[i] + t * direction[i] for i in range(2))
        if _inside_prepared(point, rings):
            return True
    return False


class LineClearance:
    """Conservative clearance checks against the occupied union and accessible domain."""

    def __init__(self, accessible, occupied, *, original_obstacles=()):
        original_obstacles = tuple(original_obstacles)
        if accessible.is_empty or not accessible.is_valid:
            raise ValueError("Angular analysis requires valid, non-empty accessible space")
        if not occupied.is_valid:
            raise ValueError("Angular analysis requires valid occupied geometry")
        if any(not isinstance(polygon, Polygon) or polygon.is_empty or not polygon.is_valid
               for polygon in original_obstacles):
            raise ValueError("Angular analysis requires valid original obstacle polygons")
        self.accessible = accessible
        self.obstacles = [part for part in _parts(occupied) if isinstance(part, Polygon)]
        min_x, min_y, max_x, max_y = accessible.bounds
        scale = max(max_x - min_x, max_y - min_y, 1)
        self.frame = box(min_x - scale, min_y - scale, max_x + scale, max_y + scale)
        self.outside = [
            part for part in _parts(self.frame.difference(accessible))
            if isinstance(part, Polygon)
        ]
        self._forbidden = [_prepare_polygon(polygon)
                           for polygon in (*self.outside, *self.obstacles, *original_obstacles)]

    def permits(self, line: LineString) -> bool:
        if not self.accessible.covers(line):
            return False
        return self.permits_exact(*line.coords)

    def permits_exact(self, start, end) -> bool:
        start, end = _exact_point(start), _exact_point(end)
        bounds = tuple(Fraction.from_float(value) for value in self.frame.bounds)
        if any(not (bounds[0] < point[0] < bounds[2]
                    and bounds[1] < point[1] < bounds[3]) for point in (start, end)):
            return False
        if start == end:
            return not any(_inside_prepared(start, rings) for rings in self._forbidden)
        return not any(
            _crosses_prepared(start, end, rings) for rings in self._forbidden
        )

    def maximal_interval(self, start, end):
        """Return exact rational endpoints of the clear interval containing a seed.

        The result must not be converted to floats for geometric predicates:
        rounding an endpoint can move the entire support into an obstacle.
        """
        start, end = _exact_point(start), _exact_point(end)
        if start == end:
            raise ValueError("A maximal interval requires two distinct seed points")
        if not self.permits_exact(start, end):
            raise ValueError("The seed crosses a forbidden interior or leaves the frame")
        direction = _direction(start, end)
        bounds = tuple(Fraction.from_float(value) for value in self.frame.bounds)
        limits = []
        for axis in range(2):
            if direction[axis]:
                values = ((bounds[axis] - start[axis]) / direction[axis],
                          (bounds[axis + 2] - start[axis]) / direction[axis])
                limits.append((min(values), max(values)))
        low = max(limit[0] for limit in limits)
        high = min(limit[1] for limit in limits)
        left = tuple(start[i] + low * direction[i] for i in range(2))
        right = tuple(start[i] + high * direction[i] for i in range(2))
        axis = 0 if direction[0] else 1
        events = {low, high, Fraction(0), Fraction(1)}
        for rings in self._forbidden:
            for _, _, edges in rings:
                for a, b, _ in edges:
                    for point in _intersections(left, right, a, b):
                        events.add((point[axis] - start[axis]) / direction[axis])
        ordered = sorted(events)
        clear = []
        for a, b in zip(ordered, ordered[1:]):
            t = (a + b) / 2
            point = tuple(start[i] + t * direction[i] for i in range(2))
            clear.append(not any(_inside_prepared(point, rings) for rings in self._forbidden))
        first = ordered.index(Fraction(0))
        last = ordered.index(Fraction(1))
        if not all(clear[first:last]):
            raise ValueError("The seed crosses a forbidden interior")
        while first and clear[first - 1]:
            first -= 1
        while last < len(clear) and clear[last]:
            last += 1
        return tuple(tuple(start[i] + t * direction[i] for i in range(2))
                     for t in (ordered[first], ordered[last]))


@dataclass(frozen=True)
class SampleAttachment:
    sample: tuple
    point: tuple
    line_id: int

    @property
    def arrival(self):
        return None if self.sample == self.point else _direction(self.sample, self.point)

    @property
    def departure(self):
        return None if self.sample == self.point else _direction(self.point, self.sample)


def attach_spatial_samples(samples, lines: Sequence[AngularLine], clearance: LineClearance):
    """Attach each sample by its shortest visible connector to the selected linework."""
    vertices = {
        _exact_point(point)
        for polygon in _parts(clearance.accessible) if isinstance(polygon, Polygon)
        for ring in (polygon.exterior, *polygon.interiors)
        for point in list(ring.coords)[:-1]
    }
    attachments = []
    for sample in samples:
        origin = _exact_point(sample)
        if not clearance.permits_exact(origin, origin):
            raise ValueError(f"Spatial sample is outside accessible space: {sample}")
        best = None
        for line in lines:
            a, b = _exact_point(line.start), _exact_point(line.end)
            direction = _direction(a, b)
            length_squared = sum(value * value for value in direction)
            projection = sum((origin[i] - a[i]) * direction[i] for i in range(2)) / length_squared
            projection = min(Fraction(1), max(Fraction(0), projection))

            def at(t):
                return tuple(a[i] + t * direction[i] for i in range(2))

            point = at(projection)
            candidates = [projection]
            if not clearance.permits_exact(origin, point):
                events = {Fraction(0), Fraction(1)}
                for vertex in vertices:
                    ray = _direction(origin, vertex)
                    denominator = _cross(direction, ray)
                    offset = _direction(a, origin)
                    if denominator:
                        t = _cross(offset, ray) / denominator
                        distance = _cross(offset, direction) / denominator
                        if 0 <= t <= 1 and distance >= 0:
                            events.add(t)
                    elif _on_segment(vertex, a, b):
                        axis = 0 if direction[0] else 1
                        events.add((vertex[axis] - a[axis]) / direction[axis])
                ordered = sorted(events)
                candidates = list(ordered)
                for low, high in zip(ordered, ordered[1:]):
                    if clearance.permits_exact(origin, at((low + high) / 2)):
                        candidates.append(min(high, max(low, projection)))
            for t in candidates:
                point = at(t)
                distance_squared = sum((point[i] - origin[i]) ** 2 for i in range(2))
                key = (distance_squared, line.line_id, t)
                if (best is None or key < best[0]) and clearance.permits_exact(origin, point):
                    best = (key, SampleAttachment(origin, point, line.line_id))
        if best is None:
            raise AngularAttachmentError(f"No visible axial attachment for spatial sample: {sample}")
        attachments.append(best[1])
    return attachments


@dataclass
class AngularNetwork:
    """A segment graph whose movement states retain the direction of arrival."""

    segments: nx.Graph
    states: nx.DiGraph

    @classmethod
    def from_lines(
        cls, lines: Sequence[AngularLine], stops: list[Coordinate], *,
        clearance: LineClearance | None = None,
    ) -> "AngularNetwork":
        if not lines:
            raise ValueError("An angular network requires at least one axial line")
        if clearance is not None:
            geometries = [LineString((line.start, line.end)) for line in lines]
            for line, geometry in zip(lines, geometries):
                if not clearance.permits(geometry):
                    raise ValueError(f"Axial line {line.line_id} is not geometrically valid")
        endpoints = [(_exact_point(line.start), _exact_point(line.end)) for line in lines]
        node_points = [{start, end} for start, end in endpoints]
        for i, (start, end) in enumerate(endpoints):
            for j in range(i + 1, len(endpoints)):
                points = _intersections(start, end, *endpoints[j])
                node_points[i].update(points)
                node_points[j].update(points)
        stop_points = [_exact_point(point) for point in stops]
        for point in stop_points:
            matched = False
            for (start, end), points in zip(endpoints, node_points):
                if _on_segment(point, start, end):
                    points.add(point)
                    matched = True
            if not matched:
                raise ValueError(f"Spatial sample is not attached to an axial line: {point}")
        graph = nx.Graph()
        for (start, end), points in zip(endpoints, node_points):
            direction = _direction(start, end)
            axis = 0 if direction[0] else 1
            ordered = sorted(points, key=lambda point: (point[axis] - start[axis]) / direction[axis])
            for left, right in zip(ordered, ordered[1:]):
                graph.add_edge(left, right)
        states = nx.DiGraph()
        for left, right in graph.edges:
            states.add_node((left, right))
            states.add_node((right, left))
        for node in graph:
            for previous in graph[node]:
                for following in graph[node]:
                    states.add_edge(
                        (previous, node), (node, following),
                        weight=angular_turn_cost(_direction(previous, node),
                                                 _direction(node, following)),
                    )
        return cls(graph, states)

    def shortest_depth(
        self, origin: Coordinate, destination: Coordinate, *,
        arrival: Coordinate | None = None, departure: Coordinate | None = None,
    ) -> float:
        """Minimise cumulative angular change, including optional connector headings."""
        origin, destination = _exact_point(origin), _exact_point(destination)
        if origin not in self.segments or destination not in self.segments:
            raise ValueError("Both endpoints must be attached to the angular network")
        if arrival is not None:
            angular_turn_cost(arrival, arrival)
        if departure is not None:
            angular_turn_cost(departure, departure)
        if origin == destination:
            if arrival is None or departure is None:
                return 0.0
            return angular_turn_cost(arrival, departure)

        start = object()
        end = object()
        graph = self.states.copy()
        for following in self.segments[origin]:
            vector = _direction(origin, following)
            graph.add_edge(start, (origin, following),
                           weight=angular_turn_cost(arrival, vector) if arrival else 0.0)
        for previous in self.segments[destination]:
            vector = _direction(previous, destination)
            graph.add_edge((previous, destination), end,
                           weight=angular_turn_cost(vector, departure) if departure else 0.0)
        try:
            return nx.shortest_path_length(graph, start, end, weight="weight")
        except nx.NetworkXNoPath as error:
            raise AngularConnectivityError("The attached spatial samples are not connected") from error


def angular_sample_depths(samples, lines: Sequence[AngularLine], clearance: LineClearance, *,
                          components=None):
    """Measure directed angular depth between identical, explicitly attached samples."""
    attachments = attach_spatial_samples(samples, lines, clearance)
    return attachments, angular_attachment_depths(
        lines, attachments, clearance=clearance, components=components,
    )


def angular_attachment_depths(lines, attachments, *, clearance=None, components=None):
    network = AngularNetwork.from_lines(
        lines, [attachment.point for attachment in attachments], clearance=clearance,
    )
    depths = {}
    for i, origin in enumerate(attachments):
        for j, destination in enumerate(attachments):
            if i != j and (components is None or components[i] == components[j]):
                depths[i, j] = network.shortest_depth(
                    origin.point, destination.point,
                    arrival=origin.arrival, departure=destination.departure,
                )
    if not depths:
        raise ValueError("No spatial sample pairs are in the same accessible component")
    return depths


def _angular_attachment_depths_by_origin(lines, attachments, *, clearance=None, components=None):
    """Calculate the same directed depths using one search per origin."""
    network = AngularNetwork.from_lines(
        lines, [attachment.point for attachment in attachments], clearance=clearance,
    )
    graph = network.states.copy()
    depths = {}
    for i, origin in enumerate(attachments):
        destinations = [
            (j, destination) for j, destination in enumerate(attachments)
            if i != j and (components is None or components[i] == components[j])
        ]
        if not destinations:
            continue
        if origin.arrival is not None:
            angular_turn_cost(origin.arrival, origin.arrival)
        source = object()
        for following in network.segments[origin.point]:
            vector = _direction(origin.point, following)
            graph.add_edge(source, (origin.point, following),
                           weight=angular_turn_cost(origin.arrival, vector) if origin.arrival else 0.0)
        distances = nx.single_source_dijkstra_path_length(graph, source, weight="weight")
        graph.remove_node(source)
        for j, destination in destinations:
            if destination.departure is not None:
                angular_turn_cost(destination.departure, destination.departure)
            if origin.point == destination.point:
                depths[i, j] = (
                    angular_turn_cost(origin.arrival, destination.departure)
                    if origin.arrival is not None and destination.departure is not None else 0.0
                )
                continue
            choices = []
            for previous in network.segments[destination.point]:
                state = (previous, destination.point)
                if state in distances:
                    vector = _direction(previous, destination.point)
                    final = angular_turn_cost(vector, destination.departure) if destination.departure else 0.0
                    choices.append(distances[state] + final)
            if not choices:
                raise AngularConnectivityError("The attached spatial samples are not connected")
            depths[i, j] = min(choices)
    if not depths:
        raise ValueError("No spatial sample pairs are in the same accessible component")
    return depths


def topological_sample_depths(lines: Sequence[AngularLine], attachments, *, components=None):
    """Measure line-to-line depth for the same attached spatial samples."""
    graph = nx.Graph()
    graph.add_nodes_from(line.line_id for line in lines)
    endpoints = [(_exact_point(line.start), _exact_point(line.end)) for line in lines]
    for i, line in enumerate(lines):
        for j in range(i + 1, len(lines)):
            if _intersections(*endpoints[i], *endpoints[j]):
                graph.add_edge(line.line_id, lines[j].line_id)
    depths = {}
    for i, origin in enumerate(attachments):
        for j, destination in enumerate(attachments):
            if i == j or (components is not None and components[i] != components[j]):
                continue
            try:
                depths[i, j] = nx.shortest_path_length(graph, origin.line_id, destination.line_id)
            except nx.NetworkXNoPath as error:
                raise AngularConnectivityError("The attached axial lines are not connected") from error
    return depths
