from types import SimpleNamespace

import matplotlib.pyplot as plt
from scipy.spatial import Voronoi

from voronoi_app.render import fig_aggregation


class DummyAxes:
    def __init__(self):
        self.calls = []

    def fill(self, *args, **kwargs):
        pass

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
