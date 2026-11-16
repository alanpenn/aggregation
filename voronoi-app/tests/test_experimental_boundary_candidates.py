from fractions import Fraction

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, _cross, _direction, _exact_point
from voronoi_app.exact_enumeration import _supports, _vertices, generate_fresh_exact_candidate_pool
from voronoi_app.experimental_boundary_candidates import (
    _boundary_vertices, canonical_interval, enumerate_boundary_endpoint_candidates,
)


def test_boundary_endpoint_tangencies_are_exact_deduplicated_and_keep_contacts():
    occupied = {10: box(2, 1, 3, 2), 11: box(4, 3, 5, 4)}
    union = unary_union(list(occupied.values()))
    domain = box(0, 0, 6, 6).difference(union)
    audit = enumerate_boundary_endpoint_candidates({0: domain}, occupied)
    expected = canonical_interval((Fraction(0), Fraction(0)), (Fraction(6), Fraction(6)))
    line = next(candidate for candidate in audit.candidates
                if canonical_interval(candidate.start, candidate.end) == expected)
    assert len(line.supports) >= 2
    contacts = {contact.point: {ref.building_id for ref in contact.buildings}
                for contact in line.contacts}
    assert contacts[(Fraction(2), Fraction(2))] == {10}
    assert contacts[(Fraction(4), Fraction(4))] == {11}
    clearance = LineClearance(domain, union, original_obstacles=occupied.values())
    assert all(clearance.permits_exact(line.start, line.end) for line in audit.candidates)
    assert audit.counts["occupied-interior"] > 0


def test_boundary_and_single_corner_can_add_a_new_exact_interval():
    occupied = {10: box(2, 1, 3, 2)}
    domain = box(0, 0, 6, 6).difference(occupied[10])
    audit = enumerate_boundary_endpoint_candidates({0: domain}, occupied)
    baseline, _ = generate_fresh_exact_candidate_pool({0: domain}, occupied)
    baseline_intervals = {canonical_interval(line.start, line.end)
                          for line in baseline.pool.candidates}
    expected = canonical_interval((Fraction(0), Fraction(0)), (Fraction(6), Fraction(6)))
    assert any(canonical_interval(line.start, line.end) == expected for line in audit.candidates)
    assert expected not in baseline_intervals


def test_boundary_vertex_shared_by_buildings_keeps_all_references():
    occupied = {10: box(1, 1, 2, 2), 11: box(2, 1, 3, 2),
                12: box(4, 0, 5, 1)}
    domain = box(0, 0, 6, 4).difference(unary_union(list(occupied.values())))
    audit = enumerate_boundary_endpoint_candidates({0: domain}, occupied)
    shared = (Fraction(2), Fraction(1))
    contacts = [contact for candidate in audit.candidates for contact in candidate.contacts
                if contact.point == shared]
    assert contacts
    assert all({ref.building_id for ref in contact.buildings} == {10, 11}
               for contact in contacts)


def test_collinear_open_cell_subdivision_does_not_create_candidates():
    occupied = {10: box(2, 1, 3, 2)}
    coarse = enumerate_boundary_endpoint_candidates({0: box(0, 0, 6, 6)}, occupied)
    refined = enumerate_boundary_endpoint_candidates(
        {0: box(0, 0, 3, 6), 1: box(3, 0, 6, 6)}, occupied
    )
    intervals = lambda audit: {canonical_interval(line.start, line.end)
                               for line in audit.candidates}
    assert intervals(coarse) == intervals(refined)
    assert coarse.counts["boundary-vertices"] == refined.counts["boundary-vertices"]


def test_original_building_vertex_is_retained_when_overlay_omits_it():
    occupied = {10: Polygon([(2, 1), (3, 1), (3, 2), (2, 2), (2, 1.5)])}
    domain = box(0, 0, 6, 6).difference(occupied[10]).simplify(0, preserve_topology=True)
    point = (Fraction(2), Fraction(3, 2))
    assert point not in {_exact_point(p) for ring in (domain.exterior, *domain.interiors)
                         for p in ring.coords}
    vertices, _ = _vertices(occupied)
    boundary, contacts = _boundary_vertices(domain, vertices)
    assert point in boundary and point in contacts


def test_clear_maximal_sightlines_are_not_exhausted_by_these_finite_support_rules():
    occupied = {10: box(2, 1, 3, 2)}
    domain = box(0, 0, 6, 6).difference(occupied[10])
    clearance = LineClearance(domain, occupied[10], original_obstacles=occupied.values())
    height = Fraction(1, 3)
    start, end = clearance.maximal_interval((1, height), (5, height))
    assert clearance.permits_exact(start, end)
    assert canonical_interval(start, end) == ((Fraction(0), height), (Fraction(6), height))
    existing, _ = generate_fresh_exact_candidate_pool({0: domain}, occupied)
    proposed = enumerate_boundary_endpoint_candidates({0: domain}, occupied)
    interval = canonical_interval(start, end)
    assert interval not in {canonical_interval(line.start, line.end)
                            for line in existing.pool.candidates}
    assert interval not in {canonical_interval(line.start, line.end)
                            for line in proposed.candidates}


def test_boundary_vertex_pair_without_an_occupied_corner_is_another_class():
    occupied = {10: box(4, 1, 5, 2)}
    domain = box(0, 0, 6, 6).difference(occupied[10])
    clearance = LineClearance(domain, occupied[10], original_obstacles=occupied.values())
    start, end = clearance.maximal_interval((0, 0), (6, 6))
    assert clearance.permits_exact(start, end)
    interval = canonical_interval(start, end)
    existing, _ = generate_fresh_exact_candidate_pool({0: domain}, occupied)
    proposed = enumerate_boundary_endpoint_candidates({0: domain}, occupied)
    assert interval not in {canonical_interval(line.start, line.end)
                            for line in existing.pool.candidates}
    assert interval not in {canonical_interval(line.start, line.end)
                            for line in proposed.candidates}


def test_disconnected_accessible_components_cannot_be_bridged():
    occupied = {10: box(4, 1, 5, 2)}
    opened = {0: box(0, 0, 3, 3), 1: box(4, 0, 7, 3)}
    domain = unary_union(list(opened.values())).difference(occupied[10])
    clearance = LineClearance(domain, occupied[10], original_obstacles=occupied.values())
    audit = enumerate_boundary_endpoint_candidates(opened, occupied)
    assert audit.counts["domain-or-union"] > 0
    assert all(clearance.permits_exact(line.start, line.end) for line in audit.candidates)


def test_boundary_enumerator_matches_exhaustive_exact_small_case():
    occupied = {10: box(2, 1, 3, 2), 11: box(4, 3, 5, 4)}
    union = unary_union(list(occupied.values()))
    domain = box(0, 0, 6, 6).difference(union)
    clearance = LineClearance(domain, union, original_obstacles=occupied.values())
    vertices, _ = _vertices(occupied)
    boundary = set()
    for ring in (domain.exterior, *domain.interiors):
        points = list(map(_exact_point, list(ring.coords)[:-1]))
        for i, point in enumerate(points):
            turn = _cross(_direction(points[i - 1], point),
                          _direction(point, points[(i + 1) % len(points)]))
            if turn or point in vertices:
                boundary.add(point)
    expected = set()
    for a in boundary:
        for b, corners in vertices.items():
            if a == b or not any(corner.convex and _supports(corner, a) for corner in corners):
                continue
            if not clearance.permits_exact(a, b):
                continue
            start, end = clearance.maximal_interval(a, b)
            if a in (start, end):
                expected.add(canonical_interval(start, end))
    audit = enumerate_boundary_endpoint_candidates({0: domain}, occupied)
    assert {canonical_interval(line.start, line.end) for line in audit.candidates} == expected
