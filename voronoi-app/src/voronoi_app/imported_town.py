"""Reviewed plan polygons and their adapter to the certified axial engine."""
from dataclasses import dataclass, replace
from fractions import Fraction
from math import isfinite

import networkx as nx
from shapely import constrained_delaunay_triangles, get_parts, make_valid, set_precision, union_all
from shapely.geometry import LineString, Polygon, mapping, shape
from shapely.strtree import STRtree

from .angular import _cross, _exact_point, _on_segment
from .complementary_axial import ComplementaryStudy, no_progress
from .exact_enumeration import exact_pool_to_dict, generate_fresh_exact_candidate_pool
from .face_adjacency import face_adjacency
from .region_incidence_angular import build_incidence, halfplanes, positive_interior

ROLES = {"building", "street", "exclude", "boundary"}


def polygon_parts(geometry):
    if isinstance(geometry, Polygon):
        return [] if geometry.is_empty else [geometry]
    return [p for part in getattr(geometry, "geoms", ()) for p in polygon_parts(part)]


def ordered(geometries):
    return sorted(geometries, key=lambda p: (p.bounds, p.normalize().wkb_hex))


def feature(identifier, role, geometry, **properties):
    return {"type": "Feature", "id": identifier,
            "properties": {"role": role, **properties}, "geometry": mapping(geometry)}


def collection(features):
    return {"type": "FeatureCollection", "features": list(features)}


@dataclass
class ReviewedTown:
    buildings: dict
    streets: object
    excluded: object
    boundary: object
    components: list
    report: dict
    approved: dict
    grid: float


def review_geometry(document, *, grid_bits=4):
    """Validate and snap approved geometry to a binary grid in plan coordinates."""
    if document.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection.")
    if not isinstance(grid_bits, int) or not 0 <= grid_bits <= 20:
        raise ValueError("Grid precision must be from 0 to 20 binary fractional bits.")
    grid = 2.0 ** -grid_bits
    buildings, streets, excluded, boundaries = {}, [], [], []
    kept, repaired, changed = [], [], []
    unsnapped = {role: [] for role in ROLES}
    identifiers = set()
    for index, record in enumerate(document["features"]):
        props = record.get("properties") or {}
        role = props.get("role")
        if role not in ROLES:
            raise ValueError(f"Feature {index + 1} needs a building, street, exclude or boundary role.")
        identifier = str(record.get("id", props.get("id", f"{role}-{index+1}")))
        if identifier in identifiers:
            raise ValueError(f"Duplicate feature identifier {identifier}.")
        identifiers.add(identifier)
        original = shape(record["geometry"])
        if (original.geom_type not in {"Polygon", "MultiPolygon"} or original.is_empty
                or original.has_z or any(not isfinite(v) or abs(v) >= 2**(50-grid_bits)
                                         for v in original.bounds)):
            raise ValueError(f"{identifier} needs finite two-dimensional polygon geometry in range.")
        valid = original if original.is_valid else union_all(polygon_parts(make_valid(original)))
        if not original.is_valid:
            repaired.append(identifier)
        snapped = set_precision(valid, grid)
        if snapped.is_empty or not snapped.is_valid:
            raise ValueError(f"{identifier} collapses on the quantisation grid. Use finer precision.")
        area_change = set_precision(snapped, 0).symmetric_difference(valid, grid_size=0).area
        if area_change:
            changed.append({"id": identifier, "symmetric_difference_area": area_change})
        kept.append(feature(identifier, role, snapped, **{k: v for k, v in props.items() if k != "role"}))
        unsnapped[role].append(valid)
        if role == "building":
            buildings[identifier] = snapped
        else:
            {"street": streets, "exclude": excluded, "boundary": boundaries}[role].append(snapped)
    if not boundaries or not streets:
        raise ValueError("Approve at least one street polygon and an outer analysis boundary.")
    bounds, raw_streets, excluded_shape = (union_all(group, grid_size=grid)
                                          for group in (boundaries, streets, excluded))
    occupied = union_all(list(buildings.values()), grid_size=grid)
    named = list(buildings)
    building_index = STRtree(list(buildings.values()))
    overlaps = [[a, named[j]] for i, a in enumerate(named)
                for j in building_index.query(buildings[a], predicate="intersects")
                if i < j and buildings[a].intersection(buildings[named[j]]).area > 0]
    if overlaps:
        raise ValueError(f"Building interiors overlap. Correct these feature pairs: {overlaps[:15]}")
    clipped = raw_streets.intersection(bounds, grid_size=grid)
    domain = clipped.difference(union_all([occupied, excluded_shape], grid_size=grid), grid_size=grid)
    components = ordered(polygon_parts(domain))
    if not components or not domain.is_valid:
        raise ValueError("The reviewed geometry leaves no valid circulation polygon.")
    if any(domain.intersection(g).area > 0 for g in (occupied, excluded_shape)) or not bounds.covers(domain):
        raise ValueError("Overlay at this grid precision is inconsistent. Correct intersections or use finer precision.")
    reference = union_all(unsnapped["street"]).intersection(union_all(unsnapped["boundary"]))
    reference = reference.difference(union_all([*unsnapped["exclude"], *unsnapped["building"]]))
    report = {"repaired": repaired, "quantisation_changes": changed,
              "street_union_overlap_area": sum(p.area for p in streets) - raw_streets.area,
              "street_area_outside_boundary": max(0.0, raw_streets.area - clipped.area),
              "street_building_overlap_area": clipped.intersection(occupied).area,
              "street_exclusion_overlap_area": clipped.intersection(excluded_shape).area,
              "domain_symmetric_difference_area": reference.symmetric_difference(
                  set_precision(domain, 0), grid_size=0).area,
              "components": [{"area": p.area, "holes": len(p.interiors), "bounds": p.bounds}
                             for p in components]}
    return ReviewedTown(buildings, domain, excluded_shape, bounds, components, report,
                        collection(kept), grid)


def exact_area(geometry):
    def double_area(ring):
        coordinates = list(map(_exact_point, ring.coords))
        return abs(sum(_cross(a, b) for a, b in zip(coordinates, coordinates[1:])))
    return sum((double_area(p.exterior) - sum(map(double_area, p.interiors))) / 2
               for p in polygon_parts(geometry))


def subdivide(domain, *, merge=False):
    regions = ordered(constrained_delaunay_triangles(domain).geoms)
    if merge:
        active = dict(enumerate(regions))
        graph = face_adjacency(active, active)
        for left in range(len(regions)):
            if left not in active:
                continue
            for right in sorted(graph[left]):
                if right <= left or right not in active:
                    continue
                combined = active[left].union(active[right])
                if isinstance(combined, Polygon) and combined.equals(combined.convex_hull):
                    active[left] = combined
                    del active[right]
        regions = ordered(active.values())
    if (not regions or any(p.interiors or not p.equals(p.convex_hull) for p in regions)
            or not union_all(regions).equals(domain)
            or sum(map(exact_area, regions)) != exact_area(domain)):
        raise ValueError("The convex subdivision failed coverage or no-overlap validation.")
    return dict(enumerate(regions))


@dataclass
class TownAnalysis:
    study: ComplementaryStudy
    prepared: object
    result: object
    regions: dict
    adjacency: dict
    blocks: dict
    contacts: list
    domain: Polygon
    audit: dict
    movement: dict | None = None


def make_study(town, component, *, merge=False, progress=no_progress):
    domain = town.components[component]
    regions = subdivide(domain, merge=merge)
    # Contact components include vertex contacts, matching the existing rule.
    labels = {i: label for i, label in enumerate(sorted(town.buildings))}
    buildings = {i: town.buildings[label] for i, label in labels.items()}
    contact_graph = nx.Graph()
    contact_graph.add_nodes_from(buildings)
    contacts = []
    index = STRtree(list(buildings.values()))
    for a, left in buildings.items():
        for b in sorted(map(int, index.query(left, predicate="touches"))):
            if a >= b:
                continue
            contact = left.boundary.intersection(buildings[b].boundary)
            contacts.append({"left": labels[a], "right": labels[b],
                             "kind": "edge" if contact.length > 0 else "vertex"})
            contact_graph.add_edge(a, b)
    blocks = {i: union_all([buildings[j] for j in sorted(group)])
              for i, group in enumerate(nx.connected_components(contact_graph))}
    support_parts = [(block_id, p) for block_id, block in blocks.items()
                     for p in ordered(polygon_parts(block)) if p.intersects(domain)]
    supports = {i: p for i, (_, p) in enumerate(support_parts)}
    original = [p for building in buildings.values() for p in polygon_parts(building)
                if p.intersects(domain)]
    # The winding classes are contact-connected holes in the chosen street
    # polygon. A vertex contact doesn't open a physical passage between holes.
    records = dict(buildings)
    holes = {len(records) + i: Polygon(ring) for i, ring in enumerate(domain.interiors)}
    records.update(holes)
    hole_ids = list(holes)
    hole_index = STRtree(list(holes.values()))
    hole_graph = nx.Graph()
    hole_graph.add_nodes_from(holes)
    exterior = LineString(domain.exterior.coords)
    pinch_points = set()
    for i, polygon in holes.items():
        touching = [hole_ids[j] for j in hole_index.query(polygon, predicate="touches") if i < hole_ids[j]]
        hole_graph.add_edges_from((i, j) for j in touching)
        for neighbor in [exterior, *(holes[j] for j in touching)]:
            contact = polygon.boundary.intersection(neighbor)
            pinch_points.update(_exact_point(part.coords[0]) for part in get_parts(contact)
                                if part.geom_type == "Point" and not part.is_empty)
    ring_blocks = []
    rings = []
    for group in nx.connected_components(hole_graph):
        cells = sorted(group)
        kind = "boundary" if any(holes[i].intersects(exterior) for i in cells) else "internal"
        ring_blocks.append({"id": cells[0], "cells": cells, "kind": kind, "associated_holes": cells})
        if kind == "internal":
            enclosure = holes[cells[0]] if len(cells) == 1 else union_all(
                [holes[i] for i in cells]).convex_hull
            rings.append(enclosure.exterior)
    problem, audit = generate_fresh_exact_candidate_pool(
        regions, supports, domain=domain, regions=regions, original_obstacles=original,
        circulation_rings=rings, pinch_points=sorted(pinch_points),
        progress=lambda done, total, _: progress("Certified tangent enumeration", f"{done:,} / {total:,} pairs"))
    region_record_ids = []
    for region in regions.values():
        region_record_ids.append(len(records))
        records[len(records)] = region
    _, traversals, _ = build_incidence(problem.pool.candidates, regions, [])
    inputs = {
        "settlement": {"polygons_wkb": {str(i): p.wkb_hex for i, p in records.items()},
                       "building_labels": {str(i): name for i, name in labels.items()}},
        "topology": {"accessible_wkb": domain.wkb_hex, "occupied_wkb": problem.occupied.wkb_hex,
                     "blocks_wkb": {str(i): p.wkb_hex for i, p in blocks.items()},
                     "support_polygon_index": {str(i): {"block": block_id, "wkb": p.wkb_hex}
                                               for i, (block_id, p) in enumerate(support_parts)},
                     "non_traversable_contacts": [list(map(str, p)) for p in sorted(pinch_points)],
                     "topology": {"main_open_cells": region_record_ids,
                                  "effective_occupied_cells": list(buildings),
                                  "occupied_blocks": ring_blocks}},
        "candidates": {"pool": exact_pool_to_dict(problem.pool), "obstacle_witnesses": problem.obstacles,
                       "regions_wkb": {str(i): p.wkb_hex for i, p in regions.items()}},
        "analysis": {"holes": sum(block["kind"] == "internal" for block in ring_blocks), "incidence": {
            "doorways": [], "doorway_regions": [], "region_lines": {
                str(i): sorted(ids) for i, ids in traversals.items()}}},
    }
    return ComplementaryStudy(inputs, original_obstacles=original), regions, blocks, contacts, audit.counts


def analyse_town(town, component, *, order="sheaf", merge=False, exchange=False, progress=no_progress):
    study, regions, blocks, contacts, audit = make_study(town, component, merge=merge, progress=progress)
    prepared = study.prepare(progress)
    result = None if prepared.failure else study.reduce_prepared(prepared, order, progress)
    if exchange and result and result.certified:
        improved = study.improve(result, order, progress)
        if improved.certified:
            result = replace(improved, deletions=result.deletions)
    if result and result.certified:
        # Independent rational half-plane clipping checks the selected coverage
        # without the candidate pool's spatial index or saved incidence.
        missing = []
        for i, region in regions.items():
            planes = halfplanes([_exact_point(p) for p in region.exterior.coords])
            if not any(positive_interior(study.lines[j].start, study.lines[j].end, planes)
                       for j in result.ids):
                missing.append(i)
        pinches = [tuple(Fraction(value) for value in point)
                   for point in study.inputs["topology"]["non_traversable_contacts"]]
        blocked = [j for j in result.ids
                   if any(_on_segment(point, study.lines[j].start, study.lines[j].end) for point in pinches)]
        if missing:
            result = replace(result, summary=result.summary | {"certified": False, "missing_regions": missing,
                             "regions": len(regions) - len(missing)},
                             failure="Independent exact positive-interior coverage check disagrees.")
        elif blocked:
            result = replace(result, summary=result.summary | {"certified": False, "blocked_contacts": blocked,
                             "clear": result.summary["clear"] - len(blocked)},
                             failure="Independent exact clearance found a zero-width contact.")
    return TownAnalysis(study, prepared, result, regions, face_adjacency(regions, regions),
                        blocks, contacts, town.components[component], audit)


def analyse_entrances(analysis, records):
    """Route independently of geometry-only selection from reviewed plan points."""
    from copy import copy
    from shapely.geometry import Point
    from .strict_coverage_experiment import incidence_sets

    result = analysis.result
    if result is None or not result.certified:
        raise ValueError("Entrance routing requires a certified final map.")
    study = copy(analysis.study)
    doors = []
    for index, record in enumerate(records):
        x, y = record["coordinates"]
        p = Point(x, y)
        if not analysis.domain.covers(p) or not study.clearance.permits((x, y), (x, y)):
            raise ValueError(f"Entrance {record.get('id', index+1)} is outside the selected street domain.")
        doors.append({"id": record.get("id", index+1), "point": list(map(str, _exact_point((x, y)))),
                      "status": record.get("status", "user-supplied")})
    incident, traversals, _ = build_incidence(study.lines, analysis.regions, doors)
    incidence = {"doorways": doors, "doorway_regions": incident,
                 "region_lines": {str(i): sorted(ids) for i, ids in traversals.items()}}
    study.inputs = study.inputs | {"analysis": study.inputs["analysis"] | {"incidence": incidence}}
    _, links = incidence_sets(incidence)
    reached = [not set(result.ids).isdisjoint(group) for group in links]
    routing = study.movement(result) if len(doors) >= 2 and all(reached) else None
    analysis.movement = {"entrances": doors, "reachable_by_region_incidence": reached,
                         "routing": routing}
    return analysis.movement
