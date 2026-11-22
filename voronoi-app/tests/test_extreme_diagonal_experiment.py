from fractions import Fraction

from shapely.geometry import Point

from voronoi_app.batch_routing_reference import MasterNetwork
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.extreme_diagonal_experiment import membership, opposed_pairs
from voronoi_app.extreme_diagonal_synthetic import layout


def p(x, y):
    return Fraction(x), Fraction(y)


def candidate(i, a, b):
    return ExactCandidate(i, a, b, a, b, "test")


def test_extreme_pair_ignores_face_lines_and_short_or_same_sided_diagonals():
    axis = ((0, 0), (16, 0))
    lines = [
        candidate(0, p(0, -2), p(16, 2)),
        candidate(1, p(16, -2), p(0, 2)),
        candidate(2, p(0, 2), p(16, 2)),
        candidate(3, p(2, -2), p(9, 2)),
        candidate(4, p(0, 1), p(16, 2)),
    ]
    members = membership(axis, lines, 2.15)
    assert 2 in members
    assert opposed_pairs(axis, lines, members, width=2.15) == [(0, 1)]
    assert opposed_pairs(axis, lines, members - {1}, width=2.15) == []


def test_shared_connector_route_trace_preserves_turn_stop():
    line = candidate(0, p(-1, 0), p(1, 0))
    stop = p(0, 0)
    doors = [{"point": p(0, -1), "connectors": [(0, stop)]},
             {"point": p(1, -1), "connectors": [(0, stop)]}]
    network = MasterNetwork([line], doors)
    for angular in (False, True):
        routes = network.route({0}, angular, trace_pairs=[(0, 1)])
        assert routes[0, 1] == [p(0, -1), stop, p(1, -1)]


def test_grid_layout_places_fixed_doors_on_their_shared_faces():
    for fixture in ("grid-8x-4", "curve", "taper", "bend", "irregular"):
        polygons, occupied, doors, _, _ = layout(fixture)
        assert all(poly.is_valid and poly.area > 0 for poly in polygons.values())
        assert set(occupied) == {d["building_cell"] for d in doors}
        for door in doors:
            location = Point(door["point"])
            assert polygons[door["open_cell"]].boundary.covers(location)
            assert polygons[door["building_cell"]].boundary.covers(location)


def test_angular_route_trace_includes_departure_stop_of_first_edge():
    line = candidate(0, p(0, 0), p(2, 0))
    doors = [{"point": p(0, -1), "connectors": [(0, line.start)]},
             {"point": p(2, 1), "connectors": [(0, line.end)]}]
    trace = MasterNetwork([line], doors).route({0}, True, trace_pairs=[(0, 1)])
    assert trace[0, 1] == [p(0, -1), line.start, line.end, p(2, 1)]
