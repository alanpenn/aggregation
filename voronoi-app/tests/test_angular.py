import json
import pytest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import unary_union

from voronoi_app.angular import (
    AngularConnectivityError, AngularNetwork, LineClearance, SampleAttachment,
    _angular_attachment_depths_by_origin, _cross, _crosses_polygon_interior, _crosses_prepared,
    _direction, _exact_point, _on_segment, _prepare_polygon, angular_sample_depths, angular_turn_cost,
    angular_attachment_depths, attach_spatial_samples, topological_sample_depths,
)
from voronoi_app.axial import AxialLine
from voronoi_app.angular_optimisation import optimise_angular_map, spatial_samples


def line(index, start, end):
    return AxialLine(index, start, end)


def test_angular_cost_uses_movement_direction():
    assert angular_turn_cost((1, 0), (1, 0)) == 0
    assert angular_turn_cost((1, 0), (0, 1)) == 1
    assert angular_turn_cost((1, 0), (-1, 0)) == 2
    assert angular_turn_cost((-1, 0), (1, 0)) == 2
    assert angular_turn_cost((1e300, 1e300), (-1e300, 1e300)) == 1
    with pytest.raises(ValueError, match="non-zero"):
        angular_turn_cost((0, 0), (1, 0))


def test_straight_right_angle_and_reversal_paths():
    network = AngularNetwork.from_lines(
        [line(0, (0, 0), (2, 0)), line(1, (1, 0), (1, 1))],
        [(0, 0), (2, 0), (1, 1)],
    )
    assert network.shortest_depth((0, 0), (2, 0)) == 0
    assert network.shortest_depth((0, 0), (1, 1)) == 1
    assert network.shortest_depth((0, 0), (2, 0), arrival=(-1, 0)) == 2
    assert network.shortest_depth((0, 0), (2, 0), arrival=(1, 0)) == 0


def test_shortest_path_chooses_lower_cumulative_turn():
    network = AngularNetwork.from_lines(
        [line(0, (0, 0), (1, 0)), line(1, (1, 0), (1, 1)),
         line(2, (0, 0), (1, 1))],
        [(0, 0), (1, 1)],
    )
    assert network.shortest_depth((0, 0), (1, 1), arrival=(1, 0)) == pytest.approx(0.5)


def test_geometrically_disjoint_lines_do_not_connect():
    network = AngularNetwork.from_lines(
        [line(0, (0, 0), (1, 0)), line(1, (1 + 1e-10, 0), (2, 0))],
        [(0, 0), (2, 0)],
    )
    with pytest.raises(ValueError, match="not connected"):
        network.shortest_depth((0, 0), (2, 0))
    with pytest.raises(ValueError, match="not attached"):
        AngularNetwork.from_lines([line(0, (0, 0), (1, 0))], [(0.5, 0.1)])


def test_exact_intersection_and_overlapping_lines_are_noded():
    intersection = (Fraction(1, 3), Fraction(1, 3))
    network = AngularNetwork.from_lines(
        [line(0, (0, 0), (1, 1)), line(1, (0, 1), (0.5, 0)),
         line(2, (0.5, 0.5), (2, 2))],
        [(0, 0), intersection, (2, 2)],
    )
    assert network.shortest_depth((0, 0), (2, 2)) == 0
    assert network.shortest_depth((0, 0), intersection) == 0


@pytest.mark.parametrize(
    "lines,attachments,components",
    [
        (
            [line(0, (0, 0), (2, 0)), line(1, (1, -1), (1, 1))],
            [SampleAttachment((0, 0), (0, 0), 0),
             SampleAttachment((1, 2), (1, 1), 1),
             SampleAttachment((2, 1), (2, 0), 0)],
            None,
        ),
        (
            [line(0, (0, 0), (1, 0)), line(1, (3, 0), (4, 0))],
            [SampleAttachment((0, 1), (0, 0), 0),
             SampleAttachment((1, 0), (1, 0), 0),
             SampleAttachment((3, -1), (3, 0), 1),
             SampleAttachment((4, 0), (4, 0), 1)],
            [0, 0, 1, 1],
        ),
        (
            [line(0, (0, 0), (2, 0)), line(1, (1, -1), (1, 1)),
             line(2, (1, 0), (3, 0))],
            [SampleAttachment((1, 0), (1, 0), 0),
             SampleAttachment((1, 1), (1, 0), 1),
             SampleAttachment((2, 0), (1, 0), 2),
             SampleAttachment((3, 0), (3, 0), 2)],
            None,
        ),
    ],
    ids=["connectors", "disconnected-components", "coincident-intersections"],
)
def test_per_origin_angular_paths_match_per_pair(lines, attachments, components):
    expected = angular_attachment_depths(lines, attachments, components=components)
    actual = _angular_attachment_depths_by_origin(lines, attachments, components=components)
    assert actual.keys() == expected.keys()
    assert actual == pytest.approx(expected, abs=1e-12, rel=0)


def test_per_origin_angular_paths_preserve_disconnected_and_empty_pair_errors():
    lines = [line(0, (0, 0), (1, 0)), line(1, (3, 0), (4, 0))]
    attachments = [SampleAttachment((0, 0), (0, 0), 0),
                   SampleAttachment((4, 0), (4, 0), 1)]
    for calculate in (angular_attachment_depths, _angular_attachment_depths_by_origin):
        with pytest.raises(AngularConnectivityError, match="not connected"):
            calculate(lines, attachments)
        with pytest.raises(ValueError, match="No spatial sample pairs"):
            calculate(lines, attachments, components=[0, 1])


def test_per_origin_paths_match_for_alternative_visible_attachments():
    lines = [line(0, (0, 0), (4, 0)), line(1, (2, 0), (2, 3))]
    clearance = LineClearance(box(-1, -1, 5, 4), box(10, 10, 11, 11))
    samples = [(1, 1), (3, 1), (2, 2)]
    for order in (lines, list(reversed(lines))):
        attachments = attach_spatial_samples(samples, order, clearance)
        expected = angular_attachment_depths(order, attachments)
        actual = _angular_attachment_depths_by_origin(order, attachments)
        assert actual == pytest.approx(expected, abs=1e-12, rel=0)
    alternate = [SampleAttachment((1, 1), (2, 1), 1),
                 SampleAttachment((3, 1), (3, 0), 0),
                 SampleAttachment((2, 2), (2, 2), 1)]
    assert _angular_attachment_depths_by_origin(lines, alternate) == pytest.approx(
        angular_attachment_depths(lines, alternate), abs=1e-12, rel=0,
    )


@pytest.mark.parametrize("direction", [(0, 0), (float("inf"), 0)])
@pytest.mark.parametrize("invalid_field", ["arrival", "departure"])
def test_per_origin_paths_reject_invalid_connector_directions(direction, invalid_field):
    lines = [line(0, (0, 0), (2, 0))]
    attachments = [
        SimpleNamespace(point=(0, 0), arrival=(1, 0), departure=(1, 0)),
        SimpleNamespace(point=(2, 0), arrival=(1, 0), departure=(1, 0)),
    ]
    target = attachments[0] if invalid_field == "arrival" else attachments[1]
    setattr(target, invalid_field, direction)
    for calculate in (angular_attachment_depths, _angular_attachment_depths_by_origin):
        with pytest.raises(ValueError, match="Movement directions"):
            calculate(lines, attachments)


def test_per_origin_paths_match_degenerate_axial_line_error():
    lines = [SimpleNamespace(line_id=0, start=(0, 0), end=(0, 0))]
    attachments = [SampleAttachment((0, 0), (0, 0), 0),
                   SampleAttachment((1, 0), (0, 0), 0)]
    for calculate in (angular_attachment_depths, _angular_attachment_depths_by_origin):
        with pytest.raises(ZeroDivisionError):
            calculate(lines, attachments)


def test_clearance_permits_boundary_contact_but_rejects_microscopic_crossings():
    occupied = box(1, 1, 2, 2)
    accessible = box(0, 0, 3, 3).difference(occupied)
    clearance = LineClearance(accessible, occupied)
    boundary = LineString(((0, 1), (3, 1)))
    crossing = LineString(((0, 1), (3, 1 + 1e-14)))
    assert clearance.permits(boundary)
    assert _crosses_polygon_interior(crossing, occupied)
    assert not clearance.permits(crossing)
    assert not clearance.permits_exact((0, 1), (3, 1 + Fraction(1, 10**30)))
    with pytest.raises(ValueError, match="not geometrically valid"):
        AngularNetwork.from_lines(
            [line(0, (0, 1), (3, 1 + 1e-14))], [(0, 1)], clearance=clearance,
        )


def test_exact_maximal_interval_keeps_tangency_and_stops_at_obstacles():
    occupied = box(1, 1, 2, 2)
    clearance = LineClearance(box(0, 0, 4, 3).difference(occupied), occupied)
    assert clearance.maximal_interval((0, 1), (1, 1)) == ((0, 1), (4, 1))
    assert clearance.maximal_interval((0, 1.5), (0.5, 1.5)) == ((0, 1.5), (1, 1.5))
    with pytest.raises(ValueError, match="forbidden"):
        clearance.maximal_interval((0, 1.5), (3, 1.5))


_Y_GEOMETRY = json.loads(
    (Path(__file__).parent / "fixtures" / "angular_y_geometry.json").read_text()
)


@pytest.fixture(scope="module")
def y_clearance():
    return LineClearance(shape(_Y_GEOMETRY["domain"]), shape(_Y_GEOMETRY["occupied"]))


@pytest.fixture(scope="module")
def y_boundary_vertices():
    domain = shape(_Y_GEOMETRY["domain"])
    parts = [domain] if isinstance(domain, Polygon) else list(domain.geoms)
    vertices = {}
    for polygon in parts:
        for ring in (polygon.exterior, *polygon.interiors):
            points = [_exact_point(point) for point in list(ring.coords)[:-1]]
            for index, point in enumerate(points):
                vertices.setdefault(point, []).append((points[index - 1], points[(index + 1) % len(points)]))
    return vertices


@pytest.mark.parametrize("pair", _Y_GEOMETRY["unresolved"])
def test_y_unresolved_support_has_safe_exact_maximal_interval(y_clearance, y_boundary_vertices, pair):
    a, b = _exact_point(pair["start"]), _exact_point(pair["end"])
    for point, other in ((a, b), (b, a)):
        direction = _direction(point, other)
        assert any(
            _cross(direction, _direction(point, previous))
            * _cross(direction, _direction(point, following)) >= 0
            for previous, following in y_boundary_vertices[point]
        )
    start, end = y_clearance.maximal_interval(pair["start"], pair["end"])
    assert y_clearance.permits_exact(start, end)
    assert _on_segment(_exact_point(pair["start"]), start, end)
    assert _on_segment(_exact_point(pair["end"]), start, end)
    direction = tuple(end[i] - start[i] for i in range(2))
    before = tuple(start[i] - direction[i] / 1000 for i in range(2))
    after = tuple(end[i] + direction[i] / 1000 for i in range(2))
    assert not y_clearance.permits_exact(before, end)
    assert not y_clearance.permits_exact(start, after)


@pytest.mark.parametrize("region_id,expected", [("82", False), ("226", True)])
def test_y_recovered_support_coverage_is_checked_without_endpoint_rounding(
    y_clearance, region_id, expected,
):
    region = _prepare_polygon(shape(_Y_GEOMETRY["regions"][region_id]))
    for entry in _Y_GEOMETRY["supports"][region_id]:
        interval = y_clearance.maximal_interval(*entry["support"])
        assert y_clearance.permits_exact(*interval)
        assert _crosses_prepared(*interval, region) is expected


def test_y_region_82_has_safe_traversal_missing_from_saved_candidates(y_clearance):
    region = shape(_Y_GEOMETRY["regions"]["82"])
    point = region.representative_point()
    interval = y_clearance.maximal_interval(
        (point.x, point.y), (point.x, point.y + 0.1),
    )
    assert y_clearance.permits_exact(*interval)
    assert _crosses_prepared(*interval, _prepare_polygon(region))


def test_shared_obstacle_boundary_is_occupied_union_interior():
    occupied = unary_union([box(1, 1, 2, 2), box(2, 1, 3, 2)])
    accessible = box(0, 0, 4, 3).difference(occupied)
    clearance = LineClearance(accessible, occupied)
    assert not clearance.permits(LineString(((2, 0), (2, 3))))


def test_common_samples_attach_exactly_and_include_connector_turns():
    clearance = LineClearance(box(0, 0, 10, 10), Polygon())
    attachments, depths = angular_sample_depths(
        [(4, 3), (7, 3)], [line(4, (0, 5), (10, 5))], clearance,
    )
    assert [attachment.point for attachment in attachments] == [(4, 5), (7, 5)]
    assert depths[0, 1] == pytest.approx(2)
    assert depths[1, 0] == pytest.approx(2)
    assert topological_sample_depths([line(4, (0, 5), (10, 5))], attachments) == {
        (0, 1): 0, (1, 0): 0,
    }


def test_sample_attachment_uses_nearest_visible_point_not_blocked_projection():
    occupied = box(4, 4, 6, 6)
    clearance = LineClearance(box(0, 0, 10, 10).difference(occupied), occupied)
    attachment = attach_spatial_samples([(2, 5)], [line(0, (8, 2), (8, 8))], clearance)[0]
    assert attachment.point == (8, 2)
    assert clearance.permits_exact(attachment.sample, attachment.point)


def test_sample_attachment_rejects_unreachable_component():
    accessible = unary_union([box(0, 0, 1, 1), box(2, 0, 3, 1)])
    clearance = LineClearance(accessible, Polygon())
    with pytest.raises(ValueError, match="No visible"):
        attach_spatial_samples([(0.5, 0.5)], [line(0, (2, 0.5), (3, 0.5))], clearance)


@pytest.mark.parametrize("mode", ["fewest", "penalty"])
def test_angular_search_finds_straighter_feasible_synthetic_map(mode):
    domain = box(0, 0, 4, 2)
    regions = {0: box(0, 0, 2, 2), 1: box(2, 0, 4, 2)}
    candidates = [
        line(0, (0, 0), (2, 2)), line(1, (2, 2), (4, 0)),
        line(2, (0, 1), (4, 1)),
    ]
    kwargs = dict(
        candidates=candidates, initial_ids={0, 1}, regions=regions,
        accessible=domain, occupied=Polygon(), samples=[(0.5, 1), (3.5, 1)],
        mode=mode, penalty=0.1, iterations=12, seed=7,
    )
    result = optimise_angular_map(**kwargs)
    repeat = optimise_angular_map(**kwargs)
    assert [item.line_id for item in result.lines] == [2]
    assert [item.line_id for item in repeat.lines] == [2]
    assert result.objective < result.initial_objective
    assert result.depths == repeat.depths


def test_angular_search_preserves_ring_coverage_and_rejects_unsafe_line():
    occupied = box(1, 1, 2, 2)
    domain = box(0, 0, 3, 3).difference(occupied)
    regions = {
        0: box(0, 0, 1, 3), 1: box(2, 0, 3, 3),
        2: box(0, 0, 3, 1), 3: box(0, 2, 3, 3),
    }
    candidates = [
        line(0, (0, 1), (3, 1)), line(1, (0, 2), (3, 2)),
        line(2, (1, 0), (1, 3)), line(3, (2, 0), (2, 3)),
        line(4, (0, 0), (3, 3)),
    ]
    result = optimise_angular_map(
        candidates, {0, 1, 2, 3}, regions, domain, occupied,
        [(0.5, 0.5), (2.5, 2.5)], iterations=30, seed=2,
    )
    assert {item.line_id for item in result.lines} == {0, 1, 2, 3}
    assert result.safe_candidates == 4
    assert not result.repaired_seed


def test_single_convex_region_produces_multiple_fixed_samples():
    points = spatial_samples({0: box(0, 0, 10, 10)}, count=4)
    assert len(set(points)) == 4
    assert points == spatial_samples({0: box(0, 0, 10, 10)}, count=4)


def test_angular_search_can_exchange_two_lines_for_two():
    domain = box(0, 0, 4, 2)
    regions = {0: box(0, 0, 2, 2), 1: box(2, 0, 4, 2)}
    candidates = [
        line(0, (0, 0), (2, 2)), line(1, (2, 2), (4, 0)),
        line(2, (0, 1), (2, 1)), line(3, (2, 1), (4, 1)),
    ]
    result = optimise_angular_map(
        candidates, {0, 1}, regions, domain, Polygon(),
        [(0.5, 1), (3.5, 1)], iterations=6, seed=7,
    )
    assert {item.line_id for item in result.lines} == {2, 3}
    assert result.objective < result.initial_objective
    assert result.accepted_moves["two-for-two"] == 1


def test_angular_search_repairs_an_unsafe_greedy_seed():
    occupied = box(1, 1, 2, 3)
    domain = box(0, 0, 3, 3).difference(occupied)
    regions = {0: box(0, 0, 3, 1)}
    candidates = [
        line(0, (0, 1.5), (3, 1.5)),
        line(1, (0, 0.5), (3, 0.5)),
    ]
    result = optimise_angular_map(
        candidates, {0}, regions, domain, occupied,
        [(0.5, 0.5), (2.5, 0.5)], iterations=0,
    )
    assert result.repaired_seed
    assert [item.line_id for item in result.lines] == [1]


def test_angular_search_fails_explicitly_when_safe_coverage_is_impossible():
    occupied = box(1, 1, 2, 2)
    domain = box(0, 0, 3, 3).difference(occupied)
    with pytest.raises(ValueError, match="safety screen cannot cover"):
        optimise_angular_map(
            [line(0, (0, 1.5), (3, 1.5))], {0},
            {0: box(0, 1, 1, 2)}, domain, occupied,
            [(0.5, 1.5), (0.5, 1.75)], iterations=0,
        )


def test_angular_search_reports_pairs_between_disconnected_components():
    domain = unary_union([box(0, 0, 2, 2), box(4, 0, 6, 2)])
    regions = {0: box(0, 0, 2, 2), 1: box(4, 0, 6, 2)}
    candidates = [line(0, (0, 1), (2, 1)), line(1, (4, 1), (6, 1))]
    result = optimise_angular_map(
        candidates, {0, 1}, regions, domain, Polygon(),
        [(0.5, 1), (1.5, 1), (4.5, 1), (5.5, 1)], iterations=0,
    )
    assert result.components == 2
    assert result.excluded_pairs == 8
    assert len(result.depths) == 4
