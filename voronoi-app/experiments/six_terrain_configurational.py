"""Matched six-terrain configurational pilot on saved exact geometry."""

import argparse
from collections import Counter
import csv
from hashlib import sha256
import os
from pathlib import Path
import resource
import sys
from time import perf_counter

import networkx as nx
import numpy as np

from experiments.configurational_fixtures import FIXTURES, build, fixture_result
from experiments.configurational_sources import load_cohort
from experiments.configurational_spatial import spatial_overlay
from experiments.configurational_statistics import distribution, high_choice_geometry, summarize
from experiments.flat40_configurational import (
    COVER, METRICS, authenticated_inputs, check, json_file, read, summary,
)
from voronoi_app import configurational, configurational_traversal
from voronoi_app.configurational import axial_graph, convex_graph, measures, segment_graph
from voronoi_app.configurational_traversal import SCALE, Traversal

CONFIG = Path(__file__).with_name("six_terrain_configurational_config.json")
MODES = ("axial", "segment", "angular", "metric")


def analyze(lines, frozen_edges):
    axial = axial_graph(lines)
    check({tuple(sorted(edge)) for edge in axial.edges} == frozen_edges, "Exact intersections differ from archive")
    segments = segment_graph(axial)
    check(nx.is_connected(axial) and nx.is_connected(segments), "Disconnected certified axial inventory")
    traversal = Traversal(segments)
    segments.graph["continuous_traversal"] = {
        "states": [{"id": state, "segment": traversal.ids[state // 2], "start": start, "end": end}
                   for state, (start, end) in enumerate(traversal.points)],
        "outgoing": traversal.links,
        "outgoing_fields": ["target_state", "turn_microdegrees", "twice_midpoint_distance_microunits"],
    }
    return {"axial": (axial, measures(axial)), "segment": (segments, measures(segments)),
            "angular": (segments, traversal.measures(segments)),
            "metric": (segments, traversal.measures(segments, "metric"))}


def highest(graph, rows, count=10):
    return [{"id": i, "points": graph.nodes[i]["points"], "owners": graph.nodes[i]["owners"], "choice": rows[i]["choice"]}
            for i in sorted(rows, key=lambda i: (-rows[i]["choice"], i))[:count]]


def angular_audit(segments, corrected):
    nominal = measures(segments, angular=True)
    old = summarize(segments, nominal)
    current = summarize(segments, corrected, weighted=True)
    traversal = Traversal(segments)
    differences, pair_rows = [], []
    direction_costs = {}
    for source, identifier in enumerate(traversal.ids):
        old_cost = nx.single_source_dijkstra_path_length(segments, identifier, weight="angular_weight")
        directed, sigma, _, _ = traversal.paths([2*source, 2*source+1])
        for target, other in enumerate(traversal.ids):
            if target == source:
                continue
            states = traversal.terminals(directed, target)
            new = directed[states[0]][0]
            paths = sum(sigma[s] for s in states)
            if target < source:
                check(direction_costs[target, source] == (new, paths), "Route reversal is not symmetric")
                continue
            direction_costs[source, target] = new, paths
            old_angle = old_cost[other] // len(segments)
            delta = (new - old_angle) / SCALE
            differences.append(delta)
            if delta:
                pair_rows.append({"source": identifier, "target": other, "historical_degrees": old_angle / SCALE,
                                  "continuous_degrees": new / SCALE, "continuous_tied_paths": paths})
    old_top = highest(segments, nominal)
    new_top = highest(segments, corrected)
    counts = Counter("higher" if x > 0 else "lower" if x < 0 else "equal" for x in differences)
    return {"historical": old, "continuous": current, "top10_historical": old_top, "top10_continuous": new_top,
            "top10_overlap": len({x["id"] for x in old_top} & {x["id"] for x in new_top}),
            "pair_angle_delta_degrees": distribution(differences), "pair_counts": dict(counts),
            "changed_pairs": pair_rows,
            "node_changes": {node: {"historical": nominal[node], "continuous": corrected[node]} for node in segments}}


def graph_summary(data):
    return {kind: summarize(graph, nodes, weighted=kind in ("angular", "metric")) |
            {"high_choice_spatial": high_choice_geometry(graph, nodes)} for kind, (graph, nodes) in data.items()}


def checkpoint(out, name, data, results):
    directory = out / "cases" / name
    directory.mkdir(parents=True)
    json_file(directory / "graphs.json", {kind: nx.node_link_data(graph, edges="edges")
              for kind, (graph, _) in data.items() if kind not in ("angular", "metric")})
    with (directory / "nodes.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["representation", "node", *METRICS, "reachable", "eccentricity"])
        writer.writeheader()
        for kind, (_, rows) in data.items():
            writer.writerows({"representation": kind, "node": node, **rows[node]} for node in sorted(rows))
    json_file(directory / "summary.json", results)


def archive_replay(reference, legacy, convex):
    expected = read(legacy / "statistics.json")["graphs"]
    observed = {}
    for label, data in reference.items():
        for kind in ("axial", "segment", "angular"):
            if label == "34-H" and kind == "angular":
                continue  # The historical atlas did not analyze this control angularly.
            graph = data[kind][0]
            rows = measures(graph, angular=kind == "angular")
            observed[f"{label} {kind}"] = summary(graph, rows)
    observed["Maximal convex"] = summary(*convex)
    discrepancies = {}
    for name, row in observed.items():
        previous = expected[name]
        for key in ("nodes", "edges", "component_sizes", "intelligibility", "metrics"):
            if row[key] != previous[key]:
                discrepancies[f"{name}/{key}"] = [previous[key], row[key]]
    # Byte-identical replay is also recorded by the standalone historical runner.
    return {"observed": observed, "discrepancies": discrepancies}


def variability(summaries, matched):
    pairs = ("flat-40", "flat-41")
    output = {}
    for kind in MODES:
        for field in (*METRICS, "intelligibility", "choice_gini"):
            def scalar(case):
                row = summaries[case][kind]
                if field == "intelligibility":
                    return row["intelligibility"]["r"]
                if field == "choice_gini":
                    return row["choice_concentration"]["gini"]
                return row["measures"][field]["mean"]

            a, b = map(scalar, pairs)
            values = list(map(scalar, matched))
            output[f"{kind}/{field}"] = {"flat_seed_observations": dict(zip(pairs, (a,b))),
                                        "flat_absolute_seed_difference": abs(a-b),
                                        "flat_two_seed_sample_sd": abs(a-b) / (2**.5),
                                        "matched_terrain_observations": dict(zip(matched, values)),
                                        "matched_terrain_range": max(values)-min(values),
                                        "matched_terrain_sample_sd": float(np.std(values, ddof=1)),
                                        "range_exceeds_flat_seed_difference": max(values)-min(values) > abs(a-b)}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--legacy", required=True, type=Path)
    parser.add_argument("--source-revision", default="8cb6d461f707691dedea77f5e3a387c6c441fc06")
    parser.add_argument("--data", type=Path, default=os.environ.get("AGGREGATION_DATA_ROOT"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.data is None:
        parser.error("Set AGGREGATION_DATA_ROOT or use --data.")
    sys.set_int_max_str_digits(0)
    start = perf_counter()
    out = args.output
    out.mkdir(parents=True)
    (out / "configuration.json").write_bytes(CONFIG.read_bytes())
    lines, polygons, selection, frozen, _, routes, hashes = authenticated_inputs(args.records, args.data, args.evidence)
    cases, inventory, matched, records = load_cohort(args.data, hashes["migration_inventory"])
    assessment = {"matched": matched, "supplementary": sorted(set(cases) - set(matched)),
                  "full_maximal_convex_comparison": len(matched) == sum(inventory[c]["maximal_convex"] is not None for c in matched),
                  "without_archived_CH_inventory": sorted(set(inventory) - set(cases)),
                  "comparison_selector": "Archived frozen C-H under original regional constraints for every terrain",
                  "maximal_convex_missing": [c for c in matched if inventory[c]["maximal_convex"] is None],
                  "flat40_pilot_1": "No separately named flat40-pilot-1 directory found; preserved flat40-configurational-1 used."}
    json_file(out / "source-inventory.json", inventory)
    json_file(out / "comparability.json", assessment)
    json_file(out / "verified-hashes.json", {"source_revision": args.source_revision, "flat40_inputs": hashes,
                                            "cohort_manifest_files": records,
                                            "analysis_source": {path.name: sha256(path.read_bytes()).hexdigest()
                                                for path in [*Path(__file__).parent.glob("configurational_*.py"),
                                                             Path(__file__), CONFIG, Path(configurational.__file__),
                                                             Path(configurational_traversal.__file__)]}})
    timings = {"input_verification_seconds": perf_counter() - start}
    fixture_results = {name: {mode: fixture_result(edges, mode) for mode in ("angular", "metric", "angular_metric")}
                       for name, edges in FIXTURES.items()}
    reversal = Traversal(build(FIXTURES["reversal"]))
    cost, multiplicity, _, _ = reversal.paths([0])
    check(cost[1] == (180_000_000, 1, 0) and multiplicity[1] == 1, "Reversal fixture failed")
    fixture_results["reversal"]["forced"] = {"expected_cost": [180_000_000, 1, 0], "actual_cost": cost[1],
                                             "expected_paths": 1, "actual_paths": multiplicity[1]}
    json_file(out / "angular-fixtures.json", fixture_results)

    begin = perf_counter()
    reference = {}
    for label in ("31-H", "29-H", "34-H"):
        ids = set(selection[label])
        edges = {tuple(sorted((i,j))) for i in ids for j in frozen[i]["intersections"] if j in ids}
        reference[label] = analyze({i: lines[i] for i in ids}, edges)
    graph = convex_graph(polygons)
    convex = graph, measures(graph)
    replay = archive_replay(reference, args.legacy, convex)
    json_file(out / "historical-flat40-replay.json", replay)
    check(not replay["discrepancies"], "Historical Flat 40 replay differs; see the saved audit.")
    audit = {label: angular_audit(*reference[label]["angular"]) for label in ("31-H", "29-H")}
    json_file(out / "flat40-angular-audit.json", audit)
    reference["31-H"]["convex"] = convex
    summaries = {}
    for label in ("31-H", "29-H"):
        name = f"flat40-{label}"
        summaries[name] = graph_summary(reference[label])
        checkpoint(out, name, reference[label], summaries[name])
    timings["flat40_reference_seconds"] = perf_counter() - begin

    terrain = {}
    for name, case in cases.items():
        begin = perf_counter()
        terrain[name] = reference["34-H"] if name == "flat-40" else analyze(case.lines, case.edges)
        check(set(terrain[name]["axial"][0]) == set(case.lines)
              and set(terrain[name]["axial"][0].edges) == case.edges, f"Case does not match common C-H inventory: {name}")
        summaries[name] = graph_summary(terrain[name])
        checkpoint(out, name, terrain[name], summaries[name])
        timings[f"{name}_seconds"] = perf_counter() - begin

    begin = perf_counter()
    primary = reference["31-H"]
    spatial = spatial_overlay(cases["flat-40"].accessible, primary["axial"], primary["angular"], convex)
    spatial["archived_exact_area_by_cover_multiplicity"] = read(args.evidence / COVER / "coverage-maximal.json")["area_by_count"]
    json_file(out / "flat40-spatial-overlay.json", spatial)
    timings["spatial_overlay_seconds"] = perf_counter() - begin
    seed = variability(summaries, matched)
    json_file(out / "seed-variability.json", seed)
    json_file(out / "statistics.json", summaries)

    from experiments.configurational_reporting import exports
    begin = perf_counter()
    exports(out, cases, matched, terrain, reference, summaries, audit, seed, spatial, fixture_results, routes)
    timings["export_seconds"] = perf_counter() - begin
    timings["total_seconds"] = perf_counter() - start
    timings["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == "darwin" else 1024)
    json_file(out / "runtime.json", timings)
    print(f"Analyzed {len(cases)} verified settlements, including {len(matched)} matched terrain cases, in {timings['total_seconds']:.1f}s.")


if __name__ == "__main__":
    main()
