from fractions import Fraction as F

import pytest

from experiments.configurational_spatial import distance_squared
from experiments.configurational_statistics import concentration, distribution


def test_equal_choice_and_fractional_percentile_boundary():
    equal = concentration([1, 1, 1])
    assert equal["gini"] == 0
    assert equal["top_5_share"] == pytest.approx(.05)
    assert equal["top_10_share"] == pytest.approx(.10)
    assert concentration([0, 0]) == {"gini": None, "top_5_share": None, "top_10_share": None,
                                      "max_over_mean": None, "zero_fraction": 1}
    assert distribution([2, 2])["skewness_population"] is None


def test_exact_sampling_distance_clamps_to_segment_endpoint():
    as_point = lambda x, y: (F(x), F(y))
    a, b = as_point(0, 0), as_point(2, 0)
    assert distance_squared(as_point(3, 1), a, b) == 2
    assert distance_squared(as_point(1, "1/3"), a, b) == F(1, 9)


def test_seed_comparison_excludes_unmatched_count_and_uses_common_seeds():
    from types import SimpleNamespace

    from experiments.configurational_seed_audit import MODES, group_variability
    from experiments.configurational_sources import MATCH_KEYS
    from experiments.flat40_configurational import METRICS

    cases, rows = {}, {}
    for terrain, seed, count, value in (
        ("flat", 40, 100, 1), ("flat", 41, 100, 50),
        ("shoulder", 40, 100, 3), ("shoulder", 41, 89, 999),
    ):
        identifier = f"{terrain}-{seed}"
        cases[identifier] = SimpleNamespace(inventory=dict(
            settings={key: seed if key == "seed" else "shared" for key in MATCH_KEYS},
            building_count=count, terrain=terrain, seed=seed))
        rows[identifier] = {kind: dict(measures={metric: {"mean": value} for metric in METRICS},
            intelligibility={"r": value}, choice_concentration={"gini": value, "top_10_share": value})
            for kind in MODES}
    summary = group_variability(cases, rows)
    assert summary["unmatched_illustrative"] == ["shoulder-41"]
    assert summary["common_seeds_for_between_terrain_means"] == [40]
    result = summary["comparison"]["angular/mean_depth"]
    assert result["matched_seed_terrain_means"] == {"flat": 1, "shoulder": 3}
    assert result["largest_observed_within_terrain_range"] == 49
