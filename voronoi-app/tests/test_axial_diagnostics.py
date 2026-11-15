import json
from types import SimpleNamespace

import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from voronoi_app.axial import AxialLine
from voronoi_app.axial_diagnostics import (
    BuildingCorner, _independent_interval, audit_axial_candidates, cached_axial_audit, is_occluding,
)
from voronoi_app.axial_generator import _maximal_interval, _occludes, generate_axial_map
from voronoi_app.axial_snapshot import make_axial_snapshot, rerun_axial_snapshot, save_axial_snapshot
from voronoi_app.render import fig_axial_diagnostics, fig_unresolved_tangents


def audit_for(buildings, candidates=(), cells=None):
    occupied = {i: polygon for i, polygon in enumerate(buildings)}
    if cells is None:
        cells = {0: box(0, 0, 10, 8).difference(unary_union(buildings))}
    generated = SimpleNamespace(candidate_lines=[
        AxialLine(i, tuple(line.coords[0]), tuple(line.coords[-1]))
        for i, line in enumerate(candidates)
    ])
    return audit_axial_candidates(cells, occupied, generated)


def find_pair(audit, start, end):
    return next(pair for pair in audit.pairs
                if {pair.start, pair.end} == {start, end})


def test_facing_convex_corners_are_mutual_tangent():
    buildings = [box(1, 1, 2, 2), box(4, 1, 5, 2)]
    audit = audit_for(buildings, [LineString([(0, 2), (10, 2)])])
    pair = find_pair(audit, (2, 2), (4, 2))
    assert audit.convex_building_vertices == 8
    assert pair.status == "present"
    assert pair.maximal.equals(LineString([(0, 2), (10, 2)]))
    assert audit.source_indices["occluding"] == {0}


def test_visible_corners_are_not_necessarily_occluding():
    first = BuildingCorner((2, 2), (1, 2), (2, 1))
    second = BuildingCorner((4, 3), (4, 4), (5, 3))
    assert not is_occluding(first, second.point, 1e-9)
    assert not is_occluding(second, first.point, 1e-9)
    assert not _occludes(first.previous, first.point, first.following, second.point, 1e-9)
    assert not _occludes(second.previous, second.point, second.following, first.point, 1e-9)
    audit = audit_for([box(1, 1, 2, 2), box(4, 3, 5, 4)])
    assert all({pair.start, pair.end} != {(2, 2), (4, 3)} for pair in audit.pairs)
    assert audit.non_occluding_pairs > 0


def test_same_nonconvex_building_corners_across_recess():
    building = Polygon([(1, 1), (5, 1), (5, 5), (4, 5),
                        (4, 2), (2, 2), (2, 5), (1, 5)])
    audit = audit_for([building])
    pair = find_pair(audit, (2, 5), (4, 5))
    assert pair.status == "missing"
    assert pair.maximal.equals(LineString([(0, 5), (10, 5)]))
    cells = {0: box(0, 0, 10, 8).difference(building)}
    generated = generate_axial_map(cells, {1: building})
    audit = audit_axial_candidates(cells, {1: building}, generated)
    assert find_pair(audit, (2, 5), (4, 5)).status == "present"


def test_intermediate_tangential_building_corner_does_not_truncate():
    buildings = [box(1, 1, 2, 2), Polygon([(4, 1), (6, 1), (5, 2)]),
                 box(8, 1, 9, 2)]
    audit = audit_for(buildings)
    pair = find_pair(audit, (2, 2), (8, 2))
    assert pair.maximal.equals(LineString([(0, 2), (10, 2)]))
    assert pair.generator_interval.equals(pair.maximal)


def test_independent_extension_crosses_multiple_open_cells():
    cells = {i: box(i * 2, 0, (i + 1) * 2, 2) for i in range(5)}
    accessible = unary_union(list(cells.values()))
    line = _independent_interval(accessible, (2, 1), (8, 1), 1e-9)
    assert line.equals(LineString([(0, 1), (10, 1)]))
    assert sum(line.relate_pattern(cell, "T********") for cell in cells.values()) == 5


def test_sub_tolerance_obstacle_is_not_bridged():
    accessible = box(0, 0, 10, 2).difference(box(5, 0, 5.00000001, 2))
    assert _maximal_interval(accessible, (1, 1), (9, 1), 1e-6) is None
    issues = []
    line = _maximal_interval(accessible, (1, 1), (4, 1), 1e-6, ambiguities=issues)
    assert line.hausdorff_distance(LineString([(0, 1), (5, 1)])) < 1e-8
    assert issues


def test_blocked_pairs_are_rejected_not_silently_reported_missing():
    audit = audit_for([box(1, 1, 2, 3), box(4, 0.5, 5, 3.5), box(7, 1, 8, 3)])
    assert audit.blocked_pairs > 0
    assert audit.possible_pairs == audit.coincident_pairs + audit.blocked_pairs + audit.visible_pairs
    assert audit.visible_pairs == audit.non_occluding_pairs + len(audit.pairs)


def test_audit_and_plot_accept_real_generator_output():
    buildings = {1: box(2, 1, 3, 2), 2: box(5, 1, 6, 2)}
    cells = {0: box(0, 0, 8, 4).difference(unary_union(list(buildings.values())))}
    generated = generate_axial_map(cells, buildings)
    audit = audit_axial_candidates(cells, buildings, generated)
    assert find_pair(audit, (3, 2), (5, 2)).status == "present"
    assert sum(counts["added"] for counts in audit.stage_counts.values()) == generated.candidates
    assert sum(counts["unmatched"] for counts in audit.stage_counts.values()) == 0
    result = SimpleNamespace(open_spaces=[0], buildings=[1, 2],
                             config=SimpleNamespace(canvas_size=8))
    figure = fig_axial_diagnostics(result, generated, {**cells, **buildings}, audit)
    assert figure.axes[0].collections
    assert figure.axes[0].get_legend() is not None


def test_snapshot_round_trip_preserves_unresolved_geometry_and_reruns_without_generation(
    tmp_path, monkeypatch
):
    buildings = {1: box(2, 1, 3, 2), 2: box(5, 1, 6, 2)}
    cells = {0: box(0, 0, 8, 4).difference(unary_union(list(buildings.values())))}
    generated = generate_axial_map(cells, buildings)
    start, end = (3.0, 2.0), (5.0, 2.0)
    generated.ambiguous_pairs.append((start, end, "uncovered gap before interval within tolerance"))
    audit = audit_axial_candidates(cells, buildings, generated)
    config = {"seed": 42, "terrain_provider": "flat", "canvas_size": 8}
    snapshot = make_axial_snapshot(config, cells, buildings, generated, audit, {0})
    pair = next(item for item in snapshot["audit"]["unresolved"]
                if {tuple(item["start"]), tuple(item["end"])} == {start, end})
    assert pair["exact_visible"] and pair["buffered_visible"]
    assert not pair["crosses_occupied_interior"]
    assert pair["generator_interval"] and pair["independent_interval"]
    assert pair["reason"] == "uncovered gap before interval within tolerance"

    path = save_axial_snapshot(snapshot, tmp_path)
    data = json.loads(path.read_text())
    monkeypatch.setattr("voronoi_app.axial_generator.generate_axial_map",
                        lambda *args, **kwargs: pytest.fail("generator must not run"))
    restored_cells, restored_buildings, restored, restored_config, paired, rerun = (
        rerun_axial_snapshot(data)
    )
    assert restored_config == config and paired == {0}
    assert restored_cells[0].equals_exact(cells[0], 0)
    assert all(restored_buildings[i].equals_exact(polygon, 0)
               for i, polygon in buildings.items())
    assert restored.candidate_lines == generated.candidate_lines
    assert find_pair(rerun, start, end).status == "indeterminate clipping"
    figure = fig_unresolved_tangents(restored_cells, restored_buildings, rerun)
    segments = [LineString(segment)
                for collection in figure.axes[0].collections
                if hasattr(collection, "get_segments")
                for segment in collection.get_segments()]
    assert any(line.equals(LineString([start, end])) for line in segments)
    assert any(line.equals(find_pair(rerun, start, end).maximal) for line in segments)
    assert len(figure.axes[0].patches) == len(cells) + len(buildings)


def test_invalid_snapshot_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        rerun_axial_snapshot({"version": 2})
    with pytest.raises(ValueError, match="Invalid axial diagnostic snapshot"):
        rerun_axial_snapshot({"version": 1})


def test_snapshot_preserves_experimental_coverage_model():
    cells = {0: box(0, 0, 2, 2)}
    generated = generate_axial_map(cells, {}, coverage_model="convex")
    audit = audit_axial_candidates(cells, {}, generated)
    snapshot = make_axial_snapshot({}, cells, {}, generated, audit, {0})
    assert snapshot["axial_coverage_model"] == "convex"
    assert rerun_axial_snapshot(snapshot)[2].coverage_model == "convex"


def test_audit_progress_reports_phases_and_final_classifications(monkeypatch):
    buildings = {1: box(2, 1, 3, 2), 2: box(5, 1, 6, 2)}
    cells = {0: box(0, 0, 8, 4).difference(unary_union(list(buildings.values())))}
    generated = generate_axial_map(cells, buildings)
    baseline = audit_axial_candidates(cells, buildings, generated)
    ticks = iter(range(10000))
    monkeypatch.setattr("voronoi_app.axial_diagnostics.monotonic", lambda: next(ticks))
    updates = []
    audit = audit_axial_candidates(cells, buildings, generated, progress=updates.append)

    assert [pair.status for pair in audit.pairs] == [pair.status for pair in baseline.pairs]
    assert audit.stage_counts == baseline.stage_counts
    assert {"Replaying corner pairs", "Classifying corner pairs"} <= {
        update.phase for update in updates
    }
    final = updates[-1]
    assert final.examined == final.total == audit.possible_pairs
    assert final.valid == sum(pair.status in ("present", "missing") for pair in audit.pairs)
    assert final.unresolved == sum(pair.status == "indeterminate clipping" for pair in audit.pairs)
    assert final.invalid == audit.coincident_pairs + audit.blocked_pairs + audit.non_occluding_pairs
    assert final.valid + final.invalid + final.unresolved == final.total
    assert final.elapsed > 0 and final.remaining == 0
    assert len(updates) < audit.possible_pairs


def test_audit_cache_uses_geometry_candidates_and_ambiguities(monkeypatch):
    calls = []

    def fake_audit(open_polygons, occupied_polygons, generated, *, progress=None):
        calls.append((open_polygons, occupied_polygons, generated, progress))
        return object()

    monkeypatch.setattr("voronoi_app.axial_diagnostics.audit_axial_candidates", fake_audit)
    cells = {0: box(0, 0, 10, 10)}
    buildings = {1: box(1, 1, 2, 2)}
    generated = SimpleNamespace(
        candidate_lines=[AxialLine(0, (0, 0), (10, 10))], ambiguous_pairs=[],
    )
    cache = {}
    first, hit = cached_axial_audit(cells, buildings, generated, cache)
    assert not hit
    result, hit = cached_axial_audit(
        {0: box(0, 0, 10, 10)}, {1: box(1, 1, 2, 2)},
        SimpleNamespace(candidate_lines=[AxialLine(0, (0, 0), (10, 10))],
                        ambiguous_pairs=[]),
        cache,
    )
    assert hit and result is first and len(calls) == 1

    changed = [
        ({0: box(0, 0, 9, 10)}, buildings, generated),
        (cells, {1: box(1, 1, 3, 2)}, generated),
        (cells, buildings, SimpleNamespace(
            candidate_lines=[AxialLine(0, (0, 0), (9, 10))], ambiguous_pairs=[])),
        (cells, buildings, SimpleNamespace(
            candidate_lines=generated.candidate_lines,
            ambiguous_pairs=[((1, 1), (2, 2), "clipping ambiguity")])),
    ]
    for changed_cells, changed_buildings, changed_generated in changed:
        cache.clear()
        _, hit = cached_axial_audit(cells, buildings, generated, cache)
        assert not hit
        _, hit = cached_axial_audit(cells, buildings, generated, cache)
        assert hit
        _, hit = cached_axial_audit(changed_cells, changed_buildings, changed_generated, cache)
        assert not hit
    assert len(calls) == 9

    cache.clear()
    cached_axial_audit(cells, buildings, generated, cache)
    monkeypatch.setattr("voronoi_app.axial_diagnostics.is_occluding",
                        lambda corner, other, tolerance: False)
    _, hit = cached_axial_audit(cells, buildings, generated, cache)
    assert not hit and len(calls) == 11


def test_audit_progress_updates_periodically_in_long_pair_pass(monkeypatch):
    buildings = {
        i: box(2 + (i % 4) * 4, 2 + (i // 4) * 4,
               3 + (i % 4) * 4, 3 + (i // 4) * 4)
        for i in range(12)
    }
    cells = {0: box(0, 0, 20, 16).difference(unary_union(list(buildings.values())))}
    generated = SimpleNamespace(candidate_lines=[], ambiguous_pairs=[])
    ticks = iter(range(10000))
    monkeypatch.setattr("voronoi_app.axial_diagnostics.monotonic", lambda: next(ticks))
    updates = []
    audit = audit_axial_candidates(cells, buildings, generated, progress=updates.append)
    classification = [update for update in updates if update.phase == "Classifying corner pairs"]
    assert any(0 < update.examined < audit.possible_pairs for update in classification)
    assert all(update.valid + update.invalid + update.unresolved == update.examined
               for update in classification)
    assert len(updates) < audit.possible_pairs // 10


def test_empty_audit_reports_complete_progress():
    updates = []
    audit = audit_axial_candidates(
        {0: box(0, 0, 2, 2)}, {},
        SimpleNamespace(candidate_lines=[], ambiguous_pairs=[]),
        progress=updates.append,
    )
    assert audit.possible_pairs == 0
    assert updates[-1].phase == "Classifying corner pairs"
    assert updates[-1].examined == updates[-1].total == 0
    assert updates[-1].remaining == 0
