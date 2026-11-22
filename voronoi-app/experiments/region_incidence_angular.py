"""Run convex-region angular analysis on the preserved benchmark."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from voronoi_app.batch_store import BatchStore, encode

from .route_sparse import BASELINES, ROOT, saved_comparison

DEFAULT_OUT = ROOT / "region-incidence-angular" / "pilot-2"


def add_alternatives(store, case, parameters, parent):
    slug = case.replace(" ", "-")
    extreme_path = ROOT / "extreme-diagonals" / "pilot-3" / f"{slug}.json"
    extreme_id = json.loads(extreme_path.read_text())["record"]
    manifest, result, stamp = store.load(extreme_id)
    if manifest["status"] != "successful" or manifest["parent"]["id"] != parent:
        raise ValueError("Extreme-diagonal results do not share the benchmark lineage.")
    sources = {extreme_id: stamp}
    maps = {}

    def add(name, ids, stats):
        maps[name] = {"line_ids": sorted(ids),
                      "angular_statistics": stats["angular"]["cost"],
                      "metric_statistics": stats["metric"]["cost"]}

    for i, corridor in enumerate(result["corridors"], 1):
        for key in ("B", "C"):
            variant = corridor["variants"][key]
            if "route" in variant:
                ids = set(corridor["exterior"]) | set(variant["representatives"])
                add(f"extreme-{i}-{key}", ids, variant["route"])
    sparse_dir = ROOT / "route-sparse" / "pilot-2"
    manifest, sparse, stamps = saved_comparison(store, slug, sparse_dir)
    if manifest["parent"]["id"] != parent:
        raise ValueError("Sparse results do not share the benchmark lineage.")
    for name in ("beam", "matched"):
        maps_of_kind = [m for m in sparse["maps"] if m["name"] == name]
        if maps_of_kind:
            chosen = min(maps_of_kind, key=lambda m: (m["line_count"], m["length"], m["line_ids"]))
            add(f"sparse-{name}", chosen["line_ids"], chosen["routing"])
    parameters.update(additional_maps=maps, additional_source_records=sources | stamps)


def run(case, out):
    store = BatchStore(ROOT)
    record_id = next(x["record"] for x in json.loads(BASELINES.read_text()) if x["case"] == case)
    record, reference, stamp = store.load(record_id)
    if record["status"] != "successful":
        raise ValueError("Expected a successful archived comparison.")
    out.mkdir(exist_ok=True, parents=True)
    journal = out / (case.replace(" ", "-") + ".json")
    if journal.exists():
        raise FileExistsError(journal)
    parameters = {"case": case, "reference_id": record_id, "reference_sha256": stamp,
                  "reference": {k: reference[k] for k in ("doorways", "pairs", "maps")}}
    parent = record["parent"]["id"]
    add_alternatives(store, case, parameters, parent)
    result = store.run("validation", "voronoi_app.region_incidence_angular:analyze", "2", parameters, parent)
    with journal.open("xb") as stream:
        stream.write(encode({"record": result["id"], "status": result["status"],
                             "error": result.get("error")}))
    return result["status"] != "successful"


def export(out):
    store = BatchStore(ROOT)
    rows = []
    for case in ("Hill-42", "Y-42"):
        journal = json.loads((out / f"{case}.json").read_text())
        if journal["status"] != "successful":
            raise ValueError(journal)
        record, result, _ = store.load(journal["record"])
        for name, data in result["maps"].items():
            archived = record["parameters"]["reference"]["maps"].get(name)
            common = [(a, b) for a, b in zip(data["angular"], archived["routes"]["angular"], strict=True)
                      if a is not None and b is not None] if archived else []
            row = {"case": case, "record": record["id"], "map": name,
                   "lines": len(data["line_ids"]), "interior_regions_covered": len(data["covered_regions"]),
                   "required_regions": len(result["region_lines"]),
                   "unattached_doors": len(data["unattached_doors"]),
                   "attachment_failure_pairs": data["pair_status"].count("attachment_failure"),
                   "disconnected_pairs": data["pair_status"].count("disconnected"),
                   "zero_angular_depth_pairs": data["zero_depth"],
                   "common_angular_pairs": len(common) if archived else None,
                   "incidence_angular_mean_common": mean(a for a, _ in common) if common else None,
                   "connector_angular_mean_common": mean(b for _, b in common) if common else None}
            for key in ("statistics", "connector_angular_statistics", "connector_metric_statistics"):
                prefix = "incidence_angular" if key == "statistics" else key.removesuffix("_statistics")
                row.update({f"{prefix}_{k}": v for k, v in data[key].items()})
            rows.append(row)
    with (out / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: "null" if v is None else v for k, v in row.items()} for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("case", choices=["Hill 42", "Y 42", "export"])
    args = parser.parse_args()
    return export(args.output) if args.case == "export" else run(args.case, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
