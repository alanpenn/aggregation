from fractions import Fraction

import pytest
from shapely.geometry import box

from voronoi_app.angular import LineClearance
from voronoi_app.batch_routing_reference import MasterNetwork
from voronoi_app.exact_axial import ExactCandidate, _bounds
from voronoi_app.experimental_circulation_topology import evaluate_circulation_lines
from voronoi_app.experimental_entrance_reduction import visibility_masks
from voronoi_app.region_incidence_angular import angular_depth, build_incidence
from voronoi_app.strict_coverage_experiment import incidence_sets, omissions, verify_monotone


def line(i, first, second):
    a, b = [tuple(map(Fraction, p)) for p in (first, second)]
    return ExactCandidate(i, a, b, a, b, "test")


def test_boundary_only_doorway_failure_and_addition_with_multiple_eligible_lines():
    lines = [line(0, (0, 0), (3, 0)), line(1, (0, 1), (3, 1)), line(2, (1, 0), (1, 2))]
    geometry = {162: box(0, 0, 3, 2)}
    incident, by_region, _ = build_incidence(lines, geometry, [{"point": ["3", "1"]}])
    legacy = visibility_masks(lines, [set(), {162}, {162}], geometry, [_bounds(x) for x in lines])
    assert legacy[0] == 1 << 162
    regions, doors = incidence_sets({"region_lines": by_region, "doorway_regions": incident})
    assert doors == [{1, 2}]
    assert omissions({0}, regions, doors) == ([162], [0])
    assert omissions({0, 1}, regions, doors) == ([], [])
    assert omissions({0, 2}, regions, doors) == ([], [])


def test_strict_coverage_repair_can_preserve_a_required_winding_class():
    obstacle = box(1, 1, 2, 2)
    accessible = box(0, 0, 3, 3).difference(obstacle)
    clearance = LineClearance(accessible, obstacle, original_obstacles=[obstacle])
    blocks = [{"id": "internal", "kind": "internal", "cells": [0], "associated_holes": []}]
    ring = [line(0, (1, 1), (2, 1)), line(1, (2, 1), (2, 2)),
            line(2, (2, 2), (1, 2)), line(3, (1, 2), (1, 1))]
    repair = line(4, (0, 1), (1, 1))
    for selection, expected in [(ring[:3], 0), (ring, 1), (ring + [repair], 1)]:
        topology = evaluate_circulation_lines({0: obstacle}, selection, blocks, clearance)
        assert topology["independent_circulation_rank"] == expected
        assert not topology["lines_crossing_effective_occupied_space"]


def test_full_pool_incidence_angular_depth_is_monotone_for_exact_subsets():
    lines = [line(0, (0, 0), (3, 0)), line(1, (3, 0), (3, 3)), line(2, (3, 3), (0, 3)),
             line(3, (0, 0), (3, 3))]
    network = MasterNetwork(lines, [])
    full, _ = angular_depth(network, {0, 1, 2, 3}, [{0, 3}, {2, 3}], [(0, 1)])
    subset, _ = angular_depth(network, {0, 1, 2}, [{0}, {2}], [(0, 1)])
    assert full == [0.]
    assert subset == [2.]
    verify_monotone(full, subset)
    with pytest.raises(ValueError, match="beats"):
        verify_monotone(subset, full)
