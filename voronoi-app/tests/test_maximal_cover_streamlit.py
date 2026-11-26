from pathlib import Path
from fractions import Fraction

from shapely.geometry import box
from streamlit.testing.v1 import AppTest

from experiments.live_maximal_cover import LEGACY, METHOD, advance_cover, read_checkpoint
from voronoi_app.complementary_axial import ComplementaryStudy, settlement_snapshot
from voronoi_app.region_incidence_angular import exact_region_lines


ROOT = Path(__file__).resolve().parents[1]
COMPLEMENTARY = "Complementary tangents + structural reduction"


def test_live_cover_defaults_persist_and_geometry_changes_invalidate():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not app.exception
    assert app.selectbox(key="axial_coverage_method").value == METHOD
    assert app.selectbox(key="axial_selection_method").value == COMPLEMENTARY
    assert app.selectbox(key="complementary_order").value == "sheaf"
    assert app.checkbox(key="complementary_exchanges").value
    app.selectbox(key="axial_coverage_method").select(LEGACY).run()
    app.selectbox(key="complementary_order").select("shortest").run()
    app.slider(key="grid_num_points").set_value(30)
    app.slider(key="agg_max_dyads").set_value(3)
    app.button(key="run_experiment").click().run()
    assert "complementary_snapshot" in app.session_state
    app.number_input(key="seed").set_value(73).run()
    assert "complementary_snapshot" not in app.session_state
    assert app.selectbox(key="axial_coverage_method").value == LEGACY
    assert app.selectbox(key="complementary_order").value == "shortest"
    assert not app.exception


def test_incomplete_checkpoint_blocks_selection(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "app"))
    import maximal_cover_ui
    from experiments import live_maximal_cover
    monkeypatch.setattr(maximal_cover_ui, "read_checkpoint",
                        lambda snapshot, _: live_maximal_cover.read_checkpoint(snapshot, tmp_path))
    monkeypatch.setattr(maximal_cover_ui, "advance_cover",
                        lambda snapshot, _, budget: live_maximal_cover.advance_cover(snapshot, tmp_path, budget))
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    app.slider(key="grid_num_points").set_value(30)
    app.slider(key="agg_max_dyads").set_value(3)
    app.button(key="run_experiment").click().run()
    app.number_input(key="maximal_cover_budget").set_value(1)
    app.button(key="advance_maximal_cover").click().run()
    assert not app.exception
    assert any("Enumeration checkpoint" in item.value for item in app.caption)
    assert not any(button.key == "generate_complementary" for button in app.button)


def test_exact_completed_registry_drives_ch_and_preserves_frozen_pool(tmp_path):
    cells = {3*y+x: box(x, y, x+1, y+1) for x in range(3) for y in range(3)}
    snapshot = settlement_snapshot(cells, {4:1}, [1], [(1,4)])
    partial = advance_cover(snapshot, tmp_path, 1)
    assert not partial["ready"]
    assert not partial["enumeration_complete"]
    done = advance_cover(snapshot, tmp_path, 1000)
    assert done["ready"]
    assert done["uncovered_area"] == "0"
    assert len(done["regions"]) == 4
    assert read_checkpoint(snapshot, tmp_path) == done
    assert read_checkpoint(snapshot | {"doors":[]}, tmp_path) is None

    study = ComplementaryStudy.from_settlement(snapshot, maximal_regions=done["regions"])
    legacy = ComplementaryStudy.from_settlement(snapshot)
    assert study.lines == legacy.lines
    assert study.geometry.blocks == legacy.geometry.blocks
    rings = {int(i): [tuple(map(Fraction, p)) for p in ring]
             for i, ring in study.inputs["candidates"]["regions_exact"].items()}
    assert study.regions == exact_region_lines(study.lines, rings)
    result = study.reduce_prepared(study.prepare(), "sheaf")
    assert result.certified
    assert result.summary["regions"] == 4
    assert result.summary["rank"] == 1
