"""Run bounded fixed-attachment exchanges on the prepared Valley network."""

import argparse
import json
import math
import time
from fractions import Fraction
from pathlib import Path

from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, SampleAttachment
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import ExactCandidate, candidate_graph, closed_routes, region_coverage
from voronoi_app.experimental_angular_selection import (
    AngularResult, _structural_failure, improve_fidelity, optimise_fidelity,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--epsilon", type=float, default=.05)
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--removal-limit", type=int, default=4)
    parser.add_argument("--revisit-pair", choices=("1-50", "49-54", "49-23"))
    args = parser.parse_args()
    state = args.data_dir
    data = json.loads((state / "prepared.json").read_text())
    raw_reference = json.loads((state / "reference.json").read_text())
    heuristic = json.loads((state / "heuristic.json").read_text())
    settlement = json.loads((state / "settlement.json").read_text())
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    attachments = [SampleAttachment(tuple(map(Fraction, item["sample"])),
                                    tuple(map(Fraction, item["point"])), item["line_id"])
                   for item in data["attachments"]]
    components = [item["component"] for item in data["attachments"]]
    groups = [{i for i, value in enumerate(data["components"]) if value == component}
              for component in range(len(set(data["components"])))]
    covers = [set(values) for values in data["covers"]]
    targets = set(range(data["regions"]))
    reference = AngularResult({(a, b): d for a, b, d in raw_reference["depths"]},
                              frozenset(raw_reference["witness_lines"]))
    labels = {int(label): int(cell) for cell, label in settlement["building_labels"].items()}
    pair_candidates = {}
    for pair in ((1, 50), (49, 54), (49, 23)):
        cells = {labels[label] for label in pair}
        matched = []
        for i, record in enumerate(data["records"]):
            entry = record["baseline"]
            if entry is None:
                continue
            if any(cells <= {ref["building_id"] for ref in
                             support["start_vertices"] + support["end_vertices"]}
                   for support in entry["provenance"]):
                matched.append(i)
        pair_candidates[f"{pair[0]}-{pair[1]}"] = matched
    print("pair candidates", pair_candidates, flush=True)
    started = time.monotonic()
    if args.revisit_pair:
        previous = json.loads((state / "exchange-result.json").read_text())
        if previous["epsilon"] != args.epsilon:
            raise ValueError("Revisit must use the previous result's angular tolerance")
        initial_selected = set(previous["selected"])
        additions = pair_candidates[args.revisit_pair]
        filename = f"exchange-revisit-{args.revisit_pair}.json"
    else:
        initial = optimise_fidelity(
            lines, covers, targets, groups, data["obstacles"], attachments, components,
            reference, args.epsilon, set(data["ring_candidates"]), attempt_limit=4,
            seed_witnesses=set(heuristic["witness_lines"]),
        )
        initial_selected = set(initial.selected)
        additions = list(dict.fromkeys(i for ids in pair_candidates.values() for i in ids
                                       if i not in initial_selected))
        additions += [
            i for i in sorted(range(len(lines)), key=lambda j: (-lines[j].length, j))
            if i not in initial_selected and i not in additions
        ][:2]
        filename = "exchange-result.json"
    print("initial feasible", len(initial_selected), "seconds",
          round(time.monotonic() - started, 2), flush=True)
    print("bounded exchange additions", additions, flush=True)
    result = improve_fidelity(
        lines, covers, targets, groups, data["obstacles"], attachments, components,
        reference, args.epsilon, initial_selected, clearance, additions=additions,
        attempt_limit=args.attempts, removal_limit=args.removal_limit,
    )
    selected_lines = [lines[i] for i in sorted(result.selected)]
    actual_coverage = set().union(*region_coverage(selected_lines, convex_regions(accessible)))
    if actual_coverage != targets:
        raise ValueError("Exact recomputation found incomplete convex coverage")
    if not all(clearance.permits_exact(line.start, line.end) for line in selected_lines):
        raise ValueError("An exchange result is not exactly clear")
    if _structural_failure(lines, covers, targets, groups, data["obstacles"], result.selected):
        raise ValueError("Exchange result failed structural recertification")
    differences = {pair: result.depths[pair] - depth
                   for pair, depth in reference.depths.items() if math.isfinite(depth)}
    before_graph = candidate_graph([lines[i] for i in sorted(initial_selected)])
    after_graph = candidate_graph(selected_lines)
    output = {
        "epsilon": args.epsilon, "pair_candidates": pair_candidates,
        "initial": sorted(initial_selected), "selected": sorted(result.selected),
        "initial_length": sum(lines[i].length for i in initial_selected),
        "selected_length": sum(line.length for line in selected_lines),
        "initial_intersections": before_graph.number_of_edges(),
        "selected_intersections": after_graph.number_of_edges(),
        "coverage": len(actual_coverage), "region_count": len(targets),
        "rings": len(closed_routes(selected_lines, data["obstacles"])),
        "ring_count": len(data["obstacles"]), "components": len(groups),
        "attempted": result.attempted, "exchanges": result.exchanges,
        "mean_increase": sum(differences.values()) / len(differences),
        "max_increase": max(differences.values()),
        "increased_pairs": sum(value > 1e-10 for value in differences.values()),
        "ordered_pairs": len(differences), "seconds": time.monotonic() - started,
    }
    with (state / filename).open("x") as file:
        json.dump(output, file, allow_nan=False)
    print("exchange result", json.dumps(output), flush=True)


if __name__ == "__main__":
    main()
