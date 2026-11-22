"""Replay strict convex-region coverage repairs on the preserved benchmark."""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from voronoi_app.batch_routing_reference import interval
from voronoi_app.batch_store import BatchStore, encode

from .region_incidence_angular import DEFAULT_OUT as INCIDENCE
from .route_sparse import ROOT

OUT = ROOT / "strict-coverage" / "pilot-2"


def read(path):
    return json.loads(path.read_text())


def archive_maps(store, parent, saved):
    chain = store._inputs("validation", parent["parent"]["id"])
    master = chain["candidates"][1]["pool"]["candidates"]
    known = {interval(line): i for i, line in enumerate(master)}
    extra, sources, maps = [], {}, []

    def add(record, name, ids, pool=master):
        ids = list(ids)
        if pool is master:
            converted = ids
        else:
            converted = []
            for i in ids:
                row = pool[i]
                key = interval(row)
                if key not in known:
                    known[key] = len(master) + len(extra)
                    extra.append({k: row[k] for k in ("start", "end")})
                converted.append(known[key])
        maps.append({"name": f"{record['id']}/{name}", "source_record": record["id"],
                     "archive_name": name, "original_line_ids": ids, "line_ids": sorted(set(converted)),
                     "source_status": record["status"]})

    for path in sorted((store.root / "records").glob("*/record.json")):
        header = read(path)
        if header["settlement_id"] != parent["settlement_id"] or header["status"] not in ("successful", "invalid"):
            continue
        method = header["method"]["identity"]
        module, _, name = method.partition(":")
        family = module.split(".")[-1]
        relevant = {"selection", "sheaf_experiment", "batch_routing_reference",
                    "region_incidence_angular", "route_sparse_experiment",
                    "route_sparse_matched", "extreme_diagonal_experiment"}
        if header["stage"] != "selection" and family not in relevant:
            continue
        record, data, stamp = store.load(header["id"])
        before = len(maps)
        if record["stage"] == "selection" and "lines" in data:
            source = {line["id"]: line for line in data["lines"]}
            add(record, name, data["line_ids"], source)
        elif family == "sheaf_experiment":
            pool_chain = store._inputs("validation", record["parent"]["id"])
            pool = pool_chain["candidates"][1]["pool"]["candidates"]
            if name == "diagnostics":
                add(record, "diagnostic-selection", [data["source_ids"][i] for i in data["selected"]], pool)
            elif name == "backward_order":
                add(record, data["order"], data["map"]["source_ids"], pool)
            elif name == "reduction":
                for key, item in data["strategies"].items():
                    add(record, key, item["source_ids"], pool)
                for key, item in data["orders"].items():
                    add(record, f"order-{key}", item["map"]["source_ids"], pool)
            elif name == "order_route_measures":
                for key, ids in record["parameters"]["orders"].items():
                    add(record, f"order-{key}", ids, pool)
        elif family in ("batch_routing_reference", "region_incidence_angular", "route_sparse_experiment"):
            choices = data.get("maps", {})
            if isinstance(choices, list):
                choices = {f"{item['name']}-{i}": item for i,item in enumerate(choices)}
            for key, item in choices.items():
                add(record, key, item["line_ids"])
            for i, item in enumerate(data.get("marginal", [])):
                add(record, f"marginal-{i}", item["line_ids"])
            for group in data.get("sheaves", []):
                for i, item in enumerate(group["alternatives"]):
                    add(record, f"sheaf-{group['group']}-{i}", item["line_ids"])
        elif family == "route_sparse_matched":
            add(record, "baseline", data["baseline"]["line_ids"])
            for i, item in enumerate(data["improvements"]):
                add(record, f"exchange-{i}", item["line_ids"])
        elif family == "extreme_diagonal_experiment":
            for i, corridor in enumerate(data["corridors"], 1):
                for key, item in corridor["variants"].items():
                    if "representatives" in item:
                        add(record, f"corridor-{i}-{key}", set(corridor["exterior"]) | set(item["representatives"]))
        if len(maps) > before:
            sources[record["id"]] = stamp
    if not maps:
        raise ValueError("No archived maps found.")
    return {"maps": maps, "extra_intervals": extra, "archive_sources": sources}


def run(case, step, output, *, scan_passes=False):
    store = BatchStore(ROOT)
    record, saved, stamp = store.load(read(INCIDENCE / f"{case}.json")["record"])
    if record["status"] != "successful":
        raise ValueError("A verified incidence record is required.")
    parameters = {"case": case, "incidence": saved,
                  "incidence_record": record["id"], "incidence_sha256": stamp,
                  "reference": record["parameters"]["reference"]}
    output.mkdir(parents=True, exist_ok=True)
    journal = output / f"{case}-{step}.json"
    if journal.exists():
        raise FileExistsError(journal)
    parent = record["parent"]["id"]
    if step == "audit":
        parameters.update(archive_maps(store, record, saved))
        method = "audit"
    elif step.endswith("metric"):
        start = step.removesuffix("metric")
        source = read(output / f"{case}-{start}.json")["record"]
        repair_record, repaired, stamp = store.load(source)
        if repair_record["status"] != "successful":
            raise ValueError("A successful strict repair is required.")
        parameters.update(start=start, seed=repaired["results"]["route-aware-additions"]["line_ids"],
                          repair_record=source, repair_sha256=stamp, scan_passes=False)
        method = "metric_control"
    else:
        parameters.update(start=step, per_rule=3, swap_window=6, scan_passes=scan_passes)
        method = "repair"
    result = store.run("validation", f"voronoi_app.strict_coverage_experiment:{method}",
                       "3" if method == "repair" else "2" if method == "metric_control" else "1",
                       parameters, parent)
    with journal.open("xb") as stream:
        stream.write(encode({"record": result["id"], "status": result["status"],
                             "error": result.get("error")}))
    print(case, step, result["status"], result.get("error"), flush=True)
    return result["status"] != "successful"


def export(directory):
    store = BatchStore(ROOT)
    audits, repairs, catalogue = [], [], []
    for path in sorted(directory.glob("*.json")):
        case, step = path.stem.rsplit("-", 1)
        state = read(path)
        if state["status"] != "successful":
            raise ValueError(state)
        record, data, _ = store.load(state["record"])
        if step == "audit":
            chain = store._inputs("validation", record["parent"]["id"])
            labels = chain["settlement"][1]["building_labels"]
            for row in data["maps"].values():
                audits.append({"case": case, **{k: row[k] for k in
                               ("source_record", "archive_name", "source_status", "lines",
                                "old_coverage", "strict_coverage")},
                               "required_regions": data["required_regions"],
                               "original_line_ids": json.dumps(row["original_line_ids"]),
                               "master_line_ids": json.dumps(row["line_ids"]),
                               "missing_regions": json.dumps(row["missing_regions"]),
                               "boundary_only_regions": json.dumps(row["boundary_only_regions"]),
                               "unattached_buildings": json.dumps(
                                   [labels[str(data["doors"][i]["building_cell"])] for i in row["unattached_doors"]])})
            for group, key, candidate_sets in (
                ("region", "missing_regions", data["region_repair_candidates"]),
                ("door", "unattached_doors", {str(i): candidates for i,candidates in
                                             enumerate(data["door_repair_candidates"])}),
            ):
                for i in sorted({i for row in data["maps"].values() for i in row[key]}):
                    candidates = candidate_sets[str(i)]
                    catalogue.append({"case": case, "kind": group, "id": i,
                                      "building_label": labels[str(data["doors"][i]["building_cell"])]
                                      if group == "door" else None,
                                      "certified_candidates": len(candidates), "line_ids": json.dumps(candidates)})
            continue
        for name, row in data["results"].items():
            measures = {}
            for key in ("angular_statistics", "angular_excess", "metric_statistics", "metric_change"):
                for stat in ("mean", "median", "p95", "max", "reachable", "unreachable"):
                    measures[f"{key}_{stat}"] = row.get(key, {}).get(stat)
            old = record["parameters"]["incidence"]["maps"][data["start"]]["angular"]
            angular_changes = [b-a for a,b in zip(old, row["angular"], strict=True)
                               if a is not None and b is not None] if "angular" in row else []
            repairs.append({"case": case, "start": step, "method": name, "order": row.get("order"),
                            "record": record["id"], "status": row.get("status", "valid"),
                            "lines": len(row["line_ids"]), "length": row.get("length"),
                            "old_coverage": row.get("strict_coverage"), "strict_coverage": row.get("strict_coverage"),
                            "rank": row.get("winding_rank"), "required_rank": row.get("required_rank"),
                            "unattached_doors": row.get("unattached_doors"),
                            "added": json.dumps(row.get("added")), "removed": json.dumps(row.get("removed")),
                            "metric_newly_unreachable": row.get("metric_newly_unreachable"),
                            "angular_common_pairs": len(angular_changes) if "angular" in row else None,
                            "angular_mean_change_common": mean(angular_changes) if angular_changes else None,
                            **measures})
    for name, rows in (("audit.csv", audits), ("repairs.csv", repairs), ("repair-candidates.csv", catalogue)):
        with (directory / name).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({k: "null" if v is None else v for k,v in row.items()} for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--scan-passes", action="store_true", help="Finish each deletion pass before sorting again.")
    parser.add_argument("case", choices=["Hill-42", "Y-42", "export"])
    parser.add_argument("step", nargs="?", choices=["A", "B", "Ametric", "Bmetric", "audit"])
    args = parser.parse_args()
    if args.case == "export":
        return export(args.output)
    if args.step is None:
        parser.error("Specify A, B or audit.")
    return run(args.case, args.step, args.output, scan_passes=args.scan_passes)


if __name__ == "__main__":
    raise SystemExit(main())
