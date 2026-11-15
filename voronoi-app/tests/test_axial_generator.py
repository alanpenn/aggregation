import pytest
import networkx as nx
from math import hypot
from types import SimpleNamespace
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union

from voronoi_app.axial_generator import (
    ConvexCoverageError,
    _candidate_graph, _closed_routes, _comparable_mean_depths, _connect_selected,
    _maximal_interval, _reduce_collectively_redundant, _reduce_dominated,
    _select_axial_candidates, generate_axial_map,
)
from voronoi_app.axial import AxialLine, AxialMap
from voronoi_app.convex_coverage import convex_regions, line_region_coverage
from voronoi_app.core import ExperimentPipeline
from voronoi_app.orchestrator import (
    ExperimentOrchestrator, generate_experiment_axial_map, run_experiment_pipeline,
)
from voronoi_app.render import UNASSIGNED_OPEN_COLOR, fig_convex_coverage, fig_generated_axial_map


def cells(coordinates):
    return {
        index: box(x, y, x + 1, y + 1)
        for index, (x, y) in enumerate(sorted(coordinates))
    }


def assert_coverage(result, polygons):
    assert result.covered_cells == set(polygons)
    lines = [LineString((line.start, line.end)) for line in result.axial_map.lines]
    assert all(any(line.relate_pattern(polygon, "T********") for line in lines)
               for polygon in polygons.values())
    accessible = unary_union(list(polygons.values()))
    assert all(accessible.buffer(1e-8).covers(line) for line in lines)


def assert_connected(result):
    representation = result.axial_map.to_representation()
    graph = nx.Graph()
    graph.add_nodes_from(representation.nodes)
    graph.add_edges_from(representation.edges)
    assert nx.number_connected_components(graph) == result.axial_components
    assert result.axial_components == result.open_components


def assert_maximal(result, accessible):
    min_x, min_y, max_x, max_y = accessible.bounds
    scale = hypot(max_x - min_x, max_y - min_y)
    tolerance = max(scale * 1e-9, 1e-12)
    extension = max(scale * 1e-6, 1e-8)
    segments = [LineString((line.start, line.end)) for line in result.axial_map.lines]
    for index, segment in enumerate(segments):
        assert all(segment.hausdorff_distance(other) > tolerance
                   for other in segments[index + 1:])
    for line in result.axial_map.lines:
        x, y = line.start
        x2, y2 = line.end
        length = hypot(x2 - x, y2 - y)
        dx, dy = (x2 - x) / length, (y2 - y) / length
        for endpoint, direction in ((line.start, -1), (line.end, 1)):
            farther = (endpoint[0] + direction * extension * dx,
                       endpoint[1] + direction * extension * dy)
            assert not accessible.buffer(tolerance).covers(LineString([endpoint, farther])), (
                line.line_id, endpoint
            )


def test_convex_coverage_single_convex_space_and_boundary_contact():
    domain = box(0, 0, 4, 2)
    regions = convex_regions(domain)
    assert len(regions) == 1 and regions[0].equals(domain)
    lines = [
        LineString([(0, 0), (4, 0)]),
        LineString([(-1, -1), (0, 0)]),
        LineString([(0, 1), (4, 1)]),
    ]
    assert line_region_coverage(lines, regions) == [set(), set(), {0}]


@pytest.mark.parametrize(
    "domain",
    [
        unary_union([box(0, 0, 3, 1), box(0, 1, 1, 3)]),
        box(0, 0, 4, 4).difference(box(1, 1, 3, 3)),
        unary_union([box(0, 0, 1, 1), box(3, 0, 4, 1)]),
    ],
    ids=["concave", "obstacle-hole", "disconnected"],
)
def test_convex_regions_preserve_domain_without_obstacle_interiors(domain):
    regions = convex_regions(domain)
    assert unary_union(list(regions.values())).equals(domain)
    assert all(domain.covers(region) and region.equals(region.convex_hull)
               for region in regions.values())
    assert len(regions) >= 2


def test_convex_region_selection_is_stable_under_open_cell_refinement():
    coarse = {0: box(0, 0, 2, 2), 1: box(2, 0, 4, 2)}
    refined = cells({(x, y) for x in range(4) for y in range(2)})
    domain = unary_union(list(coarse.values()))
    assert domain.equals(unary_union(list(refined.values())))
    coarse_regions = convex_regions(domain)
    refined_regions = convex_regions(unary_union(list(refined.values())))
    assert len(coarse_regions) == len(refined_regions)
    assert all(coarse_regions[i].equals(refined_regions[i]) for i in coarse_regions)
    candidates = [LineString([(0, 1), (4, 1)]), LineString([(2, 0), (2, 2)])]
    coarse_covers = line_region_coverage(candidates, coarse_regions)
    refined_covers = line_region_coverage(candidates, refined_regions)
    assert coarse_covers == refined_covers
    before = _select_axial_candidates(
        candidates, coarse_covers, set(coarse_regions), set(), domain, [], 1e-9,
        coverage_model="convex",
    )
    after = _select_axial_candidates(
        candidates, refined_covers, set(refined_regions), set(), domain, [], 1e-9,
        coverage_model="convex",
    )
    assert before.selected == after.selected


def test_convex_refinement_preserves_obstacle_requirements_and_selection():
    coarse = cells({(x, y) for x in range(3) for y in range(3)} - {(1, 1)})
    refined = {
        4 * cell + dy * 2 + dx: box(polygon.bounds[0] + dx * 0.5,
                                    polygon.bounds[1] + dy * 0.5,
                                    polygon.bounds[0] + (dx + 1) * 0.5,
                                    polygon.bounds[1] + (dy + 1) * 0.5)
        for cell, polygon in coarse.items() for dx in range(2) for dy in range(2)
    }
    obstacle = box(1, 1, 2, 2)
    domain = unary_union(list(coarse.values()))
    assert domain.equals(unary_union(list(refined.values())))
    baseline = generate_axial_map(coarse, {99: obstacle})
    candidates = [LineString((line.start, line.end)) for line in baseline.candidate_lines]
    edges = [LineString((a, b)) for a, b in zip(obstacle.exterior.coords,
                                               list(obstacle.exterior.coords)[1:])]
    ring_candidates = {
        next(i for i, line in enumerate(candidates) if line.covers(edge)) for edge in edges
    }
    regions_a = convex_regions(domain)
    regions_b = convex_regions(unary_union(list(refined.values())))
    assert len(regions_a) == len(regions_b)
    assert all(regions_a[i].equals(regions_b[i]) for i in regions_a)
    covers_a = line_region_coverage(candidates, regions_a)
    covers_b = line_region_coverage(candidates, regions_b)
    assert covers_a == covers_b
    selection_a = _select_axial_candidates(
        candidates, covers_a, set(regions_a), ring_candidates, domain,
        [Point(1.5, 1.5)], 1e-9, coverage_model="convex",
    )
    selection_b = _select_axial_candidates(
        candidates, covers_b, set(regions_b), ring_candidates, domain,
        [Point(1.5, 1.5)], 1e-9, coverage_model="convex",
    )
    assert selection_a.selected == selection_b.selected
    assert _closed_routes([candidates[i] for i in selection_a.selected], [Point(1.5, 1.5)]) == {0}


def test_convex_selection_keeps_candidates_and_reports_region_coverage():
    polygons = {0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1)}
    baseline = generate_axial_map(polygons, {})
    convex = generate_axial_map(polygons, {}, coverage_model="convex")
    assert [(line.start, line.end) for line in baseline.candidate_lines] == [
        (line.start, line.end) for line in convex.candidate_lines
    ]
    assert convex.covered_regions == set(convex.coverage_regions)
    assert all(any(LineString((line.start, line.end)).relate_pattern(region, "T********")
                   for line in convex.axial_map.lines)
               for region in convex.coverage_regions.values())
    assert_connected(convex)


def test_convex_diagnostic_shows_uncovered_regions():
    domain = box(0, 0, 2, 2)
    generated = SimpleNamespace(
        coverage_regions={0: domain}, covered_regions=set(),
        axial_map=AxialMap([AxialLine(0, (0, 1), (2, 1))]),
    )
    result = SimpleNamespace(buildings=set(), config=SimpleNamespace(canvas_size=2))
    figure = fig_convex_coverage(result, generated, {0: domain})
    legend = {text.get_text() for text in figure.axes[0].get_legend().get_texts()}
    assert "Uncovered convex region" in legend
    assert len(figure.axes[0].lines) == 1


def test_convex_selection_reports_uncoverable_region():
    domain = box(0, 0, 1, 1)
    candidates = [LineString([(0, 0), (1, 0)])]
    regions = convex_regions(domain)
    with pytest.raises(ValueError, match="could not cover convex regions"):
        _select_axial_candidates(
            candidates, line_region_coverage(candidates, regions), set(regions),
            set(), domain, [], 1e-9, coverage_model="convex",
        )


def test_failed_convex_generation_exposes_uncovered_region_diagnostic(monkeypatch):
    monkeypatch.setattr(
        "voronoi_app.axial_generator.line_region_coverage",
        lambda lines, regions: [set() for _ in lines],
    )
    domain = box(0, 0, 2, 2)
    with pytest.raises(ConvexCoverageError, match="could not cover convex regions") as caught:
        generate_axial_map({0: domain}, {}, coverage_model="convex")
    error = caught.value
    assert set(error.coverage_regions) - error.covered_regions == set(error.coverage_regions)
    result = SimpleNamespace(buildings=set(), config=SimpleNamespace(canvas_size=2))
    figure = fig_convex_coverage(result, error, error.polygons)
    assert any(patch.get_label() == "Uncovered convex region"
               for patch in figure.axes[0].get_legend().legend_handles)


def test_short_corridor_seed_extends_both_ways():
    line = _maximal_interval(box(0, 0, 10, 2), (4, 1), (6, 1), 1e-9)
    assert line is not None
    assert line.equals(LineString([(0, 1), (10, 1)]))


def test_diagonal_extends_across_adjacent_cells():
    polygons = cells({(x, y) for x in range(3) for y in range(3)})
    accessible = unary_union(list(polygons.values()))
    line = _maximal_interval(accessible, (1, 1), (2, 2), 1e-9)
    assert line is not None
    assert line.hausdorff_distance(LineString([(0, 0), (3, 3)])) < 1e-9
    assert sum(line.relate_pattern(polygon, "T********")
               for polygon in polygons.values()) == 3


def test_maximal_extension_stops_at_occupied_obstacle():
    accessible = box(0, 0, 10, 2).difference(box(4, 0, 6, 2))
    line = _maximal_interval(accessible, (2, 1), (3, 1), 1e-9)
    assert line is not None
    assert line.equals(LineString([(0, 1), (4, 1)]))
    assert _maximal_interval(accessible, (3, 1), (7, 1), 1e-9) is None


def test_boundary_following_candidate_extends_consistently():
    accessible = box(0, 0, 10, 2)
    line = _maximal_interval(accessible, (3, 0), (5, 0), 1e-9)
    reversed_line = _maximal_interval(accessible, (5, 0), (3, 0), 1e-9)
    assert line is not None and reversed_line is not None
    assert line.equals(LineString([(0, 0), (10, 0)]))
    assert line.equals(reversed_line)


def test_centroid_candidates_find_long_irregular_corridor_axis():
    xs = [0, 1.9, 4.2, 6.1, 8.4, 10.2, 12.0]
    offsets = [0, 0.12, -0.1, 0.15, -0.08, 0.1, 0]
    polygons = {
        i: Polygon([
            (xs[i], -1 + offsets[i]), (xs[i + 1], -1 + offsets[i + 1]),
            (xs[i + 1], 1 + offsets[i + 1]), (xs[i], 1 + offsets[i]),
        ])
        for i in range(len(xs) - 1)
    }
    result = generate_axial_map(polygons, {})
    assert_coverage(result, polygons)
    assert_connected(result)
    assert len(result.axial_map.lines) == 1
    assert result.axial_map.lines[0].length >= 12
    first, last = polygons[0].centroid, polygons[len(polygons) - 1].centroid
    assert any(LineString((line.start, line.end)).distance(first) < 1e-8
               and LineString((line.start, line.end)).distance(last) < 1e-8
               for line in result.candidate_lines)


def test_centroid_candidates_do_not_cross_occupied_obstacle():
    polygons = {0: box(0, 0, 1, 1), 1: box(2, 0, 3, 1)}
    result = generate_axial_map(polygons, {2: box(1, 0, 2, 1)})
    accessible = unary_union(list(polygons.values()))
    assert all(accessible.buffer(1e-8).covers(LineString((line.start, line.end)))
               for line in result.candidate_lines)


def test_deduplicated_candidates_retain_all_defining_seeds():
    result = generate_axial_map(cells({(0, 0), (1, 0), (2, 0)}), {})
    candidate = next(line for line in result.candidate_lines
                     if LineString((line.start, line.end)).equals(LineString(((0, .5), (3, .5)))))
    seeds = {(tuple(item["start"]), tuple(item["end"])) for item in candidate.attributes["supports"]
             if item["source"] == "centroid"}
    assert seeds == {
        ((.5, .5), (1.5, .5)), ((.5, .5), (2.5, .5)), ((1.5, .5), (2.5, .5)),
    }


def test_rectangular_ring_preserves_closed_route_around_obstacle():
    polygons = cells({(x, y) for x in range(3) for y in range(3)} - {(1, 1)})
    result = generate_axial_map(polygons, {99: box(1, 1, 2, 2)})
    assert_coverage(result, polygons)
    assert_connected(result)
    assert_maximal(result, unary_union(list(polygons.values())))
    assert result.required_rings == result.preserved_rings == 1
    lines = [LineString((line.start, line.end)) for line in result.axial_map.lines]
    assert any(face.covers(Point(1.5, 1.5)) for face in polygonize(unary_union(lines)))
    for index in range(len(lines)):
        remaining = lines[:index] + lines[index + 1:]
        coverage = all(any(line.relate_pattern(polygon, "T********") for line in remaining)
                       for polygon in polygons.values())
        ring = any(face.covers(Point(1.5, 1.5))
                   for face in polygonize(unary_union(remaining)))
        remaining_graph = _candidate_graph(remaining, unary_union(list(polygons.values())))
        connected = bool(remaining) and nx.is_connected(remaining_graph)
        assert not (coverage and ring and connected)


@pytest.mark.parametrize(
    "coordinates",
    [
        {(0, 0), (1, 0), (2, 0), (3, 0)},
        {(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)},
        {(0, 1), (1, 1), (2, 1), (1, 0), (1, 2)},
        {(0, 1), (1, 1), (2, 1), (1, 2), (1, 3)},
    ],
    ids=["corridor", "L-junction", "cross-junction", "T-junction"],
)
def test_corridors_and_junctions_are_covered(coordinates):
    polygons = cells(coordinates)
    result = generate_axial_map(polygons, {})
    assert_coverage(result, polygons)
    assert_connected(result)
    assert_maximal(result, unary_union(list(polygons.values())))
    assert result.required_rings == result.preserved_rings == 0


def test_coverage_fallback_enters_a_single_open_cell():
    polygons = {0: box(0, 0, 1, 1)}
    result = generate_axial_map(polygons, {})
    assert_coverage(result, polygons)
    assert len(result.axial_map.lines) == 1


def test_open_route_does_not_count_as_an_obstacle_ring():
    lines = [
        LineString([(0, 0), (3, 0)]),
        LineString([(3, 0), (3, 3)]),
        LineString([(3, 3), (0, 3)]),
    ]
    assert _closed_routes(lines, [Point(1.5, 1.5)]) == set()


def test_collinear_overlap_connects_axial_lines():
    axial_map = AxialMap([
        AxialLine(0, (0, 0), (2, 0)),
        AxialLine(1, (1, 0), (3, 0)),
        AxialLine(2, (4, 0), (5, 0)),
    ])
    assert axial_map.to_representation().edges == [(0, 1)]
    lines = [LineString((line.start, line.end)) for line in axial_map.lines]
    assert list(_candidate_graph(lines, box(-1, -1, 6, 1)).edges) == [(0, 1)]
    assert list(_candidate_graph(lines, box(4, -1, 6, 1)).edges) == []


def test_disconnected_line_groups_use_minimum_available_bridge():
    lines = [
        LineString([(0, 0), (1, 0)]),
        LineString([(3, 0), (4, 0)]),
        LineString([(1, 0), (3, 0)]),
    ]
    graph = _candidate_graph(lines, box(-1, -1, 5, 1))
    selected = _connect_selected(graph, {0, 1}, [set(range(3))])
    assert selected == {0, 1, 2}
    assert nx.is_connected(graph.subgraph(selected))


def test_unconnectable_line_groups_are_reported():
    graph = nx.Graph()
    graph.add_nodes_from([0, 1])
    with pytest.raises(ValueError, match="connectivity cannot be achieved"):
        _connect_selected(graph, {0, 1}, [{0, 1}])


def test_multiple_candidates_can_form_a_bridge():
    graph = nx.path_graph(4)
    selected = _connect_selected(graph, {0, 3}, [set(graph)])
    assert selected == {0, 1, 2, 3}


def test_dominance_removes_longer_line_only_when_coverage_allows():
    lines = [LineString([(0, i), (length, i)])
             for i, length in enumerate((1, 10, 2, 2))]
    graph = nx.Graph([(0, 2), (0, 3), (1, 2), (2, 3)])
    covers = [{10, 20}, {10}, {30}, {40}]
    selected, decisions = _reduce_dominated(
        lines, graph, set(graph), covers, {10, 20, 30, 40}, [set(graph)], [],
    )
    assert selected == {0, 2, 3}
    assert any(d.dominated == 1 and d.dominator == 0 and d.accepted for d in decisions)
    assert any(not d.accepted and d.reason == "open-cell coverage" for d in decisions)
    before, after, count = _comparable_mean_depths(graph, set(graph), selected)
    assert count == 3 and after <= before
    for left, right in ((0, 2), (0, 3), (2, 3)):
        assert nx.shortest_path_length(graph.subgraph(selected), left, right) <= (
            nx.shortest_path_length(graph, left, right)
        )


def test_line_with_extra_connection_is_not_dominated():
    lines = [LineString([(0, i), (1, i)]) for i in range(5)]
    graph = nx.Graph([(0, 2), (0, 4), (1, 2), (1, 3), (2, 3)])
    covers = [{i} for i in range(5)]
    selected, decisions = _reduce_dominated(
        lines, graph, set(graph), covers, set(range(5)), [set(graph)], [],
    )
    assert selected == set(graph)
    assert not any(d.dominated == 1 and d.dominator == 0 for d in decisions)


def test_dominance_keeps_obstacle_ring_when_coverage_and_connectivity_remain():
    lines = [
        LineString([(0, 0), (2, 0)]), LineString([(2, 0), (2, 2)]),
        LineString([(2, 2), (0, 2)]), LineString([(0, 2), (0, 0)]),
    ]
    graph = _candidate_graph(lines, box(-1, -1, 3, 3))
    selected, decisions = _reduce_dominated(
        lines, graph, set(graph), [{0}] * 4, {0}, [set(graph)], [Point(1, 1)],
    )
    assert selected == set(graph)
    assert decisions and all(not d.accepted and d.reason == "obstacle circulation ring"
                             for d in decisions)


def test_dominance_preserves_each_open_component():
    lines = [LineString([(0, 0), (1, 0)]), LineString([(3, 0), (4, 0)])]
    graph = nx.empty_graph(2)
    selected, decisions = _reduce_dominated(
        lines, graph, {0, 1}, [{0}, {0}], {0}, [{0}, {1}], [],
    )
    assert selected == {0, 1}
    assert decisions and all(d.reason == "open-space connectivity" for d in decisions)


def test_dominance_rechecks_connections_after_every_removal():
    lines = [LineString([(0, i), (i + 1, i)]) for i in range(4)]
    graph = nx.complete_graph(4)
    covers = [{0}, {0}, {1}, {1}]
    selected, decisions = _reduce_dominated(
        lines, graph, set(graph), covers, {0, 1}, [set(graph)], [],
    )
    accepted = [d for d in decisions if d.accepted]
    assert len(accepted) == 2
    assert len(selected) == 2
    assert nx.is_connected(graph.subgraph(selected))
    assert all(not d.accepted and d.reason == "open-cell coverage"
               for d in decisions[decisions.index(accepted[-1]) + 1:])


def test_collective_redundancy_removes_line_without_a_single_dominator():
    lines = [LineString([(0, i), (1, i)]) for i in range(5)]
    graph = nx.cycle_graph(5)
    covers = [{0}, {0, 1}, {2}, {3}, {4}]
    cells = set(range(5))
    selected, dominance = _reduce_dominated(
        lines, graph, set(graph), covers, cells, [set(graph)], [],
    )
    assert selected == set(graph)
    assert not any(d.dominated == 0 for d in dominance)
    selected, decisions = _reduce_collectively_redundant(
        lines, graph, selected, covers, cells, [set(graph)], [],
    )
    assert selected == {1, 2, 3, 4}
    assert any(d.candidate == 0 and d.accepted for d in decisions)
    assert all(not d.accepted and d.reason == "open-cell coverage"
               for d in decisions[1:])


def test_collective_redundancy_keeps_essential_ring_and_coverage():
    lines = [
        LineString([(0, 0), (2, 0)]), LineString([(2, 0), (2, 2)]),
        LineString([(2, 2), (0, 2)]), LineString([(0, 2), (0, 0)]),
    ]
    graph = _candidate_graph(lines, box(-1, -1, 3, 3))
    selected, decisions = _reduce_collectively_redundant(
        lines, graph, set(graph), [{0}, {0}, {0}, {0, 1}],
        {0, 1}, [set(graph)], [Point(1, 1)],
    )
    assert selected == set(graph)
    assert {(d.candidate, d.reason) for d in decisions} == {
        (0, "obstacle circulation ring"), (1, "obstacle circulation ring"),
        (2, "obstacle circulation ring"), (3, "open-cell coverage"),
    }


def test_collective_redundancy_reconsiders_connectivity_after_removal():
    lines = [LineString([(0, i), (1, i)]) for i in range(3)]
    graph = nx.path_graph(3)
    selected, decisions = _reduce_collectively_redundant(
        lines, graph, set(graph), [{0}, set(), set()], {0}, [set(graph)], [],
    )
    assert selected == {0}
    assert [(d.candidate, d.accepted, d.reason) for d in decisions if d.candidate == 1] == [
        (1, False, "open-space connectivity"),
        (1, True, "coverage, connectivity and obstacle rings preserved"),
    ]


def test_ring_and_attached_corridor_form_one_line_network():
    coordinates = ({(x, y) for x in range(3) for y in range(3)} - {(1, 1)})
    coordinates |= {(3, 1), (4, 1), (5, 1)}
    polygons = cells(coordinates)
    result = generate_axial_map(polygons, {99: box(1, 1, 2, 2)})
    assert_coverage(result, polygons)
    assert_connected(result)
    assert_maximal(result, unary_union(list(polygons.values())))
    assert result.required_rings == result.preserved_rings == 1


def test_selected_graph_shortcut_matches_full_candidate_graph(monkeypatch):
    polygons = cells({(x, y) for x in range(3) for y in range(3)} - {(1, 1)})
    occupied = {99: box(1, 1, 2, 2)}
    shortcut = generate_axial_map(polygons, occupied)
    real_candidate_graph = _candidate_graph
    calls = []

    def force_full_graph(candidates, accessible):
        graph = real_candidate_graph(candidates, accessible)
        calls.append(len(candidates))
        if len(calls) == 1:
            graph.remove_edges_from(list(graph.edges))
        return graph

    monkeypatch.setattr("voronoi_app.axial_generator._candidate_graph", force_full_graph)
    full = generate_axial_map(polygons, occupied)
    assert len(calls) == 2
    assert shortcut.candidates == full.candidates
    assert shortcut.axial_map.lines == full.axial_map.lines
    assert shortcut.covered_cells == full.covered_cells
    assert shortcut.preserved_rings == full.preserved_rings


def test_disconnected_open_components_are_connected_separately():
    polygons = {0: box(0, 0, 1, 1), 1: box(5, 0, 6, 1)}
    result = generate_axial_map(polygons, {})
    assert_coverage(result, polygons)
    assert_connected(result)
    assert result.open_components == 2


def test_each_disjoint_obstacle_in_one_hole_is_checked():
    coordinates = {(x, y) for x in range(5) for y in range(3)} - {
        (1, 1), (2, 1), (3, 1)
    }
    polygons = cells(coordinates)
    result = generate_axial_map(polygons, {98: box(1, 1, 2, 2), 99: box(3, 1, 4, 2)})
    assert_coverage(result, polygons)
    assert result.required_rings == result.preserved_rings == 2
    lines = [LineString((line.start, line.end)) for line in result.axial_map.lines]
    faces = list(polygonize(unary_union(lines)))
    assert all(any(face.covers(point) for face in faces)
               for point in (Point(1.5, 1.5), Point(3.5, 1.5)))


def test_invalid_open_geometry_is_reported():
    with pytest.raises(ValueError, match="invalid polygon"):
        generate_axial_map({0: Polygon([(0, 0), (1, 1), (0, 1), (1, 0)])}, {})


def test_uncoverable_cell_is_reported():
    with pytest.raises(ValueError, match="could not cover open cells"):
        generate_axial_map({0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1)},
                           {9: box(0, 0, 1, 1)})


def test_unpreserved_obstacle_ring_is_reported(monkeypatch):
    polygons = cells({(x, y) for x in range(3) for y in range(3)} - {(1, 1)})
    monkeypatch.setattr("voronoi_app.axial_generator._closed_routes", lambda lines, obstacles: set())
    with pytest.raises(ValueError, match="preserve 0 of 1"):
        generate_axial_map(polygons, {99: box(1, 1, 2, 2)})


def experiment_with_polygons(monkeypatch, polygons, buildings, paired_open):
    experiment = SimpleNamespace(
        pipeline=ExperimentPipeline(),
        grid=SimpleNamespace(nodes=[None] * len(polygons)),
        buildings=set(buildings),
        open_spaces=set(paired_open),
        config=SimpleNamespace(canvas_size=10),
    )
    monkeypatch.setattr(ExperimentOrchestrator, "_space_polygons", lambda self, grid: polygons)
    return experiment


def test_unassigned_cell_between_dyads_extends_candidates_and_covers_all(monkeypatch):
    polygons = {
        0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1), 2: box(2, 0, 3, 1),
        3: box(0, 1, 1, 2), 4: box(2, 1, 3, 2),
    }
    experiment = experiment_with_polygons(monkeypatch, polygons, {3, 4}, {0, 2})
    result, _ = generate_experiment_axial_map(experiment)
    open_polygons = {i: polygons[i] for i in (0, 1, 2)}
    assert experiment.open_spaces == {0, 2}
    assert_coverage(result, open_polygons)
    assert_connected(result)
    assert result.open_cells == 3
    axis = LineString([(0, 0.5), (3, 0.5)])
    assert any(LineString((line.start, line.end)).equals(axis)
               for line in result.candidate_lines)
    assert any(LineString((line.start, line.end)).equals(axis)
               for line in result.axial_map.lines)
    assert_maximal(result, unary_union(list(open_polygons.values())))


def test_unassigned_passage_connects_open_spaces(monkeypatch):
    polygons = {
        0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1),
        2: box(2, 0, 3, 1), 3: box(2, 1, 3, 2),
        4: box(0, 1, 1, 2),
    }
    experiment = experiment_with_polygons(monkeypatch, polygons, {4}, {0, 2, 3})
    result, _ = generate_experiment_axial_map(experiment)
    assert_coverage(result, {i: polygons[i] for i in (0, 1, 2, 3)})
    assert_connected(result)
    assert result.open_components == result.axial_components == 1
    assert any(1 in line.attributes["covered_cells"] for line in result.axial_map.lines)


def test_unassigned_cell_completes_circulation_ring(monkeypatch):
    polygons = cells({(x, y) for x in range(3) for y in range(3)})
    building = next(i for i, polygon in polygons.items() if polygon.equals(box(1, 1, 2, 2)))
    unassigned = next(i for i, polygon in polygons.items() if polygon.equals(box(1, 0, 2, 1)))
    paired = set(polygons) - {building, unassigned}
    experiment = experiment_with_polygons(monkeypatch, polygons, {building}, paired)
    result, _ = generate_experiment_axial_map(experiment)
    assert_coverage(result, {i: polygons[i] for i in set(polygons) - {building}})
    assert_connected(result)
    assert result.required_rings == result.preserved_rings == 1
    faces = polygonize(unary_union([LineString((line.start, line.end))
                                   for line in result.axial_map.lines]))
    assert any(face.covers(Point(1.5, 1.5)) for face in faces)
    assert unassigned not in experiment.open_spaces


def test_occupied_cell_still_blocks_candidates_through_unassigned_space(monkeypatch):
    polygons = {i: box(i, 0, i + 1, 1) for i in range(4)}
    experiment = experiment_with_polygons(monkeypatch, polygons, {2}, {0, 3})
    result, _ = generate_experiment_axial_map(experiment)
    assert_coverage(result, {i: polygons[i] for i in (0, 1, 3)})
    assert result.open_components == result.axial_components == 2
    assert all(not LineString((line.start, line.end)).relate_pattern(polygons[2], "T********")
               for line in result.candidate_lines)
    assert any(LineString((line.start, line.end)).equals(LineString([(0, .5), (2, .5)]))
               for line in result.candidate_lines)


def test_missing_unassigned_cell_geometry_is_reported(monkeypatch):
    polygons = {0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1)}
    experiment = experiment_with_polygons(monkeypatch, polygons, {1}, {0})
    experiment.grid.nodes.append(None)
    with pytest.raises(ValueError, match=r"Missing polygon geometry for cells: \[2\]"):
        generate_experiment_axial_map(experiment)


def test_unassigned_cells_are_rendered_as_traversable(monkeypatch):
    from matplotlib.colors import to_rgba
    polygons = {i: box(i, 0, i + 1, 1) for i in range(3)}
    experiment = experiment_with_polygons(monkeypatch, polygons, {2}, {0})
    result, _ = generate_experiment_axial_map(experiment)
    figure = fig_generated_axial_map(experiment, result, polygons)
    colors = [patch.get_facecolor() for patch in figure.axes[0].patches]
    assert to_rgba(UNASSIGNED_OPEN_COLOR) in colors
    assert to_rgba("white") in colors
    assert to_rgba("grey") in colors
    assert "traversable" in figure.axes[0].get_legend().get_texts()[0].get_text()


def test_default_voronoi_experiment_coverage_and_rings():
    experiment = run_experiment_pipeline(ExperimentPipeline(seed=42))
    result, polygons = generate_experiment_axial_map(experiment)
    open_polygons = {cell: polygon for cell, polygon in polygons.items()
                     if cell not in experiment.buildings}
    occupied_polygons = {cell: polygons[cell] for cell in experiment.buildings}
    assert len(experiment.open_spaces) == len(experiment.buildings) == 100
    assert len(open_polygons) == len(experiment.grid.nodes) - len(experiment.buildings)
    assert_coverage(result, open_polygons)
    assert_connected(result)
    assert result.required_rings == result.preserved_rings
    lines = [LineString((line.start, line.end)) for line in result.axial_map.lines]
    faces = list(polygonize(unary_union(lines)))
    accessible = unary_union(list(open_polygons.values()))
    occupied = unary_union([polygons[cell] for cell in experiment.buildings])
    assert_maximal(result, accessible.difference(occupied))
    parts = [accessible] if accessible.geom_type == "Polygon" else accessible.geoms
    obstacles = [
        Polygon(ring).intersection(occupied).representative_point()
        for part in parts for ring in part.interiors
        if Polygon(ring).intersection(occupied).area > 1e-12
    ]
    assert len(obstacles) == result.required_rings
    assert all(any(face.covers(point) for face in faces) for point in obstacles)
    figure = fig_generated_axial_map(experiment, result, polygons)
    assert len(figure.axes[0].lines) == len(result.axial_map.lines)
    diagnostic = fig_generated_axial_map(experiment, result, polygons, show_candidates=True)
    assert len(diagnostic.axes[0].collections[0].get_segments()) == result.candidates
    assert len(result.candidate_lines) == result.candidates
    from voronoi_app.axial_diagnostics import audit_axial_candidates
    audit = audit_axial_candidates(open_polygons, occupied_polygons, result)
    assert all(pair.status in ("present", "indeterminate clipping") for pair in audit.pairs)
    assert {frozenset((pair.start, pair.end)) for pair in audit.pairs
            if pair.status == "indeterminate clipping"} == {
                frozenset((start, end)) for start, end, _ in result.ambiguous_pairs
            }
    assert any(line.attributes["sources"] == ["centroid"] for line in result.candidate_lines)
