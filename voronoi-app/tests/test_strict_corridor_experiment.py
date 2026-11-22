from fractions import Fraction

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from voronoi_app.angular import _exact_point
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.strict_corridor_experiment import interior_witness, physical_profile


def test_bank_profile_distinguishes_two_sided_street_from_open_band():
    axis = ((0, 0), (20, 0))
    south = box(0, -4, 20, -2)
    north = box(0, 3, 20, 5)
    street = physical_profile(axis, unary_union([south, north]))
    assert street["two_banks"] == 9
    assert street["median_banked_width"] == pytest.approx(5)
    assert physical_profile(axis, south)["two_banks"] == 0


def test_protocol_witness_is_an_exact_point_inside_traversed_region():
    a, b = (Fraction(-1), Fraction(1)), (Fraction(5), Fraction(1))
    line = ExactCandidate(0, a, b, a, b, "test")
    ring = list(map(_exact_point,box(0,0,4,2).exterior.coords))
    assert interior_witness(line, ring) == (Fraction(2), Fraction(1))
