"""Tests for the morphic grammar module (hand-defined cell configurations)."""

import math
import sys
from pathlib import Path

import networkx as nx
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voronoi_app.morphic import morphology as mo  # noqa: E402
from voronoi_app.morphic.carrier import Carrier, build_voronoi_carrier  # noqa: E402
from voronoi_app.morphic.experiment import (  # noqa: E402
    MorphicConfig, run_batch, run_comparison, run_experiment,
)
from voronoi_app.morphic.metrics import measure_configuration  # noqa: E402
from voronoi_app.morphic.rules import (  # noqa: E402
    TERMINATION_ENCLOSED, TERMINATION_NO_CANDIDATES, TERMINATION_TARGET_REACHED,
    AdjacentAggregation, EnclosingAggregation, RandomOccupation, run_rule,
)


def cid(column, row, columns=5):
    return row * columns + column


@pytest.fixture
def grid5():
    return Carrier.from_square_grid(5, 5)


# 8 cells surrounding the centre cell (2, 2) of a 5x5 grid.
RING = [cid(c, r) for c in (1, 2, 3) for r in (1, 2, 3) if (c, r) != (2, 2)]
CENTRE = cid(2, 2)


# ---- adjacency -----------------------------------------------------------

def test_edge_adjacency_only(grid5):
    assert grid5.neighbours(0) == [1, 5]
    assert cid(1, 1) not in grid5.adjacency[0]  # diagonal = point contact


def test_point_contact_is_not_adjacency():
    polygons = {0: box(0, 0, 1, 1), 1: box(1, 1, 2, 2), 2: box(1, 0, 2, 1)}
    carrier = Carrier.from_polygons(polygons, (0, 0, 2, 2))
    assert 1 not in carrier.adjacency[0]
    assert 2 in carrier.adjacency[0] and 1 in carrier.adjacency[2]


def test_adjacency_is_symmetric_on_voronoi():
    carrier = build_voronoi_carrier(60, seed=3)
    for cell, neighbours in carrier.adjacency.items():
        for neighbour, length in neighbours.items():
            assert carrier.adjacency[neighbour][cell] == length > 0


def test_voronoi_carrier_has_exact_cell_count():
    assert len(build_voronoi_carrier(200, seed=40).cells) == 200


# ---- exterior / enclosed open space ---------------------------------------

def test_enclosed_and_exterior_open_space(grid5):
    enclosed = mo.enclosed_open_components(grid5, RING)
    assert enclosed == [frozenset({CENTRE})]
    exterior = mo.exterior_open_cells(grid5, RING)
    assert CENTRE not in exterior
    assert exterior == set(grid5.cells) - set(RING) - {CENTRE}
    categories = mo.classify_cells(grid5, RING)
    assert categories[CENTRE] == mo.ENCLOSED_OPEN
    assert categories[RING[0]] == mo.OCCUPIED
    assert categories[0] == mo.EXTERIOR_OPEN


def test_gap_in_ring_leaks_to_exterior(grid5):
    occupied = [c for c in RING if c != cid(2, 1)]
    assert mo.enclosed_open_components(grid5, occupied) == []
    assert CENTRE in mo.exterior_open_cells(grid5, occupied)


# ---- graph cycles versus geometric enclosure ------------------------------

def test_cycle_without_enclosure(grid5):
    block = [cid(1, 1), cid(2, 1), cid(1, 2), cid(2, 2)]
    assert mo.graph_cycle_count(grid5, block) == 1
    assert mo.enclosed_open_components(grid5, block) == []


def test_cycle_with_enclosure(grid5):
    assert mo.graph_cycle_count(grid5, RING) == 1
    assert len(mo.enclosed_open_components(grid5, RING)) == 1


def test_enclosure_without_graph_cycle(grid5):
    # Removing a corner of the ring breaks the cycle, but the four
    # edge-neighbours of the centre are still occupied, so it stays enclosed.
    occupied = [c for c in RING if c != cid(1, 1)]
    assert mo.graph_cycle_count(grid5, occupied) == 0
    assert len(mo.enclosed_open_components(grid5, occupied)) == 1


def test_vertex_triangle_is_trivial_cycle():
    from shapely.geometry import Polygon
    o, a, b, c = (0, 0), (2, 0), (-1, 1.7), (-1, -1.7)
    carrier = Carrier.from_polygons(
        {0: Polygon([o, a, b]), 1: Polygon([o, b, c]), 2: Polygon([o, c, a])},
        (-1, -1.7, 2, 1.7),
    )
    assert mo.graph_cycle_count(carrier, [0, 1, 2]) == 1
    assert mo.triangle_count(carrier, [0, 1, 2]) == 1
    assert mo.nontrivial_cycle_count(carrier, [0, 1, 2]) == 0
    assert mo.enclosed_open_components(carrier, [0, 1, 2]) == []


def test_nontrivial_cycles_on_square_ring(grid5):
    assert mo.nontrivial_cycle_count(grid5, RING) == 1


def test_enclosure_score(grid5):
    assert mo.enclosure_score(grid5, RING, [CENTRE]) == pytest.approx(1.0)
    without = [c for c in RING if c != cid(2, 1)]
    assert mo.enclosure_score(grid5, without, [CENTRE]) == pytest.approx(0.75)
    assert mo.enclosure_score(grid5, [], [CENTRE]) == 0.0


# ---- components, boundary and metrics --------------------------------------

def test_components_and_boundary_cells(grid5):
    occupied = [0, 1, 24]
    assert mo.occupied_components(grid5, occupied) == [frozenset({0, 1}), frozenset({24})]
    assert mo.candidate_cells(grid5, [0]) == [1, 5]
    assert mo.aggregate_boundary_cells(grid5, RING) == set(RING)


def test_measurements_and_missing_values(grid5):
    block = [cid(1, 1), cid(2, 1), cid(1, 2), cid(2, 2)]
    metrics = measure_configuration(grid5, block)
    assert metrics["occupied_area"] == pytest.approx(4)
    assert metrics["aggregate_perimeter"] == pytest.approx(8)
    assert metrics["compactness"] == pytest.approx(4 * math.pi * 4 / 64)
    assert metrics["n_open_components"] == 1
    assert metrics["target_enclosed"] is None

    empty = measure_configuration(grid5, [])
    assert empty["compactness"] is None
    assert empty["aggregate_perimeter"] is None
    assert empty["largest_occupied_component"] is None

    full = measure_configuration(grid5, grid5.cells)
    assert full["open_connectivity_mean"] is None


def test_open_connectivity_uses_open_graph_only(grid5):
    metrics = measure_configuration(grid5, RING)
    # The enclosed centre cell has no open neighbours.
    assert metrics["n_enclosed_open_components"] == 1
    assert metrics["open_connectivity_min"] == 0.0


# ---- generative rules -------------------------------------------------------

@pytest.fixture(scope="module")
def voronoi60():
    return build_voronoi_carrier(80, seed=7)


def test_random_mode_not_required_to_be_connected(voronoi60):
    result = run_rule(RandomOccupation(), voronoi60, 30, seed=1)
    assert len(set(result.occupied)) == 30
    assert result.termination == TERMINATION_TARGET_REACHED
    assert len(mo.occupied_components(voronoi60, result.occupied)) > 1


@pytest.mark.parametrize("seed", range(5))
def test_adjacent_mode_stays_connected(voronoi60, seed):
    result = run_rule(AdjacentAggregation(), voronoi60, 40, seed=seed)
    assert len(mo.occupied_components(voronoi60, result.occupied)) == 1
    for step in result.transformations:
        assert step.delta_occupied_components <= 0 or step.step == 1


@pytest.mark.parametrize("seed", range(5))
def test_enclosing_mode_connected_and_target_preserved(voronoi60, seed):
    rule = EnclosingAggregation(strength=1.0, target_size=2, after_enclosure="continue")
    result = run_rule(rule, voronoi60, 40, seed=seed)
    assert result.target and not (result.target & set(result.occupied))
    assert len(mo.occupied_components(voronoi60, result.occupied)) == 1


def test_enclosing_stops_when_target_enclosed():
    carrier = Carrier.from_square_grid(7, 7)
    rule = EnclosingAggregation(strength=1.0, after_enclosure="stop")
    result = run_rule(rule, carrier, len(carrier.cells) - 1, seed=3)
    assert result.termination == TERMINATION_ENCLOSED
    assert mo.is_target_enclosed(carrier, result.occupied, result.target)
    assert len(mo.occupied_components(carrier, result.occupied)) == 1


def test_termination_when_no_candidates_remain():
    carrier = Carrier.from_square_grid(4, 4)
    rule = EnclosingAggregation(strength=0.5, after_enclosure="continue")
    result = run_rule(rule, carrier, len(carrier.cells), seed=0)
    assert result.termination == TERMINATION_NO_CANDIDATES
    assert len(result.occupied) == len(carrier.cells) - 1
    assert not (result.target & set(result.occupied))


def test_reproducible_under_fixed_seed(voronoi60):
    first = run_rule(EnclosingAggregation(), voronoi60, 30, seed=11)
    second = run_rule(EnclosingAggregation(), voronoi60, 30, seed=11)
    assert first.occupied == second.occupied
    other = run_rule(AdjacentAggregation(), voronoi60, 30, seed=12)
    assert other.occupied != run_rule(AdjacentAggregation(), voronoi60, 30, seed=11).occupied


def test_transformation_log_is_complete(voronoi60):
    result = run_rule(AdjacentAggregation(), voronoi60, 10, seed=2)
    assert [t.step for t in result.transformations] == list(range(1, 11))
    assert [t.cell for t in result.transformations] == result.occupied
    assert all(t.n_candidates >= 1 and t.rule == "adjacent" for t in result.transformations)
    assert result.transformations[0].n_candidates == len(voronoi60.cells)


def test_enclosure_strength_zero_is_unbiased_weighting(voronoi60):
    rule = EnclosingAggregation(strength=0.0)
    from voronoi_app.morphic.rules import State
    state = State(carrier=voronoi60)
    rule.prepare(state)
    state.occupy(rule.eligible(state)[0])
    weights = rule.weights(state, rule.eligible(state))
    assert weights is None or len(set(weights)) == 1


def test_invalid_strength_rejected():
    with pytest.raises(ValueError):
        EnclosingAggregation(strength=1.5)


# ---- experiment layer -------------------------------------------------------

def test_comparison_shares_geometry_and_ids_are_deterministic():
    base = MorphicConfig(num_cells=60, occupied_target=15, seed=4)
    runs = run_comparison(base, ["random", "adjacent", "enclosing"])
    carriers = {id(run.carrier) for run in runs.values()}
    assert len(carriers) == 1
    again = run_experiment(MorphicConfig(num_cells=60, occupied_target=15, seed=4, mode="adjacent"))
    assert again.experiment_id == runs["adjacent"].experiment_id
    assert again.result.occupied == runs["adjacent"].result.occupied


def test_batch_smoke():
    runs = run_batch([1, 2], ["random", "enclosing_continue"],
                     MorphicConfig(num_cells=50, occupied_target=12))
    assert len(runs) == 4
    assert all(run.metrics["n_occupied"] == 12 for run in runs)


# ---- existing behaviour preserved -----------------------------------------

def test_existing_pipeline_still_runs():
    from voronoi_app.core import ExperimentPipeline
    from voronoi_app.orchestrator import run_experiment_pipeline

    output = run_experiment_pipeline(ExperimentPipeline(seed=5, space_syntax_measure="connectivity"))
    assert "connectivity" in output.analysis_results
    assert output.measure_values == output.analysis_results["connectivity"]
