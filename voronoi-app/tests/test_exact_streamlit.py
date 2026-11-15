from pathlib import Path
from time import monotonic

import pytest
from streamlit.testing.v1 import AppTest

from voronoi_app.core import ExperimentPipeline
from voronoi_app.exact_enumeration import generate_fresh_exact_candidate_pool
from voronoi_app.orchestrator import ExperimentOrchestrator, run_experiment_pipeline


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("seed", "grid", "grid_params"), [
    (11, "voronoi", {"num_points": 30}),
    (42, "voronoi", {"num_points": 30}),
    (73, "voronoi", {"num_points": 30}),
    (42, "cartesian", {"resolution": 6}),
    (42, "topography_responsive_voronoi", {"num_points": 30}),
])
def test_fresh_pool_from_generated_settlement(seed, grid, grid_params):
    pipeline = ExperimentPipeline(
        grid_generator=grid, grid_params=grid_params, aggregation_params={"max_dyads": 3},
        seed=seed,
    )
    experiment = run_experiment_pipeline(pipeline)
    polygons = ExperimentOrchestrator(pipeline)._space_polygons(experiment.grid)
    opened = {cell: polygon for cell, polygon in polygons.items()
              if cell not in experiment.buildings}
    occupied = {cell: polygons[cell] for cell in experiment.buildings}
    start = monotonic()
    problem, audit = generate_fresh_exact_candidate_pool(opened, occupied)
    print(f"\ngrid={grid} seed={seed} candidates={len(problem.pool.candidates)} "
          f"seconds={monotonic() - start:.2f} counts={audit.counts}")
    assert problem.pool.candidates
    assert audit.counts["missing-certified-supports"] == 0
    assert all(line.provenance and problem.clearance.permits_exact(line.start, line.end)
               for line in problem.pool.candidates)


def test_exact_ui_enumeration_filters_and_new_experiment_invalidation():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    app.selectbox(key="axial_display").select("Exact axial candidates").run()
    app.slider(key="grid_num_points").set_value(30)
    app.slider(key="agg_max_dyads").set_value(3)
    app.button(key="run_experiment").click().run()
    assert not app.exception
    assert not app.error
    assert "exact_candidate_result" not in app.session_state
    app.button(key="run_exact_candidates").click().run()
    assert not app.exception
    assert not app.error
    saved = app.session_state["exact_candidate_result"]
    assert saved[3].pool.candidates
    chosen = app.selectbox(key="exact_inspect").value
    selected = next(line for line in saved[3].pool.candidates if line.line_id == chosen)
    assert any("maximal interval (exact)" in item.value for item in app.json)
    source = selected.provenance[0].source
    app.multiselect(key="exact_types").set_value([source]).run()
    assert not app.exception
    options = {int(option) for option in app.selectbox(key="exact_inspect").options}
    assert options
    assert options == {line.line_id for line in saved[3].pool.candidates
                       if any(s.source == source for s in line.provenance)}
    refs = [ref for support in selected.provenance
            for ref in (*support.start_vertices, *support.end_vertices)]
    assert refs
    building = refs[0].building_id
    app.multiselect(key="exact_buildings").set_value([building]).run()
    options = {int(option) for option in app.selectbox(key="exact_inspect").options}
    assert options == {
        line.line_id for line in saved[3].pool.candidates
        if any(s.source == source for s in line.provenance)
        and any(ref.building_id == building for s in line.provenance
                for ref in (*s.start_vertices, *s.end_vertices))
    }
    app.number_input(key="exact_min_length").set_value(selected.length + 1000).run()
    assert any("No candidates match" in item.value for item in app.info)
    app.number_input(key="exact_min_length").set_value(0.0).run()
    assert not app.exception
    app.selectbox(key="axial_display").select("Existing sightlines").run()
    app.selectbox(key="axial_display").select("Exact axial candidates").run()
    assert app.session_state["exact_candidate_result"] is saved
    app.number_input(key="seed").set_value(73)
    app.button(key="run_experiment").click().run()
    assert not app.exception
    assert app.session_state["current_exact_experiment"].pipeline.seed == 73
    assert "exact_candidate_result" not in app.session_state
    app.button(key="run_exact_candidates").click().run()
    assert not app.exception
    assert not app.error
    assert app.session_state["exact_candidate_result"] is not saved


@pytest.mark.parametrize("mode", ["Existing sightlines", "Axial Map"])
def test_existing_display_modes_still_run(mode):
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    app.selectbox(key="axial_display").select(mode).run()
    app.slider(key="grid_num_points").set_value(30)
    app.slider(key="agg_max_dyads").set_value(3)
    app.button(key="run_experiment").click().run()
    assert not app.exception
    assert not app.error
    assert any("completed with seed" in item.value for item in app.success)
    expected = "Axial sightlines" if mode == "Existing sightlines" else "Axial Map"
    assert any(item.value == expected for item in app.subheader)
