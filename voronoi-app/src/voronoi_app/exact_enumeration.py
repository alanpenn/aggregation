"""Rebuild exact axial candidates from original occupied vertices and faces."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import hypot

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .angular import (
    LineClearance, _cross, _crosses_prepared, _direction, _exact_point, _prepare_polygon,
)
from .angular_optimisation import _obstacles
from .axial_generator import _parts
from .convex_coverage import convex_regions
from .exact_axial import (
    ExactCandidate, ExactCandidateSet, ExactProblem, ExactSupport, VertexReference, build_candidates,
)


@dataclass(frozen=True)
class _Vertex:
    reference: VertexReference
    point: tuple[Fraction, Fraction]
    previous: tuple[Fraction, Fraction]
    following: tuple[Fraction, Fraction]
    convex: bool


@dataclass
class EnumerationAudit:
    counts: dict[str, int]
    domain_rejections: list[ExactSupport]


def _vertices(occupied):
    points = defaultdict(list)
    faces = []
    for building_id, polygon in sorted(occupied.items()):
        if not isinstance(polygon, Polygon) or polygon.is_empty or not polygon.is_valid:
            raise ValueError(f"Invalid occupied polygon {building_id}")
        if polygon.interiors:
            raise ValueError(f"Occupied polygon {building_id} has interior rings; "
                             "their face provenance is not supported")
        coordinates = list(map(_exact_point, list(polygon.exterior.coords)[:-1]))
        orientation = sum(_cross(a, b) for a, b in zip(coordinates, coordinates[1:] + coordinates[:1]))
        if orientation == 0:
            raise ValueError(f"Occupied polygon {building_id} has zero exact area")
        vertices = []
        for index, current in enumerate(coordinates):
            previous, following = coordinates[index - 1], coordinates[(index + 1) % len(coordinates)]
            turn = _cross(_direction(previous, current), _direction(current, following))
            vertex = _Vertex(VertexReference(building_id, index), current, previous, following,
                             turn * orientation > 0)
            vertices.append(vertex)
            points[current].append(vertex)
        faces.extend(zip(vertices, vertices[1:] + vertices[:1]))
    return points, faces


def _supports(vertex, other):
    direction = _direction(vertex.point, other)
    return (_cross(direction, _direction(vertex.point, vertex.previous))
            * _cross(direction, _direction(vertex.point, vertex.following)) >= 0)


def _refs(vertices):
    return tuple(sorted((vertex.reference for vertex in vertices),
                        key=lambda ref: (ref.building_id, ref.vertex_index)))


def _support_dict(support):
    def reference(ref):
        return {"building_id": ref.building_id, "vertex_index": ref.vertex_index}

    return {
        "source": support.source,
        "start": [str(value) for value in support.start],
        "end": [str(value) for value in support.end],
        "start_vertices": [reference(ref) for ref in support.start_vertices],
        "end_vertices": [reference(ref) for ref in support.end_vertices],
    }


def _support_from_dict(data):
    def references(values):
        return tuple(VertexReference(value["building_id"], value["vertex_index"]) for value in values)

    return ExactSupport(data["source"], tuple(Fraction(value) for value in data["start"]),
                        tuple(Fraction(value) for value in data["end"]),
                        references(data["start_vertices"]), references(data["end_vertices"]))


def exact_pool_to_dict(pool):
    """Serialize exact candidates, coverage and every retained support without rounding."""
    return {
        "version": 1,
        "candidates": [{
            "id": line.line_id, "start": [str(v) for v in line.start],
            "end": [str(v) for v in line.end], "seed_start": [str(v) for v in line.seed_start],
            "seed_end": [str(v) for v in line.seed_end], "source": line.source,
            "aliases": [{"source": source, "start": [str(v) for v in start],
                         "end": [str(v) for v in end]} for source, start, end in line.aliases],
            "provenance": [_support_dict(support) for support in line.provenance],
            "regions": sorted(pool.covers[index]),
        } for index, line in enumerate(pool.candidates)],
        "ring_candidates": sorted(pool.ring_candidates),
        "rejected": [{"source": source, "start": [str(v) for v in start],
                      "end": [str(v) for v in end]} for source, start, end in pool.rejected],
        "fallback_regions": sorted(pool.fallback_regions),
    }


def exact_pool_from_dict(data):
    """Restore a pool serialized by :func:`exact_pool_to_dict`."""
    if data["version"] != 1:
        raise ValueError("Unsupported exact candidate pool version")

    def point(values):
        return tuple(Fraction(value) for value in values)

    lines = []
    for entry in data["candidates"]:
        lines.append(ExactCandidate(
            entry["id"], point(entry["start"]), point(entry["end"]),
            point(entry["seed_start"]), point(entry["seed_end"]), entry["source"],
            tuple((alias["source"], point(alias["start"]), point(alias["end"]))
                  for alias in entry["aliases"]),
            tuple(_support_from_dict(support) for support in entry["provenance"]),
        ))
    if any(line.line_id != index for index, line in enumerate(lines)):
        raise ValueError("Exact pool candidate IDs must match their indices")
    return ExactCandidateSet(
        lines, [set(entry["regions"]) for entry in data["candidates"]],
        set(data["ring_candidates"]),
        [(entry["source"], point(entry["start"]), point(entry["end"]))
         for entry in data["rejected"]],
        set(data["fallback_regions"]),
    )


def generate_fresh_exact_candidate_pool(open_polygons, occupied_polygons, *, progress=None):
    """Enumerate original convex corner supports and building faces without legacy lines.

    Union/domain exclusions remain conservative and are reported separately. Boundary and
    fallback supports can lack building references when their points are not building vertices.
    """
    if not open_polygons or not occupied_polygons:
        raise ValueError("Fresh exact generation requires open and occupied polygons")
    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=occupied_polygons.values())
    regions = convex_regions(accessible)
    points, faces = _vertices(occupied_polygons)
    convex = {point: [vertex for vertex in vertices if vertex.convex]
              for point, vertices in points.items()}
    convex = {point: vertices for point, vertices in convex.items() if vertices}
    prepared = [(building, _prepare_polygon(polygon))
                for building, polygon in sorted(occupied_polygons.items())]
    counts = Counter()
    domain_rejections = []
    seeds = []

    def classify(support):
        for _, rings in prepared:
            if _crosses_prepared(support.start, support.end, rings):
                counts[f"{support.source}:occupied-interior"] += 1
                return False
        if not clearance.permits_exact(support.start, support.end):
            counts[f"{support.source}:domain-or-union"] += 1
            domain_rejections.append(support)
            return False
        counts[f"{support.source}:valid"] += 1
        return True

    for left, right in faces:
        if not (_supports(left, right.point) and _supports(right, left.point)):
            counts["occupied-face:not-supporting"] += 1
            continue
        support = ExactSupport("occupied-face", left.point, right.point,
                               (left.reference,), (right.reference,))
        if classify(support):
            seeds.append(support)
    pairs = combinations(sorted(convex), 2)
    total = len(convex) * (len(convex) - 1) // 2
    for examined, (start, end) in enumerate(pairs, 1):
        left = [vertex for vertex in convex[start] if _supports(vertex, end)]
        right = [vertex for vertex in convex[end] if _supports(vertex, start)]
        if not left or not right:
            counts["mutual-tangent:not-supporting"] += 1
        else:
            different_buildings = any(
                a.reference.building_id != b.reference.building_id for a in left for b in right
            )
            source = "mutual-tangent" if different_buildings else "same-building-tangent"
            support = ExactSupport(source, start, end, _refs(left), _refs(right))
            if classify(support):
                seeds.append(support)
        if progress is not None and (examined % 2000 == 0 or examined == total):
            progress(examined, total, dict(counts))

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
                coordinates = list(map(_exact_point, ring.coords))
                for start, end in zip(coordinates[:-1], coordinates[1:]):
                    ring_seeds.append(ExactSupport("ring-boundary", start, end,
                                                   _refs(points.get(start, ())),
                                                   _refs(points.get(end, ()))))
    pool = build_candidates(clearance, regions, ring_seeds, seeds)
    if pool.rejected:
        raise ValueError("Pre-certified fresh supports failed candidate construction")
    if not all(line.provenance for line in pool.candidates):
        raise ValueError("A fresh candidate is missing provenance")
    retained = {support for line in pool.candidates for support in line.provenance}
    missing = (set(ring_seeds) | set(seeds)) - retained
    if missing:
        raise ValueError(f"{len(missing)} certified supports are missing from the exact candidate pool")
    counts["convex-vertex-positions"] = len(convex)
    counts["corner-pairs-examined"] = total
    counts["ring-boundary:valid"] = len(ring_seeds)
    counts["fallback:valid"] = len(pool.fallback_regions)
    counts["distinct-candidates"] = len(pool.candidates)
    counts["missing-certified-supports"] = 0
    counts["deduplicated-supports"] = (
        len(ring_seeds) + len(seeds) + len(pool.fallback_regions) - len(pool.candidates)
    )
    counts["distinct-mutual-tangent-lines"] = sum(
        any(support.source == "mutual-tangent" for support in line.provenance)
        for line in pool.candidates
    )
    counts["distinct-occupied-face-lines"] = sum(
        any(support.source == "occupied-face" for support in line.provenance)
        for line in pool.candidates
    )
    return (ExactProblem(pool, accessible, occupied, regions, clearance,
                         [(point.x, point.y) for point in witnesses]),
            EnumerationAudit(dict(counts), domain_rejections))
