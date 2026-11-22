import gzip
import json
import os
from fractions import Fraction
from pathlib import Path

import pytest
from shapely.geometry import box

from voronoi_app.angular import LineClearance
from voronoi_app.exact_axial import ExactCandidate, candidate_graph
from voronoi_app.experimental_tangent_reduction import (
    augment_weighted, minimum_cover, reduce_tangent, represented, tangent_masks, weight,
)


def line(i, a, b):
    a, b = tuple(map(Fraction, a)), tuple(map(Fraction, b))
    return ExactCandidate(i, a, b, a, b, "test")


def test_minimum_cover_handles_shared_candidates_and_existing_support():
    masks = [0b001, 0b010, 0b100, 0b011, 0b110]
    chosen = minimum_cover(masks, 0b111)
    assert len(chosen) == 2 and represented(chosen, masks) == 0b111
    assert minimum_cover(masks, 0b111, initial=0b001) == (4,)
    with pytest.raises(ValueError, match="cannot be represented"):
        minimum_cover([0b001], 0b111)


def test_weighted_augmentation_counts_each_tangent_once():
    masks = tangent_masks(3, [{"candidates": [0, 1]}, {"candidates": [1, 2]}])
    assert weight(represented({0, 1}, masks), [10, 5]) == 15
    result, added = augment_weighted({0}, masks, [10, 5], 15, [0, 1, 2])
    assert result == {0, 1} and added == [1]


def test_reduction_preserves_tangent_and_finds_two_for_one():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (1, -2), (1, 2)), line(3, (-2, -2), (2, 2))]
    graph = candidate_graph(lines)
    occupied = box(8, 8, 9, 9)
    clearance = LineClearance(box(-5, -5, 10, 10).difference(occupied), occupied,
                              original_obstacles=[occupied])
    masks = [1, 0, 0, 1]
    args = (lines, [{0}, {1}, {2}, {1, 2}], {0, 1, 2}, [set(range(4))], graph, [],
            {0, 1, 2}, clearance, masks, [10], 1, 10)
    selected, exchanges, stats = reduce_tangent(*args)
    assert selected == {0, 3} and exchanges == [((1, 2), (3,))]
    assert stats["searches"]["3-for-2"] > 0
    assert reduce_tangent(*args) == (selected, exchanges, stats)
    with pytest.raises(ValueError, match="tangent constraints"):
        reduce_tangent(*args[:6], {1, 2}, *args[7:])
    obstacle = box(0.5, 0.5, 0.6, 0.6)
    blocked = LineClearance(box(-5, -5, 10, 10).difference(obstacle), obstacle,
                            original_obstacles=[obstacle])
    with pytest.raises(ValueError, match="Exchange candidate 3 fails exact clearance"):
        reduce_tangent(*args[:7], blocked, *args[8:])


def test_tangent_constrained_three_for_two_and_single_removal():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (0, -2), (0, 2)), line(3, (1, -2), (1, 2)),
             line(4, (-2, -2), (2, 2)), line(5, (-2, 2), (2, -2)),
             line(6, (Fraction(1, 2), -1), (Fraction(1, 2), 1))]
    graph = candidate_graph(lines)
    occupied = box(8, 8, 9, 9)
    clearance = LineClearance(box(-5, -5, 10, 10).difference(occupied), occupied,
                              original_obstacles=[occupied])
    covers = [{0}, {1, 4}, {2, 5}, {3, 6}, {1, 2, 3}, {4, 5, 6}, {0}]
    selected, exchanges, _ = reduce_tangent(
        lines, covers, set(range(7)), [set(range(7))], graph, [],
        {0, 1, 2, 3, 6}, clearance, [1, 0, 0, 0, 0, 0, 0], [1], 1, 1)
    assert selected == {0, 4, 5}
    assert exchanges == [((6,), ()), ((1, 2, 3), (4, 5))]


@pytest.mark.skipif(
    not os.environ.get("TANGENT_REDUCTION_DATA") or not os.environ.get("SHORTEST_PATH_VISIBILITY_DATA"),
    reason="set both saved result directories to audit Y tangent constraints",
)
def test_saved_y_tangent_constraints_and_minimum_cover():
    path = Path(os.environ["TANGENT_REDUCTION_DATA"]) / "results.json.gz"
    tangent_path = Path(os.environ["SHORTEST_PATH_VISIBILITY_DATA"]) / "backbone-records.json.gz"
    with gzip.open(path, "rt") as file:
        results = json.load(file)
    with gzip.open(tangent_path, "rt") as file:
        edges = json.load(file)["edges"]
    edges.sort(key=lambda edge: (-edge["usage"], edge["start"], edge["end"]))
    masks = tangent_masks(3214, edges)
    weights = [edge["usage"] for edge in edges]
    assert tuple(results["minimum_top_ten_cover"]) == minimum_cover(masks, (1 << 10) - 1)
    assert len(results["minimum_top_ten_cover"]) == 10
    for label, minimum in (("weighted-25", 25), ("weighted-50", 50),
                           ("weighted-75", 75), ("weighted-90", 90)):
        selected = results["maps"][label]["selected"]
        assert 100 * weight(represented(selected, masks), weights) >= minimum * sum(weights)
    assert represented(results["maps"]["top-ten"]["selected"], masks) & ((1 << 10) - 1) == (1 << 10) - 1


@pytest.mark.skipif(
    not os.environ.get("TANGENT_REDUCTION_DATA") or not os.environ.get("TANGENT_REDUCTION_REPLAY"),
    reason="set both tangent-reduction result directories to compare independent replays",
)
def test_saved_y_replay_is_deterministic():
    outputs = []
    for variable in ("TANGENT_REDUCTION_DATA", "TANGENT_REDUCTION_REPLAY"):
        with gzip.open(Path(os.environ[variable]) / "results.json.gz", "rt") as file:
            outputs.append(json.load(file))
    for label in ("top-ten", "weighted-25", "weighted-50", "weighted-75", "weighted-90"):
        assert outputs[0]["details"][label]["selected"] == outputs[1]["details"][label]["selected"]
        assert outputs[0]["details"][label]["exchanges"] == outputs[1]["details"][label]["exchanges"]
        assert outputs[0]["route_pairs"][label] == outputs[1]["route_pairs"][label]
    assert outputs[0]["ablations"] == outputs[1]["ablations"]
