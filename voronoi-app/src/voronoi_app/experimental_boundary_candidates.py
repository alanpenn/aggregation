"""Experimental exact boundary-endpoint/occluding-vertex candidate enumeration.

This module is not used by either application generator or selector.
"""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from math import inf, nextafter

from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .angular import (
    LineClearance, _cross, _crosses_prepared, _direction, _exact_point, _on_segment,
    _prepare_polygon,
)
from .axial_generator import _parts
from .exact_axial import ExactSupport, VertexReference
from .exact_enumeration import _refs, _supports, _vertices


Point = tuple[Fraction, Fraction]


@dataclass(frozen=True)
class VertexContact:
    point: Point
    buildings: tuple[VertexReference, ...]
    accessible_boundary: bool


@dataclass(frozen=True)
class BoundaryCandidate:
    start: Point
    end: Point
    supports: tuple[ExactSupport, ...]
    contacts: tuple[VertexContact, ...]


@dataclass(frozen=True)
class BoundaryAudit:
    candidates: tuple[BoundaryCandidate, ...]
    counts: dict[str, int]


def canonical_interval(start, end):
    """Canonical identity of an unoriented exact interval, independent of IDs."""
    return tuple(sorted((start, end)))


def _boundary_vertices(accessible, vertices):
    all_boundary = set()
    boundary = set()
    edges = []
    for part in _parts(accessible):
        if not isinstance(part, Polygon):
            continue
        for ring in (part.exterior, *part.interiors):
            points = list(map(_exact_point, list(ring.coords)[:-1]))
            all_boundary.update(points)
            for index, point in enumerate(points):
                following = points[(index + 1) % len(points)]
                edges.append((point, following))
                turn = _cross(_direction(points[index - 1], point),
                              _direction(point, following))
                if turn or point in vertices:
                    boundary.add(point)
    for point in vertices.keys() - all_boundary:
        if any(_on_segment(point, start, end) for start, end in edges):
            boundary.add(point)
            all_boundary.add(point)
    return boundary, all_boundary


def enumerate_boundary_endpoint_candidates(open_polygons, occupied_polygons, *, progress=None):
    """Enumerate boundary-vertex to original convex supporting-corner intervals.

    A qualifying boundary vertex changes the exact boundary direction or is an
    original building vertex; collinear cell-subdivision points are excluded.
    Both vertices must be on the same clear interval and the boundary vertex
    must be an endpoint of that maximal interval. Shared vertices and all
    collinear original building/boundary vertices are retained in provenance.
    """
    if not open_polygons or not occupied_polygons:
        raise ValueError("Boundary enumeration requires open and occupied polygons")
    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=occupied_polygons.values())
    vertices, _ = _vertices(occupied_polygons)
    boundary, all_boundary = _boundary_vertices(accessible, vertices)
    corners = {point: tuple(vertex for vertex in items if vertex.convex)
               for point, items in vertices.items()}
    corners = {point: items for point, items in corners.items() if items}
    original = list(occupied_polygons.values())
    prepared = [_prepare_polygon(polygon) for polygon in original]
    tree = STRtree(original)
    counts = Counter()
    intervals = {}
    contact_points = sorted(all_boundary | set(vertices))
    count = len(boundary) * len(corners)
    examined = 0
    for boundary_point in sorted(boundary):
        for corner_point, corner_vertices in sorted(corners.items()):
            examined += 1
            if boundary_point == corner_point:
                counts["coincident"] += 1
                continue
            supporting = [v for v in corner_vertices if _supports(v, boundary_point)]
            if not supporting:
                counts["corner-not-supporting"] += 1
                continue
            bounds = box(
                nextafter(float(min(boundary_point[0], corner_point[0])), -inf),
                nextafter(float(min(boundary_point[1], corner_point[1])), -inf),
                nextafter(float(max(boundary_point[0], corner_point[0])), inf),
                nextafter(float(max(boundary_point[1], corner_point[1])), inf),
            )
            if any(_crosses_prepared(boundary_point, corner_point, prepared[int(i)])
                   for i in tree.query(bounds)):
                counts["occupied-interior"] += 1
                continue
            if not clearance.permits_exact(boundary_point, corner_point):
                counts["domain-or-union"] += 1
                continue
            start, end = clearance.maximal_interval(boundary_point, corner_point)
            if boundary_point not in (start, end):
                counts["boundary-not-endpoint"] += 1
                continue
            support = ExactSupport(
                "boundary-endpoint-to-occluding-vertex", boundary_point, corner_point,
                _refs(vertices.get(boundary_point, ())), _refs(vertices.get(corner_point, ())),
            )
            key = canonical_interval(start, end)
            if key not in intervals:
                intervals[key] = []
            intervals[key].append(support)
            counts["accepted-supports"] += 1
        if progress is not None:
            progress(examined, count, dict(counts))
    candidates = []
    for (start, end), supports in sorted(intervals.items()):
        contacts = tuple(
            VertexContact(point, _refs(vertices.get(point, ())), point in all_boundary)
            for point in contact_points if _on_segment(point, start, end)
        )
        candidates.append(BoundaryCandidate(start, end, tuple(supports), contacts))
    counts["boundary-vertices"] = len(boundary)
    counts["convex-corner-positions"] = len(corners)
    counts["examined"] = examined
    counts["distinct-intervals"] = len(candidates)
    counts["duplicate-supports"] = counts["accepted-supports"] - len(candidates)
    return BoundaryAudit(tuple(candidates), dict(counts))
