"""Export exact selected intervals and numbered maps for the facewise cohort."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
from time import sleep
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Rectangle
from shapely import from_wkb

from experiments.audit_facewise_growth import prefix_audit, replay
from experiments.facewise_matched import metrics
from experiments.facewise_rerun import ROOT
from experiments.plot_facewise_matched import plot_case
from experiments.strict_generalisation import CASES, ROOT as LEGACY, case_path
from experiments.strict_generalisation_export import METHODS, screened_methods
from voronoi_app.batch_routing_reference import interval
from voronoi_app.batch_store import BatchStore, atomic_write, encode

TITLES = dict(zip(METHODS, ("Full certified pool", "Strict entrance-guided",
                          "Strict backward", "Geometric extreme pair", "Route-ranked pair"), strict=True))


def write_table(path, rows):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def rows_for_case(journal, store, path):
    stages = journal["stages"]
    payloads = {name: store.load(entry["record"]) for name, entry in stages.items()}
    settlement = payloads.get("settlement", (None, None, None))[1]
    if settlement is None:
        raise ValueError(f"{journal['case']} has no saved settlement geometry for numbered maps.")
    topology = (payloads.get("topology", (None, None, None))[1] or {}).get("topology", {})
    candidates = payloads.get("candidates", (None, None, None))[1] or {}
    analysis = payloads.get("analysis", (None, None, None))
    data = analysis[1] or {}
    methods, screen, screen_id = screened_methods(store, path, journal, stages.get("analysis"), analysis[2], data)
    polygons = {int(i): from_wkb(wkb) for i, wkb in settlement["polygons_wkb"].items()}
    regions = {int(i): from_wkb(wkb) for i, wkb in candidates.get("regions_wkb", {}).items()}
    lines = candidates.get("pool", {}).get("candidates", [])
    assigned = set(settlement["dyad_open_cells"])
    excluded = set(topology.get("excluded_open_cells", []))
    failure = next((entry for entry in stages.values() if entry["status"] != "successful"), {})
    failure_reason = (failure.get("error") or {}).get("message")
    if "analysis" not in stages and lines:
        candidate_validation = candidates.get("geometric_certification", {})
        methods["full_pool"] = {
            "status": "invalid", "reason": failure_reason or
            "Candidate certification failed. " + json.dumps(candidate_validation, sort_keys=True),
            "line_ids": list(range(len(lines))), "line_count": len(lines),
        }
    certificate = settlement["aggregation_certificate"]
    internal = len(topology["internal_blocks"]) if topology else None
    holes = len(topology["circulation_holes"]) if topology else None
    common = {
        "case": journal["case"], "terrain": journal["terrain"], "seed": journal["seed"],
        **{f"{name}_record": stages.get(name, {}).get("record") for name in ("settlement", "topology", "candidates", "analysis")},
        "physical_screen_record": screen_id,
        "configuration": json.dumps(journal["configuration"], sort_keys=True),
        "aggregation_valid": certificate["valid"], "completed_dyads": len(settlement["doors"]),
        "assigned_open_components": certificate["assigned_open_components"],
        "excluded_assigned": len(excluded & assigned) if topology else None,
        "excluded_unassigned": len(excluded - assigned) if topology else None,
        "excluded_open": len(excluded) if topology else None,
        "internal_blocks": internal, "accessible_holes": holes,
        "boundary_blocks": sum(block["kind"] == "boundary" for block in topology.get("occupied_blocks", [])) if topology else None,
        "rank_hole_count_agrees": internal == holes if topology else None, "required_rank": internal,
        "candidates": len(lines) if candidates else None, "required_regions": len(regions) if candidates else None,
        "doorways": len(data["doorways"]) if "doorways" in data else None,
        "excluded_doorways": len(data["excluded_doors"]) if "excluded_doors" in data else None,
        "eligible_pairs": len(data["pairs"]) if "pairs" in data else None,
        "corridors": sum(row["accepted"] for row in screen) if "corridors" in data else None,
        "generation_seconds": sum(stages[key]["seconds"] for key in ("settlement", "topology", "candidates") if key in stages),
        "analysis_seconds": stages.get("analysis", {}).get("seconds"),
        "peak_worker_rss_mib": max(entry["peak_rss_mib"] for entry in stages.values()),
    }
    incidence = data.get("incidence", {})
    single_regions = [int(i) for i, ids in incidence.get("region_lines", {}).items() if len(ids) == 1]
    single_doors = [i for i, groups in enumerate(incidence.get("doorway_regions", []))
                    if len({line for group in groups for line in incidence["region_lines"][str(group)]}) == 1]
    outputs = {}
    for method in METHODS:
        result = methods.get(method, {})
        reason = result.get("reason") or "; ".join(data.get("failure_reasons", [])) or failure_reason
        status = result.get("status", "failed" if failure else "unsupported")
        if not result:
            reason = reason or "Upstream strict map could not be established."
        candidates_for_plot = result.get("line_ids", result.get("attempted_line_ids", []))
        if not candidates_for_plot and status == "invalid" and method in METHODS[-2:]:
            key = "extreme" if method == "geometric_extreme" else "best_ranked"
            for band, screened in zip(data.get("corridors", []), screen, strict=True):
                if screened["accepted"] and band["trials"]:
                    attempt = band[key] or band["trials"][0]
                    candidates_for_plot = attempt["line_ids"]
                    result = result | {"failed_trial": attempt, "constraints": attempt["constraints"]}
                    reason = (reason or "") + " " + attempt.get("reason", "")
                    break
        constraints = result.get("constraints", {})
        costs = result.get("routing", {})
        if status == "valid" and any(costs[name]["cost"]["unreachable"] for name in ("angular", "metric")):
            status, reason = "invalid", "Incomplete doorway route reachability."
        stats = common | {"method": method, "status": status, "reason": reason, "lines": result.get("line_count"),
                          "length": result.get("length"), "intersections": result.get("intersections"),
                          "components": constraints.get("components"), "rank": constraints.get("rank"),
                          "covered_regions": len(regions) - len(constraints["missing_regions"]) if "missing_regions" in constraints else None,
                          "evaluation_seconds": result.get("evaluation_seconds"),
                          "evaluation_peak_rss_mib": result.get("evaluation_peak_rss_mib")}
        for name, values in costs.items():
            for category, measures in values.items():
                stats.update({f"{name}_{category}_{key}": value for key, value in measures.items()})
            stats[f"{name}_zero_baselines"] = sum(value == 0 for value in data["maps"]["full_pool"]["routes"][name])
            stats[f"{name}_undefined_proportions"] = len(data["pairs"]) - values["proportional"]["reachable"]
        if len(set(candidates_for_plot)) != len(candidates_for_plot) or any(lines[i]["id"] != i for i in candidates_for_plot):
            raise ValueError("Selection IDs do not match the exact candidate inventory.")
        outputs[method] = {"stats": stats, "result": result, "selected_intervals": [
            {key: lines[i][key] for key in ("id", "start", "end")} for i in candidates_for_plot]}
    return settlement, topology, polygons, regions, outputs, data, screen, single_regions, single_doors


def draw_axial(ax, settlement, topology, polygons, regions, item, title, small=False, changes=None):
    stats = item["stats"]
    buildings = settlement["building_labels"]
    main = topology.get("main_open_cells", [])
    ax.add_collection(PolyCollection([polygons[i].exterior.coords for i in main], facecolors="#d8ebea",
                                     edgecolors="none"))
    ax.add_collection(PolyCollection([polygons[int(i)].exterior.coords for i in buildings],
                                     facecolors="#545b62", edgecolors="#343a3f", linewidths=.25))
    missing = item["result"].get("constraints", {}).get("missing_regions", [])
    ax.add_collection(PolyCollection([regions[i].exterior.coords for i in missing],
                                     facecolors="#ffc4b1", edgecolors="#a94639", linewidths=.35))
    if changes is None:
        segments = [interval(line) for line in item["selected_intervals"]]
        collection = LineCollection(segments, colors="#155b94", alpha=.6, linewidths=.6, zorder=3)
        ax.add_collection(collection)
        expected = [[[float(value) for value in point] for point in segment] for segment in segments]
        if [segment.tolist() for segment in collection.get_segments()] != expected:
            raise ValueError("Plotted axial intervals differ from the saved selection.")
    else:
        for lines, color in changes:
            ax.add_collection(LineCollection([interval(line) for line in lines], colors=color, linewidths=.6, zorder=3))
    for i, label in buildings.items():
        point = polygons[int(i)].representative_point()
        ax.text(point.x, point.y, label, ha="center", va="center", color="white", fontsize=3.4 if small else 5.5, zorder=4)
    x0, y0, x1, y1 = settlement["grid"]["extent"]
    ax.add_patch(Rectangle((x0,y0), x1-x0,y1-y0, fill=False, linewidth=.7, edgecolor="#33383e"))
    ax.set(xlim=(x0,x1), ylim=(y0,y1), aspect="equal")
    ax.set_axis_off()
    size = 8 if small else 11

    def label(value):
        return "—" if value is None else str(value)

    ax.set_title(f"{title}\n{stats['status'].capitalize()} · {label(stats['lines'])} lines"
                 f" · Rank {label(stats['rank'])}/{label(stats['required_rank'])}\n"
                 f"Strict region coverage {label(stats['covered_regions'])}/{label(stats['required_regions'])}", fontsize=size)
    if stats["reason"]:
        from textwrap import fill
        ax.text(.5, -.025, fill(stats["reason"], 38 if small else 85), transform=ax.transAxes,
                va="top", ha="center", color="#902f28", fontsize=size-2)


def save(fig, root, stem, atlas):
    for ext in ("png", "pdf"):
        fig.savefig(root / f"{stem}.{ext}", dpi=310, bbox_inches="tight", facecolor="white")
    atlas.savefig(fig, bbox_inches="tight")
    plt.close(fig)
    return {kind: f"numbered-maps/{stem}.{kind}" for kind in ("png", "pdf")}


def aggregation_comparison(journal, legacy, settlement, topology, polygons, visual_dir, atlas):
    case = journal["case"]
    old_journal = json.loads(case_path(LEGACY, journal["terrain"], journal["seed"]).read_bytes())
    old_id = old_journal["stages"]["settlement"]["record"]
    old = legacy.load(old_id)[1]
    old_top = legacy.load(old_journal["stages"]["topology"]["record"])[1]["topology"]
    old_polygons = {int(i): from_wkb(wkb) for i, wkb in old["polygons_wkb"].items()}
    if old["polygons_wkb"] != settlement["polygons_wkb"]:
        raise ValueError("Matched aggregation plot requires identical clipped cell coordinates.")
    old_rows = prefix_audit(old["doors"], old["building_labels"], replay(old), old_polygons)
    new_rows = settlement["aggregation_certificate"]["placements"]
    summary = {"legacy_settlement": old_id, "corrected_settlement": journal["stages"]["settlement"]["record"],
               "legacy": metrics(old, old_top, old_rows),
               "corrected": metrics(settlement, topology, new_rows) if topology else
                   {"dyads": len(new_rows), "assigned_components": settlement["aggregation_certificate"]["assigned_open_components"]}}
    plot_case(visual_dir, case, polygons, old, settlement, old_rows, new_rows, summary, atlas=atlas)
    files = {name: {ext: f"numbered-maps/{case}-{name}.{ext}" for ext in ("png", "pdf")}
             for name in ("comparison", "corrected-parents", "named-closeups")
             if (visual_dir / f"{case}-{name}.pdf").exists()}
    return summary, {"aggregation": files, "legacy_settlement": old_id, "legacy_placement_audit": old_rows}


def export_aggregation(root):
    store, legacy = BatchStore(root), BatchStore(LEGACY)
    visual_dir = root / "numbered-maps"
    visual_dir.mkdir(exist_ok=True)
    atlas_path = root / "numbered-aggregation-atlas.pdf"
    rows, index = [], []
    with PdfPages(atlas_path.with_suffix(".tmp")) as atlas:
        for terrain, seed in CASES:
            journal = json.loads(case_path(root, terrain, seed).read_bytes())
            stages = journal["stages"]
            settlement = store.load(stages["settlement"]["record"])[1]
            topology = store.load(stages["topology"]["record"])[1]["topology"]
            polygons = {int(i): from_wkb(wkb) for i, wkb in settlement["polygons_wkb"].items()}
            summary, visuals = aggregation_comparison(journal, legacy, settlement, topology, polygons, visual_dir, atlas)
            rows.extend({"case": journal["case"], "variant": variant, **summary[variant]}
                        for variant in ("legacy", "corrected"))
            index.append({"case": journal["case"], "settlement_record": stages["settlement"]["record"],
                          "topology_record": stages["topology"]["record"], **visuals})
    atlas_path.with_suffix(".tmp").replace(atlas_path)
    write_table(root / "aggregation-comparisons.csv", rows)
    atomic_write(root / "aggregation-visual-index.json", encode({"atlas": atlas_path.name, "cases": index}))


def export(root):
    store, legacy = BatchStore(root), BatchStore(LEGACY)
    visual_dir = root / "numbered-maps"
    visual_dir.mkdir(exist_ok=True)
    rows, index, comparisons, bands = [], [], [], []
    atlas_path = root / "numbered-axial-atlas.pdf"
    with PdfPages(atlas_path.with_suffix(".tmp")) as atlas:
        for terrain, seed in CASES:
            path = case_path(root, terrain, seed)
            if not path.exists():
                continue
            journal = json.loads(path.read_bytes())
            if all(entry["status"] == "successful" for entry in journal["stages"].values()) and "analysis" not in journal["stages"]:
                continue
            case = journal["case"]
            settlement, topology, polygons, regions, outputs, data, screen, single_regions, single_doors = rows_for_case(journal, store, path)
            terrain_name = "Hill" if terrain == "hill" else "Converging Valleys (Y)"
            config = settlement["configuration"]
            ap, gp = config["aggregation_params"], config["grid_params"]
            subtitle = (f"{terrain_name} · seed {seed} · {gp['num_points']} sites · jitter {gp['jitter_ratio']} · "
                        f"canvas {config['canvas_size']:g}\nSlope {ap['building_slope_preference']} · contour {ap['contour_preference']}"
                        f" · dyad limit {ap['max_dyads']} · stagnation limit {ap['stagnation_limit']}")
            lineage = {key: value["record"] for key, value in journal["stages"].items()}
            entry = {"case": case, "records": lineage, "methods": {},
                     "singleton_regions": single_regions, "singleton_doorways": single_doors}
            for method, item in outputs.items():
                fig, ax = plt.subplots(figsize=(8, 8.9), layout="constrained")
                fig.suptitle(subtitle)
                draw_axial(ax, settlement, topology, polygons, regions, item, TITLES[method])
                item["visual"] = save(fig, visual_dir, f"{case}-{method}", atlas)
                entry["methods"][method] = item
                rows.append(item["stats"] | {"png": item["visual"]["png"], "pdf": item["visual"]["pdf"]})
            fig, axes = plt.subplots(1, 5, figsize=(18, 5), layout="constrained")
            fig.suptitle(subtitle)
            for (method, item), ax in zip(outputs.items(), axes, strict=True):
                draw_axial(ax, settlement, topology, polygons, regions, item, TITLES[method], small=True)
            entry["sheet"] = save(fig, visual_dir, f"{case}-methods", atlas)
            for method in METHODS[-2:]:
                item = outputs[method]
                if item["stats"]["status"] != "valid":
                    continue
                before = {line["id"]: line for line in outputs["strict_backward"]["selected_intervals"]}
                after = {line["id"]: line for line in item["selected_intervals"]}
                removed, added = sorted(before.keys()-after.keys()), sorted(after.keys()-before.keys())
                fig, ax = plt.subplots(figsize=(8, 8.9), layout="constrained")
                fig.suptitle(subtitle)
                draw_axial(ax, settlement, topology, polygons, regions, item,
                           f"{TITLES[method]} · removed {len(removed)} (red), added {len(added)} (green)",
                           changes=[([before[i] for i in removed], "#ae2438"), ([after[i] for i in added], "#16745b")])
                item["substitution"] = save(fig, visual_dir, f"{case}-{method}-changes", atlas) | {"removed_ids": removed, "added_ids": added}
            summary, aggregation_index = aggregation_comparison(
                journal, legacy, settlement, topology, polygons, visual_dir, atlas)
            entry.update(aggregation_index)
            entry["physical_bands"] = screen
            for variant in ("legacy", "corrected"):
                comparisons.append({"case": case, "variant": variant, **summary[variant]})
            for i, (band, screening) in enumerate(zip(data.get("corridors", []), screen, strict=True), 1):
                bands.append({"case": case, "band": i, **screening, "qualifying_pairs": band["qualifying_pairs"],
                              "tested_pairs": len(band["trials"])})
            if "full_pool" in data.get("maps", {}) and "routes" in data["maps"]["full_pool"]:
                reference_path = root / "route-references" / f"{case}.json"
                reference_path.parent.mkdir(exist_ok=True)
                if not reference_path.exists():
                    reference = {"identity": {"candidate_record": lineage["candidates"], "doorways": data["doorways"],
                                              "pairs": data["pairs"]}, **data["maps"]["full_pool"]["routes"]}
                    atomic_write(reference_path, encode(reference))
                saved_reference = json.loads(reference_path.read_bytes())
                if any(saved_reference[name] != values for name, values in data["maps"]["full_pool"]["routes"].items()):
                    raise ValueError(f"{case} route checkpoint differs from analysis.")
                entry["route_reference"] = {"file": str(reference_path.relative_to(root)),
                                            "sha256": sha256(reference_path.read_bytes()).hexdigest()}
            # Raw arrays stay in immutable analysis records and checkpoint files.
            for item in entry["methods"].values():
                item["result"] = {key: value for key, value in item["result"].items() if key != "routes"}
            index.append(entry)
    if not index:
        return
    atlas_path.with_suffix(".tmp").replace(atlas_path)
    write_table(root / "statistics.csv", rows)
    write_table(root / "aggregation-comparisons.csv", comparisons)
    write_table(root / "corridors.csv", bands)
    atomic_write(root / "visual-index.json", encode({"atlas": atlas_path.name, "case_count": len(index),
                                                   "method_count": len(rows), "cases": index}))
    report(root, rows, comparisons, index)
    if len(index) == len(CASES):
        artifacts = [*root.glob("numbered-maps/*"), *root.glob("route-references/*.json"),
                     *root.glob("*.csv"), *root.glob("*-atlas.pdf"), *root.glob("*-index.json"), root / "report.md"]
        publication = {"settlements": len(index), "methods": len(rows),
                       "statuses": dict(Counter(row["status"] for row in rows)),
                       "case_records": {entry["case"]: entry["records"] for entry in index},
                       "files_sha256": {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
                                        for path in sorted(artifacts)}}
        atomic_write(root / "export-record.json", encode(publication))


def report(root, rows, comparisons, index):
    indexed = {entry["case"] for entry in index}
    with (LEGACY / "comparison.csv").open(newline="") as stream:
        old = {(row["case"], row["method"]): row for row in csv.DictReader(stream)}
    store = BatchStore(LEGACY)
    for terrain, seed in CASES:
        path = case_path(LEGACY, terrain, seed)
        journal = json.loads(path.read_bytes())
        candidate_record = journal["stages"]["candidates"]["record"]
        candidates = store.load(candidate_record)[1]["pool_summary"]["candidates"]
        for method in METHODS:
            old[path.stem, method]["candidates"] = candidates
    keys = ("internal_blocks", "accessible_holes", "candidates", "corridors", "lines", "angular_cost_mean", "metric_cost_mean",
            "generation_seconds", "analysis_seconds", "peak_worker_rss_mib")
    write_table(root / "legacy-method-comparisons.csv", [
        {"case": row["case"], "method": row["method"], "legacy_status": old[row["case"], row["method"]]["status"],
         "corrected_status": row["status"], **{f"{variant}_{key}": record.get(key) for key in keys
         for variant, record in (("legacy", old[row["case"], row["method"]]), ("corrected", row))}}
        for row in rows])
    counts = Counter(row["status"] for row in rows)
    backward = {row["case"]: row for row in rows if row["method"] == "strict_backward"}
    valid_pairs = [(seed, backward[f"hill-{seed}"]["lines"], backward[f"converging_valleys-{seed}"]["lines"])
                   for seed in range(40, 46) if all(backward.get(f"{terrain}-{seed}", {}).get("status") == "valid"
                                                  for terrain in ("hill", "converging_valleys"))]
    outcome = ", ".join(f"{n} {status}" for status, n in sorted(counts.items()))
    paired_summary = (f"Hill had more strict backward lines in {sum(h > y for _, h, y in valid_pairs)} of "
                      f"{len(valid_pairs)} seed pairs with a validated result on both terrains."
                      if valid_pairs else "No seed pair in this export has a validated backward map on both terrains.")
    lines = ["# Corrected facewise axial and movement experiment", "", "## Executive summary", "",
             f"The export includes {len(indexed)} of 12 settlements and {len(rows)} of 60 method records ({outcome}).",
             paired_summary, "", "## Aggregation, topology and circulation", "",
             "The legacy growth rule admitted Voronoi ridge neighbours with no positive-length clipped face. "
             "The corrected strategy builds the clipped face graph before placing the seed dyad and uses it for both links of each extension. "
             "Independent placement certificates recompute the face lengths and verify unique assignments, the recorded parent, and seed connectivity at every growth prefix.",
             "Slope and contour scores retain their original formula and weights. The corrected candidate order follows cell IDs, "
             "so random scores and growth histories can diverge even when a legacy seed never placed an invalid dyad.",
             "The grid and aggregation use the archived seed with NumPy's legacy random stream and Python's seeded random stream for aggregation. "
             "Each immutable batch record lists method, package source hashes, runtime versions and parent output hashes.",
             "", "| Case | Cohort | Dyads | Assigned-open components | Excluded assigned | Excluded unassigned | Internal blocks | Geometric holes |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in comparisons:
        lines.append("| " + " | ".join(str(row.get(key, "—")) for key in ("case", "variant", "dyads", "assigned_components", "excluded_assigned", "excluded_unassigned", "internal_blocks", "circulation_holes")) + " |")
    lines.extend(["", "In Y 40 and Y 41 the disconnected assigned-open cells disappeared. "
                  "The unassigned exclusions increased from 54 to 184 and from 115 to 130, respectively. "
                  "They are cells cut off from the main accessible component by the corrected building arrangement. "
                  "Y 45 also has a large unassigned exclusion. See the aggregation table for the seed-specific counts.",
                  "The open-space graph uses positive shared length. Occupied blocks group both vertex and face contacts. "
                  "The two rightmost columns independently compare occupied-block requirements with holes of the accessible polygon.",
                  "", "## Axial selection and movement", "",
                  "Angular costs are in quarter turns with zero angular entry and exit cost through incident regions. "
                  "Metric costs include certified regional connectors and travel along the selected intervals. They are shortest paths in the finite certified graph.",
                  "Each eligible doorway is the exact shared-face midpoint of the saved building–open dyad. "
                  "Regional attachments allow certified projections and feasible interval endpoints on every line traversing an incident convex region. "
                  "The same doorway pair order is used within each settlement. The full-pool arrays are computed once and saved with that order.",
                  "Absolute excess is computed per comparable pair against the full pool. Proportional excess uses the positive full-pool cost as the denominator. "
                  "The statistics file reports zero baselines and the number of undefined proportions.",
                  "Strict entrance-guided starts from winding supports and adds lines for incidence and angular access. "
                  "Strict backward applies shortest-first iterative deletion from the guided set with structural checks. "
                  "The two corridor methods share the legacy physical band screen and trial limits. The extreme pair is ordered geometrically within a band. "
                  "The route-ranked method ranks admissible trials by the archived angular and length criteria.",
                  "", "| Case | Method | Status | Lines | Winding/required | Angular mean | Metric mean |",
                  "|---|---|---|---:|---:|---:|---:|"])
    for row in rows:
        def fmt(value):
            return "—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"| {row['case']} | {TITLES[row['method']]} | {row['status']} | {fmt(row['lines'])} | "
                     f"{fmt(row['rank'])}/{fmt(row['required_rank'])} | {fmt(row.get('angular_cost_mean'))} | {fmt(row.get('metric_cost_mean'))} |")
    problems = [row for row in rows if row["status"] != "valid" and row["reason"]]
    if problems:
        lines += ["", "### Invalid or unsupported results", ""]
        lines.extend(f"- {row['case']} · {TITLES[row['method']]} — {row['reason']}" for row in problems)
    if valid_pairs:
        lines += ["", "### Matched strict backward counts", "",
                  "| Seed | Legacy Hill | Corrected Hill | Legacy Y | Corrected Y | Corrected Hill minus Y |",
                  "|---|---:|---:|---:|---:|---:|"]
        for seed, h, y in valid_pairs:
            legacy_hill = old[f"hill-{seed}", "strict_backward"]["lines"]
            legacy_y = old[f"converging_valleys-{seed}", "strict_backward"]["lines"]
            lines.append(f"| {seed} | {legacy_hill} | {h} | {legacy_y} | {y} | {h-y} |")
    lines += ["", "## Corridor hypothesis", ""]
    for method in METHODS[-2:]:
        valid = [row for row in rows if row["method"] == method and row["status"] == "valid"]
        savings = [row for row in valid if row["lines"] < backward[row["case"]]["lines"]]
        improves = [row for row in valid if all(row[f"{cost}_cost_mean"] <= backward[row["case"]][f"{cost}_cost_mean"]
                                                for cost in ("angular", "metric"))]
        gains = sum(row in improves for row in savings)
        lines.append(f"{TITLES[method]} yielded {len(valid)} validated substitutions, "
                     f"{len(savings)} with fewer lines, {len(improves)} with both mean costs at or below strict backward, "
                     f"and {gains} meeting both criteria.")
    full = [row for row in rows if row["method"] == "full_pool" and row["corridors"] is not None]
    if full:
        lines.append(f"The physical screen retained {sum(row['corridors'] for row in full)} bands across "
                     f"{len(full)} analyzed settlements.")
    lines += ["", "## Legacy comparison and limits", "",
              "The archived and corrected cohorts share seeds and terrain parameters. Building assignments and doorway populations "
              "can differ, so comparisons between cohorts use aggregate measures. Route excess within a cohort uses consistent doorway pairs.",
              "The corridor search uses the archived physical screen, pair limits and ranking. The outcomes apply to the tested alternatives. "
              "Worker peak RSS is a process high-water mark, and evaluation timing excludes case-wide candidate generation. "
              "The convex coverage proof uses the certified constrained triangle cover and containment of each seed triangle in its expanded hull. "
              "Exact geometric and routing certificates apply to saved intervals and their incidence graph. "
              "The candidate family is enumerated from the existing support-generation procedure.",
              "The Y 41 candidate attempt first failed the overlapping-hull union check. The retry certified coverage from the constrained triangle cover "
              "and seed containment with the same hull construction. The initial failure and successful retry remain in the case journal.",
              "Differences in worker concurrency and archived runtime environments affect timing comparisons. The study uses six seeds per terrain, "
              "so consistency across the matched seeds is a descriptive result.",
              "", "## Research priorities", "",
              "Investigate cases with missing candidates, region incidence or winding before drawing terrain-level conclusions. "
              "Use the geometry and route arrays to test sensitivity to convex partition and support enumeration.",
              "", "## Reproduce or resume", "",
              "From the repository root, use the same environment as the recorded stage manifests. Successful stages are resumed from the case journals.", "",
              "```sh", "PYTHONPATH=src:. .venv/bin/python -m experiments.facewise_rerun --workers 2",
              "PYTHONPATH=src:. .venv/bin/python -m experiments.facewise_rerun_export --wait", "```",
              "", "[Numbered vector atlas](numbered-axial-atlas.pdf) · [Visual index](visual-index.json) · "
              "[Statistics](statistics.csv) · [Legacy method comparisons](legacy-method-comparisons.csv)"]
    atomic_write(root / "report.md", ("\n".join(lines) + "\n").encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--aggregation-only", action="store_true")
    parser.add_argument("--wait", action="store_true", help="Wait until every case reaches a terminal stage.")
    args = parser.parse_args()
    if args.output.resolve() == LEGACY.resolve():
        parser.error("Use the corrected cohort directory for exports.")
    if args.wait:
        while True:
            terminal = 0
            for terrain, seed in CASES:
                path = case_path(args.output, terrain, seed)
                if path.exists():
                    stages = json.loads(path.read_bytes())["stages"]
                    terminal += "analysis" in stages or any(entry["status"] != "successful" for entry in stages.values())
            if terminal == len(CASES):
                break
            sleep(30)
    (export_aggregation if args.aggregation_only else export)(args.output)


if __name__ == "__main__":
    main()
