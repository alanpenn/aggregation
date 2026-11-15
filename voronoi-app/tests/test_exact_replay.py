"""Replay the preserved exact Y-settlement certifications without regenerating candidates."""

import gzip
import hashlib
import json
import math
from pathlib import Path

import networkx as nx
import pytest
from shapely.ops import unary_union

from voronoi_app.angular import (
    LineClearance, _angular_attachment_depths_by_origin, _exact_point,
    angular_attachment_depths, topological_sample_depths,
)
from voronoi_app.angular_optimisation import _obstacles
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import (
    _attach_selected_samples, candidate_graph, closed_routes, region_coverage,
)
from voronoi_app.exact_enumeration import exact_pool_from_dict


FIXTURES = Path(__file__).parent / "fixtures" / "exact_y"
MAPS = ("reference23", "reference24", "best23", "best24", "best25", "best_all_excluded")


def _json_key(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _identity(candidate):
    def point(p):
        return [str(value) for value in p]

    def support_identity(support):
        endpoints = [
            [point(p), sorted([r.building_id, r.vertex_index] for r in references)]
            for p, references in ((support.start, support.start_vertices),
                                  (support.end, support.end_vertices))
        ]
        return [support.source, sorted(endpoints, key=_json_key)]

    endpoints = sorted([point(candidate.start), point(candidate.end)], key=_json_key)
    supports = sorted((support_identity(s) for s in candidate.provenance), key=_json_key)
    return [endpoints, supports]


def _identity_hash(candidates):
    identities = sorted((_identity(line) for line in candidates), key=_json_key)
    return hashlib.sha256(_json_key(identities).encode("ascii")).hexdigest()


@pytest.fixture(scope="module")
def replay():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    artifacts = {}
    for name, entry in manifest["files"].items():
        path = FIXTURES / entry["fixture"]
        raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        assert len(raw) == entry["bytes"]
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        artifacts[name] = json.loads(raw)

    reference = artifacts["exact-y-24-forced-reference.json"]
    reference23 = artifacts["exact-y-23-pareto-reference.json"]
    results = artifacts["exact-y-pareto-results.json"]
    assert results["settlement_sha256"] == manifest["files"][reference["settlement_source"]]["sha256"]
    assert results["pool_sha256"] == manifest["files"][reference["pool_source"]]["sha256"]
    assert results["baseline_sha256"] == manifest["files"]["exact-y-24-forced-reference.json"]["sha256"]
    assert results["reference23_sha256"] == manifest["files"]["exact-y-23-pareto-reference.json"]["sha256"]
    assert reference23["samples"] == reference["samples"]
    assert reference["selected"] == results["certifications"]["reference24"]["selected"]
    assert reference23["map"]["selected"] == results["certifications"]["reference23"]["selected"]
    for source, name in ((reference, "reference24"), (reference23["map"], "reference23")):
        assert source["metrics"] == pytest.approx(
            results["certifications"][name]["metrics"], abs=1e-10, rel=0,
        )

    opened, occupied, _, _, _ = load_axial_snapshot(artifacts[reference["settlement_source"]])
    union = unary_union(list(occupied.values()))
    domain = unary_union(list(opened.values())).difference(union)
    clearance = LineClearance(domain, union, original_obstacles=occupied.values())
    regions = convex_regions(domain)
    tolerance = math.hypot(domain.bounds[2] - domain.bounds[0],
                           domain.bounds[3] - domain.bounds[1]) * 1e-9
    witnesses, _ = _obstacles(domain, union, tolerance)
    obstacles = [(witness.x, witness.y) for witness in witnesses]
    pool = exact_pool_from_dict(artifacts[reference["pool_source"]])
    assert len(pool.candidates) == 1651
    assert len(regions) == 267
    assert len(obstacles) == 3
    assert len(reference["samples"]) == 36
    assert _identity_hash(pool.candidates) == manifest["canonical_identity"]["pool_sha256"]

    vertices = {building: [_exact_point(point) for point in list(polygon.exterior.coords)[:-1]]
                for building, polygon in occupied.items()}
    for candidate in pool.candidates:
        for support in candidate.provenance:
            for point, refs in ((support.start, support.start_vertices),
                                (support.end, support.end_vertices)):
                for ref in refs:
                    assert vertices[ref.building_id][ref.vertex_index] == point

    selected_ids = sorted({identifier for name in MAPS
                           for identifier in results["certifications"][name]["selected"]})
    selected = [pool.candidates[identifier] for identifier in selected_ids]
    assert all(clearance.permits_exact(line.start, line.end) for line in selected)
    coverage = dict(zip(selected_ids, region_coverage(selected, regions)))
    assert all(coverage[identifier] == pool.covers[identifier] for identifier in selected_ids)
    return manifest, reference, results, pool, regions, clearance, obstacles, coverage


@pytest.mark.parametrize("name", MAPS)
def test_certified_exact_map_replay(replay, name):
    manifest, reference, results, pool, regions, clearance, obstacles, coverage = replay
    saved = results["certifications"][name]
    ids = saved["selected"]
    assert len(ids) == len(set(ids)) == saved["metrics"]["count"]
    lines = [pool.candidates[identifier] for identifier in ids]
    assert [line.line_id for line in lines] == ids
    assert _identity_hash(lines) == manifest["canonical_identity"]["maps_sha256"][name]
    assert set().union(*(coverage[identifier] for identifier in ids)) == set(regions)
    assert nx.is_connected(candidate_graph(lines))
    assert closed_routes(lines, obstacles) == {0, 1, 2}

    attachments = _attach_selected_samples(reference["samples"], lines, clearance, {})
    per_pair = angular_attachment_depths(lines, attachments)
    per_origin = _angular_attachment_depths_by_origin(lines, attachments)
    topological = topological_sample_depths(lines, attachments)
    assert len(per_pair) == len(per_origin) == len(topological) == 36 * 35
    assert per_origin.keys() == per_pair.keys() == topological.keys()
    assert per_origin == pytest.approx(per_pair, abs=1e-12, rel=0)
    calculated = {
        "length": sum(line.length for line in lines),
        "angular": sum(per_pair.values()) / len(per_pair),
        "topological": sum(topological.values()) / len(topological),
    }
    for metric, value in calculated.items():
        assert value == pytest.approx(saved["metrics"][metric], abs=1e-10, rel=0)
