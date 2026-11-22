"""Run and export the preserved route-efficient sparse-map experiment."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from voronoi_app.batch import run_stage
from voronoi_app.batch_routing_reference import interval
from voronoi_app.batch_store import BatchStore, digest, encode
from voronoi_app.route_sparse_experiment import pareto


ROOT = Path("diagnostics/preserved-axial-benchmark")
BASELINES = ROOT / "routing-references" / "e101fc909354439e8695fd77ac791d41" / "cases.json"
SHEAVES = ROOT / "sheaf-experiments" / "hill-y-comparison" / "cases.json"


def read(path):
    return json.loads(path.read_text())


def run(case, kind, directory):
    path = directory / f"{case.replace(' ', '-')}-{kind}.json"
    if path.exists():
        raise FileExistsError(path)
    store = BatchStore(ROOT)
    record_id = next(row["record"] for row in read(BASELINES) if row["case"] == case)
    record, reference, checksum = store.load(record_id)
    if record["status"] != "successful":
        raise ValueError("A successful routing reference is required.")
    parent = record["parent"]["id"]
    master_records = store._inputs("validation", parent)
    fresh = master_records["candidates"][1]["pool"]["candidates"]
    doorway_data = {k: reference[k] for k in ("doorways", "pairs", "node_count", "segment_count")}
    doorway_data["master_geometry_sha256"] = reference.get("master_geometry_sha256") or digest(
        encode({"candidate_records": fresh, "doorways": reference["doorways"]})
    )
    doorway_data["maps"] = {name: {k: value[k] for k in ("line_ids", "total_length", "routes")}
                            for name, value in reference["maps"].items()}
    params = {"case": case, "reference_record": record_id, "reference_sha256": checksum,
              "reference": doorway_data}
    if kind == "sensitivity":
        params["limits"] = [32, 96]
    else:
        archived = next(row for row in read(SHEAVES) if row["case"] == case)
        diag, groups, stamp = store.load(archived["diagnostics"])
        old = store.load(archived["input_records"]["candidates"])[1]["pool"]["candidates"]
        fresh_ids = {interval(line): line["id"] for line in fresh}
        sheaves = [[fresh_ids[interval(old[member["source_id"]])] for member in group["members"]]
                  for group in groups["sheaves"]]
        metric, angular = (reference["maps"]["A"]["excess_over_full"][k]["absolute_statistics"]["mean"]
                           for k in ("metric", "angular"))
        params.update({
            "sheaves": sheaves, "sheaf_record": diag["id"], "sheaf_sha256": stamp,
            "mean_excess_budgets": {"balanced": [metric * 1.35, angular * 1.35],
                                   "metric-priority": [metric * 1.18, angular * 2.0],
                                   "angular-priority": [metric * 2.0, angular * 1.18],
                                   "loose": [metric * 2.2, angular * 2.2]},
            "sample_origins": 8, "beam_rounds": 36, "beam_width": 2, "proposal_window": 14,
            "block_sizes": [2, 4], "complete_shortlist": 5, "beam_exchanges": 2,
            "sheaf_double_trials": 8, "sheaf_replacements": 3,
        })
    module, method = "route_sparse_experiment", kind
    if kind == "matched":
        module, method = "route_sparse_matched", "matched_exchanges"
        params.update({"exchange_rounds": 3, "addition_limit": 6, "removal_limit": 6})
    result = run_stage(store, "validation", f"voronoi_app.{module}:{method}",
                       params, parent, "2" if kind == "sparse_routes" else "1")
    with path.open("xb") as stream:
        stream.write(encode({"record": result["id"], "status": result["status"],
                             "error": result.get("error")}))
    print(path, result["status"], result.get("error"), flush=True)
    return int(result["status"] != "successful")


def saved_comparison(store, case, directory):
    state = read(directory / f"{case}-sparse_routes.json")
    record, data, checksum = store.load(state["record"])
    if record["status"] != "successful":
        raise ValueError("A successful sparse search is required.")
    references = {record["id"]: checksum}
    matched_path = directory / f"{case}-matched.json"
    if matched_path.exists():
        control, matched, stamp = store.load(read(matched_path)["record"])
        if control["status"] != "successful" or control["parent"] != record["parent"]:
            raise ValueError("The matched-count search does not share the validated inputs.")
        references[control["id"]] = stamp
        data["maps"].extend(row | {"name": "matched"} for row in matched["improvements"])
        data["pareto_indices"] = pareto(data["maps"])
    return record, data, references


def audit(case, directory):
    path = directory / f"{case.replace(' ', '-')}-audit.json"
    if path.exists():
        raise FileExistsError(path)
    store = BatchStore(ROOT)
    record, data, references = saved_comparison(store, case.replace(" ", "-"), directory)
    maps = [{"index": i, "line_ids": data["maps"][i]["line_ids"],
             "unreachable": data["maps"][i]["routing"]["metric"]["cost"]["unreachable"]}
            for i in data["pareto_indices"]]
    params = {"source_records": references, "maps": maps,
              "doorways": record["parameters"]["reference"]["doorways"]}
    result = run_stage(store, "validation", "voronoi_app.route_sparse_validation:validate_retained",
                       params, record["parent"]["id"], "1")
    with path.open("xb") as stream:
        stream.write(encode({"record": result["id"], "status": result["status"],
                             "error": result.get("error")}))
    print(path, result["status"], result.get("error"), flush=True)
    return int(result["status"] != "successful")


def export(directory):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    from shapely import from_wkb

    if (directory / "comparison.csv").exists():
        raise FileExistsError(directory / "comparison.csv")
    store = BatchStore(ROOT)
    rows, marginals, alternatives = [], [], []
    for case in ("Hill-42", "Y-42"):
        record, data, _ = saved_comparison(store, case, directory)
        inputs = store._inputs("validation", record["parent"]["id"])
        settlement = inputs["settlement"][1]
        candidates = inputs["candidates"][1]["pool"]["candidates"]
        frontier = set(data["pareto_indices"])
        for item in data["marginal"]:
            row = {"case": case, "removed": item["removed"], "classification": item["classification"],
                   "constraint_status": item["constraints"]["status"]}
            row.update({k: item["constraints"][k] for k in (
                "coverage_regions", "required_regions", "components", "rank", "required_rank",
                "unattached_doors",
            )})
            for k, measure in item["relative_to_start"].items():
                for field in ("cost", "absolute"):
                    row.update({f"{k}_{field}_{stat}": value for stat, value in measure[field].items()})
                row[f"{k}_p95_shift"] = (measure["cost"]["p95"] - data["base"]["routing"][k]["cost"]["p95"]
                                         if measure["cost"]["p95"] is not None else None)
                row[f"{k}_max_shift"] = (measure["cost"]["max"] - data["base"]["routing"][k]["cost"]["max"]
                                         if measure["cost"]["max"] is not None else None)
            marginals.append(row)
        original = set(data["base"]["line_ids"])
        for group in data["sheaves"]:
            for item in group["alternatives"]:
                selected = set(item["line_ids"])
                row = {"case": case, "sheaf": group["group"], "kind": item["kind"],
                       "lines": len(selected), "status": item["constraints"]["status"],
                       "removed_ids": " ".join(map(str, sorted(original - selected))),
                       "added_ids": " ".join(map(str, sorted(selected - original)))}
                for k in ("metric", "angular"):
                    route = item.get("relative_to_start", {}).get(k, {})
                    row.update({f"{k}_delta_{stat}": route.get("absolute", {}).get(stat)
                                for stat in ("mean", "p95", "max")})
                alternatives.append(row)
        figure, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
        for i, entry in enumerate(data["maps"]):
            row = {"case": case, "map": entry["name"], "index": i,
                   "pareto": i in frontier, "line_count": entry["line_count"], "length": entry["length"],
                   "selected_ids": " ".join(map(str, entry["line_ids"])),
                   "route_seconds": entry["route_seconds"],
                   **{k: entry["constraints"].get(k) for k in
                      ("status", "coverage_regions", "required_regions", "components", "rank", "required_rank")}}
            for ax, k in zip(axes, ("metric", "angular"), strict=True):
                measure = entry["routing"][k]
                for group, stats in measure.items():
                    row.update({f"{k}_{group}_{stat}": value for stat, value in stats.items()})
                style = {"A": ("black", "s"), "beam": ("#217ab4", "o"), "B": ("#aa4326", "D"),
                         "matched": ("#427c2a", "*")}
                colour, marker = style.get(entry["name"], ("#888888", "^"))
                ax.scatter(entry["line_count"], measure["absolute"]["mean"], s=30, color=colour,
                           marker=marker, alpha=1 if i in frontier else .38)
                ax.set(xlabel="Selected lines", ylabel=f"Mean absolute {k} excess")
                ax.grid(alpha=.25)
            rows.append(row)
        figure.suptitle(f"{case} · Squares entrance guided, circles beam, diamonds best backward, stars matched")
        with (directory / f"{case}-pareto.png").open("xb") as stream:
            figure.savefig(stream, format="png", dpi=155)
        plt.close(figure)
        beam = [data["maps"][i] for i in frontier if data["maps"][i]["name"] in ("beam", "matched")]
        if beam:
            beam_counts = [row["line_count"] for row in beam if row["name"] == "beam"]
            sparse_limit = min(beam_counts or [row["line_count"] for row in beam]) + 8
            sparse = [row for row in beam if row["line_count"] <= sparse_limit]
            count = Counter(i for row in sparse for i in row["line_ids"])
            figure, ax = plt.subplots(figsize=(10, 9), layout="constrained")
            for key, value in settlement["polygons_wkb"].items():
                label = settlement["building_labels"].get(key)
                if label is not None:
                    poly = from_wkb(value)
                    x, y = poly.exterior.xy
                    ax.fill(x, y, color="#393939")
                    xy = poly.representative_point()
                    ax.text(xy.x, xy.y, str(label), color="white", size=5,
                            ha="center", va="center", zorder=4)
            lines = sorted(count, key=lambda i: (count[i], i))
            segments = [interval(candidates[i]) for i in lines]
            lc = LineCollection(segments, cmap="viridis", norm=Normalize(0, 1),
                                array=[count[i] / len(sparse) for i in lines], linewidths=1.2, zorder=3)
            ax.add_collection(lc)
            ax.autoscale()
            ax.set(aspect="equal", title=f"{case} · {len(sparse)} sparse Pareto maps")
            ax.axis("off")
            figure.colorbar(lc, ax=ax, label="Fraction of sparse maps retaining line", shrink=.6)
            with (directory / f"{case}-survival.png").open("xb") as stream:
                figure.savefig(stream, format="png", dpi=180)
            plt.close(figure)
            with (directory / f"{case}-survival.json").open("xb") as stream:
                stream.write(encode({
                    "maps": len(sparse), "maximum_lines": sparse_limit, "counts": dict(count),
                    "intervals": {i: [candidates[i]["start"], candidates[i]["end"]] for i in lines},
                }))
    for filename, data in (("comparison.csv", rows), ("marginal.csv", marginals),
                           ("sheaf-alternatives.csv", alternatives)):
        with (directory / filename).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows({k: "null" if value is None else value for k, value in row.items()}
                             for row in data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--case", choices=["Hill 42", "Y 42"])
    parser.add_argument("--kind", choices=["sparse_routes", "sensitivity", "matched", "audit"])
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.export:
        export(args.directory)
        return 0
    if args.case is None or args.kind is None:
        parser.error("--case and --kind are required when running a stage")
    if args.kind == "audit":
        return audit(args.case, args.directory)
    return run(args.case, args.kind, args.directory)


if __name__ == "__main__":
    raise SystemExit(main())
