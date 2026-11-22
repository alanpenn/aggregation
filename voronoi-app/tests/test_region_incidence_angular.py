from fractions import Fraction

import pytest
from shapely.geometry import box

from voronoi_app.batch_routing_reference import MasterNetwork
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.region_incidence_angular import angular_depth, build_incidence


def line(i, start, end):
    a, b = (tuple(map(Fraction, p)) for p in (start, end))
    return ExactCandidate(i, a, b, a, b, "test")


def test_door_on_shared_boundary_uses_both_regions_and_excludes_boundary_lines():
    regions = {0: box(0, 0, 2, 2), 1: box(2, 0, 4, 2)}
    lines = [line(0, (0, 1), (2, 1)), line(1, (2, 0), (2, 2)),
             line(2, (2, 0), (4, 2)), line(3, (4, 2), (5, 3))]
    incident, memberships, _ = build_incidence(lines, regions, [{"point": ["2", "1"]}])
    assert incident == [[0, 1]]
    assert memberships == {0: {0}, 1: {2}}


def test_angular_depth_shared_line_turns_and_distinct_failure_states():
    lines = [line(0, (0, 0), (4, 0)), line(1, (2, 0), (2, 3)),
             line(2, (2, 3), (4, 3)), line(3, (10, 0), (11, 0))]
    network = MasterNetwork(lines, [])
    costs, reasons = angular_depth(network, {0, 1, 2, 3}, [{0}, {0, 1}, {2}, {3}, set()],
                                    [(0, 1), (0, 2), (0, 3), (0, 4), (1, 2)])
    assert costs[:2] == pytest.approx([0, 2])
    assert costs[2:4] == [None, None]
    assert costs[4] == pytest.approx(1)
    assert reasons == ["reachable", "reachable", "disconnected", "attachment_failure", "reachable"]


def test_angular_depth_obeys_order_of_intersections_along_intermediate_line():
    lines = [line(0, (4, -2), (6, 0)), line(1, (0, 0), (6, 0)),
             line(2, (0, 0), (2, 2))]
    network = MasterNetwork(lines, [])
    # The middle leg must go west, requiring two 135-degree turns.
    costs, _ = angular_depth(network, {0, 1, 2}, [{0}, {2}], [(0, 1)])
    assert costs == pytest.approx([3])
