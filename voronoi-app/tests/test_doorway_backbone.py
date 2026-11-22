from fractions import Fraction

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from experiments.doorway_backbone import doorway_records, routes_from_connections, shared_faces
from voronoi_app.angular import LineClearance
from voronoi_app.experimental_visibility import (
    IndexedClearance, build_visibility_graph, shortest_paths,
    visible_connections,
)


def test_shared_face_midpoint_preserves_exact_binary_coordinates():
    building = box(2, 1, 4, 3)
    opened = {7: box(0, 1, 2, 3)}
    buildings = {9: building}
    accessible = box(0, 0, 7, 4).difference(building)
    graph = build_visibility_graph(accessible, buildings)
    indexed = IndexedClearance(LineClearance(accessible, building, original_obstacles=[building]))
    records = doorway_records([(7, 9)], opened, buildings, {9: 2}, graph, indexed)
    assert records[0]["status"] == "valid"
    assert tuple(map(Fraction, records[0]["point"])) == (Fraction(2), Fraction(2))
    assert records[0]["connections"]
    assert records[0]["building_label"] == 2
    assert shared_faces(opened[7], building) == [
        ((Fraction(2), Fraction(1)), (Fraction(2), Fraction(3)))
    ]


def test_disjoint_or_point_contact_is_not_a_door():
    assert shared_faces(box(0, 0, 1, 1), box(2, 0, 3, 1)) == []
    assert shared_faces(box(0, 0, 1, 1), box(1, 1, 2, 2)) == []


def test_face_midpoint_routes_directly_and_around_obstacle():
    buildings = {1: box(2, 1, 4, 3)}
    occupied = unary_union(list(buildings.values()))
    accessible = box(0, 0, 7, 4).difference(occupied)
    graph = build_visibility_graph(accessible, buildings)
    indexed = IndexedClearance(LineClearance(accessible, occupied, original_obstacles=buildings.values()))
    faces = {7: box(0, 1, 2, 3), 8: box(4, 1, 7, 3)}
    records = doorway_records([(7, 1), (8, 1)], faces, buildings, {1: 1}, graph, indexed)
    points = [(tuple(map(Fraction, d["point"])), d["component"]) for d in records]
    points.append(((Fraction(2), Fraction(1)), records[0]["component"]))
    routes = shortest_paths(graph, points, points, indexed, same_set=True)
    lookup = {(r["source"], r["destination"]): r for r in routes}
    assert lookup[(0, 2)]["status"] == "direct"
    assert lookup[(0, 1)]["status"] == "occluded"
    assert lookup[(0, 1)]["length"] == pytest.approx(4.0)
    assert routes == shortest_paths(graph, points, points, indexed, same_set=True)
    links = [visible_connections(point, component, graph, indexed) for point, component in points]
    assert routes_from_connections(graph, points, links, indexed) == routes
