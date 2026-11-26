"""Exhaustive Flat 40 two-for-one search on archived C-H selections."""
import argparse
from collections import Counter
from fractions import Fraction
from itertools import combinations, product
from math import atan2, degrees
from pathlib import Path
from subprocess import check_output

import networkx as nx

from experiments.constructive_axial import ROOT as D_ARCHIVE
from experiments.controlled_preselection import metrics
from experiments.cross_terrain_axial import CaseStudy, DEST, origin
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _cross, _direction, _intersections
from voronoi_app.batch_store import BatchStore, encode
from voronoi_app.exact_axial import candidate_graph
from voronoi_app.research_data import data_root, sha256_file

CASE = "flat-40"
THRESHOLDS = (10, 15, 20, 30)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b, strict=True))


def point_text(p):
    return list(map(str, p))


def angle(a, b):
    return degrees(atan2(float(abs(_cross(a, b))), float(dot(a, b))))


def continuation(left, right):
    points = sorted(_intersections(left.start, left.end, right.start, right.end))
    if not points:
        return None
    if len(points) > 1:
        return {"kind": "collinear_overlap", "interval": [point_text(p) for p in points]}
    p, = points
    # Each ray points from the actual junction to an endpoint. If the
    # junction is itself an endpoint, that arm does not exist.
    arms = [sorted({x for x in (line.start, line.end) if x != p}) for line in (left, right)]
    choices = [(angle(_direction(p, a), _direction(p, b)), a, b)
               for a, b in product(*arms)]
    if not choices:
        return None
    theta, a, b = max(choices)
    endpoints = [p in (line.start, line.end) for line in (left, right)]
    collinear = not _cross(_direction(left.start, left.end), _direction(right.start, right.end))
    return {"kind": "collinear_touch" if collinear else "endpoint" if any(endpoints) else "transverse_interior",
            "junction": point_text(p), "endpoint_flags": endpoints,
            "theta": theta, "delta": 180-theta,
            "arms": [point_text(a), point_text(b)]}


def verified_study(manifest_path):
    root = data_root()
    manifest = read(manifest_path)
    droot = D_ARCHIVE / CASE
    paths = [droot / f for f in ("source.json", "geometry.json", "D.json")]
    paths += [D_ARCHIVE / "export-checksums.json", DEST / "inputs.json",
              DEST / CASE / "structural.json", DEST / CASE / "C-H.json"]
    journal_path = origin(CASE) / "cases" / f"{CASE}.json"
    historic = DEST.parent / "unrestricted-structural-reduction-1"
    paths += [journal_path, origin(CASE) / "route-references" / f"{CASE}.json",
              historic / "inputs.json", historic / "sheaf.json"]
    # Authenticate the pointers before following any record IDs.
    verified = {}

    def verify(path):
        relative = path.relative_to(root).as_posix()
        checksum = sha256_file(path)
        if manifest.get(relative) != checksum:
            raise ValueError(f"Missing or mismatched migration digest: {relative}")
        verified[relative] = checksum

    for path in paths:
        verify(path)
    journal = read(journal_path)
    cohort = read(DEST / "inputs.json")[CASE]
    if cohort["journal_sha256"] != sha256_file(journal_path) or cohort["records"] != journal["stages"]:
        raise ValueError("Benchmark and source journal disagree.")
    for stage, entry in journal["stages"].items():
        directory = origin(CASE) / "records" / entry["record"]
        for name in ("record.json", "output.json"):
            verify(directory / name)
        record = read(directory / "record.json")
        if record.get("parent"):
            BatchStore(origin(CASE))._inputs(record["stage"], record["parent"]["id"])
    study = CaseStudy(CASE)
    structural = read(DEST / CASE / "structural.json")
    ch = read(DEST / CASE / "C-H.json")["ids"]
    d = read(droot / "D.json")["maps"]["exchanged"]
    observed = (len(study.lines), len(structural["complementary_raw"]),
                len(structural["complementary_repaired"]), len(ch), len(d),
                len(study.regions), len(study.doors), study.winding.required)
    if (observed != (1534, 628, 629, 34, 33, 292, 100, 24)
            or structural["source"] != study.source
            or read(historic / "inputs.json")["source"] != study.source
            or read(historic / "sheaf.json")["final_ids"] != ch
            or ch != structural["methods"]["C-H"]["ids"] or d != structural["methods"]["D"]["ids"]):
        raise ValueError(f"Archived reference inventories disagree: {observed}")
    if [line.line_id for line in study.lines] != list(range(len(study.lines))):
        raise ValueError("Candidate IDs are not canonical.")
    return study, ch, d, {"verified_inputs": verified, "manifest_sha256": sha256_file(manifest_path),
                          "lineage": study.source, "reference_counts": observed,
                          "experiment_sha256": sha256_file(__file__),
                          "git_head": check_output(["git", "rev-parse", "HEAD"], text=True).strip()}


def certificate(study, ids):
    order = sorted(ids)
    graph = candidate_graph([study.lines[i] for i in order])
    edges = {tuple(sorted((order[i], order[j]))) for i, j in graph.edges}
    if edges != {tuple(sorted(edge)) for edge in study.graph.subgraph(ids).edges}:
        raise RuntimeError("Recomputed exact selected intersections differ from the frozen graph.")
    if nx.number_connected_components(graph) != 1:
        raise ValueError("Selected lines are disconnected.")
    return {"ids": sorted(ids), "metrics": metrics(study, ids),
            "coverage": sum(not ids.isdisjoint(group) for group in study.regions.values()),
            "doorways": sum(not ids.isdisjoint(group) for group in study.doors),
            "components": 1, "winding": study.confirmed(frozenset(ids))}


def arm_geometry(row, line):
    direction = _direction(line.start, line.end)
    junction = tuple(Fraction(value) for value in row["junction"])
    angles, projected = [], []
    for end in row["arms"]:
        ray = _direction(junction, tuple(Fraction(value) for value in end))
        aligned_angle = angle(ray, direction)
        angles.append(min(aligned_angle, 180-aligned_angle))
        lo, hi = sorted(dot(_direction(junction, p), ray)/dot(ray, ray) for p in (line.start, line.end))
        projected.append(max(0, min(hi, 1)-max(lo, 0)))
    return angles, projected


def replacement_geometry(study, pair, row, replacement, retained):
    line = study.lines[replacement]
    angles, projected = arm_geometry(row, line)
    return {"arm_deviation_degrees": angles, "projected_arm_overlap_fractions": list(map(str, projected)),
            "replacement_length": line.length,
            "removed_lengths": [study.lines[i].length for i in pair],
            "longer_than_both": line.length > max(study.lines[i].length for i in pair),
            "aligned_with_both": max(angles) <= 30 + 1e-12,
            "overlaps_both_arm_projections": all(value > 0 for value in projected),
            "replacement_provenance": study.inputs["candidates"]["pool"]["candidates"][replacement]["provenance"],
            "lost_retained_contacts": sorted(((study.neighbors[pair[0]] | study.neighbors[pair[1]]) & retained)
                                             - study.neighbors[replacement]),
            "gained_retained_contacts": sorted((study.neighbors[replacement] & retained)
                                               - (study.neighbors[pair[0]] | study.neighbors[pair[1]]))}


def scan(study, current):
    rows, overlaps, valid = [], [], []
    disjoint = pair_count = 0
    for a, b in combinations(sorted(current), 2):
        row = continuation(study.lines[a], study.lines[b])
        if bool(row) != (b in study.neighbors[a]):
            raise ValueError(f"Exact intersection differs from the saved graph: {a}, {b}")
        if row is None:
            disjoint += 1
            continue
        row["pair"] = [a, b]
        if row["kind"] in {"collinear_overlap", "collinear_touch"}:
            overlaps.append(row)
            continue
        pair_count += 1
        if row["delta"] > 30 + 1e-12:
            continue
        remaining = current - {a, b}
        region_gaps = {i: group for i, group in study.regions.items() if remaining.isdisjoint(group)}
        door_gaps = {i: group for i, group in enumerate(study.doors) if remaining.isdisjoint(group)}
        row.update(required_regions=sorted(region_gaps), required_doorways=sorted(door_gaps))
        counts, finalists = Counter(), []
        motif = Counter()
        for i in range(len(study.lines)):
            if i in current:
                continue
            line = study.lines[i]
            good_match = False
            if line.length > max(study.length[a], study.length[b]):
                angles, overlap = arm_geometry(row, line)
                good_match = max(angles) <= 30 + 1e-12 and all(value > 0 for value in overlap)
            if any(i not in group for group in region_gaps.values()):
                counts["missing_region"] += 1
                motif["missing_region"] += good_match
                continue
            if any(i not in group for group in door_gaps.values()):
                counts["missing_doorway"] += 1
                motif["missing_doorway"] += good_match
                continue
            trial = remaining | {i}
            status = "clearance" if not study.clear(i) else "connectivity" if not study.connected(trial) else None
            if status:
                counts[status] += 1
                motif[status] += good_match
                finalists.append({"replacement": i, "status": status})
                continue
            dynamic = study.winding.rank(trial)
            if dynamic is not None and dynamic < study.winding.required:
                counts["winding_rank_deficit"] += 1
                motif["winding_rank_deficit"] += good_match
                finalists.append({"replacement": i, "status": "winding_rank_deficit",
                                  "dynamic_rank": dynamic})
                continue
            # An inconclusive dynamic check goes to the independent validator,
            # as does every possible success.
            try:
                cert = certificate(study, trial)
            except ValueError:
                cert = None
            status = "accepted" if cert is not None else "winding"
            counts[status] += 1
            motif[status] += good_match
            finalists.append({"replacement": i, "status": status, "dynamic_rank": dynamic})
            if cert is not None:
                valid.append({"removed": [a, b], "replacement": i, "delta": row["delta"],
                              "geometry": replacement_geometry(study, (a, b), row, i, remaining),
                              "certificate": cert})
        row.update(counts=dict(counts), longer_aligned_projected=dict(+motif), incidence_survivors=finalists)
        rows.append(row)
    return {"current": sorted(current), "nonintersecting_pairs": disjoint,
            "noncollinear_intersections": pair_count, "collinear": overlaps,
            "threshold_counts": {str(t): sum(row["delta"] <= t + 1e-12 for row in rows) for t in THRESHOLDS},
            "pairs": rows, "accepted": valid}


def run(manifest, output):
    study, ch, d, provenance = verified_study(manifest)
    ch_cert, d_cert = (certificate(study, set(ids)) for ids in (ch, d))
    pending = [frozenset(ch)]
    known = set(pending)
    scans = []
    for selection in pending:
        result = scan(study, selection)
        scans.append(result)
        print(f"{len(selection)} lines, {len(result['pairs'])} pairs, {len(result['accepted'])} accepted exchanges",
              flush=True)
        for accepted in result["accepted"]:
            next_selection = frozenset(accepted["certificate"]["ids"])
            if next_selection not in known:
                known.add(next_selection)
                pending.append(next_selection)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(encode({"provenance": provenance, "reference_CH": ch_cert, "reference_D": d_cert,
                             "scans": scans, "minimum_reachable": min(map(len, known))}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    run(options.manifest, options.output)
