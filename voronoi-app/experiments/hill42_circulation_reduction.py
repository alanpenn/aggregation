"""Thin the saved Hill 42 witness network and certify the resulting subset."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from experiments.hill42_circulation_repair import EXPECTED_HASHES, geometry_inputs, sha256
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_circulation_topology import (
    _ring_covers_cells,
    analyse_circulation_topology,
    bounded_face_rings,
)


def reduce_witness(lines, cells, polygons):
    retained = {line.line_id: line for line in lines}
    for line in sorted(lines, key=lambda candidate: (-candidate.length, candidate.line_id)):
        trial = [other for line_id, other in retained.items() if line_id != line.line_id]
        if any(_ring_covers_cells(face, cells, polygons) for face in bounded_face_rings(trial)):
            del retained[line.line_id]
    return retained


def run(data_path, map_path, repair_path):
    hashes = {"hill-data": sha256(data_path), "hill-map": sha256(map_path)}
    repair = json.loads(repair_path.read_text())
    if hashes != EXPECTED_HASHES or repair["input_sha256"] != hashes:
        raise ValueError("Hill inputs do not match the preserved repair")
    _, polygons, _, buildings, dyads, _, _ = geometry_inputs(data_path, map_path)

    candidates = {}
    for record in repair["proposed_candidates"]:
        line_id = record["candidate_id"]
        start, end = (tuple(map(Fraction, record[key])) for key in ("start", "end"))
        candidates[line_id] = ExactCandidate(line_id, start, end, start, end, record["source"])

    baseline = analyse_circulation_topology(polygons, buildings, dyads, list(candidates.values()))
    if not baseline["circulation_constraints_satisfied"] or baseline["lines_crossing_effective_occupied_space"]:
        raise ValueError("Saved repair failed exact validation")

    retained = {}
    witnesses = []
    for block in repair["all_11_block_repairs"]["block_cycle_witnesses"]:
        lines = [candidates[line_id] for line_id in block["witness_candidate_ids"]]
        reduced = reduce_witness(lines, block["cells"], polygons)
        retained.update(reduced)
        witnesses.append({
            "block": block["block"],
            "original_line_count": len(lines),
            "retained_candidate_ids": sorted(reduced),
        })

    result = analyse_circulation_topology(polygons, buildings, dyads, list(retained.values()))
    if not result["circulation_constraints_satisfied"] or result["lines_crossing_effective_occupied_space"]:
        raise ValueError("Reduced network failed exact validation")

    return {
        "input_sha256": {**hashes, "hill-repair": sha256(repair_path)},
        "original_line_count": len(candidates),
        "original_total_length": sum(line.length for line in candidates.values()),
        "retained_line_count": len(retained),
        "retained_total_length": sum(line.length for line in retained.values()),
        "retained_candidate_ids": sorted(retained),
        "winding_rank": result["independent_circulation_rank"],
        "required_rank": result["required_circulation_rank"],
        "missing_axial_rings": result["missing_axial_rings"],
        "clearance_rejections": result["lines_crossing_effective_occupied_space"],
        "block_witnesses": witnesses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("hill-data", "hill-map", "hill-repair", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.hill_data, args.hill_map, args.hill_repair)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
