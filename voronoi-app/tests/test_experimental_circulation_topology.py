from fractions import Fraction

from shapely.geometry import Polygon, box

from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_circulation_topology import analyse_circulation_topology


def candidate(line_id, start, end):
    a = tuple(Fraction(value) for value in start)
    b = tuple(Fraction(value) for value in end)
    return ExactCandidate(line_id, a, b, a, b, "test")


def courtyard():
    polygons = {
        row * 5 + column: box(column, row, column + 1, row + 1)
        for row in range(5) for column in range(5)
    }
    buildings = {
        row * 5 + column
        for row in (1, 2, 3) for column in (1, 2, 3)
        if (row, column) != (2, 2)
    }
    dyads = {0, 4, 20, 24}
    ring = [
        candidate(0, (1, 1), (4, 1)),
        candidate(1, (4, 1), (4, 4)),
        candidate(2, (4, 4), (1, 4)),
        candidate(3, (1, 4), (1, 1)),
    ]
    return polygons, buildings, dyads, ring


def test_excluded_open_cell_joins_its_unique_building_block_and_ring_winds_once():
    polygons, buildings, dyads, ring = courtyard()
    result = analyse_circulation_topology(polygons, buildings, dyads, ring)
    assert result["rule"]["main_open_component"].startswith("largest edge-connected")
    assert len(result["main_open_cells"]) == 16
    assert result["excluded_open_components"] == [{
        "component": 0,
        "cells": [12],
        "open_components": [1],
        "touching_building_blocks": [0],
        "touches_outer_boundary": False,
        "assignment": "building_block",
        "block": 0,
        "reason": "unique_topological_building_contact",
    }]
    assert result["internal_blocks"] == ["internal-0"]
    assert len(result["circulation_holes"]) == 1
    assert result["unassociated_internal_blocks"] == []
    assert result["missing_axial_rings"] == []
    assert result["hole_witnesses"][0]["winding"] == 1
    assert result["independent_circulation_rank"] == 1
    assert result["circulation_constraints_satisfied"]


def test_missing_closed_route_is_reported_without_hard_coded_ring_count():
    polygons, buildings, dyads, _ = courtyard()
    result = analyse_circulation_topology(polygons, buildings, dyads, [])
    assert len(result["circulation_holes"]) == 1
    assert result["missing_axial_rings"] == ["internal-0"]
    assert result["missing_independent_circulation_classes"] == 1


def test_boundary_touching_building_block_is_special_not_an_internal_ring():
    polygons = {
        0: Polygon([(0, 0), (1, .2), (.2, 1)]),
        1: box(2, 2, 4, 4),
    }
    result = analyse_circulation_topology(
        polygons, {0}, set(), [], settlement_boundary=box(0, 0, 5, 5),
    )
    assert result["occupied_blocks"][0]["kind"] == "boundary"
    assert result["internal_blocks"] == []
    assert result["circulation_holes"] == []
    assert result["missing_axial_rings"] == []


def test_selected_route_crossing_effectively_occupied_cell_is_not_a_ring_witness():
    polygons, buildings, dyads, ring = courtyard()
    unsafe = ring + [candidate(4, (0, 2), (5, 2))]
    result = analyse_circulation_topology(polygons, buildings, dyads, unsafe)
    assert result["lines_crossing_effective_occupied_space"] == [4]
    assert result["missing_axial_rings"] == []


def test_unfilled_cells_participate_in_open_component_classification():
    polygons, buildings, dyads, _ = courtyard()
    result = analyse_circulation_topology(polygons, buildings, dyads, [])
    assert result["cell_classes"]["0"] == "dyad_open"
    assert result["cell_classes"]["1"] == "unfilled_open"
    assert result["cell_classes"]["12"] == "unfilled_open"


def test_excluded_component_touching_multiple_building_blocks_stays_distinct():
    polygons = {
        0: box(0, 0, 2, 2),
        1: box(2, 2, 4, 4),
        2: box(2, 1, 3, 2),
        3: box(3, 4, 4, 5),
    }
    result = analyse_circulation_topology(
        polygons, {2, 3}, set(), [], settlement_boundary=box(0, 0, 6, 6),
    )
    assert result["main_open_cells"] == [0]
    excluded = result["excluded_open_components"][0]
    assert excluded["reason"] == "ambiguous_multiple_building_blocks"
    assert excluded["touching_building_blocks"] == [0, 1]
    assert excluded["assignment"] == "distinct_effectively_occupied_block"
    assert any(block["cells"] == [1] and block["kind"] == "excluded_open"
               for block in result["occupied_blocks"])


def test_one_face_enclosing_two_blocks_does_not_claim_two_independent_rings():
    polygons = {
        row * 9 + column: box(column, row, column + 1, row + 1)
        for row in range(9) for column in range(9)
    }
    buildings = {2 * 9 + 2, 6 * 9 + 6}
    ring = [
        candidate(0, (1, 1), (8, 1)),
        candidate(1, (8, 1), (8, 8)),
        candidate(2, (8, 8), (1, 8)),
        candidate(3, (1, 8), (1, 1)),
    ]

    result = analyse_circulation_topology(polygons, buildings, set(), ring)

    assert len(result["circulation_holes"]) == 2
    assert result["missing_axial_rings"] == []
    assert result["circulation_cycle_winding_vectors"] == [[1, 1]]
    assert result["independent_circulation_rank"] == 1
    assert result["required_circulation_rank"] == 2
    assert result["missing_independent_circulation_classes"] == 1
    assert not result["circulation_constraints_satisfied"]


def test_separate_faces_span_two_independent_circulation_classes():
    polygons = {
        row * 9 + column: box(column, row, column + 1, row + 1)
        for row in range(9) for column in range(9)
    }
    buildings = {2 * 9 + 2, 6 * 9 + 6}
    ring = [
        candidate(0, (1, 1), (4, 1)),
        candidate(1, (4, 1), (4, 4)),
        candidate(2, (4, 4), (1, 4)),
        candidate(3, (1, 4), (1, 1)),
        candidate(4, (5, 5), (8, 5)),
        candidate(5, (8, 5), (8, 8)),
        candidate(6, (8, 8), (5, 8)),
        candidate(7, (5, 8), (5, 5)),
    ]

    result = analyse_circulation_topology(polygons, buildings, set(), ring)

    assert len(result["circulation_cycles"]) == 2
    assert result["independent_circulation_rank"] == 2
    assert result["missing_independent_circulation_classes"] == 0
    assert result["circulation_constraints_satisfied"]
