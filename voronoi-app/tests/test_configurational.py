from fractions import Fraction

import networkx as nx
import pytest

from voronoi_app.configurational import axial_graph, convex_graph, measures, pearson, segment_graph


def test_transverse_crossing_splits_without_rounding():
    cross = (Fraction(1, 3), Fraction(1, 2))
    axial = axial_graph({12: ((0, cross[1]), (1, cross[1])), 19: ((cross[0], 0), (cross[0], 1))})
    assert axial.edges[12, 19]["contacts"] == (cross,)
    graph = segment_graph(axial)
    assert (len(graph), len(graph.edges)) == (4, 6)
    assert all(row["junction"] == cross for _, _, row in graph.edges(data=True))
    assert sorted(row["turn_microdegrees"] for _, _, row in graph.edges(data=True)) == [0, 0] + [90_000_000] * 4
    assert all(row["mean_depth"] == 60 for row in measures(graph, angular=True).values())


def test_collinear_overlaps_keep_owner_inventory_and_touch():
    lines = {3: ((0, 0), (3, 0)), 5: ((1, 0), (2, 0)), 7: ((3, 0), (4, 0))}
    axial = axial_graph(lines)
    assert set(axial.edges) == {(3, 5), (3, 7)}
    segments = segment_graph(axial)
    assert [row["owners"] for _, row in segments.nodes(data=True)] == [[3], [3, 5], [3], [7]]
    assert nx.is_isomorphic(segments, nx.path_graph(4))
    rows = measures(segments, angular=True)
    assert all(row["mean_depth"] == 0 and row["integration"] == 1 for row in rows.values())
    assert rows[1]["choice"] == pytest.approx(2 / 3)


def test_convex_boundary_touch_is_excluded_and_tiny_overlap_is_exact():
    def rectangle(a, b):
        return tuple((Fraction(x), Fraction(y)) for x, y in ((a, 0), (b, 0), (b, 1), (a, 1)))

    epsilon = Fraction(1, 10**40)
    graph = convex_graph({"a": rectangle(0, 1), "b": rectangle(1, 2), "c": rectangle(1 - epsilon, 1 + epsilon)})
    assert not graph.has_edge("a", "b")
    assert graph["a"]["c"]["overlap_area"] == graph["b"]["c"]["overlap_area"] == epsilon


def test_disconnected_and_equal_shortest_paths_have_explicit_normalisation():
    graph = nx.cycle_graph(4)
    graph.add_node(4)
    rows = measures(graph)
    assert rows[0]["reachable"] == 3
    assert rows[0]["mean_depth"] == pytest.approx(4 / 3)
    assert rows[0]["integration"] == pytest.approx(9 / 28)
    assert rows[0]["choice"] == pytest.approx(1 / 12)
    assert rows[4] == dict(connectivity=0, mean_depth=None, integration=0, choice=0, reachable=0)
    assert pearson([1, 1], [2, 3]) is None
    assert pearson([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)
