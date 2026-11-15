"""Independent audit of building-corner tangents in the axial candidate set."""

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import marshal
from math import hypot
from numbers import Integral
import pickle
from time import monotonic

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .axial_generator import _maximal_interval, _parts


@dataclass(frozen=True)
class BuildingCorner:
    point: tuple
    previous: tuple
    following: tuple


@dataclass(frozen=True)
class TangentPair:
    start: tuple
    end: tuple
    maximal: object
    status: str
    attempted: bool
    generator_interval: object
    reason: str = ""


@dataclass
class AxialAudit:
    boundary_vertices: int
    convex_building_vertices: int
    mixed_boundary_vertices: int
    possible_pairs: int
    coincident_pairs: int
    blocked_pairs: int
    buffered_only_pairs: int
    visible_pairs: int
    non_occluding_pairs: int
    pairs: list
    source_indices: dict
    stage_counts: dict
    tolerance: float


@dataclass(frozen=True)
class AuditProgress:
    phase: str
    unit: str
    examined: int
    total: int
    corner_total: int
    valid: int
    invalid: int
    unresolved: int
    elapsed: float
    remaining: float | None


def audit_cache_key(open_polygons, occupied_polygons, generated):
    """Key every input used by the audit, preserving iteration order."""
    inputs = (
        tuple(marshal.dumps(function.__code__) for function in (
            audit_axial_candidates, is_occluding, _independent_interval,
            _cross, _maximal_interval, _parts,
        )),
        tuple((cell, polygon.wkb) for cell, polygon in open_polygons.items()),
        tuple((cell, polygon.wkb) for cell, polygon in occupied_polygons.items()),
        tuple((tuple(line.start), tuple(line.end)) for line in generated.candidate_lines),
        tuple((tuple(start), tuple(end), reason)
              for start, end, reason in getattr(generated, "ambiguous_pairs", [])),
    )
    return sha256(pickle.dumps(inputs, protocol=4)).digest()


def cached_axial_audit(open_polygons, occupied_polygons, generated, cache, *, progress=None):
    """Retain the most recent complete audit in the supplied session cache."""
    key = audit_cache_key(open_polygons, occupied_polygons, generated)
    if cache.get("key") == key:
        return cache["audit"], True
    audit = audit_axial_candidates(open_polygons, occupied_polygons, generated, progress=progress)
    cache.clear()
    cache.update(key=key, audit=audit)
    return audit, False


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def is_occluding(corner, other, tolerance):
    """Whether both incident faces lie on the same side of the sightline."""
    dx, dy = other[0] - corner.point[0], other[1] - corner.point[1]
    length = hypot(dx, dy)
    if length <= tolerance:
        return False
    direction = (dx / length, dy / length)
    sides = [
        _cross(direction, (p[0] - corner.point[0], p[1] - corner.point[1]))
        for p in (corner.previous, corner.following)
    ]
    return not (min(sides) < -tolerance and max(sides) > tolerance)


def _independent_interval(accessible, start, end, tolerance):
    """Independently clip the support, anchoring it with an exactly covered seed."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    ux, uy = dx / length, dy / length
    min_x, min_y, max_x, max_y = accessible.bounds
    reach = 3 * max(hypot(max_x - min_x, max_y - min_y), length)
    support = LineString([
        (start[0] - reach * ux, start[1] - reach * uy),
        (start[0] + reach * ux, start[1] + reach * uy),
    ])
    intervals = []
    for line in _parts(accessible.intersection(support)):
        if not isinstance(line, LineString) or line.length <= tolerance:
            continue
        projections = [
            (x - start[0]) * ux + (y - start[1]) * uy
            for x, y in (line.coords[0], line.coords[-1])
        ]
        intervals.append((min(projections), max(projections)))
    if accessible.covers(LineString((start, end))):
        intervals.append((0.0, length))
    merged = []
    for low, high in sorted(intervals):
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
    for low, high in merged:
        if low <= tolerance and high >= length - tolerance:
            return LineString([
                (start[0] + low * ux, start[1] + low * uy),
                (start[0] + high * ux, start[1] + high * uy),
            ])
    return None


def audit_axial_candidates(open_polygons, occupied_polygons, generated, *, progress=None):
    """Compare exhaustive visible building-corner tangents with actual candidates.

    Only exposed corners whose two incident open-space boundary edges are
    occupied faces are classified. Mixed canvas/building corners are counted
    separately. Pair counts and vertex attempts are unordered.
    """
    started = monotonic()
    phase_started = started
    last_update = started
    total = corner_total = examined = valid = invalid = unresolved = 0
    phase = "Preparing geometry"
    unit = "items"

    def report(*, force=False):
        nonlocal last_update
        if progress is None:
            return
        now = monotonic()
        if not force and now - last_update < 0.5:
            return
        remaining = None
        if total and examined:
            remaining = max(0.0, (now - phase_started) * (total - examined) / examined)
        elif not total and unit != "items":
            remaining = 0.0
        progress(AuditProgress(phase, unit, examined, total, corner_total, valid, invalid, unresolved,
                               now - started, remaining))
        last_update = now

    def start_phase(name, count, label):
        nonlocal phase, phase_started, examined, total, unit
        phase, total, unit = name, count, label
        phase_started = monotonic()
        examined = 0
        report(force=True)

    def advance():
        nonlocal examined
        if examined % 32 == 0:
            report()
        examined += 1

    report(force=True)
    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    if accessible.is_empty or not accessible.is_valid:
        raise ValueError("Audit requires valid, non-empty accessible geometry")
    min_x, min_y, max_x, max_y = accessible.bounds
    tolerance = max(hypot(max_x - min_x, max_y - min_y) * 1e-9, 1e-12)
    buffered = accessible.buffer(tolerance)
    occupied_boundary = occupied.boundary
    corners = []
    edges = []
    obstacle_edges = []
    boundary_count = mixed = 0
    for part in _parts(accessible):
        if not isinstance(part, Polygon):
            continue
        part = orient(part, sign=1.0)
        for ring_index, ring in enumerate([part.exterior, *part.interiors]):
            vertices = list(ring.coords)[:-1]
            boundary_count += len(vertices)
            if ring_index:
                occupied_part = Polygon(ring).intersection(occupied)
                if any(isinstance(component, Polygon) and component.area > tolerance * tolerance
                       for component in _parts(occupied_part)):
                    obstacle_edges.extend((vertices[i], vertices[(i + 1) % len(vertices)])
                                          for i in range(len(vertices)))
            for i, current in enumerate(vertices):
                previous = vertices[i - 1]
                following = vertices[(i + 1) % len(vertices)]
                edges.append((current, following))
                incoming = (current[0] - previous[0], current[1] - previous[1])
                outgoing = (following[0] - current[0], following[1] - current[1])
                if _cross(incoming, outgoing) >= -tolerance * tolerance:
                    continue
                if occupied.is_empty:
                    continue
                faces = [
                    occupied_boundary.distance(Point((current[0] + p[0]) / 2,
                                                     (current[1] + p[1]) / 2)) <= tolerance
                    for p in (previous, following)
                ]
                if all(faces):
                    corners.append(BuildingCorner(current, previous, following))
                elif any(faces):
                    mixed += 1

    corner_total = len(corners) * (len(corners) - 1) // 2
    start_phase("Replaying boundary candidates", len(edges) + len(obstacle_edges), "seeds")
    lines = [LineString((line.start, line.end)) for line in generated.candidate_lines]
    tree = STRtree(lines)
    geometry_indices = {id(line): i for i, line in enumerate(lines)}

    def matching(line):
        if line is None:
            return set()
        matches = set()
        for item in tree.query(line.buffer(tolerance)):
            index = int(item) if isinstance(item, Integral) else geometry_indices[id(item)]
            if lines[index].hausdorff_distance(line) <= tolerance:
                matches.add(index)
        return matches

    sources = {"boundary": set(), "vertex": set(), "centroid": set(), "fallback": set(),
               "occluding": set()}
    stage_counts = {
        stage: dict(attempted=0, visibility_rejected=0, unexamined=0, ambiguous=0, zero_length=0,
                    clipping_failed=0, duplicate=0, added=0, unmatched=0)
        for stage in ("boundary", "obstacle", "vertex", "centroid", "fallback")
    }
    replay_seen = set()

    def replay(stage, start, end):
        counts = stage_counts[stage]
        counts["attempted"] += 1
        if hypot(end[0] - start[0], end[1] - start[1]) <= tolerance:
            counts["zero_length"] += 1
            return set()
        line = _maximal_interval(accessible, start, end, tolerance)
        if line is None:
            counts["clipping_failed"] += 1
            return set()
        indices = matching(line)
        if not indices:
            counts["unmatched"] += 1
        elif indices & replay_seen:
            counts["duplicate"] += 1
        else:
            counts["added"] += 1
            replay_seen.add(min(indices))
        return indices

    for start, end in edges:
        sources["boundary"].update(replay("boundary", start, end))
        advance()
    for start, end in obstacle_edges:
        sources["boundary"].update(replay("obstacle", start, end))
        advance()
    report(force=True)

    attempted = set()
    ambiguous_pairs = {
        frozenset((start, end)): reason
        for start, end, reason in getattr(generated, "ambiguous_pairs", [])
    }
    start_phase("Replaying corner pairs", corner_total, "corner pairs")
    for left, right in combinations(corners, 2):
        advance()
        start, end = left.point, right.point
        if not (is_occluding(left, end, tolerance) and is_occluding(right, start, tolerance)):
            continue
        segment = LineString((start, end))
        if not buffered.covers(segment):
            stage_counts["vertex"]["visibility_rejected"] += 1
            continue
        attempted.add(frozenset((start, end)))
        if frozenset((start, end)) in ambiguous_pairs:
            stage_counts["vertex"]["ambiguous"] += 1
        elif accessible.covers(segment):
            sources["vertex"].update(replay("vertex", start, end))

    report(force=True)
    start_phase("Preparing centroid candidates", 0, "items")
    centres = []
    for cell in sorted(open_polygons):
        polygon = open_polygons[cell]
        centre = polygon.centroid
        if not polygon.contains(centre):
            centre = polygon.representative_point()
        if accessible.covers(centre):
            centres.append((centre.x, centre.y))
    centre_pairs = sorted(
        combinations(centres, 2),
        key=lambda pair: -hypot(pair[1][0] - pair[0][0], pair[1][1] - pair[0][1]),
    )
    start_phase("Replaying centroid pairs", len(centre_pairs), "centroid pairs")
    for start, end in centre_pairs:
        if accessible.covers(LineString((start, end))):
            sources["centroid"].update(replay("centroid", start, end))
        else:
            stage_counts["centroid"]["visibility_rejected"] += 1
        advance()
    report(force=True)

    classified = sources["boundary"] | sources["vertex"] | sources["centroid"]
    covered = set()
    start_phase("Checking fallback coverage", len(open_polygons), "cells")
    for cell, polygon in open_polygons.items():
        if any(lines[i].relate_pattern(polygon, "T********") for i in replay_seen):
            covered.add(cell)
        advance()
    report(force=True)
    remaining_cells = sorted(set(open_polygons) - covered)
    start_phase("Replaying fallback candidates", len(remaining_cells), "cells")
    for cell in remaining_cells:
        polygon = open_polygons[cell]
        centre = polygon.centroid
        if not polygon.contains(centre):
            centre = polygon.representative_point()
        step = centre.distance(accessible.boundary) / 2
        if step <= tolerance:
            advance()
            continue
        for dx, dy in ((1.0, 0.0), (0.0, 1.0)):
            replay("fallback", (centre.x - step * dx, centre.y - step * dy),
                   (centre.x + step * dx, centre.y + step * dy))
        advance()
    report(force=True)
    sources["fallback"] = set(range(len(lines))) - classified

    pairs = []
    coincident = blocked = buffered_only = visible = non_occluding = 0
    start_phase("Classifying corner pairs", corner_total, "corner pairs")
    for left, right in combinations(corners, 2):
        if examined % 32 == 0:
            report()
        examined += 1
        start, end = left.point, right.point
        if hypot(end[0] - start[0], end[1] - start[1]) <= tolerance:
            coincident += 1
            invalid += 1
            continue
        segment = LineString((start, end))
        if not buffered.covers(segment):
            blocked += 1
            invalid += 1
            continue
        if not accessible.covers(segment):
            buffered_only += 1
        visible += 1
        if not (is_occluding(left, end, tolerance) and is_occluding(right, start, tolerance)):
            non_occluding += 1
            invalid += 1
            continue
        reference = _independent_interval(accessible, start, end, tolerance)
        generator_interval = _maximal_interval(accessible, start, end, tolerance)
        reason = ambiguous_pairs.get(frozenset((start, end)), "")
        if reference is None or reason:
            status = "indeterminate clipping"
            unresolved += 1
        elif matching(reference):
            status = "present"
            valid += 1
            sources["occluding"].update(matching(reference))
        else:
            status = "missing"
            valid += 1
        pairs.append(TangentPair(start, end, reference, status,
                                 frozenset((start, end)) in attempted, generator_interval, reason))

    report(force=True)
    return AxialAudit(
        boundary_count, len(corners), mixed, corner_total,
        coincident, blocked, buffered_only, visible, non_occluding, pairs, sources, stage_counts,
        tolerance,
    )
