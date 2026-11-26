"""Exact spatial graph construction and common global configurational measures."""

from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from math import atan2, degrees, fsum

import networkx as nx
import numpy as np

from .angular import _cross, _direction, _intersections
from .region_incidence_angular import halfplanes


def rational_points(points):
    return tuple(tuple(map(Fraction, point)) for point in points)


def axial_graph(lines):
    """Map canonical line IDs to rational endpoints and connect exact contacts."""
    graph = nx.Graph()
    lines = {identifier: rational_points(endpoints) for identifier, endpoints in lines.items()}
    for identifier, endpoints in sorted(lines.items()):
        if endpoints[0] == endpoints[1]:
            raise ValueError(f"Zero-length axial line {identifier}")
        graph.add_node(identifier, points=endpoints)
    for (i, a), (j, b) in combinations(sorted(lines.items()), 2):
        contacts = tuple(sorted(_intersections(*a, *b)))
        if contacts:
            graph.add_edge(i, j, contacts=contacts)
    return graph


def segment_graph(axial):
    """Split at every exact contact and merge identical intervals with their ownership."""
    stops = {i: set(row["points"]) for i, row in axial.nodes(data=True)}
    for i, j, row in axial.edges(data=True):
        stops[i].update(row["contacts"])
        stops[j].update(row["contacts"])
    ownership = defaultdict(set)
    for owner, points in stops.items():
        ordered = sorted(points)
        for a, b in zip(ordered, ordered[1:]):
            ownership[a, b].add(owner)
    graph = nx.Graph()
    junctions = defaultdict(list)
    for i, ((a, b), owners) in enumerate(sorted(ownership.items())):
        graph.add_node(i, points=(a, b), owners=sorted(owners))
        junctions[a].append((i, _direction(a, b)))
        junctions[b].append((i, _direction(b, a)))
    for point, segments in junctions.items():
        for (i, u), (j, v) in combinations(segments, 2):
            dot = sum(a * b for a, b in zip(u, v))
            angle = degrees(atan2(float(abs(_cross(u, v))), float(-dot)))
            turn = round(angle * 1_000_000)
            # A simple path has at most n-1 transitions, so angle always wins.
            graph.add_edge(i, j, junction=point, turn_microdegrees=turn,
                           angular_weight=len(graph) * turn + 1)
    return graph


def polygon_area(points):
    return abs(sum(_cross(p, q) for p, q in zip(points, points[1:] + points[:1]))) / 2


def intersection_area(points, planes):
    """Clip a convex ring by exact oriented half-planes."""
    for a, direction in planes:
        clipped = []
        for p, q in zip(points, points[1:] + points[:1]):
            f = _cross(direction, _direction(a, p))
            g = _cross(direction, _direction(a, q))
            if f >= 0:
                clipped.append(p)
            if (f >= 0) != (g >= 0):
                clipped.append(tuple(x + f / (f - g) * (y - x) for x, y in zip(p, q)))
        points = clipped
        if len(points) < 3:
            return Fraction(0)
    return polygon_area(points)


def convex_graph(polygons):
    """Connect only strictly positive rational overlap areas."""
    graph = nx.Graph()
    bounds = []
    planes = {}
    for key, points in sorted(polygons.items()):
        points = rational_points(points)
        if points[0] == points[-1]:
            points = points[:-1]
        planes[key] = halfplanes(points + points[:1])
        graph.add_node(key, points=points)
        x, y = zip(*points)
        bounds.append((min(x), max(x), min(y), max(y), key))
    bounds.sort()
    for i, (_, right, bottom, top, key) in enumerate(bounds):
        for left, _, low, high, other in bounds[i + 1:]:
            if left >= right:
                break
            if bottom < high and low < top:
                area = intersection_area(graph.nodes[key]["points"], planes[other])
                if area > 0:
                    graph.add_edge(key, other, overlap_area=area)
    return graph


def measures(graph, *, angular=False):
    """Global depths and centralities under the pilot's frozen metric."""
    n = len(graph)
    weight = "angular_weight" if angular else None
    choice = nx.betweenness_centrality(graph, normalized=True, endpoints=False, weight=weight)
    distances = (nx.all_pairs_dijkstra_path_length(graph, weight=weight) if angular
                 else nx.all_pairs_shortest_path_length(graph))
    rows = {}
    for node, nearby in distances:
        reach = len(nearby) - 1
        values = (value // n / 1_000_000 for value in nearby.values()) if angular else nearby.values()
        depth = fsum(values) / reach if reach else None
        integration = (reach / (n - 1) / (1 + depth)) if reach else 0.0
        rows[node] = dict(connectivity=graph.degree(node), mean_depth=depth,
                          integration=integration, choice=choice[node], reachable=reach)
    return rows


def pearson(x, y):
    """Return a Pearson coefficient, or None for undefined correlation."""
    if len(x) < 2 or max(x) == min(x) or max(y) == min(y):
        return None
    return float(np.corrcoef(x, y)[0, 1])
