import json
import os
from fractions import Fraction
from pathlib import Path

import networkx as nx
import pytest
from shapely.geometry import box
from shapely.strtree import STRtree

from experiments.shortest_path_backbone import matching_candidates
from voronoi_app.angular import LineClearance, SampleAttachment
from voronoi_app.exact_axial import ExactCandidate, candidate_graph
from voronoi_app.experimental_connectivity_selection import connectivity_order, structural_failure
from voronoi_app.experimental_structural_backbone import (
    complete_coverage, footprint, grow_backbone, preserves_footprint, reach_masks,
    reduce_selection,
)
from voronoi_app.experimental_visibility import _outward_bounds
from voronoi_app.experimental_structural_routes import evaluate_routes


def line(i, a, b):
    a, b = tuple(map(Fraction, a)), tuple(map(Fraction, b))
    return ExactCandidate(i, a, b, a, b, "test")


def test_growth_uses_fixed_full_graph_not_convex_coverage():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (0, -2), (0, 2)),
             line(2, (-2, -2), (2, 2)), line(3, (6, 0), (7, 0))]
    graph = candidate_graph(lines)
    order = connectivity_order(lines, graph)
    groups = [{0, 1, 2}, {3}]
    selected, reasons = grow_backbone(lines, graph, groups, [], set(), 10)
    assert selected == grow_backbone(lines, graph, groups, [], set(), 10)[0]
    assert order[0] in selected and 3 in selected
    assert len(selected) > 2
    assert any("direction" in values for values in reasons.values())
    assert all(nx.is_connected(graph.subgraph(selected & group)) for group in groups)


def test_coverage_completion_repairs_ring_and_connectivity():
    lines = [line(0, (0, 0), (2, 0)), line(1, (2, 0), (2, 2)),
             line(2, (2, 2), (0, 2)), line(3, (0, 2), (0, 0)),
             line(4, (0, 0), (2, 2))]
    graph = candidate_graph(lines)
    covers = [{0}, {0}, {1}, {1}, {0, 1}]
    result, added, repairs, _ = complete_coverage(
        lines, covers, {0, 1}, [set(range(5))], graph, [(1, Fraction(1, 2))],
        {4}, {0, 1, 2, 3})
    assert not added and repairs
    assert structural_failure(lines, covers, {0, 1}, [set(range(5))], graph,
                              [(1, Fraction(1, 2))], result) is None


def test_two_for_one_preserves_structural_footprint_and_clearance():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (1, -2), (1, 2)), line(3, (-2, -2), (2, 2))]
    graph = candidate_graph(lines)
    covers = [{0}, {1}, {2}, {1, 2}]
    required = footprint(lines, reach_masks(graph, 4), {0})
    occupied = box(8, 8, 9, 9)
    clearance = LineClearance(box(-5, -5, 10, 10).difference(occupied), occupied,
                              original_obstacles=[occupied])
    args = (lines, covers, {0, 1, 2}, [set(range(4))], graph, [],
            {0, 1, 2}, clearance, required)
    selected, exchanges, _ = reduce_selection(*args)
    assert (selected, exchanges) == reduce_selection(*args)[:2]
    assert selected == {0, 3} and exchanges == [((1, 2), (3,))]
    assert preserves_footprint(footprint(lines, reach_masks(graph, 4), selected), required)
    occupied = box(Fraction(1, 2), Fraction(1, 2), Fraction(3, 5), Fraction(3, 5))
    blocked = LineClearance(box(-5, -5, 10, 10).difference(occupied), occupied,
                            original_obstacles=[occupied])
    with pytest.raises(ValueError, match="Exchange candidate 3 fails exact clearance"):
        reduce_selection(*args[:7], blocked, required)


def test_single_removal_and_three_for_two_are_both_searched():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (0, -2), (0, 2)), line(3, (1, -2), (1, 2)),
             line(4, (-2, -2), (2, 2)), line(5, (-2, 2), (2, -2)),
             line(6, (Fraction(1, 2), -1), (Fraction(1, 2), 1))]
    graph = candidate_graph(lines)
    covers = [{0}, {1, 4}, {2, 5}, {3, 6}, {1, 2, 3}, {4, 5, 6}, {0}]
    required = footprint(lines, reach_masks(graph, 7), {0})
    occupied = box(8, 8, 9, 9)
    clearance = LineClearance(box(-5, -5, 10, 10).difference(occupied), occupied,
                              original_obstacles=[occupied])
    selected, exchanges, attempts = reduce_selection(
        lines, covers, set(range(7)), [set(range(7))], graph, [],
        {0, 1, 2, 3, 6}, clearance, required)
    assert selected == {0, 4, 5}
    assert exchanges == [((6,), ()), ((1, 2, 3), (4, 5))]
    assert attempts["feasibility_checks"] >= 2
    assert all(attempts["searches"].values())


def test_tangent_containment_requires_collinear_subsegment():
    lines = [line(0, (0, 0), (4, 0)), line(1, (2, -1), (2, 1))]
    candidates = [(item.start, item.end) for item in lines]
    tree = STRtree([_outward_bounds(a, b) for a, b in candidates])
    assert matching_candidates((Fraction(1), Fraction(0)), (Fraction(3), Fraction(0)),
                               candidates, tree) == [0]


def test_routes_use_fixed_attachments_and_allow_direct_visibility():
    lines = [line(0, (0, 0), (4, 0)), line(1, (2, 0), (2, 3))]
    attachments = [[SampleAttachment((0, -1), (0, 0), 0)],
                   [SampleAttachment((3, 3), (2, 3), 1)],
                   [SampleAttachment((4, -1), (4, 0), 0)]]
    references = {(0, 1): {"status": "occluded", "length": 6.0},
                  (0, 2): {"status": "direct", "length": 4.0}}
    paths, stats = evaluate_routes(lines, attachments, [0, 0, 0], references)
    assert paths[0]["status"] == "routed"
    assert paths[0]["metric"] == pytest.approx(7)
    assert paths[0]["angular"] == pytest.approx(3)
    assert paths[1]["status"] == "direct" and paths[1]["angular"] == 0
    assert stats["intersection_points"] == 1
    reduced, _ = evaluate_routes(lines[:1], attachments, [0, 0, 0], references)
    assert reduced[0]["status"] == "attachment-failure"
    assert reduced[1]["status"] == "direct"


def test_routes_distinguish_disconnected_network_from_attachment_failure():
    lines = [line(0, (0, 0), (1, 0)), line(1, (3, 0), (4, 0))]
    attachments = [[SampleAttachment((0, -1), (0, 0), 0)],
                   [SampleAttachment((4, -1), (4, 0), 1)]]
    paths, _ = evaluate_routes(lines, attachments, [0, 0],
                               {(0, 1): {"status": "occluded", "length": 4.0}})
    assert paths[0]["status"] == "network-disconnected"


@pytest.mark.skipif(
    not os.environ.get("STRUCTURAL_BACKBONE_DATA") or not os.environ.get("STRUCTURAL_BACKBONE_REPLAY"),
    reason="set both structural-backbone result directories to compare saved replays",
)
@pytest.mark.parametrize("rule", ["gain-1%", "gain-0.5%", "gain-0.25%"])
def test_saved_input_replay_reproduces_structural_selections(rule):
    results = []
    for variable in ("STRUCTURAL_BACKBONE_DATA", "STRUCTURAL_BACKBONE_REPLAY"):
        path = Path(os.environ[variable]) / f"{rule}-stages.json"
        results.append(json.loads(path.read_text()))
    for stage in ("backbone", "completed", "reduced"):
        assert results[0][stage] == results[1][stage]
    assert results[0]["details"]["reasons"] == results[1]["details"]["reasons"]
    assert results[0]["details"]["exchanges"] == results[1]["details"]["exchanges"]
