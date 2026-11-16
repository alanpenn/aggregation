from types import SimpleNamespace

import matplotlib.pyplot as plt
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from scipy.spatial import Voronoi
from shapely.geometry import box

from voronoi_app.axial import AxialLine
from voronoi_app.render import UNASSIGNED_OPEN_COLOR, fig_aggregation, fig_angular_comparison


class DummyAxes:
    def __init__(self):
        self.calls = []
        self.fills = []

    def fill(self, *args, **kwargs):
        self.fills.append(kwargs)

    def text(self, *args, **kwargs):
        pass

    def plot(self, *args, **kwargs):
        self.calls.append((args, kwargs))

    def set_xlim(self, *args, **kwargs):
        pass

    def set_ylim(self, *args, **kwargs):
        pass

    def set_aspect(self, *args, **kwargs):
        pass

    def set_title(self, *args, **kwargs):
        pass

    def legend(self, *args, **kwargs):
        pass

    def axis(self, *args, **kwargs):
        pass


class DummyFigure:
    def tight_layout(self):
        pass


def test_fig_aggregation_draws_black_door_lines(monkeypatch):
    axes = DummyAxes()
    fig = DummyFigure()
    monkeypatch.setattr(plt, "subplots", lambda *args, **kwargs: (fig, axes))

    result = SimpleNamespace(
        voronoi=Voronoi(
            [[0, 0], [10, 0], [10, 10], [0, 10], [4, 5], [6, 5]]
        ),
        config=SimpleNamespace(canvas_size=10),
        buildings={5},
        open_spaces={4},
        doors=[(4, 5)],
        building_labels={5: 1},
        mean_depth={4: 0.5, 5: 0.5},
        los_lines=[],
    )

    fig_aggregation(result)

    assert any(
        len(args) == 2 and kwargs.get("color") == "black" and kwargs.get("linewidth") == 1.5
        for args, kwargs in axes.calls
    )
    assert any(fill.get("color") == UNASSIGNED_OPEN_COLOR for fill in axes.fills)


def test_angular_comparison_renders_selections_and_sample_depths(monkeypatch):
    figure = Figure(figsize=(10, 10))
    FigureCanvasAgg(figure)
    monkeypatch.setattr(plt, "subplots", lambda *args, **kwargs: (figure, figure.subplots()))
    result = SimpleNamespace(buildings={1}, config=SimpleNamespace(canvas_size=4))
    polygons = {0: box(0, 0, 3, 4), 1: box(3, 0, 4, 4)}
    lines = [
        AxialLine(0, (0, 1), (3, 1)),
        AxialLine(1, (0, 2), (3, 2)),
        AxialLine(2, (0, 3), (3, 3)),
        AxialLine(3, (0, 0), (3, 0)),
    ]
    samples = [(1, 1), (2, 2), (2, 3)]
    depths = {(0, 1): 1.0, (0, 2): 3.0, (1, 0): 2.0}
    figure = fig_angular_comparison(result, polygons, lines, {0, 1},
                                    [lines[1], lines[2]], samples, depths)
    ax = figure.axes[0]
    assert [line.get_color() for line in ax.lines] == ["#ca5343", "#7450a0", "#007d58"]
    assert [item.get_text() for item in ax.get_legend().get_texts()] == [
        "Greedy only", "Angular only", "Both",
    ]
    values = ax.collections[0].get_array()
    assert values.data[:2].tolist() == pytest.approx([2.0, 2.0])
    assert values.mask[2]
    assert figure.axes[1].get_ylabel() == "Mean angular depth from sample"
