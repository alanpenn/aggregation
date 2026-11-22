"""Derived open-component and circulation-hole topology for experiments."""

from fractions import Fraction
from functools import cmp_to_key

from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .face_adjacency import face_adjacency
from .angular import (
    LineClearance, _cross, _direction, _exact_point, _intersections, _ring_location,
)
from .axial_generator import _parts
from .exact_axial import _compare_directions, _segment_graph
from .experimental_visibility import _outward_bounds


def _ordered_components(graph):
    remaining = set(graph)
    components = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        component = set()
        while stack:
            cell = stack.pop()
            if cell in component:
                continue
            component.add(cell)
            stack.extend(graph[cell] - component)
        remaining -= component
        components.append(component)
    return sorted(components, key=lambda group: (-len(group), tuple(sorted(group))))


def _contact_graph(cell_ids, polygons):
    ids = sorted(cell_ids)
    graph = {cell: set() for cell in ids}
    if not ids:
        return graph
    tree = STRtree([polygons[cell].envelope for cell in ids])
    for position, left in enumerate(ids):
        boundary = polygons[left].boundary
        for raw in tree.query(polygons[left].envelope):
            other_position = int(raw)
            right = ids[other_position]
            if right <= left:
                continue
            if not boundary.intersection(polygons[right].boundary).is_empty:
                graph[left].add(right)
                graph[right].add(left)
    return graph


def _edge_graph(cell_ids, polygons):
    return {cell: set(neighbors) for cell, neighbors in face_adjacency(cell_ids, polygons).items()}


def bounded_face_rings(lines, *, segment_graph=None):
    """Return exact positive-winding bounded faces of noded segment linework."""
    graph = _segment_graph(lines) if segment_graph is None else segment_graph
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
            area2 = sum(_cross(a, b) for a, b in zip(ring, ring[1:]))
            if area2 > 0:
                faces.append(tuple(ring))
    return tuple(faces)


def _segment_inside_or_on_ring(start, end, ring):
    direction = _direction(start, end)
    if start == end:
        return _ring_location(ring, start) >= 0
    axis = 0 if direction[0] else 1
    events = {Fraction(0), Fraction(1)}
    for left, right in zip(ring, ring[1:]):
        events.update(
            (point[axis] - start[axis]) / direction[axis]
            for point in _intersections(start, end, left, right)
        )
    ordered = sorted(events)
    for value in ordered:
        point = tuple(start[i] + value * direction[i] for i in range(2))
        if _ring_location(ring, point) < 0:
            return False
    for low, high in zip(ordered, ordered[1:]):
        value = (low + high) / 2
        point = tuple(start[i] + value * direction[i] for i in range(2))
        if _ring_location(ring, point) < 0:
            return False
    return True


def _ring_covers_cells(ring, cells, polygons):
    for cell in cells:
        polygon = polygons[cell]
        if _ring_location(ring, _exact_point(polygon.representative_point().coords[0])) < 0:
            return False
        for boundary in (polygon.exterior, *polygon.interiors):
            points = tuple(map(_exact_point, boundary.coords))
            if any(not _segment_inside_or_on_ring(start, end, ring)
                   for start, end in zip(points, points[1:])):
                return False
    return True


def _matrix_rank(rows):
    basis = {}
    for values in rows:
        row = [Fraction(value) for value in values]
        for pivot, existing in sorted(basis.items()):
            if row[pivot]:
                factor = row[pivot]
                row = [value - factor * other for value, other in zip(row, existing)]
        pivot = next((index for index, value in enumerate(row) if value), None)
        if pivot is None:
            continue
        scale = row[pivot]
        basis[pivot] = [value / scale for value in row]
    return len(basis)


def analyse_circulation_topology(polygons, building_cells, dyad_open_cells, selected_lines,
                                 settlement_boundary: BaseGeometry | None = None, *,
                                 include_witness_faces=False,
                                 clearance_factory=LineClearance,
                                 face_builder=bounded_face_rings,
                                 face_location=_ring_location,
                                 face_coverage=_ring_covers_cells):
    """Derive effective blocks and validate independent full-block winding classes.

    Cell adjacency uses a positive-length shared edge. Occupied and excluded
    component aggregation uses any shared boundary contact, including a point.
    """
    polygons = {int(cell): polygon for cell, polygon in polygons.items()}
    building_cells = set(map(int, building_cells))
    dyad_open_cells = set(map(int, dyad_open_cells))
    if not polygons or not building_cells <= set(polygons):
        raise ValueError("Polygon geometry must include every occupied cell")
    if not dyad_open_cells <= (set(polygons) - building_cells):
        raise ValueError("Dyad-associated open cells must be geometrically open")
    if any(not isinstance(polygon, Polygon) or polygon.is_empty or not polygon.is_valid
           for polygon in polygons.values()):
        raise ValueError("All Voronoi cells must be valid non-empty polygons")
    all_cells = set(polygons)
    open_cells = all_cells - building_cells
    cell_classes = {
        cell: ("building" if cell in building_cells else
               "dyad_open" if cell in dyad_open_cells else "unfilled_open")
        for cell in sorted(all_cells)
    }

    open_adjacency = _edge_graph(open_cells, polygons)
    open_components = _ordered_components(open_adjacency)
    if not open_components:
        raise ValueError("Settlement has no geometrically open cells")
    main_open = open_components[0]
    excluded_components = open_components[1:]
    excluded = set().union(*excluded_components) if excluded_components else set()
    open_component_for = {
        cell: index for index, group in enumerate(open_components) for cell in group
    }
    accessible = unary_union([polygons[cell] for cell in sorted(main_open)])

    building_adjacency = _contact_graph(building_cells, polygons)
    building_components = _ordered_components(building_adjacency)
    building_component_for = {
        cell: index for index, group in enumerate(building_components) for cell in group
    }
    excluded_groups = _ordered_components(_contact_graph(excluded, polygons))
    excluded_records = []
    blocks = []
    if settlement_boundary is None:
        settlement_parts = [
            item for item in _parts(unary_union(list(polygons.values())))
            if isinstance(item, Polygon)
        ]
        boundary_geometry = unary_union(
            [LineString(part.exterior.coords) for part in settlement_parts]
        )
    else:
        boundary_geometry = settlement_boundary.boundary
    boundary_sources = set()
    for index, group in enumerate(building_components):
        cells = set(group)
        geometry = unary_union([polygons[cell] for cell in sorted(cells)])
        if not geometry.boundary.intersection(boundary_geometry).is_empty:
            boundary_sources.update(cells)
        blocks.append({"source": "buildings", "cells": cells,
                       "building_component": index, "excluded_components": []})

    standalone = []
    for excluded_id, group in enumerate(excluded_groups):
        geometry = unary_union([polygons[cell] for cell in sorted(group)])
        touching_buildings = sorted({
            building_component_for[building]
            for cell in group for building in building_adjacency
            if not polygons[cell].boundary.intersection(polygons[building].boundary).is_empty
        })
        touches_boundary = not geometry.boundary.intersection(boundary_geometry).is_empty
        record = {"component": excluded_id, "cells": sorted(group),
                  "open_components": sorted({open_component_for[cell] for cell in group}),
                  "touching_building_blocks": touching_buildings,
                  "touches_outer_boundary": touches_boundary}
        if touches_boundary:
            boundary_sources.update(group)
            record.update(assignment="outer_boundary_block", reason="touches_outer_boundary")
            excluded_records.append(record)
            continue
        if len(touching_buildings) == 1:
            block = blocks[touching_buildings[0]]
            block["cells"].update(group)
            block["excluded_components"].append(excluded_id)
            record.update(assignment="building_block", block=touching_buildings[0],
                          reason="unique_topological_building_contact")
        else:
            reason = "no_surrounding_building_block" if not touching_buildings else (
                "ambiguous_multiple_building_blocks"
            )
            standalone.append({"source": "excluded_open", "cells": set(group),
                               "excluded_components": [excluded_id]})
            record.update(assignment="distinct_effectively_occupied_block", reason=reason)
        excluded_records.append(record)

    boundary_cells = set(boundary_sources)
    for block in blocks:
        if block["cells"] & boundary_sources:
            boundary_cells.update(block["cells"])
    internal_blocks = []
    for block in blocks:
        cells = block["cells"]
        if cells & boundary_cells:
            continue
        internal_blocks.append({"cells": set(cells), "source": block["source"],
                                "excluded_components": list(block["excluded_components"])})
    for block in standalone:
        if block["cells"] & boundary_cells:
            boundary_cells.update(block["cells"])
        else:
            internal_blocks.append(block)
    # Boundary contact can promote a whole connected occupied block.
    internal_blocks = [block for block in internal_blocks if not block["cells"] & boundary_cells]
    all_occupied_blocks = ([{"id": "boundary", "kind": "boundary",
                             "cells": set(boundary_cells)}] if boundary_cells else [])
    all_occupied_blocks.extend(
        {"id": f"internal-{index}", "kind": block["source"], "cells": set(block["cells"]),
         "excluded_components": list(block["excluded_components"])}
        for index, block in enumerate(internal_blocks)
    )
    effective_cells = building_cells | excluded
    effective_occupied = unary_union([polygons[cell] for cell in sorted(effective_cells)])

    hole_records = []
    for polygon_index, part in enumerate(
        item for item in _parts(accessible) if isinstance(item, Polygon)
    ):
        for ring_index, ring in enumerate(part.interiors):
            hole = Polygon(ring)
            related = []
            for block in all_occupied_blocks:
                geometry = unary_union([polygons[cell] for cell in sorted(block["cells"])])
                if hole.intersection(geometry).area > 0:
                    related.append(block["id"])
            hole_records.append({
                "id": f"hole-{len(hole_records)}",
                "polygon_component": polygon_index,
                "ring_index": ring_index,
                "area": hole.area,
                "associated_blocks": related,
            })

    for block in all_occupied_blocks:
        block["associated_holes"] = [
            hole["id"] for hole in hole_records if block["id"] in hole["associated_blocks"]
        ]
    internal_holes = [hole for hole in hole_records
                      if any(block["id"] in hole["associated_blocks"]
                             and block["kind"] != "boundary"
                             for block in all_occupied_blocks)]
    result = {
        "rule": {
            "main_open_component": "largest edge-connected component; ties by sorted cell IDs",
            "open_adjacency": "positive-length shared polygon boundary",
            "occupied_contact": "any shared polygon boundary, including a vertex",
            "outer_boundary": "boundary of the union of all cell polygons",
            "excluded_open_treatment": "effectively occupied; uniquely touching internal building block is merged, otherwise kept distinct",
            "ring_rule": "positive-winding exact cycles must enclose every cell of each internal occupied block and span all independent circulation classes",
        },
        "cell_classes": {str(cell): cell_classes[cell] for cell in sorted(cell_classes)},
        "open_adjacency": {str(cell): sorted(open_adjacency[cell]) for cell in sorted(open_adjacency)},
        "open_components": [sorted(group) for group in open_components],
        "open_component_records": [
            {"id": index, "cells": sorted(group), "size": len(group),
             "dyad_open_cells": len(group & dyad_open_cells),
             "unfilled_open_cells": len(group - dyad_open_cells),
             "main": index == 0}
            for index, group in enumerate(open_components)
        ],
        "main_open_component_size": len(main_open),
        "excluded_open_component_sizes": [len(group) for group in excluded_components],
        "main_open_cells": sorted(main_open),
        "excluded_open_components": excluded_records,
        "excluded_open_cells": sorted(excluded),
        "building_contact_components": [sorted(group) for group in building_components],
        "occupied_blocks": [
            {"id": block["id"], "kind": block["kind"],
             "cells": sorted(block["cells"]),
             "excluded_components": block.get("excluded_components", []),
             "associated_holes": block["associated_holes"]}
            for block in all_occupied_blocks
        ],
        "internal_blocks": [block["id"] for block in all_occupied_blocks
                            if block["kind"] != "boundary"],
        "circulation_holes": hole_records,
        "internal_circulation_holes": internal_holes,
        "unassociated_internal_blocks": [
            block["id"] for block in all_occupied_blocks
            if block["kind"] != "boundary" and not block["associated_holes"]
        ],
        "effective_occupied_cells": sorted(effective_cells),
    }
    clearance = clearance_factory(
        accessible, effective_occupied,
        original_obstacles=[polygons[cell] for cell in sorted(effective_cells)],
    )
    return result | evaluate_circulation_lines(
        polygons, selected_lines, all_occupied_blocks, clearance,
        include_witness_faces=include_witness_faces, face_builder=face_builder,
        face_location=face_location, face_coverage=face_coverage,
    )


def _circulation_block_witnesses(polygons, internal_blocks):
    block_geometry = {
        block["id"]: unary_union([polygons[cell] for cell in sorted(block["cells"])])
        for block in internal_blocks
    }
    block_witness = {
        block["id"]: _exact_point(block_geometry[block["id"]].representative_point().coords[0])
        for block in internal_blocks
    }
    return block_witness


def evaluate_circulation_lines(polygons, selected_lines, occupied_blocks, clearance, *,
                               include_witness_faces=False, face_builder=bounded_face_rings,
                               face_location=_ring_location, face_coverage=_ring_covers_cells,
                               block_witnesses=None):
    """Apply the same exact line and winding checks on an already classified domain."""
    internal_blocks = [block for block in occupied_blocks if block["kind"] != "boundary"]
    block_witness = (_circulation_block_witnesses(polygons, internal_blocks)
                     if block_witnesses is None else block_witnesses)
    valid_lines = []
    rejected_lines = []
    for line in selected_lines:
        if clearance.permits_exact(line.start, line.end):
            valid_lines.append(line)
        else:
            rejected_lines.append(line.line_id)
    faces = face_builder(valid_lines)
    face_locations = {
        block["id"]: [face_location(face, block_witness[block["id"]]) for face in faces]
        for block in internal_blocks
    }
    face_enclosures = {}
    for index, face in enumerate(faces):
        face_enclosures[index] = [
            block["id"] for block in internal_blocks
            if face_locations[block["id"]][index] == 1
            and face_coverage(face, block["cells"], polygons)
        ]
    circulation_cycles = [
        {"face_index": index, "enclosed_blocks": enclosed}
        for index, enclosed in face_enclosures.items() if enclosed
    ]
    block_order = [block["id"] for block in internal_blocks]
    winding_vectors = [
        [int(block_id in cycle["enclosed_blocks"]) for block_id in block_order]
        for cycle in circulation_cycles
    ]
    circulation_rank = _matrix_rank(winding_vectors)
    hole_witnesses = []
    missing = []
    for block in internal_blocks:
        locations = face_locations[block["id"]]
        enclosing = [
            index for index, blocks in face_enclosures.items() if block["id"] in blocks
        ]
        partial = [index for index, location in enumerate(locations)
                   if location == 1 and index not in enclosing]
        on_route = [index for index, location in enumerate(locations) if location == 0]
        record = {"block": block["id"], "winding": 1 if enclosing else 0,
                  "enclosing_faces": enclosing, "partial_enclosing_faces": partial,
                  "boundary_faces": on_route,
                  "associated_holes": list(block["associated_holes"])}
        hole_witnesses.append(record)
        if not enclosing:
            missing.append(block["id"])

    result = {
        "hole_witnesses": hole_witnesses,
        "circulation_cycles": circulation_cycles,
        "circulation_cycle_block_order": block_order,
        "circulation_cycle_winding_vectors": winding_vectors,
        "independent_circulation_rank": circulation_rank,
        "required_circulation_rank": len(internal_blocks),
        "missing_independent_circulation_classes": len(internal_blocks) - circulation_rank,
        "circulation_constraints_satisfied": (
            not missing and circulation_rank == len(internal_blocks)
        ),
        "missing_axial_rings": missing,
        "bounded_axial_faces": len(faces),
        "selected_line_count": len(selected_lines),
        "effective_clearance_line_count": len(valid_lines),
        "lines_crossing_effective_occupied_space": rejected_lines,
    }
    if include_witness_faces:
        result["witness_faces"] = {
            cycle["face_index"]: faces[cycle["face_index"]] for cycle in circulation_cycles
        }
    return result
