import pytest

from voronoi_app.route_sparse_experiment import angular_bands, compare_routes, pareto


def test_angular_excess_strata_distinguish_missing_and_zero_costs():
    full = [0.0, .02, 2.0, 3.0]
    sparse = [.1, .12, 2.2, None]
    bands = angular_bands(full, sparse)
    assert bands["[0,0.1)"]["absolute"]["mean"] == pytest.approx(.1)
    assert bands["[0,0.1)"]["percent"]["reachable"] == 1
    assert bands["[1,inf)"]["cost"]["unreachable"] == 1
    assert compare_routes({"metric": full, "angular": full},
                          {"metric": sparse, "angular": sparse})["metric"]["cost"]["reachable"] == 3


def test_pareto_keeps_count_and_both_route_objectives_and_breaks_length_ties():
    def entry(count, length, metric, angular):
        return {"line_count": count, "length": length,
                "routing": {k: {"absolute": {"mean": value}}
                            for k, value in [("metric", metric), ("angular", angular)]}}

    maps = [entry(45, 201, 3, 1), entry(45, 200, 3, 1),
            entry(44, 200, 4, 1), entry(46, 190, 3, 2),
            entry(46, 250, 1, 3)]
    assert pareto(maps) == [1, 2, 4]
