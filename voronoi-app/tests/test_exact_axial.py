import json
from fractions import Fraction
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box, shape
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, attach_spatial_samples
from voronoi_app.axial import AxialLine
from voronoi_app.exact_axial import (
    ExactCandidate, ExactCandidateSet, _attach_selected_samples, _connect_exact_selected,
    angular_selection, bounded_two_for_one_selection, build_candidates, candidate_graph, closed_routes,
    generate_exact_candidate_pool,
    greedy_selection, region_coverage, rejection,
)
from voronoi_app.exact_enumeration import (
    exact_pool_from_dict, exact_pool_to_dict, generate_fresh_exact_candidate_pool,
)


def candidate(index, start, end):
    a = tuple(Fraction(value) for value in start)
    b = tuple(Fraction(value) for value in end)
    return ExactCandidate(index, a, b, a, b, "test")


def test_exact_candidates_keep_tangent_support_and_maximal_interval():
    occupied = box(1, 1, 2, 2)
    clearance = LineClearance(box(0, 0, 3, 3).difference(occupied), occupied)
    line = ExactCandidate.from_seed(1, (0, 1), (1, 1), "boundary", clearance)
    assert (line.start, line.end) == ((0, 1), (3, 1))
    assert clearance.permits_exact(line.start, line.end)


def test_original_obstacle_polygons_are_checked_independently():
    domain = box(0, 0, 3, 3)
    original = box(1, 1, 2, 2)
    clearance = LineClearance(domain, box(10, 10, 11, 11), original_obstacles=[original])
    assert not clearance.permits_exact((0, 1.5), (3, 1.5))
    assert clearance.permits_exact((0, 1), (3, 1))


def test_exact_candidate_rejects_float_or_unrelated_seed():
    with pytest.raises(ValueError, match="rational"):
        ExactCandidate(1, (0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (1.0, 0.0), "test")
    with pytest.raises(ValueError, match="contain"):
        ExactCandidate(1, (Fraction(0), Fraction(0)), (Fraction(1), Fraction(0)),
                       (Fraction(0), Fraction(1)), (Fraction(1), Fraction(1)), "test")


def test_exact_region_coverage_excludes_boundary_only_contact():
    lines = [candidate(0, (0, 0), (2, 0)), candidate(1, (0, 1), (2, 1))]
    assert region_coverage(lines, {4: box(0, 0, 2, 2)}) == [set(), {4}]


def test_exact_graph_distinguishes_rounded_coincident_endpoints():
    tiny = Fraction(1, 10**30)
    lines = [candidate(0, (0, 0), (1, 0)),
             candidate(1, (1 + tiny, -1), (1 + tiny, 1))]
    assert not candidate_graph(lines).has_edge(0, 1)
    lines.append(candidate(2, (Fraction(1, 3), -1), (Fraction(1, 3), 1)))
    assert candidate_graph(lines).has_edge(0, 2)


def test_exact_rings_with_intersections_overlaps_and_branches():
    lines = [candidate(0, (0, 0), (3, 0)), candidate(1, (3, 0), (3, 3)),
             candidate(2, (3, 3), (0, 3)), candidate(3, (0, 3), (0, 0)),
             candidate(4, (1, 0), (2, 0)), candidate(5, (3, 1), (4, 1))]
    assert closed_routes(lines, [(1, 1), (4, 2)]) == {0}
    assert closed_routes(lines[1:], [(1, 1)]) == set()


def test_exact_ring_does_not_close_a_sub_float_gap():
    tiny = Fraction(1, 10**30)
    lines = [candidate(0, (0, 0), (1, 0)), candidate(1, (1 + tiny, 0), (1, 1)),
             candidate(2, (1, 1), (0, 1)), candidate(3, (0, 1), (0, 0))]
    assert closed_routes(lines, [(Fraction(1, 2), Fraction(1, 2))]) == set()


def test_exact_connectivity_can_use_multiple_bridge_lines():
    lines = [candidate(0, (0, 0), (0, 1)), candidate(1, (4, 0), (4, 1)),
             candidate(2, (0, 1), (2, 1)), candidate(3, (2, 1), (4, 1))]
    assert _connect_exact_selected(lines, {0, 1}, [set(range(4))]) == {0, 1, 2, 3}


def test_candidate_pool_retains_provenance_and_fills_missing_region():
    occupied = box(1, 1, 2, 2)
    clearance = LineClearance(box(0, 0, 3, 3).difference(occupied), occupied)
    pool = build_candidates(
        clearance, {0: box(0, 0, 1, 1)}, [],
        [("first", (0, 1), (1, 1)), ("second", (2, 1), (3, 1)),
         ("invalid", (0, 1.5), (3, 1.5))],
    )
    assert pool.fallback_regions == {0}
    assert len(pool.rejected) == 1
    boundary = next(line for line in pool.candidates if line.source == "first")
    assert boundary.aliases == (("second", (Fraction(2), Fraction(1)),
                                 (Fraction(3), Fraction(1))),)
    assert set().union(*pool.covers) == {0}
    assert all(clearance.permits_exact(line.start, line.end) for line in pool.candidates)


def test_generation_uses_saved_support_instead_of_rounded_endpoints():
    line = AxialLine(9, (0, 1), (3, 1 + 1e-14), {
        "supports": [{"source": "boundary", "start": [0, 1], "end": [1, 1]}],
    })
    problem = generate_exact_candidate_pool(
        {0: box(0, 0, 3, 3).difference(box(1, 1, 2, 2))},
        {1: box(1, 1, 2, 2)}, [line], [((0, 1), (1, 1))],
    )
    matching = [candidate for candidate in problem.pool.candidates
                if candidate.start[1] == candidate.end[1] == 1]
    assert len(matching) == 1
    sources = {matching[0].source, *(source for source, _, _ in matching[0].aliases)}
    assert "candidate:9:boundary" in sources
    assert "recovered-tangent:0" in sources
    assert problem.clearance.permits_exact(matching[0].start, matching[0].end)


def test_greedy_exact_selection_preserves_ring_and_coverage():
    occupied = box(1, 1, 2, 2)
    domain = box(0, 0, 3, 3).difference(occupied)
    regions = {0: box(0, 0, 1, 3), 1: box(2, 0, 3, 3),
               2: box(0, 0, 3, 1), 3: box(0, 2, 3, 3)}
    ring = [((1, 1), (2, 1)), ((2, 1), (2, 2)),
            ((2, 2), (1, 2)), ((1, 2), (1, 1))]
    pool = build_candidates(LineClearance(domain, occupied), regions, ring, [])
    selected, groups, graph = greedy_selection(pool, regions, domain, [(1.5, 1.5)])
    assert len(selected) == 4
    assert rejection(pool, selected, set(regions), groups, graph, [(1.5, 1.5)]) is None


def test_y_recovered_tangents_and_region_fallback_are_certified():
    data = json.loads((Path(__file__).parent / "fixtures" / "angular_y_geometry.json").read_text())
    domain, occupied = shape(data["domain"]), shape(data["occupied"])
    regions = {int(key): shape(value) for key, value in data["regions"].items()}
    clearance = LineClearance(domain, occupied)
    seeds = [("unresolved-tangent", entry["start"], entry["end"])
             for entry in data["unresolved"]]
    pool = build_candidates(clearance, regions, [], seeds)
    supports = [(line.source, line.seed_start, line.seed_end)
                for line in pool.candidates]
    supports.extend(alias for line in pool.candidates for alias in line.aliases)
    assert sum(source == "unresolved-tangent" for source, _, _ in supports) == 18
    assert not pool.rejected
    assert 82 in pool.fallback_regions
    assert set().union(*pool.covers) == {82, 226}
    assert all(clearance.permits_exact(line.start, line.end) for line in pool.candidates)


def test_exact_angular_exchange_uses_same_pool_and_common_samples():
    domain = box(0, 0, 4, 2)
    regions = {0: box(0, 0, 2, 2), 1: box(2, 0, 4, 2)}
    lines = [candidate(0, (0, 0), (2, 2)), candidate(1, (2, 2), (4, 0)),
             candidate(2, (0, 1), (4, 1))]
    pool = ExactCandidateSet(lines, region_coverage(lines, regions), set(), [], set())
    kwargs = dict(
        pool=pool, initial={0, 1}, regions=regions, accessible=domain,
        clearance=LineClearance(domain, box(10, 10, 11, 11)), obstacles=[],
        samples=[(.5, 1), (3.5, 1)], iterations=12, seed=7,
    )
    result = angular_selection(**kwargs)
    assert result.selected == {2}
    assert result.mean < result.initial_mean
    assert result == angular_selection(**kwargs)


def test_bounded_two_for_one_exchange_preserves_constraints_and_is_reproducible():
    domain = box(0, 0, 4, 2)
    regions = {0: box(0, 0, 2, 2), 1: box(2, 0, 4, 2)}
    lines = [candidate(0, (0, 0), (2, 2)), candidate(1, (2, 2), (4, 0)),
             candidate(2, (0, 1), (4, 1))]
    pool = ExactCandidateSet(lines, region_coverage(lines, regions), set(), [], set())
    kwargs = dict(pool=pool, initial={0, 1}, regions=regions, accessible=domain,
                  clearance=LineClearance(domain, box(10, 10, 11, 11)), obstacles=[],
                  samples=[(.5, 1), (3.5, 1)])
    result = bounded_two_for_one_selection(**kwargs)
    assert result.selected == {2}
    assert result == bounded_two_for_one_selection(**kwargs)


def test_bounded_attachment_search_matches_exhaustive_visible_search():
    occupied = box(4, 4, 6, 6)
    clearance = LineClearance(box(0, 0, 10, 10).difference(occupied), occupied)
    lines = [candidate(0, (8, 2), (8, 8)), candidate(1, (0, 2), (3, 2)),
             candidate(2, (0, 8), (3, 8))]
    samples = [(2, 5), (7, 5)]
    expected = attach_spatial_samples(samples, lines, clearance)
    cache = {}
    assert _attach_selected_samples(samples, lines, clearance, cache) == expected
    assert _attach_selected_samples(samples, lines, clearance, cache) == expected


def test_fresh_pool_preserves_building_vertex_provenance_and_rejects_shared_seams():
    occupied = {10: box(1, 1, 2, 2), 11: box(2, 1, 3, 2), 12: box(4, 1, 5, 2)}
    domain = box(0, 0, 6, 3).difference(unary_union(list(occupied.values())))
    problem, audit = generate_fresh_exact_candidate_pool({0: domain}, occupied)
    restored = exact_pool_from_dict(json.loads(json.dumps(exact_pool_to_dict(problem.pool))))
    assert restored == problem.pool
    supports = [support for line in restored.candidates for support in line.provenance]
    assert any(support.source == "mutual-tangent"
               and {ref.building_id for ref in support.start_vertices} == {10}
               and {ref.building_id for ref in support.end_vertices} == {12}
               for support in supports)
    assert any(support.source == "same-building-tangent"
               and support.start_vertices[0].building_id == support.end_vertices[0].building_id == 12
               for support in supports)
    assert audit.counts["mutual-tangent:domain-or-union"] > 0
    seam = {candidate(0, (2, 1), (2, 2)).start, candidate(0, (2, 1), (2, 2)).end}
    assert any({support.start, support.end} == seam for support in audit.domain_rejections)
    assert all({support.start, support.end} != seam for support in supports)
    assert all(problem.clearance.permits_exact(line.start, line.end)
               for line in restored.candidates)


def test_y_fresh_tangents_recover_390_251_and_candidate_5771(monkeypatch):
    data = json.loads((Path(__file__).parent / "fixtures" / "angular_y_geometry.json").read_text())
    domain = shape(data["domain"])
    occupied = {
        251: Polygon([(50.51058519704879, 40.8426815156404), (49.48572383126996, 45.324401374980944),
                      (53.90903784345668, 46.352681907095096), (55.15874075944051, 44.10308526710415),
                      (55.004058685900894, 42.19959128123505), (53.2392164510027, 40.39544243884678),
                      (51.40354728454599, 40.18980690765721)]),
        343: Polygon([(68.77806855723111, 59.16923768567187), (68.33583204636682, 62.912340402381254),
                      (69.03279126452976, 63.41481700021376), (72.11283075309032, 63.99737585691437),
                      (73.14521704039153, 60.05213032376891), (71.07312106571021, 58.1573553076887)]),
        366: Polygon([(72.68571927193062, 64.63787832552376), (73.32659712035256, 67.30228995238043),
                      (73.56390858512921, 67.53164120277839), (76.57776465327521, 68.04196452604724),
                      (78.3112003764979, 66.78004281630561), (79.70736479939316, 63.77144291013067),
                      (77.81604622258247, 62.41848511562887)]),
        390: Polygon([(78.24927240525133, 72.48833951792712), (78.15471376538504, 72.60947286308584),
                      (77.2701191487939, 76.60822242563228), (77.5806779411444, 77.0698225609674),
                      (81.42724972140937, 77.36405185240015), (83.05291981121076, 76.60210982123674),
                      (83.04765171308689, 73.7515044492607), (81.3840956103631, 71.87051912109948)]),
    }
    monkeypatch.setattr("voronoi_app.exact_enumeration.convex_regions",
                        lambda _: {0: box(0, 0, 1, 1)})
    problem, _ = generate_fresh_exact_candidate_pool({0: domain}, occupied)

    def find(start_building, start_index, end_building, end_index):
        for line in problem.pool.candidates:
            for support in line.provenance:
                pairs = {(ref.building_id, ref.vertex_index) for ref in support.start_vertices}
                other = {(ref.building_id, ref.vertex_index) for ref in support.end_vertices}
                if support.source == "mutual-tangent" and (
                    ((start_building, start_index) in pairs and (end_building, end_index) in other)
                    or ((end_building, end_index) in pairs and (start_building, start_index) in other)
                ):
                    return line
        pytest.fail("Expected original building-vertex support was not generated")

    first = find(390, 3, 251, 1)
    recovered = find(343, 1, 366, 2)
    assert first.length == pytest.approx(74.69406638431681)
    assert recovered.length == pytest.approx(43.55354665155043)
    assert problem.clearance.permits_exact(first.start, first.end)
    assert problem.clearance.permits_exact(recovered.start, recovered.end)
