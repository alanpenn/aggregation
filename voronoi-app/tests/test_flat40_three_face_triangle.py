"""Portable regression using the exact archived footprints and support endpoints."""
from fractions import Fraction
import json
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from experiments.external_committed_crawler import ExternalCommittedCrawler
from experiments.flat40_convex_enlargement import Checker
from experiments.flat40_enlarged_cover import blocked_facets
from experiments.flat40_oriented_crawler import Replay
from experiments.flat40_region257_inspection import packed
from experiments.flat40_three_face_triangle import candidates, expected_walks, targeted
from voronoi_app.angular import _inside_prepared


def coordinates(rows):
    return tuple(tuple(map(Fraction, point)) for point in rows)


def test_exact_flat40_three_face_circuits(tmp_path):
    fixture = json.loads(Path(__file__).with_name("fixtures").joinpath(
        "flat40_three_face_triangle.json").read_text())
    blocks = {label: Polygon(coordinates(ring)) for label, ring in fixture["label_to_building"].items()}
    domain = box(0, 0, 100, 100).difference(unary_union(list(blocks.values())))
    crawler = ExternalCommittedCrawler(domain, blocks.items())
    replay = Replay(crawler, blocks, tmp_path)
    groups = [[face for face in crawler.faces if {face.a, face.b} == set(coordinates(endpoints))]
              for endpoints in fixture["generating_faces"].values()]
    assert all(len(group) == 1 for group in groups)
    checker = Checker(domain, blocks)
    [(faces, _, evidence)] = candidates(groups, checker)
    triangle = coordinates(fixture["vertices"])
    assert evidence["geometry_certificate"]
    assert evidence["vertices"] == fixture["vertices"]
    assert len(blocked_facets(checker, triangle)) == 3
    assert all(_inside_prepared(v, checker.domain) for v in triangle)
    for hand in (-1, 1):
        seen = set()
        for face, walk in expected_walks(replay, faces, triangle, hand):
            seen.add(face.identifier)
            trace, closures = targeted(replay, walk, hand)
            assert closures == [packed(triangle)]
            assert sum(row["decision"] == "turn_towards_originating_face" for row in trace) == 3
            assert sum(row["decision"] == "straight_extension_from_wall" for row in trace) == 3
            arrivals = [row for row in trace if row["incoming_phase"][0] == "committed"
                        and row["outgoing_phase"][0] == "physical"]
            assert {row["incoming_phase"][1] for row in arrivals} == {f.identifier for f in faces}
        assert seen == {face.identifier for face in faces}
