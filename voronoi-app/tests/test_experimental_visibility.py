import gzip
import json
import os
from fractions import Fraction
from math import sqrt
from pathlib import Path

import pytest
from shapely.geometry import box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from voronoi_app.angular import LineClearance, _exact_point
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.experimental_visibility import (
    IndexedClearance, _outward_bounds, build_visibility_graph, component_for_point, shortest_paths,
)
from experiments.shortest_path_backbone import matching_candidates, path_segments
from experiments.shortest_path_routes import boundary_samples, graph_from_dict, grid_samples
from experiments.shortest_path_visibility import sha256


def fixture(obstacles):
    occupied = unary_union(list(obstacles.values()))
    accessible = box(0, 0, 7, 4).difference(occupied)
    graph = build_visibility_graph(accessible, obstacles)
    clearance = LineClearance(accessible, occupied, original_obstacles=obstacles.values())
    return graph, clearance, IndexedClearance(clearance)


def route(graph, clearance, start, end):
    a, b = _exact_point(start), _exact_point(end)
    ca = component_for_point(a, graph.components)
    cb = component_for_point(b, graph.components)
    return shortest_paths(graph, [(a, ca)], [(b, cb)], clearance)[0]


def test_direct_visibility_and_boundary_following():
    graph, clearance, indexed = fixture({1: box(2, 1, 4, 3)})
    direct = route(graph, indexed, (1, 1), (5, 1))
    assert direct["status"] == "direct" and direct["length"] == 4
    boundary = next(edge for edge in graph.edges
                    if {graph.vertices[edge.start].point, graph.vertices[edge.end].point}
                    == {(_exact_point((2, 1))), (_exact_point((4, 1)))})
    assert boundary.boundary_following and boundary.tangent_supported
    assert all(clearance.permits_exact(graph.vertices[e.start].point, graph.vertices[e.end].point)
               for e in graph.edges)


def test_shortest_path_around_one_and_two_obstacles():
    graph, _, indexed = fixture({1: box(2, 1, 4, 3)})
    result = route(graph, indexed, (1, 2), (5, 2))
    assert result["status"] == "occluded"
    assert result["length"] == pytest.approx(2 + 2 * sqrt(2))
    assert result["near_tie"]
    graph, _, indexed = fixture({1: box(2, 1, 3, 3), 2: box(4, 1, 5, 3)})
    result = route(graph, indexed, (1, 2), (6, 2))
    assert result["status"] == "occluded"
    assert result["length"] == pytest.approx(3 + 2 * sqrt(2))


def test_shared_original_vertices_preserve_building_provenance():
    graph, _, _ = fixture({1: box(2, 1, 3, 3), 2: box(3, 1, 4, 3)})
    vertex = next(v for v in graph.vertices if v.point == _exact_point((3, 1)))
    assert {building for building, _ in vertex.buildings} == {1, 2}


def test_pinched_shared_vertex_is_recorded_and_not_used_as_a_bridge():
    graph, _, indexed = fixture({1: box(1, 1, 2, 2), 2: box(2, 2, 3, 3)})
    shared = _exact_point((2, 2))
    vertex = next(v for v in graph.vertices if v.point == shared)
    assert {building for building, _ in vertex.buildings} == {1, 2}
    assert shared in graph.ambiguous_vertices
    index = graph.vertices.index(vertex)
    assert all(index not in (e.start, e.end) for e in graph.edges)
    result = route(graph, indexed, (1, 3), (3, 1))
    assert result["status"] != "direct"


def test_disconnected_components_are_not_connected_by_boundary_contact():
    graph, _, indexed = fixture({1: box(3, 0, 4, 4)})
    result = route(graph, indexed, (1, 2), (6, 2))
    assert result["status"] == "different-component"


def test_indexed_clearance_matches_exact_reference_and_routes_repeat():
    graph, clearance, indexed = fixture({1: box(2, 1, 4, 3)})
    points = [v.point for v in graph.vertices] + [_exact_point((1, 2)), _exact_point((5, 2)),
                                                    (Fraction(3), Fraction(2))]
    assert all(indexed.permits(a, b) == clearance.permits_exact(a, b)
               for a in points for b in points)
    assert route(graph, indexed, (1, 2), (5, 2)) == route(graph, indexed, (1, 2), (5, 2))


def test_candidate_containment_not_intersection_and_noded_direct_boundary():
    graph, _, _ = fixture({1: box(2, 1, 4, 3)})
    start, end = _exact_point((2, 1)), _exact_point((4, 1))
    candidates = [(_exact_point((1, 1)), _exact_point((5, 1))),
                  (_exact_point((3, 0)), _exact_point((3, 2))),
                  (_exact_point((2, 1)), _exact_point((3, 1)))]
    tree = STRtree([_outward_bounds(a, b) for a, b in candidates])
    assert matching_candidates(start, end, candidates, tree) == [0]
    vertex_tree = STRtree([_outward_bounds(v.point, v.point) for v in graph.vertices])
    segments = path_segments(_exact_point((1, 1)), _exact_point((5, 1)), [], graph, vertex_tree)
    assert any({graph.vertices[a].point, graph.vertices[b].point} == {start, end}
               for a, b in segments)


def test_terminal_sampling_is_deterministic_and_preserves_boundary_provenance():
    buildings = {17: box(2, 1, 4, 3)}
    graph, clearance, indexed = fixture(buildings)
    accessible = clearance.accessible
    assert grid_samples(accessible, graph, indexed, resolution=4) == grid_samples(
        accessible, graph, indexed, resolution=4
    )
    samples = boundary_samples(buildings, {17: 1}, graph, indexed, limit=2)
    assert samples == boundary_samples(buildings, {17: 1}, graph, indexed, limit=2)
    origins, destinations, eligible = samples
    assert eligible == 4 and len(origins) == len(destinations) == 2
    assert all(sample["building_faces"][0][0:2] == (17, 1) for sample in origins)


@pytest.mark.skipif(
    not os.environ.get("SHORTEST_PATH_VISIBILITY_DATA"),
    reason="set SHORTEST_PATH_VISIBILITY_DATA and SHORTEST_PATH_SNAPSHOT for saved-Y audit",
)
def test_saved_y_every_graph_edge_passes_independent_exact_clearance():
    path = Path(os.environ["SHORTEST_PATH_VISIBILITY_DATA"]) / "visibility-graph.json.gz"
    snapshot = Path(os.environ["SHORTEST_PATH_SNAPSHOT"])
    with gzip.open(path, "rt") as file:
        raw_graph = json.load(file)
    assert sha256(snapshot) == raw_graph["input_sha256"]["home/Downloads/axial-diagnostic.json"]
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    graph = graph_from_dict(raw_graph, accessible)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    assert all(clearance.permits_exact(graph.vertices[edge.start].point, graph.vertices[edge.end].point)
               for edge in graph.edges)
