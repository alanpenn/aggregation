"""Run the matched legacy/facewise growth experiment through topology only."""

import argparse
import csv
import json
from pathlib import Path

from shapely import from_wkb

from experiments.audit_facewise_growth import prefix_audit, replay
from experiments.plot_facewise_matched import plot_case
from voronoi_app.research_data import data_path
from voronoi_app.batch import run_stage
from voronoi_app.batch_store import BatchStore


def metrics(data, topology, placements):
    assigned = set(data["dyad_open_cells"])
    excluded = set(topology["excluded_open_cells"])
    return {
        "dyads": len(data["doors"]),
        "buildings": len(data["building_labels"]),
        "assigned_open": len(assigned),
        "assigned_components": placements[-1]["components"] if placements else 0,
        "excluded_assigned": len(excluded & assigned),
        "excluded_unassigned": len(excluded - assigned),
        "internal_blocks": len(topology["internal_blocks"]),
        "circulation_holes": len(topology["circulation_holes"]),
        "invalid_dyads": sum(invalid(row) for row in placements),
    }


def invalid(row):
    return row["parent_face_length"] == 0 or row["pair_face_length"] == 0


def audit(data, polygons, parents):
    return prefix_audit(data["doors"], data["building_labels"], parents, polygons)


def compare_case(source, destination, case):
    journal = json.loads((source.root / "cases" / f"{case}.json").read_text())
    results = {}
    for stage in ("settlement", "topology"):
        results[stage] = source.load(journal["stages"][stage]["record"])
    old_record, old, old_hash = results["settlement"]
    old_top_record, old_domain, old_top_hash = results["topology"]
    config = old["configuration"] | {"aggregation_strategy": "slope_preference_facewise_v1"}
    generated = run_stage(destination, "settlement", "generate-facewise-settlement", config)
    assert generated["status"] == "successful", generated
    derived = run_stage(destination, "topology", "main-open-topology", {}, generated["id"])
    assert derived["status"] == "successful", derived
    _, new, new_hash = destination.load(generated["id"])
    _, new_domain, new_top_hash = destination.load(derived["id"])
    assert old["grid"] == new["grid"] and old["polygons_wkb"] == new["polygons_wkb"]
    polygons = {int(cell): from_wkb(wkb) for cell, wkb in old["polygons_wkb"].items()}
    legacy = audit(old, polygons, replay(old))
    revised = audit(new, polygons, [row["parent_open_cell"] for row in new["placements"]])
    assigned = set()
    for row, recorded in zip(revised, new["placements"], strict=True):
        opened, building = row["open_cell"], row["building_cell"]
        assert opened != building and not {opened, building} & assigned
        assert row["components"] == 1 and not invalid(row)
        assert recorded["open_cell"] == opened and recorded["building_cell"] == building
        assert recorded["label"] == row["building"]
        assert recorded["building_face_length"] == row["pair_face_length"]
        assert recorded["parent_face_length"] == row["parent_face_length"]
        assert row["parent_open_cell"] is None or row["parent_open_cell"] in row["earlier_face_neighbors"]
        assigned.update((opened, building))
    assert set(new["dyad_open_cells"]) <= set(new_domain["topology"]["main_open_cells"])
    if case in {"converging_valleys-40", "converging_valleys-41"}:
        expected = {"converging_valleys-40": (78, 81), "converging_valleys-41": (78, 79)}
        assert (next(row["building"] for row in legacy if invalid(row)),
                next(row["building"] for row in legacy if row["components"] > 1)) == expected[case]
    shared = old["building_labels"].keys() & new["building_labels"].keys()
    summary = {
        "case": case,
        "same_number_same_building_cell": sum(
            old["building_labels"][cell] == new["building_labels"][cell] for cell in shared),
        "shared_building_cells": len(shared),
        "legacy": metrics(old, old_domain["topology"], legacy),
        "corrected": metrics(new, new_domain["topology"], revised),
        "legacy_settlement": old_record["id"], "legacy_settlement_sha256": old_hash,
        "legacy_topology": old_top_record["id"], "legacy_topology_sha256": old_top_hash,
        "corrected_settlement": generated["id"], "corrected_settlement_sha256": new_hash,
        "corrected_topology": derived["id"], "corrected_topology_sha256": new_top_hash,
    }
    with (destination.root / f"{case}.json").open("x") as stream:
        json.dump(summary | {"legacy_placements": legacy, "corrected_placements": revised}, stream, indent=2)
    plot_case(destination.root, case, polygons, old, new, legacy, revised, summary)
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=data_path('strict-generalisation/pilot-1'))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    source, destination = BatchStore(args.source), BatchStore(args.output)
    rows = []
    for terrain in ("hill", "converging_valleys"):
        for seed in (40, 41, 42):
            summary = compare_case(source, destination, f"{terrain}-{seed}")
            for variant in ("legacy", "corrected"):
                rows.append({"case": summary["case"], "variant": variant,
                             "settlement": summary[f"{variant}_settlement"],
                             "topology": summary[f"{variant}_topology"], **summary[variant],
                             "shared_building_cells": summary["shared_building_cells"],
                             "same_number_same_building_cell": summary["same_number_same_building_cell"]})
    with (args.output / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
