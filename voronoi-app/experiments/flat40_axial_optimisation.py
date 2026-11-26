"""All intersecting-pair controls, certified routing, and Flat 40 frame tests."""
import argparse
from collections import Counter
from fractions import Fraction
from itertools import combinations
from math import atan2, degrees, sqrt
from pathlib import Path
from statistics import mean
from types import SimpleNamespace

import networkx as nx
from scipy.stats import fisher_exact
from shapely import from_wkb

from experiments.cross_terrain_axial_routes import evaluate_active_union
from experiments.cross_terrain_axial import DEST
from experiments.near_collinear_consolidation import (
    certificate, continuation, dot, point_text, verified_study,
)
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _direction, _exact_point
from voronoi_app.batch_methods import _settlement
from voronoi_app.batch_store import encode
from voronoi_app.exact_axial import candidate_graph, region_coverage
from voronoi_app.experimental_circulation_topology import evaluate_circulation_lines
from voronoi_app.research_data import sha256_file


def verified_previous(path, study, ch, d, provenance):
    prior = read(path)
    historical = prior["provenance"]
    if (historical["lineage"] != study.source
            or historical["verified_inputs"] != provenance["verified_inputs"]
            or historical["manifest_sha256"] != provenance["manifest_sha256"]
            or historical["experiment_sha256"] != sha256_file(Path(__file__).with_name("near_collinear_consolidation.py"))
            or prior["reference_CH"]["ids"] != ch or prior["reference_D"]["ids"] != d):
        raise ValueError("Previous experiment does not match verified Flat 40 lineage.")
    accepted = prior["scans"][0]["accepted"]
    if {(tuple(row["removed"]), row["replacement"]) for row in accepted} != {
        ((1435, 1509), 323), ((1435, 1509), 1365), ((1435, 1509), 1436)
    }:
        raise ValueError("Unexpected archived exchange inventory.")
    maps = {}
    for row in accepted:
        replacement = row["replacement"]
        ids = (set(ch) - set(row["removed"])) | {replacement}
        if sorted(ids) != row["certificate"]["ids"] or certificate(study, ids) != row["certificate"]:
            raise ValueError(f"Archived exchange {replacement} failed independent replay.")
        maps[f"C-H+{replacement}"] = sorted(ids)
    return maps


def all_pairs(study, ch):
    selected = set(ch)
    inventory = set(range(len(study.lines))) - selected
    records = []
    for a, b in combinations(sorted(selected), 2):
        geom = continuation(study.lines[a], study.lines[b])
        if bool(geom) != (b in study.neighbors[a]):
            raise ValueError(f"Frozen graph and exact junction differ for {a}, {b}.")
        if geom is None:
            continue
        if "delta" not in geom:
            raise ValueError("Expected the frozen Flat 40 noncollinear control.")
        rest = selected - {a, b}
        region_gaps = {i: g for i, g in study.regions.items() if rest.isdisjoint(g)}
        door_gaps = {i: g for i, g in enumerate(study.doors) if rest.isdisjoint(g)}
        options = inventory.intersection(*region_gaps.values())
        reachable = options.intersection(*door_gaps.values())
        counts = Counter(missing_region=len(inventory)-len(options), missing_doorway=len(options)-len(reachable))
        trials = []
        for i in sorted(reachable):
            ids = rest | {i}
            trial = {"replacement": i}
            if not study.clear(i):
                status = "clearance"
            elif not study.connected(ids):
                status = "connectivity"
            else:
                rank = study.winding.rank(ids)
                trial["dynamic_rank"] = rank
                if rank is not None and rank < study.winding.required:
                    status = "winding_rank_deficit"
                else:
                    try:
                        trial["certificate"] = certificate(study, ids)
                    except ValueError:
                        status = "independent_failure"
                    else:
                        status = "accepted"
            trial["status"] = status
            counts[status] += 1
            trials.append(trial)
        records.append(geom | {"pair": [a, b], "uncovered_regions": sorted(region_gaps),
                               "uncovered_doorways": sorted(door_gaps), "counts": dict(counts),
                               "incidence_survivors": trials})
    if len(records) != 98 or any(sum(row["counts"].values()) != 1500 for row in records):
        raise ValueError("Incomplete all-pair search.")
    return records


def pair_summary(records):
    def group(rows):
        return {"pairs": len(rows), "successful_pairs": sum(row["counts"].get("accepted", 0) > 0 for row in rows),
                "accepted_replacements": sum(row["counts"].get("accepted", 0) for row in rows)}

    near = group([r for r in records if r["delta"] <= 30])
    other = group([r for r in records if r["delta"] > 30])
    table = [[x["successful_pairs"], x["pairs"]-x["successful_pairs"]] for x in (near, other)]
    fisher = fisher_exact(table)
    buckets = {}
    low = -1
    for high in (10, 15, 20, 30, 45, 60, 90, 180):
        buckets[f"({low}, {high}]"] = group([r for r in records if low < r["delta"] <= high])
        low = high
    return {"near": near, "other": other, "buckets": buckets, "fisher_two_sided_descriptive": float(fisher.pvalue),
            "gate_counts": dict(sum((Counter(r["counts"]) for r in records), Counter()))}


def movement(study, maps, archived_movement):
    # Use the existing certified routing definitions and fixed archived pair ordering.
    methods = {name: {"maps": {"final": ids}} for name, ids in maps.items()}
    output = evaluate_active_union(study.inputs, study.lines, study.clearance, study.reference, methods)
    baseline = output["methods"]["C-H"]["final"]
    archived = study.inputs["analysis"]["pairs"]
    output["archived_route_replay_max_absolute_error"] = {}
    for name in ("C-H", "D"):
        result = output["methods"][name]["final"]
        reference = archived_movement["methods"][name]
        output["archived_route_replay_max_absolute_error"][name] = {
            mode: max(abs(v-r) for v, r in zip(result[f"{mode}_routes"],
                                               reference[f"{mode}_routes"], strict=True))
            for mode in ("angular", "metric")}
    for method in output["methods"].values():
        result = method["final"]
        if not result["valid"]:
            raise ValueError("Unreachable archived doorway pair.")
        result["paired_vs_CH"] = {}
        for mode in ("angular", "metric"):
            delta = [v-b for v, b in zip(result[f"{mode}_routes"], baseline[f"{mode}_routes"], strict=True)]
            pos = max(range(len(delta)), key=lambda i: delta[i])
            neg = min(range(len(delta)), key=lambda i: delta[i])
            tolerance = 1e-9
            result["paired_vs_CH"][mode] = {
                "mean_signed_change": mean(delta), "mean_absolute_change": mean(map(abs, delta)),
                "improved": sum(x < -tolerance for x in delta),
                "worsened": sum(x > tolerance for x in delta),
                "unchanged": sum(abs(x) <= tolerance for x in delta),
                "worst_increase": [archived[pos], delta[pos]], "largest_decrease": [archived[neg], delta[neg]],
            }
    return output


CENTRE = (Fraction(50), Fraction(50))
FRAMES = {"archived": ((1, 0), 1, 50), "inset_5": ((1, 0), 1, 45),
          "rotate_ccw_22.62": ((12, 5), 13, 50), "rotate_cw_22.62": ((12, -5), 13, 50)}


def limits(start, end, axes, norm, half_width, *, finite):
    direction = _direction(start, end)
    axis_x, axis_y = axes
    low, high = (Fraction(0), Fraction(1)) if finite else (None, None)
    bound = half_width * norm
    for axis in (axes, (-axis_y, axis_x)):
        p = dot(_direction(CENTRE, start), axis)
        d = dot(direction, axis)
        if not d:
            if abs(p) > bound:
                return None
            continue
        a, b = sorted([(Fraction(-bound)-p)/d, (Fraction(bound)-p)/d])
        low = a if low is None else max(low, a)
        high = b if high is None else min(high, b)
    return (low, high) if low < high else None


def endpoints(start, end, interval):
    direction = _direction(start, end)
    return tuple(tuple(a+t*d for a, d in zip(start, direction, strict=True)) for t in interval)


def boundary(study, maps, accepted):
    polygons, _, _ = _settlement(study.inputs)
    bounds = tuple(_exact_point((min(p.bounds[j] for p in polygons.values()) for j in (0,1)))) + tuple(
        _exact_point((max(p.bounds[j] for p in polygons.values()) for j in (2,3))))
    if bounds != (0, 0, 100, 100):
        raise ValueError("Unexpected frozen settlement frame.")
    regions = {int(i): from_wkb(wkb) for i, wkb in study.inputs["candidates"]["regions_wkb"].items()}
    original = maps["C-H"]
    focus = sorted({i for row in accepted for i in row["pair"]} |
                   {entry["replacement"] for row in accepted for entry in row["incidence_survivors"]
                    if entry["status"] == "accepted"})

    def sides(point):
        return [name for name, axis, val in (("west",0,0),("east",0,100),("south",1,0),("north",1,100))
                if point[axis] == val]

    result = {"archive_bounds": list(map(str, bounds)), "focus_lines": {}, "fixed_geometry_stress": {}}
    for i in focus:
        line = study.lines[i]
        direction = _direction(line.start, line.end)
        length = sqrt(float(dot(direction, direction)))
        tests = {}
        for name, frame in FRAMES.items():
            raw = limits(line.start, line.end, *frame, finite=False)
            if raw:
                low, high = raw
                # Freeze any archived endpoint that was not capped by the old frame.
                low = low if sides(line.start) else max(Fraction(0), low)
                high = high if sides(line.end) else min(Fraction(1), high)
                tests[name] = {"held_non_frame_endpoint_length": max(0., float(high-low)*length),
                               "extends_outside_archived_interval": low < 0 or high > 1}
        result["focus_lines"][str(i)] = {"endpoints": [point_text(line.start), point_text(line.end)],
            "frame_sides": [sides(line.start), sides(line.end)],
            "direction_degrees_mod_180": degrees(atan2(float(direction[1]),float(direction[0]))) % 180,
            "counterfactual_lengths": tests}
    for name, frame in FRAMES.items():
        comparisons = {}
        for method, ids in maps.items():
            lines = []
            for i in ids:
                line = study.lines[i]
                interval = limits(line.start, line.end, *frame, finite=True)
                if interval:
                    a,b = endpoints(line.start, line.end, interval)
                    lines.append(SimpleNamespace(line_id=i, start=a, end=b))
            covers = region_coverage(lines, regions)
            covered = set().union(*covers)
            region_doors = study.inputs["analysis"]["incidence"]["doorway_regions"]
            graph = candidate_graph(lines)
            independent = evaluate_circulation_lines(study.polygons, lines, study.geometry.blocks,
                                                     study.geometry.domain_clearance)
            clipped = [line.line_id for line in lines if (line.start,line.end) !=
                       (study.lines[line.line_id].start,study.lines[line.line_id].end)]
            comparisons[method] = {"removed": sorted(set(ids)-{l.line_id for l in lines}), "clipped": clipped,
                "covered_regions": len(covered), "lost_region_ids": sorted(set(regions)-covered),
                "doorway_region_incidence": sum(bool(covered.intersection(g)) for g in region_doors),
                "components": nx.number_connected_components(graph), "winding": independent}
        result["fixed_geometry_stress"][name] = comparisons
    return result


def publish(path, data):
    with path.open("xb") as stream:
        stream.write(encode(data))


def run(manifest, previous, output):
    study, ch, d, provenance = verified_study(manifest)
    exchanges = verified_previous(previous, study, ch, d, provenance)
    movement_path = DEST / "flat-40" / "movement.json"
    row = "strict-generalisation/cross-terrain-constructive-1/flat-40/movement.json"
    if sha256_file(movement_path) != read(manifest)[row]:
        raise ValueError("Archived movement checksum differs from the migration manifest.")
    archived_movement = read(movement_path)
    if archived_movement["source"] != study.source:
        raise ValueError("Archived movement and structural lineage disagree.")
    provenance["verified_inputs"][row] = sha256_file(movement_path)
    maps = {"C-H": ch, **exchanges, "D": d}
    output.mkdir(parents=True, exist_ok=False)
    rows = all_pairs(study, ch)
    summary = pair_summary(rows)
    accepted = [row for row in rows if row["counts"].get("accepted")]
    publish(output/"pairs.json", {"rows": rows, "summary": summary,
        "provenance": provenance | {"prior_experiment_sha256": sha256_file(previous),
                                    "extension_sha256": sha256_file(__file__)},
        "maps": maps})
    print("Pair search complete", summary, flush=True)
    publish(output/"boundary.json", boundary(study, maps, accepted))
    print("Boundary tests complete", flush=True)
    publish(output/"movement.json", movement(study, maps, archived_movement))
    print("Movement comparison complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("manifest", "previous", "output"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    run(args.manifest, args.previous, args.output)
