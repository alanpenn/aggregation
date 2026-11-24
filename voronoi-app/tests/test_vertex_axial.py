from shapely.geometry import box

from experiments.vertex_axial import vertex_index, vertex_ranking
from test_experimental_circulation_topology import candidate


def test_vertex_index_preserves_coincident_faces_and_exact_tangent_memberships():
    polygons = {10: box(0, 0, 1, 1), 20: box(1, 0, 2, 1), 30: box(2, 1, 3, 2)}
    lines = [candidate(0, (0, 1), (2, 1)), candidate(1, (0, 0), (2, 2))]
    features = [{"normalized": [1, 0, 0, 0, 0], "redundant": [], "families": []}
                for _ in lines]
    records, supports, _ = vertex_index(polygons, {10: 1, 20: 2, 30: 3}, lines, features)
    points = {tuple(row["point"]): row for row in records}
    shared_edge = points["1", "1"]
    point_only = points["2", "1"]
    assert {row["cell"] for row in shared_edge["members"]} == {10, 20}
    assert all(row["face_contact"] for row in shared_edge["members"])
    assert {row["cell"]: row["vertex_only_neighbors"] for row in point_only["members"]} == {20: [30], 30: [20]}
    # The diagonal passes through the shared vertex and crosses the interior
    # of building 10. Building 20 alone provides a supporting tangent there.
    accepted = shared_edge["support_members"][1]
    assert [shared_edge["members"][i]["cell"] for i in accepted] == [20]
    assert shared_edge["id"] in supports[0]
    assert vertex_ranking(records, supports, features) == vertex_ranking(records, supports, features)
