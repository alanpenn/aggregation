from fractions import Fraction

import pytest
from shapely.geometry import box

from voronoi_app.angular import (
    AngularConnectivityError, AngularNetwork, LineClearance, SampleAttachment,
)
from voronoi_app.exact_axial import ExactCandidate, closed_routes
from voronoi_app.experimental_angular_selection import angular_reference, optimise_fidelity


def line(identifier, start, end):
    a = tuple(map(Fraction, start))
    b = tuple(map(Fraction, end))
    return ExactCandidate(identifier, a, b, a, b, "test")


def test_sparse_routing_matches_directional_network_and_its_witnesses():
    lines = [
        line(1, (0, 0), (4, 0)),
        line(2, (2, -2), (2, 2)),
        line(3, (0, -1), (4, 1)),
        line(4, (1, 0), (3, 0)),
        line(5, (8, 0), (10, 0)),
    ]
    attachments = [
        SampleAttachment((-1, 1), (0, 0), 1),
        SampleAttachment((2, 2), (2, 2), 2),
        SampleAttachment((4, 1), (4, 1), 3),
        SampleAttachment((2, 1), (2, 0), 4),
        SampleAttachment((8, 0), (8, 0), 5),
        SampleAttachment((0, -1), (0, 0), 1),
    ]
    components = [0, 0, 0, 0, 0, 0]
    reference = angular_reference(lines, attachments, components)
    network = AngularNetwork.from_lines(lines, [item.point for item in attachments])
    for (i, j), actual in reference.depths.items():
        try:
            expected = network.shortest_depth(
                attachments[i].point, attachments[j].point,
                arrival=attachments[i].arrival, departure=attachments[j].departure,
            )
        except AngularConnectivityError:
            assert actual == float("inf")
        else:
            assert actual == pytest.approx(expected, abs=1e-12)
    reduced = [lines[i] for i in sorted(reference.witness_lines)]
    assert angular_reference(reduced, attachments, components).depths == pytest.approx(
        reference.depths, abs=1e-12
    )
    heuristic = angular_reference(lines, attachments, components, witness_turn_penalty=1e-4)
    assert all(heuristic.depths[pair] >= depth - 1e-12
               for pair, depth in reference.depths.items())


def test_fixed_attachment_must_remain_on_its_original_line():
    with pytest.raises(ValueError, match="fixed attachment"):
        angular_reference(
            [line(1, (0, 0), (2, 0))], [SampleAttachment((0, 0), (0, 0), 2)], [0]
        )


def test_fidelity_selection_preserves_fixed_pairs_coverage_rings_and_components():
    lines = [
        line(0, (0, 0), (2, 0)),
        line(1, (2, 0), (2, 2)),
        line(2, (2, 2), (0, 2)),
        line(3, (0, 2), (0, 0)),
        line(4, (0, 0), (2, 2)),
        line(5, (10, 0), (12, 0)),
    ]
    attachments = [
        SampleAttachment((1, 0), (1, 0), 0),
        SampleAttachment((1, 2), (1, 2), 2),
        SampleAttachment((10, 0), (10, 0), 5),
        SampleAttachment((12, 0), (12, 0), 5),
    ]
    components = [0, 0, 1, 1]
    covers = [{0}, {0}, {1}, {1}, {0, 1}, {2}]
    groups = [{0, 1, 2, 3, 4}, {5}]
    full = angular_reference(lines, attachments, components)
    args = (lines, covers, {0, 1, 2}, groups, [(1, Fraction(1, 2))],
            attachments, components, full, 0.1, {0, 1, 2, 3})
    result = optimise_fidelity(*args, attempt_limit=10)
    assert result == optimise_fidelity(*args, attempt_limit=10)
    assert {0, 2, 5} <= result.selected
    assert set().union(*(covers[i] for i in result.selected)) == {0, 1, 2}
    assert closed_routes([lines[i] for i in sorted(result.selected)], [(1, Fraction(1, 2))]) == {0}
    assert all(result.depths[pair] <= full.depths[pair] + 0.1 + 1e-10
               for pair in full.depths)
    obstacle = box(0.9, 0.4, 1.1, 0.6)
    clearance = LineClearance(box(-1, -1, 13, 3).difference(obstacle), obstacle,
                              original_obstacles=[obstacle])
    assert all(clearance.permits_exact(lines[i].start, lines[i].end) for i in result.selected)
    assert all(isinstance(value, Fraction) for i in result.selected
               for value in (*lines[i].start, *lines[i].end))
