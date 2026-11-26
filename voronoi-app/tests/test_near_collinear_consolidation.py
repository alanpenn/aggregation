from fractions import Fraction
from types import SimpleNamespace

import pytest

from experiments.near_collinear_consolidation import arm_geometry, continuation


def line(a, b):
    return SimpleNamespace(start=tuple(map(Fraction, a)), end=tuple(map(Fraction, b)))


def test_directed_endpoint_turn_cannot_reverse_a_missing_arm():
    left = line((0, 0), (3, 0))
    same_side = continuation(left, line((0, 0), (3, 1)))
    across = continuation(left, line((-3, 1), (0, 0)))
    assert same_side["delta"] > 150
    assert across["delta"] == pytest.approx(18.43494882)
    assert across["endpoint_flags"] == [True, True]
    assert across["arms"] == [["3", "0"], ["-3", "1"]]


def test_interior_crossing_has_two_directions_and_is_orientation_independent():
    a = line((-4, 0), (4, 0))
    b = line((-4, -1), (4, 1))
    row = continuation(a, b)
    assert row["kind"] == "transverse_interior"
    assert row["junction"] == ["0", "0"]
    assert row["delta"] == pytest.approx(14.03624347)
    assert row == continuation(line(a.end, a.start), line(b.end, b.start))
    angles, overlap = arm_geometry(row, line((-5, 0), (5, 0)))
    assert angles == pytest.approx([0, row["delta"]])
    assert overlap == [1, 1]


def test_disjoint_and_collinear_pairs_remain_separate():
    a = line((0, 0), (4, 0))
    assert continuation(a, line((0, 1), (4, 1))) is None
    assert continuation(a, line((2, 0), (5, 0))) == {
        "kind": "collinear_overlap", "interval": [["2", "0"], ["4", "0"]],
    }
    assert continuation(a, line((4, 0), (5, 0)))["kind"] == "collinear_touch"
