from fractions import Fraction
from pathlib import Path

import matplotlib.pyplot as plt
import pytest
from streamlit.testing.v1 import AppTest

from voronoi_app.certified_maps import (
    decode_certified_research, read_certified_fixture_bytes,
)
from voronoi_app.render import fig_certified_axial_map


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "exact_y"


def test_research_display_keeps_exact_geometry_until_rendering():
    research = decode_certified_research(*read_certified_fixture_bytes(FIXTURES))
    result = research.certifications["best23"]
    lines = [research.candidates[i] for i in result["selected"]]
    original = [(line.start, line.end, line.provenance) for line in lines]
    assert len(lines) == 23
    assert all(isinstance(value, Fraction) for line in lines
               for point in (line.start, line.end) for value in point)
    figure = fig_certified_axial_map(
        research.open_polygons, research.occupied_polygons, research.paired_open_cells, lines,
    )
    try:
        segments = figure.axes[0].collections[-1].get_segments()
        assert len(segments) == 23
        for segment, line in zip(segments, lines):
            assert segment.tolist() == [[float(v) for v in line.start],
                                        [float(v) for v in line.end]]
        assert [(line.start, line.end, line.provenance) for line in lines] == original
    finally:
        plt.close(figure)


def test_research_display_rejects_modified_fixture():
    manifest, contents = read_certified_fixture_bytes(FIXTURES)
    damaged = list(contents)
    damaged[-1] += b" "
    with pytest.raises(ValueError, match="checksum mismatch"):
        decode_certified_research(manifest, tuple(damaged))


def test_streamlit_displays_all_certified_maps_without_running_live_generation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Research display must not run the live generator")

    monkeypatch.setattr("voronoi_app.orchestrator.generate_experiment_axial_map", forbidden)
    monkeypatch.setattr("voronoi_app.orchestrator.run_experiment_pipeline", forbidden)
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    app.checkbox(key="show_certified_research").check().run()
    assert not app.exception
    for key, count in (("reference23", "23"), ("reference24", "24"),
                       ("best23", "23"), ("best24", "24"), ("best25", "25"),
                       ("best_all_excluded", "23")):
        app.selectbox(key="certified_research_map").set_value(key).run()
        assert not app.exception
        assert app.metric[0].value == count
        assert any("267/267" in item.value and "3/3" in item.value
                   and "components: 1" in item.value for item in app.markdown)


def test_streamlit_surfaces_fixture_errors(monkeypatch):
    def broken_fixture(*args):
        raise ValueError("Research fixture checksum mismatch")

    monkeypatch.setattr("voronoi_app.certified_maps.read_certified_fixture_bytes", broken_fixture)
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=30).run()
    app.checkbox(key="show_certified_research").check().run()
    assert not app.exception
    assert any("checksum mismatch" in item.value for item in app.error)
    assert not app.metric
