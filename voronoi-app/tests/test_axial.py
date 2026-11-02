"""Synthetic-geometry validation for the sampled axial approximation."""

import sys
from pathlib import Path

import networkx as nx
import pytest
from shapely.geometry import LineString, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voronoi_app.morphic.axial import (  # noqa: E402
    AxialLine,
    AxialRepresentation,
    axial_diagnostics,
    extract_axial_representation,
)
from voronoi_app.morphic.axial_experiment import (
    AxialExperimentConfig,
    run_axial_comparison,
    run_axial_experiment,
    save_axial_batch,
)
from voronoi_app.morphic.axial_statistics import paired_final_tests  # noqa: E402
from voronoi_app.morphic.open_space import open_space_geometry  # noqa: E402
from voronoi_app.morphic.carrier import Carrier  # noqa: E402


def extract(geometry, spacing=2.0):
    return extract_axial_representation(
        geometry, sample_spacing=spacing, angle_step_degrees=15
    )


def assert_lines_accessible(representation):
    domain = representation.open_geometry
    for axial_line in representation.lines:
        assert axial_line.geometry.difference(domain.buffer(1e-7)).length < 1e-6
    assert representation.covered_sample_count == representation.sample_count


def test_straight_corridor_has_long_axial_line():
    domain = box(0, 0, 20, 2)
    result = extract(domain)
    assert result.lines
    assert max(line.length for line in result.lines) == pytest.approx(20)
    assert result.graph.number_of_edges() == 0
    assert_lines_accessible(result)


def test_l_corridor_has_intersecting_axial_lines():
    domain = unary_union([box(0, 0, 12, 2), box(0, 0, 2, 12)])
    result = extract(domain)
    assert len(result.lines) >= 2
    assert nx.number_connected_components(result.graph) == 1
    assert result.graph.number_of_edges() >= 1
    assert_lines_accessible(result)


def test_t_junction_has_connected_axial_graph():
    domain = unary_union([box(0, 0, 12, 2), box(5, 0, 7, 10)])
    result = extract(domain)
    assert result.graph.number_of_nodes() >= 2
    assert nx.number_connected_components(result.graph) == 1
    assert_lines_accessible(result)


def test_cross_has_intersection_relationships():
    domain = unary_union([box(0, 4, 12, 6), box(5, 0, 7, 10)])
    result = extract(domain)
    assert result.graph.number_of_edges() >= 1
    assert nx.number_connected_components(result.graph) == 1
    assert_lines_accessible(result)


def test_ring_keeps_lines_out_of_central_void():
    domain = box(0, 0, 12, 12).difference(box(3, 3, 9, 9))
    result = extract(domain)
    assert result.lines
    assert not any(line.geometry.distance(box(3, 3, 9, 9)) < 1e-6
                   and line.geometry.intersection(box(3, 3, 9, 9)).length > 1e-6
                   for line in result.lines)
    assert_lines_accessible(result)


def test_courtyard_with_entrance_lines_remain_in_open_domain():
    ring = box(0, 0, 12, 12).difference(box(3, 3, 9, 9))
    entrance = box(5, 0, 7, 3.1)
    domain = unary_union([ring, entrance])
    result = extract(domain)
    assert result.lines
    assert_lines_accessible(result)
    assert not any(line.geometry.crosses(box(4, 4, 8, 8)) for line in result.lines)


def test_disconnected_open_space_produces_disconnected_axial_graph():
    domain = unary_union([box(0, 0, 10, 2), box(20, 0, 30, 2)])
    result = extract(domain)
    assert nx.number_connected_components(result.graph) >= 2
    assert_lines_accessible(result)


def test_open_space_geometry_is_union_of_unoccupied_cells():
    carrier = Carrier.from_square_grid(3, 3)
    geometry = open_space_geometry(carrier, [4])
    assert geometry is not None
    assert geometry.area == pytest.approx(8)
    assert not geometry.contains(carrier.polygons[4].representative_point())


def test_empty_domain_returns_empty_representation():
    result = extract(LineString())
    assert result.lines == []
    assert result.graph.number_of_nodes() == 0
    metrics = axial_diagnostics(result)
    assert metrics["axial_line_count"] == 0
    assert metrics["intelligibility_pearson"] is None


def test_axial_integration_and_intelligibility_on_path_graph():
    geometries = [
        LineString([(0, i), (5, i)]) for i in range(5)
    ]
    lines = [AxialLine(i, geometry, geometry.length, ()) for i, geometry in enumerate(geometries)]
    graph = nx.path_graph(5)
    representation = AxialRepresentation("synthetic", {}, box(0, 0, 5, 5), lines, graph, 5)
    metrics = axial_diagnostics(representation, local_radius=3)
    assert metrics["axial_line_count"] == 5
    assert metrics["intersection_count"] == 4
    assert metrics["connectivity"] == {0: 1, 1: 2, 2: 2, 3: 2, 4: 1}
    assert metrics["mean_depth"][0] == pytest.approx(2.5)
    assert metrics["mean_depth"][2] == pytest.approx(1.5)
    assert metrics["mean_depth_distribution"][0] == pytest.approx(2.5)
    assert all(value is not None for value in metrics["global_integration_rra"].values())
    assert metrics["intelligibility_n"] == 5
    assert metrics["intelligibility_pearson"] is not None
    assert metrics["intelligibility_r_squared"] == pytest.approx(
        metrics["intelligibility_pearson"] ** 2
    )


def test_axial_degenerate_intelligibility_is_missing():
    geometries = [LineString([(0, i), (1, i)]) for i in range(4)]
    lines = [AxialLine(i, geometry, 1, ()) for i, geometry in enumerate(geometries)]
    graph = nx.complete_graph(4)
    representation = AxialRepresentation("synthetic", {}, box(0, 0, 1, 4), lines, graph, 4)
    metrics = axial_diagnostics(representation)
    assert metrics["intelligibility_pearson"] is None
    assert metrics["intelligibility_r_squared"] is None
    assert metrics["global_integration_rra"] == {0: None, 1: None, 2: None, 3: None}


def test_invalid_axial_settings_raise():
    with pytest.raises(ValueError):
        extract_axial_representation(box(0, 0, 1, 1), sample_spacing=0)
    with pytest.raises(ValueError):
        extract_axial_representation(box(0, 0, 1, 1), angle_step_degrees=180)


def test_axial_comparison_reuses_carrier_and_records_valid_stages():
    config = AxialExperimentConfig(
        num_cells=40, occupied_target=12, seed=3, sample_spacing=15,
        analysis_interval=5,
    )
    runs = run_axial_comparison(config, ["random", "adjacent", "enclosing"])
    assert len({run.carrier_id for run in runs.values()}) == 1
    assert len({id(run.carrier) for run in runs.values()}) == 1
    for mode, run in runs.items():
        steps = [snapshot.step for snapshot in run.snapshots]
        assert steps == sorted(set(steps))
        assert steps[-1] == len(run.generation.occupied)
        assert all(snapshot.axial_metrics["method"] == "sampled_maximal_lines_v1"
                   for snapshot in run.snapshots)
        if mode == "enclosing":
            assert steps[-1] <= config.occupied_target
            assert not any(step > len(run.generation.occupied) for step in steps)


def test_axial_experiment_reproducibility_and_json_output(tmp_path):
    config = AxialExperimentConfig(
        mode="adjacent", num_cells=30, occupied_target=8, seed=8,
        sample_spacing=20, analysis_interval=4,
    )
    first = run_axial_experiment(config)
    second = run_axial_experiment(config)
    assert first.carrier_id == second.carrier_id
    assert first.generation.occupied == second.generation.occupied
    assert [s.axial_metrics["axial_line_count"] for s in first.snapshots] == [
        s.axial_metrics["axial_line_count"] for s in second.snapshots
    ]
    paths = save_axial_batch([first], tmp_path / "out")
    assert paths["results"].exists()
    assert list(paths["carriers"].glob("*.json"))
    import json
    saved = json.loads(paths["results"].read_text())
    assert saved[0]["carrier_id"] == first.carrier_id
    assert saved[0]["generation"]["transformations"]
    assert saved[0]["snapshots"][0]["lines"]


def test_paired_statistics_use_seed_matched_common_stage():
    from types import SimpleNamespace

    runs = []
    for seed in range(5):
        for mode, shift in (("random", 0), ("adjacent", 2)):
            metrics = {
                "axial_line_count": 10 + shift,
                "line_lengths": [5 + shift, 8 + shift],
                "global_integration_distribution": [0.5 + shift, 1.0 + shift],
                "intelligibility_r_squared": 0.4,
            }
            runs.append(SimpleNamespace(
                config=SimpleNamespace(mode=mode, seed=seed),
                snapshots=[SimpleNamespace(step=60, axial_metrics=metrics)],
            ))
    results = paired_final_tests(runs, step=60)
    assert len(results) == 4
    assert all(row["n_pairs"] == 5 for row in results)
    assert all(row["mean_paired_difference_b_minus_a"] > 0 for row in results[:3])
    assert results[-1]["p_value"] == 1.0
    assert results[-1]["p_value_holm"] == 1.0
