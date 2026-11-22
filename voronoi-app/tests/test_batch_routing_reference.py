from fractions import Fraction
from math import sqrt

import pytest

from voronoi_app.angular import SampleAttachment
from voronoi_app.batch_routing_reference import MasterNetwork, excess
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_angular_selection import angular_reference


def rational(x, y):
    return Fraction(x), Fraction(y)


def line(number, start, end):
    a, b = rational(*start), rational(*end)
    return ExactCandidate(number, a, b, a, b, "test")


def test_master_routes_hold_connectors_and_match_existing_angular_cost():
    lines = [line(0, (0, 0), (2, 0)), line(1, (2, 0), (2, 3)),
             line(2, (0, 0), (2, 3))]
    terminals = [{"point": rational(0, -1), "connectors": [(0, rational(0, 0))]},
                 {"point": rational(3, 3), "connectors": [(1, rational(2, 3))]}]
    fixed = [SampleAttachment(d["point"], p, i) for d in terminals for i, p in d["connectors"]]
    network = MasterNetwork(lines, terminals)
    reduced, full = {0, 1}, {0, 1, 2}
    assert network.route(reduced, False) == pytest.approx([7])
    assert network.route(full, False) == pytest.approx([2 + sqrt(13)])
    assert network.route(reduced, True) == pytest.approx([3])
    assert network.route(full, True) == pytest.approx([1])
    for selected in (full, reduced):
        original = angular_reference([lines[i] for i in sorted(selected)], fixed, [0, 0])
        assert network.route(selected, True) == pytest.approx([original.depths[0, 1]])
    assert network.route({0, 2}, True) == [None]
    assert network.depths(full) == network.depths(reduced) == [1]


def test_same_stop_keeps_lowest_turn_without_duplicating_sparse_arcs():
    lines = [line(0, (0, 0), (2, 0)), line(1, (1, -1), (1, 1))]
    stop = rational(1, 0)
    doors = [{"point": rational(0, -1), "connectors": [(0, stop), (1, stop)]},
             {"point": rational(2, 1), "connectors": [(0, stop), (1, stop)]}]
    network = MasterNetwork(lines, doors)
    assert network.route({0, 1}, True) == pytest.approx([0])
    assert network.route({0, 1}, False) == pytest.approx([2 * sqrt(2)])
    assert network.route({0}, True) == pytest.approx([0])


def test_excess_does_not_clamp_and_marks_unavailable_percentages():
    outcome = excess([2.0, 0.0, None, 4.0], [1.0, 0.1, 2.0, None], 1e-8, 1e-9)
    assert outcome["pairs"][0]["excess"] == -1.0
    assert outcome["pairs"][1]["percent_excess"] is None
    assert outcome["violations"] == [0, 2]
    assert outcome["newly_unreachable"] == [3]


def test_sampled_origins_select_same_pairs_from_master():
    lines = [line(0, (0, 0), (4, 0))]
    doors = [{"point": rational(i, 1), "connectors": [(0, rational(i, 0))]} for i in range(4)]
    network = MasterNetwork(lines, doors)
    for angular in (False, True):
        full = network.route({0}, angular)
        assert network.route({0}, angular, origins=[1, 2]) == full[3:]
