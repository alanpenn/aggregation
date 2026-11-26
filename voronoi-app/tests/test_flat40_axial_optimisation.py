from fractions import Fraction

import pytest

from experiments.flat40_axial_optimisation import FRAMES, endpoints, limits, pair_summary


def test_boundary_clipping_keeps_exact_intersection_and_never_extends_finite_segment():
    a = (Fraction(70), Fraction(50))
    b = (Fraction(100), Fraction(50))
    t = limits(a, b, *FRAMES["inset_5"], finite=True)
    assert endpoints(a, b, t) == ((70, 50), (95, 50))
    actual = limits(a, b, *FRAMES["rotate_ccw_22.62"], finite=True)
    infinite = limits(a, b, *FRAMES["rotate_ccw_22.62"], finite=False)
    assert actual == (0, 1)
    assert endpoints(a, b, infinite)[-1] == (Fraction(625, 6), 50)


def test_success_rate_uses_pairs_not_replacement_count():
    rows = [{"delta": 15, "counts": {"accepted": 3}},
            {"delta": 20, "counts": {"missing_region": 4}},
            {"delta": 45, "counts": {"accepted": 1}}]
    summary = pair_summary(rows)
    assert summary["near"] == {"pairs": 2, "successful_pairs": 1, "accepted_replacements": 3}
    assert summary["other"]["successful_pairs"] == 1
    assert summary["fisher_two_sided_descriptive"] == pytest.approx(1)
