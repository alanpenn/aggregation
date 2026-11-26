"""Supplementary archived strict-backward analysis across available terrain seeds."""

import argparse
from collections import defaultdict
from hashlib import sha256
import csv
import os
from pathlib import Path
import sys
from time import perf_counter
import resource

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from experiments.configurational_sources import MATCH_KEYS
from experiments.configurational_seed_sources import load_strict_cohort
from experiments.configurational_reporting import LABELS, finish, name
from experiments.flat40_configurational import METRICS, canonical, check, json_file, read
from experiments.six_terrain_configurational import analyze, checkpoint, graph_summary, MODES
from voronoi_app.configurational import axial_graph


def scalar(summary, field):
    if field == "intelligibility":
        return summary["intelligibility"]["r"]
    if field in summary["choice_concentration"]:
        return summary["choice_concentration"][field]
    return summary["measures"][field]["mean"]


def group_variability(cases, rows):
    groups = defaultdict(list)
    setting_groups = defaultdict(list)
    for key, case in cases.items():
        meta = case.inventory
        signature = {k: meta["settings"][k] for k in MATCH_KEYS if k != "seed"}
        signature["building_count"] = meta["building_count"]
        setting_groups[sha256(canonical(signature)).hexdigest()].append(key)
    matched = max(setting_groups.values(), key=len)
    for key in matched:
        groups[cases[key].inventory["terrain"]].append(key)
    common_seeds = sorted(set.intersection(*[{cases[key].inventory["seed"] for key in keys}
                                             for keys in groups.values()]))
    check(common_seeds, "Recovered cohort has no common seeds.")
    unmatched = sorted(set(cases) - set(matched))
    results = {}
    for kind in MODES:
        for field in (*METRICS, "intelligibility", "gini", "top_10_share"):
            within = {}
            for terrain, keys in groups.items():
                vals = [scalar(rows[key][kind], field) for key in keys]
                if any(v is None for v in vals):
                    continue
                within[terrain] = {"observations": dict(zip(keys, vals)), "n": len(vals), "mean": float(np.mean(vals)),
                                   "range": max(vals)-min(vals), "sample_sd": float(np.std(vals, ddof=1)) if len(vals)>1 else None}
            terrain_means = {
                terrain: float(np.mean([value for key, value in r["observations"].items()
                                        if cases[key].inventory["seed"] in common_seeds]))
                for terrain, r in within.items()
            }
            between = max(terrain_means.values())-min(terrain_means.values())
            results[f"{kind}/{field}"] = {"within_terrain": within, "matched_seed_terrain_means": terrain_means,
                                         "between_terrain_mean_range": between,
                                         "largest_observed_within_terrain_range": max(x["range"] for x in within.values()),
                                         "between_exceeds_each_within_range": all(between > x["range"] for x in within.values())}
    return {"settings_groups": dict(setting_groups), "matched": sorted(matched),
            "unmatched_illustrative": unmatched, "common_seeds_for_between_terrain_means": common_seeds,
            "comparison": results}



def export_variability(out, cases, summaries):
    audit = group_variability(cases, summaries)
    results = audit["comparison"]
    json_file(out / "variability.json", audit)
    json_file(out / "statistics.json", summaries)
    with (out / "observations.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        fields = (*METRICS, "intelligibility", "gini", "top_10_share")
        writer.writerow(["case", "terrain", "seed", "role", "representation", *fields])
        for key, case in cases.items():
            for kind in MODES:
                writer.writerow([key, case.inventory["terrain"], case.inventory["seed"],
                                 "matched settings" if key in audit["matched"] else "unmatched illustrative", kind,
                                 *(scalar(summaries[key][kind], field) for field in fields)])
    with PdfPages(out / "seed-variability.pdf") as pdf:
        for field in ("intelligibility", "gini", "mean_depth", "integration"):
            fig, panels = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
            for kind, ax in zip(MODES, panels.flat):
                terrains = results[f"{kind}/{field}"]["within_terrain"]
                for i, (terrain, row) in enumerate(terrains.items()):
                    values = list(row["observations"].values())
                    ax.scatter([i]*len(values), values, s=22)
                    ax.scatter([i], [row["mean"]], marker="_", color="black", s=120)
                ax.set(xticks=range(len(terrains)), xticklabels=[f"{name(x)} (n={r['n']})" for x, r in terrains.items()], title=LABELS[kind])
                ax.tick_params(axis="x", labelrotation=18)
            fig.suptitle(f"Archived strict-backward sensitivity · {field.replace('_', ' ').title()}")
            finish(pdf, fig)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=os.environ.get("AGGREGATION_DATA_ROOT"))
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.data:
        parser.error("Set AGGREGATION_DATA_ROOT or use --data.")
    sys.set_int_max_str_digits(0)
    started = perf_counter()
    primary = read(args.primary / "verified-hashes.json")
    cases, missing, hashes = load_strict_cohort(args.data, primary["flat40_inputs"]["migration_inventory"])
    out = args.output
    out.mkdir(parents=True)
    json_file(out / "verified-hashes.json", hashes)
    json_file(out / "source-inventory.json", {k: v.inventory for k,v in cases.items()})
    json_file(out / "missing-inputs.json", missing)
    summaries = {}
    for key, case in cases.items():
        graph = axial_graph(case.lines)
        check(graph.number_of_edges() == case.inventory["archived_intersection_count"],
              f"Exact intersection count differs: {key}")
        data = analyze(case.lines, {tuple(sorted(edge)) for edge in graph.edges})
        summaries[key] = graph_summary(data)
        checkpoint(out, key, data, summaries[key])
    export_variability(out, cases, summaries)
    json_file(out / "runtime.json", {"elapsed_seconds": perf_counter()-started,
         "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == "darwin" else 1024)})
    print(f"Strict-backward seed sensitivity: {len(cases)} verified cases, {len(missing)} missing")


if __name__ == "__main__":
    main()
