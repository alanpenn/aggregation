"""Build an experimental all-line map from projected building-block faces and corners."""

from collections import Counter
from itertools import combinations

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .angular import LineClearance, _cross, _direction, _exact_point, _intersections
from .axial_generator import _parts
from .convex_coverage import convex_regions
from .exact_axial import ExactSupport, VertexReference, build_candidates, region_coverage
from .exact_enumeration import _Vertex, _supports
from .experimental_visibility import IndexedClearance, _outward_bounds


def block_rings(blocks):
    for block_id, polygon in enumerate(blocks):
        polygon = orient(polygon, sign=1)
        index = 0
        for ring in (polygon.exterior, *polygon.interiors):
            points = [_exact_point(point) for point in list(ring.coords)[:-1]]
            points = [point for i, point in enumerate(points)
                      if _cross(_direction(points[i - 1], point),
                                _direction(point, points[(i + 1) % len(points)]))]
            vertices = []
            for i, point in enumerate(points):
                previous, following = points[i - 1], points[(i + 1) % len(points)]
                convex = _cross(_direction(previous, point), _direction(point, following)) > 0
                vertices.append(_Vertex(VertexReference(block_id, index), point,
                                        previous, following, convex))
                index += 1
            yield vertices


def project_face(corner, face_vertex, clearance, edges, tree):
    """Extend away from the incident face to the first new boundary event."""
    direction = _direction(face_vertex, corner)
    bounds = clearance.frame
    limit = min((bounds[i + (2 if value > 0 else 0)] - corner[i]) / value
                for i, value in enumerate(direction) if value)
    end = tuple(value + limit * delta for value, delta in zip(corner, direction))
    axis = 0 if direction[0] else 1
    distances = [(point[axis] - corner[axis]) / direction[axis]
                 for raw in tree.query(_outward_bounds(corner, end))
                 for point in _intersections(corner, end, *edges[int(raw)])
                 if point != corner]
    stop = min(distances, default=limit)
    midpoint = tuple(value + stop * delta / 2 for value, delta in zip(corner, direction))
    if not clearance.permits(corner, midpoint):
        return corner
    return tuple(value + stop * delta for value, delta in zip(corner, direction))


def generate_projected_face_all_lines(open_polygons, occupied_polygons, *, progress=None):
    """Return the unselected exact line pool and face-projection diagnostics."""
    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=occupied_polygons.values())
    indexed = IndexedClearance(clearance)
    blocks = sorted((part for part in _parts(occupied) if isinstance(part, Polygon)),
                    key=lambda part: (part.bounds, part.wkb))
    rings = list(block_rings(blocks))
    corners = [corner for ring in rings for corner in ring]
    convex = [corner for corner in corners if corner.convex]
    concave_refs = {corner.reference for corner in corners if not corner.convex}
    edges = []
    for part in _parts(accessible):
        if isinstance(part, Polygon):
            for ring in (part.exterior, *part.interiors):
                points = list(map(_exact_point, ring.coords))
                edges.extend(zip(points, points[1:]))
    tree = STRtree([_outward_bounds(a, b) for a, b in edges])
    projections = [
        {"block": corner.reference.building_id, "vertex": corner.reference.vertex_index,
         "point": point_json(corner.point),
         "projected_faces": [point_json(project_face(corner.point, adjacent, indexed, edges, tree))
                             for adjacent in (corner.previous, corner.following)]}
        for corner in convex
    ]
    seeds = []
    sector_pairs = Counter()

    def add(source, left, right):
        seeds.append(ExactSupport(source, left.point, right.point,
                                  (left.reference,), (right.reference,)))

    total = len(corners) * (len(corners) - 1) // 2
    if progress:
        progress("Testing corner pairs", 0, total)
    for index, (left, right) in enumerate(combinations(corners, 2), 1):
        if progress and index < total and index % 256 == 0:
            progress("Testing corner pairs", index, total)
        if left.point == right.point:
            continue
        if left.convex and right.convex:
            if not (_supports(left, right.point) and _supports(right, left.point)):
                continue
            source = (
                "same-block-tangent"
                if left.reference.building_id == right.reference.building_id
                else "projected-face-mutual-tangent"
            )
            sector_pairs[source] += 1
            if indexed.permits(left.point, right.point):
                add(source, left, right)
            continue

        if ((left.convex and not _supports(left, right.point))
                or (right.convex and not _supports(right, left.point))):
            continue
        if indexed.permits(left.point, right.point):
            add("concave-endpoint", left, right)

    if progress and total:
        progress("Testing corner pairs", total, total)
    for ring in rings:
        for left, right in zip(ring, ring[1:] + ring[:1]):
            if left.convex and right.convex and indexed.permits(left.point, right.point):
                add("convex-to-convex-face", left, right)

    # Empty targets prevent the selection builder from injecting coverage fallback lines.
    if progress:
        progress("Extending maximal axial lines", 0, len(seeds))
    pool = build_candidates(
        clearance, {}, [], seeds,
        progress=(lambda done, total: progress("Extending maximal axial lines", done, total))
        if progress else None,
    )
    if pool.rejected:
        raise ValueError("A projected-face support failed exact clearance")
    for line in pool.candidates:
        for support in line.provenance:
            if support.source != "concave-endpoint":
                continue
            endpoints = {line.start, line.end}
            if ((support.start_vertices[0] in concave_refs and support.start not in endpoints)
                    or (support.end_vertices[0] in concave_refs and support.end not in endpoints)):
                raise ValueError("A clear chord continued past a concave block corner")
    regions = convex_regions(accessible)
    pool.covers = region_coverage(pool.candidates, regions)
    covered = set().union(*pool.covers)
    candidates_by_source = Counter()
    coverage_by_source = {}
    for line, cover in zip(pool.candidates, pool.covers):
        for source in {support.source for support in line.provenance}:
            candidates_by_source[source] += 1
            coverage_by_source.setdefault(source, set()).update(cover)
    return pool, {
        "blocks": len(blocks),
        "convex_corners": len(convex),
        "concave_corners": len(concave_refs),
        "mutual_sector_pairs": sum(sector_pairs.values()),
        "mutual_sector_pairs_by_source": dict(sector_pairs),
        "supports_by_source": dict(Counter(seed.source for seed in seeds)),
        "candidates_by_source": dict(candidates_by_source),
        "covered_regions_by_source": {source: len(cover)
                                      for source, cover in coverage_by_source.items()},
        "distinct_candidates": len(pool.candidates),
        "covered_convex_regions": len(covered),
        "total_convex_regions": len(regions),
        "uncovered_convex_regions": sorted(set(regions) - covered),
        "projections": projections,
    }


def point_json(point):
    return [str(value) for value in point]
