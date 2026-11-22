"""Compare preserved axial maps using a fresh-exact master routing network."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from fractions import Fraction
import gzip
from itertools import combinations
import json
from pathlib import Path
from uuid import uuid4

from voronoi_app.batch import run_stage
from voronoi_app.batch_routing_reference import describe, excess
from voronoi_app.batch_store import BatchStore, atomic_write, digest, encode


ATOL = 1e-8
RTOL = 1e-9
Y_REFERENCE_SHA = "39a9a96c7f390e90bcd7e2387ce99cf0bee31ba27d8d0ce6942a96fbb9d6a5b6"


def read(path):
    return json.loads(path.read_text())


def identity(door, *, historical=False):
    a, b = ("open_id", "building_id") if historical else ("open_cell", "building_cell")
    return door[a], door[b], tuple(map(Fraction, door["point"]))


def historical_y(path, settlement, topology, doors):
    raw = path.read_bytes()
    if digest(raw) != Y_REFERENCE_SHA:
        raise ValueError("Y doorway reference checksum differs from the preserved result.")
    data = json.loads(gzip.decompress(raw))
    hashes = data["summary"]["input_sha256"]
    provenance = settlement["provenance"]
    if (topology["excluded_open_cells"]
            or hashes["home/Downloads/axial-diagnostic.json"] != provenance["snapshot"]["sha256"]
            or hashes["valley42-exchange-2026-11-17/settlement.json"] != provenance["label_inventory"]["sha256"]
            or provenance["saved_doorway_inventory"]["sha256"] != digest(raw)):
        raise ValueError("Y continuous reference and axial settlement have different sources.")
    valid = {d["door_id"]: d for d in data["doors"] if d["status"] == "valid"}
    old = {identity(valid[door], historical=True): i for i, door in enumerate(data["valid_door_ids"])}
    if set(old) != {identity(d) for d in doors}:
        raise ValueError("Y continuous and axial doorway inventories differ.")
    index = [old[identity(d)] for d in doors]
    paths = {tuple(sorted((p["source"], p["destination"]))): p.get("length") for p in data["paths"]}
    expected = {tuple(sorted(pair)) for pair in combinations(index, 2)}
    if set(paths) != expected:
        raise ValueError("Y continuous pair inventory differs from the axial inventory.")
    return [paths[tuple(sorted(pair))] for pair in combinations(index, 2)]


def compare_case(root, out, bench, reduction_case, y_path):
    store = BatchStore(root)
    name = reduction_case["case"]
    fresh = next(c for c in bench if c["case"] == name and c["generator"] == "fresh-exact"
                 and c["selector"] == "full-pool")["records"]
    guided = next(c for c in bench if c["case"] == name and c["generator"] == "fresh-exact"
                  and c["selector"] == "entrance-guided")["records"]
    projected = reduction_case["input_records"]
    if any(fresh[k] != projected[k] for k in ("settlement", "topology")):
        raise ValueError("Selected maps do not share the master settlement and topology.")
    archived = {}

    def load(record_id, *, successful=True):
        record, value, stamp = store.load(record_id)
        if successful and record["status"] != "successful":
            raise ValueError(f"Expected a successful saved input: {record_id}")
        archived[record_id] = stamp
        return value

    fresh_doors = load(fresh["measures"])["entrances"]
    projected_doors = load(projected["measures"])["entrances"]
    if {identity(d) for d in fresh_doors} != {identity(d) for d in projected_doors}:
        raise ValueError("The saved master and projected maps have different doorways.")
    projected_lines = load(projected["candidates"])["pool"]["candidates"]
    reduced = load(reduction_case["reduction"])
    selections = {
        "fresh-entrance-guided": load(guided["selection"])["lines"],
        **{k: [projected_lines[i] for i in v["source_ids"]] for k, v in reduced["strategies"].items()},
        **{f"backward-{k}": [projected_lines[i] for i in v["map"]["source_ids"]]
           for k, v in reduced["orders"].items()},
    }
    params = {
        "case": name, "source_records": archived,
        "original_validation": {k: "successful" for k in selections},
        "maps": selections,
        "additional_connectors": [
            [[d["open_cell"], d["building_cell"], d["point"]],
             [[projected_lines[a["line"]], a["point"]] for a in d["connectors"]]]
            for d in projected_doors
        ],
        "absolute_tolerance": ATOL, "relative_tolerance": RTOL,
        "attachment_policy": "Union of saved fresh and projected connectors by exact interval and stop.",
    }
    settlement = load(fresh["settlement"])
    params["doorway_provenance"] = settlement["provenance"]
    for key in (fresh["validation"], projected["validation"], guided["validation"]):
        load(key)
    if name == "Y 42":
        params["continuous_metric"] = historical_y(
            y_path, settlement, load(fresh["topology"])["topology"], fresh_doors,
        )
        params["continuous_source"] = {"artifact": y_path.name, "sha256": Y_REFERENCE_SHA}
    record = run_stage(store, "validation", "voronoi_app.batch_routing_reference:routing_reference",
                       params, fresh["measures"], "2")
    state = {"case": name, "master_candidates": fresh["candidates"], "record": record["id"],
             "status": record["status"], "error": record.get("error", {}).get("message")}
    atomic_write(out / f"{name.replace(' ', '-')}.json", encode(state))
    return state


def finish(root, directory, hill_continuous=None):
    store = BatchStore(root)
    cases = [read(directory / f"{name}-42.json") for name in ("Hill", "Y")]
    tables, hill_pairs = [], {}
    for case in cases:
        original, routes, _ = store.load(case["record"])
        if routes is None:
            raise ValueError(case)
        reference = None
        if case["case"] == "Hill 42" and hill_continuous:
            continuous_record, reference, checksum = store.load(hill_continuous)
            if (continuous_record["status"] != "successful"
                    or continuous_record["parent"] != original["parent"]) or (
                [{k: d[k] for k in ("open_cell", "building_cell", "point")} for d in routes["doorways"]]
                != reference["doorways"]
            ):
                raise ValueError("Hill continuous and axial records have different doorway positions.")
            hill_pairs = {"source_id": hill_continuous, "source_sha256": checksum,
                          "axial_record_id": case["record"], "comparisons": {}}
        for name, entry in routes["maps"].items():
            if reference:
                comparison = excess(reference["metric"], entry["routes"]["metric"], ATOL, RTOL)
                hill_pairs["comparisons"][name] = comparison
                entry["excess_over_continuous"] = comparison
            row = {
                "case": case["case"], "map": name, "line_count": entry["line_count"],
                "total_length": entry["total_length"], "reference_record": original["id"],
                "master_candidates": case["master_candidates"],
                "map_validation": "successful", "comparison_status": original["status"],
            }
            for measure, stats in entry["statistics"].items():
                row.update({f"{measure}_{k}": v for k, v in stats.items()})
            for measure, comparison in entry["excess_over_full"].items():
                for prefix, key in (("excess", "absolute_statistics"), ("excess_pct", "percent_statistics")):
                    row.update({f"{measure}_{prefix}_{k}": v for k, v in comparison[key].items()})
                row[f"{measure}_monotonicity_violations"] = len(comparison["violations"])
            continuous = entry.get("excess_over_continuous", {})
            for prefix, key in (("excess", "absolute_statistics"), ("excess_pct", "percent_statistics")):
                stats = continuous.get(key, describe([]))
                row.update({f"continuous_metric_{prefix}_{k}": v for k, v in stats.items()})
            row["continuous_metric_violations"] = len(continuous["violations"]) if continuous else None
            tables.append(row)
    with (directory / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(tables[0]))
        writer.writeheader()
        writer.writerows({k: "null" if v is None else v for k, v in row.items()} for row in tables)
    atomic_write(directory / "comparison.json", encode(tables))
    if hill_pairs:
        atomic_write(directory / "Hill-42-continuous-detour.json", encode(hill_pairs))
    print("Comparison rows:", len(tables))


def reuse_baseline(root, reference_id, validations):
    store = BatchStore(root)
    record, reference, checksum = store.load(reference_id)
    if (record["status"] != "successful"
            or record["method"]["identity"] != "voronoi_app.batch_routing_reference:routing_reference"):
        raise ValueError("A successful full-pool routing reference is required.")
    params = dict(record["parameters"])
    parent = record["parent"]["id"]
    inputs = store._inputs("validation", parent)
    master_hash = digest(encode({
        "candidate_records": inputs["candidates"][1]["pool"]["candidates"],
        "doorways": reference["doorways"],
    }))
    params["saved_reference"] = {
        "id": reference_id, "record_sha256": checksum, "master_geometry_sha256": master_hash,
        "routes": reference["maps"]["full"]["routes"],
    }
    params["maps"], params["original_validation"] = {}, {}
    for record_id in validations:
        validated, output, stamp = store.load(record_id)
        if (validated["stage"] != "validation" or validated["status"] != "successful"
                or validated["settlement_id"] != record["settlement_id"]
                or output.get("failed_checks") != []):
            raise ValueError(f"Expected successful map validation in the same settlement: {record_id}")
        sources = store._inputs("validation", validated["parent"]["id"])
        params["maps"][record_id] = sources["selection"][1]["lines"]
        params["original_validation"][record_id] = "successful"
        params["source_records"][record_id] = stamp
    new = run_stage(store, "validation", "voronoi_app.batch_routing_reference:routing_reference",
                    params, parent, "2")
    print(json.dumps({"record": new["id"], "status": new["status"], "error": new.get("error")}))
    return int(new["status"] != "successful")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--reductions", type=Path)
    parser.add_argument("--y-visibility", type=Path)
    parser.add_argument("--finish", type=Path)
    parser.add_argument("--hill-continuous")
    parser.add_argument("--reuse-baseline", help="Saved routing reference record ID")
    parser.add_argument("--validated-map", action="append", default=[], help="Map validation record ID")
    args = parser.parse_args()
    if args.reuse_baseline:
        if not args.validated_map:
            parser.error("Provide at least one --validated-map to compare.")
        return reuse_baseline(args.store, args.reuse_baseline, args.validated_map)
    if args.finish:
        finish(args.store, args.finish, args.hill_continuous)
        return
    if not all((args.benchmark, args.reductions, args.y_visibility)):
        parser.error("Provide benchmark, reductions and y-visibility inputs.")
    output = args.store / "routing-references" / uuid4().hex
    output.mkdir(parents=True)
    print(output, flush=True)
    benchmark = read(args.benchmark)
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(compare_case, args.store, output, benchmark, case, args.y_visibility)
                   for case in read(args.reductions)]
        cases = [f.result() for f in futures]
    atomic_write(output / "cases.json", encode(cases))
    print(cases)


if __name__ == "__main__":
    raise SystemExit(main())
