"""Regression tests for the experimental constructive selector."""
from shapely.geometry import LineString

from experiments.constructive_axial import Selection, families, normalize, rankings, redundant
from test_experimental_circulation_topology import candidate, courtyard
from voronoi_app.angular import LineClearance
from voronoi_app.batch_methods import _domain, derive_topology
from voronoi_app.exact_axial import candidate_graph
from voronoi_app.experimental_visibility import IndexedClearance


def test_ranking_is_normalized_and_stable_under_ties():
    assert normalize([5, 5]) == [0, 0]
    assert normalize([3, 5, 7]) == [0, .5, 1]
    rows = [{"length": 10, "normalized": [1, 0, 0, 0, 0]},
            {"length": 10, "normalized": [1, 0, 0, 0, 0]},
            {"length": 8, "normalized": [0, 1, 1, 1, 0]}]
    assert rankings(rows) == {"A": [0, 1, 2], "B": [2, 0, 1], "B-coverage": [2, 0, 1], "D": [2, 0, 1]}


def test_transverse_families_group_only_similar_neighbors():
    similar = [{1}, {0, 2}, {1}, set()]
    assert families({0, 1, 2, 3}, similar) == [[0, 1, 2], [3]]
    assert families({0, 2, 3}, similar) == [[0], [2], [3]]


def test_duplicate_suppression_keeps_complementary_diagonals():
    horizontal = LineString([(0, 0), (50, 0)])
    duplicate = LineString([(0, 1), (50, 1)])
    crossing = LineString([(0, -3), (50, 3)])
    regions = {1, 2, 3}
    assert redundant(horizontal, duplicate, (1, 0), (1, 0), regions, regions)
    assert not redundant(horizontal, crossing, (1, 0), (50/crossing.length, 6/crossing.length), regions, regions)
    assert not redundant(horizontal, duplicate, (1, 0), (1, 0), regions, {4, 5})


def test_winding_completion_and_exchange_require_exact_enclosure():
    polygons, buildings, dyads, lines = courtyard()
    lines.append(candidate(4, (0, 1), (4, 1)))
    settlement = {"polygons_wkb": {str(i): p.wkb_hex for i,p in polygons.items()},
                  "building_labels": {str(i): i for i in buildings}, "dyad_open_cells": sorted(dyads)}
    inputs = {"settlement": settlement, "candidates": {"pool":{"ring_candidates":[0,1,2,3]}},
              "analysis": {"holes":1,"incidence":{"region_lines":{"0":[0,4]},"doorway_regions":[[0]]}}}
    inputs["topology"] = derive_topology(inputs, {}).output
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    measures = [{"regions":[0] if i in (0,4) else [], "doorways":[0] if i in (0,4) else [],
                 "redundant":[], "transverse":{}} for i in range(len(lines))]
    selector = Selection(inputs,lines,candidate_graph(lines),measures,clearance)
    current, trace = {0}, []
    assert not selector.validate(frozenset(current))["valid"]
    assert selector.complete(current,[0,1,2,3,4],trace) is None
    assert current == {0,1,2,3}
    assert trace[-1]["stage"] == "circulation" and trace[-1]["rank_gain"] == 1
    replacement, matched, attempts = selector.exchange(current,[4,0,1,2,3])
    assert replacement == matched == {1,2,3,4}
    assert all(len(attempt["remove"]) == 1 for attempt in attempts if attempt["valid"])
    assert selector.validate(replacement)["rank"] == 1


def test_face_separation_recovers_independent_winding_rank():
    from shapely.geometry import box

    polygons = {row*9+col:box(col,row,col+1,row+1) for row in range(9) for col in range(9)}
    buildings = {20,60}
    lines = [candidate(0,(1,1),(8,1)),candidate(1,(8,1),(8,8)),
             candidate(2,(8,8),(1,8)),candidate(3,(1,8),(1,1)),
             candidate(4,(4,1),(4,8))]
    settlement = {"polygons_wkb":{str(i):p.wkb_hex for i,p in polygons.items()},
                  "building_labels":{str(i):i for i in buildings},"dyad_open_cells":[]}
    inputs = {"settlement":settlement,"candidates":{"pool":{"ring_candidates":[]}},
              "analysis":{"holes":2,"incidence":{"region_lines":{"0":[0]},"doorway_regions":[[0]]}}}
    inputs["topology"] = derive_topology(inputs,{}).output
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    measures = [{"regions":[0] if i == 0 else [],"doorways":[0] if i == 0 else [],
                 "redundant":[],"transverse":{}} for i in range(len(lines))]
    selector = Selection(inputs,lines,candidate_graph(lines),measures,clearance)
    current, trace = {0,1,2,3}, []
    check = selector.validate(frozenset(current))
    assert check["rank"] == 1 and not check["missing_rings"]
    assert selector.complete(current,list(range(len(lines))),trace) is None
    assert trace == [{"stage":"circulation","add":[4],"rank_before":1,"rank_gain":1,
                      "missing_rings_repaired":0,"repair_strategy":"face separation"}]
    assert selector.validate(frozenset(current))["rank"] == 2
