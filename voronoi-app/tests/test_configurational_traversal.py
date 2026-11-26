import pytest

from experiments.configurational_fixtures import FIXTURES, brute, build, fixture_result
from voronoi_app.configurational_traversal import Traversal


@pytest.mark.parametrize("name", FIXTURES)
@pytest.mark.parametrize("mode", ["angular", "metric", "angular_metric"])
def test_fixture_against_independent_enumeration(name, mode):
    fixture_result(FIXTURES[name], mode)


def test_reversal_is_a_traversal_and_teleportation_is_impossible():
    line = Traversal(build(FIXTURES["reversal"]))
    assert line.paths([0])[0][1] == (180_000_000, 1, 0)
    assert line.points[0][1] == line.points[1][0]
    graph = build(FIXTURES["same_junction"])
    travel = Traversal(graph)
    for state, (a, b) in enumerate(travel.points):
        for following, _, _ in travel.links[state]:
            assert travel.points[following][0] == b
    assert len(travel.links[1]) == 1
    cost, witnesses = brute(travel, [2, 3], {4, 5}, "angular")
    assert cost == (151_927_513, 1, 0)
    assert len(witnesses) == 1
    assert graph.edges[0, 1]["turn_microdegrees"] + graph.edges[0, 2]["turn_microdegrees"] == 28_072_486


def test_analytic_chain_turn_and_rectangular_loop():
    chain = fixture_result(FIXTURES["straight"], "angular")
    assert chain["expected_choice"] == [0, 1, 0]
    assert all(pair["actual_cost"][0] == 0 for pair in chain["pairs"])
    assert fixture_result(FIXTURES["corner"], "angular")["pairs"][0]["actual_cost"][:2] == (90_000_000, 1)
    loop = fixture_result(FIXTURES["loop"], "angular")
    assert sum(p["actual_paths"] == 2 for p in loop["pairs"]) == 2
    assert loop["expected_choice"] == pytest.approx([1/6]*4)
    angular = fixture_result(FIXTURES["unequal_length_tie"], "angular")["pairs"]
    angular_metric = fixture_result(FIXTURES["unequal_length_tie"], "angular_metric")["pairs"]
    assert any(a["actual_paths"] == 2 and b["actual_paths"] == 1
               and a["actual_cost"][0] == b["actual_cost"][0] for a, b in zip(angular, angular_metric))
