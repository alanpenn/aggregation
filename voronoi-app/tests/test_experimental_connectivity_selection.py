from fractions import Fraction

import pytest
from shapely.geometry import box

from voronoi_app.angular import LineClearance, SampleAttachment
from voronoi_app.exact_axial import ExactCandidate, candidate_graph
from voronoi_app.experimental_connectivity_selection import (
    connectivity_cover, connectivity_order, improve_topology, repair_selection, structural_failure,
)
from experiments.valley_connectivity_terminals import map_depths


def line(identifier, start, end):
    a, b = tuple(map(Fraction, start)), tuple(map(Fraction, end))
    return ExactCandidate(identifier, a, b, a, b, "test")


def clearance():
    occupied = box(8, 8, 9, 9)
    return LineClearance(box(-5, -5, 10, 10).difference(occupied), occupied,
                         original_obstacles=[occupied])


def test_fixed_full_graph_degree_order_and_canonical_ties():
    lines = [line(0, (-2, 0), (2, 0)), line(1, (1, -1), (1, 1)),
             line(2, (0, -2), (0, 2)), line(3, (-1, -2), (-1, 2))]
    graph = candidate_graph(lines)
    order = connectivity_order(lines, graph)
    assert order[0] == 0
    assert graph.degree[2] == graph.degree[3]
    assert order.index(3) < order.index(2)
    selected = connectivity_cover(lines, [{0}, {1}, {1}, {1}], {0, 1}, graph)
    assert selected == {0, 3}


def test_length_tie_break_uses_exact_squared_length():
    lines = [line(0, (0, 0), (1, 0)),
             line(1, (3, 0), (Fraction(4) + Fraction(1, 2**60), 0))]
    assert lines[0].length == lines[1].length
    assert connectivity_order(lines, candidate_graph(lines)) == [1, 0]


def test_ring_repair_and_two_for_one_exchange_are_deterministic():
    lines = [line(0, (0, 0), (2, 0)), line(1, (2, 0), (2, 2)),
             line(2, (2, 2), (0, 2)), line(3, (0, 2), (0, 0)),
             line(4, (0, 0), (2, 2))]
    graph = candidate_graph(lines)
    covers = [{0}, {0}, {1}, {1}, {0, 1}]
    groups, obstacles = [set(range(5))], [(1, Fraction(1, 2))]
    repaired, summary = repair_selection(lines, covers, {0, 1}, groups, graph, obstacles,
                                          {4}, {0, 1, 2, 3})
    assert structural_failure(lines, covers, {0, 1}, groups, graph, obstacles, repaired) is None
    assert summary["ring_added"] == 4
    assert repaired == {0, 1, 4}

    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (1, -2), (1, 2)), line(3, (-2, -2), (2, 2))]
    covers = [{0}, {1}, {2}, {1, 2}]
    args = (lines, covers, {0, 1, 2}, [set(range(4))], candidate_graph(lines), [],
            {0, 1, 2}, clearance())
    result = improve_topology(*args)
    assert result == improve_topology(*args)
    assert result.selected == {0, 3}
    assert result.exchanges == (((1, 2), (3,)),)


def test_exchange_rejects_uncertified_addition():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (1, -2), (1, 2)), line(3, (-2, -2), (2, 2))]
    occupied = box(0.5, 0.5, 0.6, 0.6)
    blocked = LineClearance(box(-4, -4, 4, 4).difference(occupied), occupied,
                            original_obstacles=[occupied])
    with pytest.raises(ValueError, match="Candidate 3 fails exact clearance"):
        improve_topology(lines, [{0}, {1}, {2}, {1, 2}], {0, 1, 2},
                         [set(range(4))], candidate_graph(lines), [], {0, 1, 2}, blocked)


def test_three_for_two_exchange_covers_all_regions():
    lines = [line(0, (-3, 0), (3, 0)), line(1, (-1, -2), (-1, 2)),
             line(2, (0, -2), (0, 2)), line(3, (1, -2), (1, 2)),
             line(4, (-2, -2), (2, 2)), line(5, (-2, 2), (2, -2))]
    covers = [{0}, {1, 4}, {2, 5}, {3, 6}, {1, 2, 3}, {4, 5, 6}]
    result = improve_topology(lines, covers, set(range(7)), [set(range(6))],
                              candidate_graph(lines), [], {0, 1, 2, 3}, clearance())
    assert result.selected == {0, 4, 5}
    assert result.exchanges == (((1, 2, 3), (4, 5)),)


def test_fixed_terminal_options_do_not_reattach_to_excluded_lines():
    lines = [line(0, (0, 0), (4, 0)), line(1, (2, -1), (2, 1))]
    fixed = [[SampleAttachment((0, 0), (0, 0), 0)],
             [SampleAttachment((2, 1), (2, 1), 1)]]
    full, available = map_depths(lines, fixed, [0, 0])
    assert available == 2 and full[0, 1] == pytest.approx(1)
    reduced, available = map_depths(lines[:1], fixed, [0, 0])
    assert available == 1 and reduced[0, 1] == float("inf")
