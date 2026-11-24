from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest

from voronoi_app.complementary_axial import ComplementaryStudy, settlement_key

ROOT = Path(__file__).resolve().parents[1]
METHOD = "Complementary tangents + structural reduction"


def test_complementary_selection_reuses_layers_and_invalidates_on_geometry_change():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    app.selectbox(key="axial_selection_method").select(METHOD).run()
    assert app.selectbox(key="complementary_order").value == "sheaf"
    app.checkbox(key="complementary_exchanges").uncheck()
    app.slider(key="grid_num_points").set_value(30)
    app.slider(key="agg_max_dyads").set_value(3)
    app.button(key="run_experiment").click().run()
    app.button(key="generate_complementary").click().run()
    assert not app.exception
    assert not app.error
    state = app.session_state["complementary_axial"]
    assert state["reductions"]["sheaf"].certified
    study, prepared = state["study"], state["prepared"]
    snapshot = app.session_state["complementary_snapshot"]
    app.checkbox(key="complementary_building_numbers").uncheck().run()
    app.selectbox(key="complementary_stage").select("full").run()
    assert app.session_state["complementary_axial"]["study"] is study
    assert app.session_state["complementary_snapshot"] is snapshot
    app.selectbox(key="complementary_order").select("shortest").run()
    assert "shortest" not in state["reductions"]
    app.button(key="generate_complementary").click().run()
    assert state["prepared"] is prepared
    assert state["reductions"]["shortest"].certified
    reduced = state["reductions"]["shortest"]
    app.checkbox(key="complementary_exchanges").check()
    app.button(key="generate_complementary").click().run()
    assert state["reductions"]["shortest"] is reduced
    assert state["exchanges"]["shortest"].certified
    app.button(key="complementary_movement").click().run()
    assert not app.exception
    assert not app.error
    assert state["movement"][state["exchanges"]["shortest"].ids]["valid"]
    app.number_input(key="seed").set_value(73)
    app.button(key="run_experiment").click().run()
    assert app.session_state["complementary_axial"]["key"] != state["key"]
    assert app.session_state["complementary_snapshot"] is not snapshot
    assert not app.session_state["complementary_axial"]["reductions"]


def test_source_version_is_part_of_settlement_key():
    assert settlement_key({"doors": [[1, 2]]}, "v1") != settlement_key({"doors": [[1, 2]]}, "v2")


def test_uncertified_selection_is_diagnostic_only(monkeypatch):
    reduce = ComplementaryStudy.reduce_prepared

    def reject(self, prepared, order, progress):
        return replace(reduce(self, prepared, order, progress), failure="Independent validation failed.")

    monkeypatch.setattr(ComplementaryStudy, "reduce_prepared", reject)
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    app.selectbox(key="axial_selection_method").select(METHOD).run()
    app.slider(key="grid_num_points").set_value(30)
    app.slider(key="agg_max_dyads").set_value(3)
    app.button(key="run_experiment").click().run()
    app.button(key="generate_complementary").click().run()
    assert not app.exception
    assert any("Independent validation failed" in error.value for error in app.error)
    assert any("uncertified" in warning.value for warning in app.warning)
    assert all(button.key != "complementary_movement" for button in app.button)
    assert all("independent exact structural validation" not in success.value for success in app.success)
