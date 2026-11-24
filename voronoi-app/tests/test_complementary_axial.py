from fractions import Fraction
from types import SimpleNamespace

import networkx as nx
from shapely.geometry import box

from voronoi_app.complementary_axial import boundary_index, no_progress, preselect
from voronoi_app.dynamic_winding import CycleSignatures
from voronoi_app.exact_axial import candidate_graph


def line(identifier, start, end):
    return SimpleNamespace(line_id=identifier, start=tuple(map(Fraction, start)), end=tuple(map(Fraction, end)))


def test_exact_convex_support_excludes_internal_flat_and_incidental_vertices():
    polygons = {0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1)}
    topology = {"blocks_wkb": {"joined": box(0, 0, 2, 1).wkb_hex}}
    lines = [line(0, (-1, 0), (3, 0)), line(1, (-1, -1), (1, 1)),
             line(2, (-1, Fraction(1, 1000)), (3, Fraction(1, 1000)))]
    vertices, support, _ = boundary_index(topology, polygons, {0: 7, 1: 8}, lines)
    assert {tuple(v["point"]) for v in vertices} == {("0","0"),("0","1"),("2","0"),("2","1")}
    assert [vertices[v]["members"][0]["label"] for v in support[0]] == [7, 8]
    assert 1 not in support
    assert 2 not in support


def test_pair_ties_choose_canonical_ids_and_include_unindexed():
    polygons = {0: box(0, 0, 2, 2)}
    lines = [line(0, (-2, 0), (2, 0)), line(1, (-3, 0), (1, 0)),
             line(2, (-4, 0), (0, 0)), line(3, (-1, -2), (1, -2))]
    study = SimpleNamespace(polygons=polygons, lines=lines, graph=nx.empty_graph(4),
                            neighbors=[set() for _ in lines],
                            inputs={"settlement": {"building_labels": {"0": 7}},
                                    "topology": {"blocks_wkb": {"a": polygons[0].wkb_hex}}})
    ids, anchors, vertices, _ = preselect(study, no_progress)
    origin = next(v["id"] for v in vertices if v["point"] == ["0", "0"])
    assert [i for i,a in enumerate(anchors) if origin in a] == [0, 1]
    assert ids == {0, 1, 3}


def test_dynamic_winding_uses_current_cycles_and_defers_split_blocks():
    points = [(0, 0), (4, 0), (4, 4), (0, 4)]
    lines = [line(i, a, b) for i, (a, b) in enumerate(zip(points, points[1:] + points[:1]))]
    graph = candidate_graph(lines)
    polygons = {1: box(1, 1, 2, 2), 2: box(5, 5, 6, 6)}
    w = CycleSignatures(lines, graph, polygons, [{"kind": "building", "cells": [1]}])
    assert w.rank({0, 1, 2, 3}) == 1
    assert w.rank({0, 1, 2}) == 0
    split = CycleSignatures(lines, graph, polygons, [{"kind": "building", "cells": [1, 2]}])
    assert split.rank({0, 1, 2, 3}) is None
