"""Publish the six-terrain benchmark from certified immutable results."""
import argparse
import csv
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from math import hypot
from itertools import combinations
import json
from pathlib import Path
from statistics import mean, median
from time import sleep

from PIL import Image

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.stats import spearmanr
from shapely import from_wkb
from shapely.ops import unary_union

from experiments.extended_terrain import NEW_CASES, PREVIOUS, PREVIOUS_TERRAINS, ROOT, SEEDS, TERRAINS, verify_previous
from experiments.facewise_rerun_export import METHODS, TITLES, draw_axial, rows_for_case, save, write_table
from experiments.plot_facewise_matched import draw_map
from experiments.strict_generalisation import case_path
from voronoi_app.batch_store import BatchStore, atomic_write, encode

TERRAIN_LABELS = dict(zip((*TERRAINS, *PREVIOUS_TERRAINS),
                          ("Flat", "Ridge", "Shoulder", "Twin Peaks", "Hill", "Converging Valleys (Y)"), strict=True))
MEASURES = ("accessible_holes", "excluded_unassigned", "candidates", "lines", "length", "intersections",
            "mean_connectivity", "angular_cost_mean", "metric_cost_mean", "angular_absolute_mean",
            "metric_absolute_mean", "generation_seconds", "candidate_seconds", "analysis_seconds",
            "selection_seconds", "routing_seconds", "peak_worker_rss_mib")


def terminal(root, terrain, seed):
    path = case_path(root, terrain, seed)
    if not path.exists():
        return False
    stages = json.loads(path.read_bytes())["stages"]
    return "analysis" in stages or any(value["status"] != "successful" for value in stages.values())


def diagnostic_maps(fig, axes, settlement, topology, polygons, data, screen):
    fig.subplots_adjust(bottom=.1)
    assigned = set(settlement["dyad_open_cells"])
    buildings = {int(cell) for cell in settlement["building_labels"]}
    draw_map(axes[0], polygons, settlement, label_size=4)
    axes[0].set_title("Numbered aggregation and assigned open cells")
    draw_map(axes[1], polygons, settlement, label_size=4)
    accessible = set(topology.get("main_open_cells", []))
    excluded = set(topology.get("excluded_open_cells", []))
    internal = set(topology.get("internal_blocks", []))
    internal_cells = {cell for block in topology.get("occupied_blocks", []) if block["id"] in internal
                      for cell in block["cells"]}
    layers = ((accessible - assigned, "#bce4f4"), (excluded, "#f5b582"), (internal_cells & buildings, "#744486"))
    for cells, color in layers:
        axes[1].add_collection(PolyCollection([polygons[i].exterior.coords for i in cells],
                                               facecolors=color, edgecolors="none", zorder=3))
    if accessible:
        domain = unary_union([polygons[cell] for cell in sorted(accessible)])
        parts = [domain] if domain.geom_type == "Polygon" else domain.geoms
        for part in parts:
            for ring in part.interiors:
                axes[1].plot(*ring.xy, color="#ab7323", linewidth=1.2, zorder=6)
    axes[1].set_title(f"Accessible space and blocks · {len(topology.get('circulation_holes', []))} holes")
    draw_map(axes[2], polygons, settlement, label_size=4)
    accepted = 0
    for band, validation in zip(data.get("corridors", []), screen, strict=True):
        if validation["accepted"]:
            start, end = band["axis"]
            dx, dy = end[0] - start[0], end[1] - start[1]
            half_width = band["width"] / (2 * hypot(dx, dy))
            nx, ny = -dy * half_width, dx * half_width
            footprint = [(start[0] + nx, start[1] + ny), (end[0] + nx, end[1] + ny),
                         (end[0] - nx, end[1] - ny), (start[0] - nx, start[1] - ny)]
            axes[2].add_collection(PolyCollection([footprint], facecolors="#247ba1", alpha=.16, zorder=5))
            axes[2].plot([start[0], end[0]], [start[1], end[1]], color="#16658b", linewidth=1.4, zorder=6)
            accepted += 1
    axes[2].set_title(f"Physically supported corridor axes · {accepted}")
    fig.legend(handles=[Patch(color="#b9dedb", label="Assigned open"), Patch(color="#bce4f4", label="Accessible unassigned"),
                        Patch(color="#f5b582", label="Excluded open"), Patch(color="#744486", label="Internal block"),
                        Line2D([], [], color="#ab7323", label="Circulation hole"),
                        Line2D([], [], color="#16658b", label="Supported corridor axis")],
               loc="lower center", ncols=6, frameon=False)


def export_case(root, terrain, seed, atlas):
    origin = PREVIOUS if terrain in PREVIOUS_TERRAINS else root
    path = case_path(origin, terrain, seed)
    journal = json.loads(path.read_bytes())
    store = BatchStore(origin)
    if origin == PREVIOUS:
        screen_needed = "physical_screen" not in journal["stages"]
        if screen_needed:
            analysis = store.load(journal["stages"]["analysis"]["record"])[1]
            if analysis.get("corridors"):
                raise ValueError(f"Archived physical screen missing for {path.stem}.")
    settlement, topology, polygons, regions, items, data, screen, singleton_regions, singleton_doors = rows_for_case(journal, store, path)
    records = {key: value["record"] for key, value in journal["stages"].items()}
    reference = origin / "route-references" / f"{path.stem}.json"
    if reference.exists():
        reference_data = json.loads(reference.read_bytes())
        full_routes = data.get("maps", {}).get("full_pool", {}).get("routes")
        identity = reference_data["identity"]
        if (identity.get("candidate_record") != records.get("candidates")
                or any(len(reference_data[k]) != len(identity["pairs"]) for k in ("angular", "metric"))
                or (full_routes and any(reference_data[k] != full_routes[k] for k in ("angular", "metric")))):
            raise ValueError(f"Full-pool route arrays differ for {path.stem}.")
    pool_item = items["full_pool"]
    if pool_item["stats"]["status"] != "valid" and not pool_item["selected_intervals"] and "candidates" in records:
        payload = store.load(records["candidates"])[1]
        if payload:
            pool_item["selected_intervals"] = [{key: line[key] for key in ("id", "start", "end")}
                                               for line in payload["pool"]["candidates"]]
            pool_item["stats"]["lines"] = len(pool_item["selected_intervals"])
    title = f"{TERRAIN_LABELS[terrain]} · seed {seed}"
    directory = root / "numbered-maps"
    case = {"case": path.stem, "terrain": terrain, "record_root": str(origin), "records": records,
            "methods": {}, "singleton_regions": singleton_regions, "singleton_doorways": singleton_doors,
            "route_reference": str(reference) if reference.exists() else None}
    rows = []
    bands = data.get("corridors", [])
    case["corridor_bands"] = [{key: band[key] for key in ("axis", "length", "width", "length_to_width",
                                                          "qualifying_pairs", "selected_members")} | validation
                              for band, validation in zip(bands, screen, strict=True)]
    assigned = set(settlement["dyad_open_cells"])
    main = set(topology.get("main_open_cells", []))
    occupied = len(settlement["building_labels"])
    incidence = data.get("incidence", {})
    region_lines = incidence.get("region_lines", {})
    case["singleton_region_lines"] = {str(i): region_lines[str(i)][0] for i in singleton_regions}
    case["singleton_doorway_lines"] = {
        str(i): next(iter({line for region in incidence["doorway_regions"][i] for line in region_lines[str(region)]}))
        for i in singleton_doors}
    for method, item in items.items():
        stats = item["stats"]
        entry = item["result"]
        constraints = entry.get("constraints", {})
        count, intersections = stats["lines"], stats["intersections"]
        stats.update(occupied_cells=occupied, assigned_open_cells=len(assigned),
                     unassigned_open_cells=len(polygons) - len(assigned) - occupied,
                     accessible_open_cells=len(main), accessible_unassigned=len(main - assigned),
                     singleton_regions=len(singleton_regions), singleton_doorways=len(singleton_doors),
                     aggregation_termination=settlement["aggregation_certificate"].get("termination"),
                     seed_component_recovery=bool(journal.get("earlier_attempts", {}).get("topology")),
                     mean_connectivity=2 * intersections / count if count and intersections is not None else None,
                     candidate_seconds=journal["stages"].get("candidates", {}).get("seconds"),
                     settlement_seconds=journal["stages"]["settlement"]["seconds"],
                     selection_seconds=entry.get("selection_seconds"), routing_seconds=entry.get("routing_seconds"),
                     shared_corridor_seconds=data.get("shared_corridor_seconds"),
                     connector_seconds=data.get("connector_seconds"))
        if method in METHODS[-2:] and entry.get("pair"):
            key = "extreme" if method == "geometric_extreme" else "best_ranked"
            band = next((band for band, validation in zip(bands, screen, strict=True)
                         if validation["accepted"] and band[key] and
                         band[key]["pair"] == entry["pair"] and band[key]["line_ids"] == entry["line_ids"]), None)
            if band:
                stats.update(corridor_length=band["length"], corridor_width=band["width"],
                             corridor_aspect_ratio=band["length_to_width"])
        if stats["status"] == "valid":
            if (not constraints["valid"] or constraints["unattached_doors"] or stats["covered_regions"] != len(regions)
                    or stats["rank"] != stats["required_rank"] or stats["components"] != 1):
                raise ValueError(f"{path.stem}/{method} has inconsistent structural validation.")
            if any(len(route) != stats["eligible_pairs"] or any(cost is None for cost in route)
                   for route in entry["routes"].values()):
                raise ValueError(f"{path.stem}/{method} has incomplete routes.")
        ids = entry.get("line_ids", entry.get("attempted_line_ids"))
        if ids is not None and ids != [line["id"] for line in item["selected_intervals"]]:
            raise ValueError(f"{path.stem}/{method} has mismatched selected IDs.")
        fig, ax = plt.subplots(figsize=(8, 8.9), layout="constrained")
        fig.suptitle(title)
        draw_axial(ax, settlement, topology, polygons, regions, item, TITLES[method])
        for door_id in constraints.get("unattached_doors", []):
            x, y = (float(Fraction(value)) for value in incidence["doorways"][door_id]["point"])
            ax.scatter(x, y, marker="x", c="#b31544", zorder=9)
        item["visual"] = save(fig, directory, f"{path.stem}-{method}", atlas)
        with Image.open(root / item["visual"]["png"]) as raster:
            if min(raster.size) < 2000:
                raise ValueError(f"{path.stem}/{method} image is below the inspection resolution.")
        pdf = (root / item["visual"]["pdf"]).read_bytes()
        if not pdf.startswith(b"%PDF") or b"/Subtype /Image" in pdf:
            raise ValueError(f"{path.stem}/{method} was not exported as vector geometry.")
        item["result"] = {key: value for key, value in entry.items() if key != "routes"}
        case["methods"][method] = item
        rows.append(stats | item["visual"])
    fig, axes = plt.subplots(1, 5, figsize=(18, 5), layout="constrained")
    fig.suptitle(title)
    for method, ax in zip(METHODS, axes, strict=True):
        draw_axial(ax, settlement, topology, polygons, regions, items[method], TITLES[method], small=True)
    case["comparison"] = save(fig, directory, f"{path.stem}-comparison", atlas)
    fig, axes = plt.subplots(1, 3, figsize=(15, 6))
    fig.suptitle(title)
    diagnostic_maps(fig, axes, settlement, topology, polygons, data, screen)
    case["topology_and_corridors"] = save(fig, directory, f"{path.stem}-topology", atlas)
    before = {line["id"]: line for line in items["strict_backward"]["selected_intervals"]}
    for method in METHODS[-2:]:
        item = items[method]
        if item["stats"]["status"] != "valid":
            continue
        after = {line["id"]: line for line in item["selected_intervals"]}
        removed, added = sorted(before.keys() - after), sorted(after.keys() - before)
        fig, ax = plt.subplots(figsize=(8, 8.9), layout="constrained")
        fig.suptitle(title)
        draw_axial(ax, settlement, topology, polygons, regions, item,
                   f"{TITLES[method]} · {len(removed)} removed (red) · {len(added)} added (green)",
                   changes=[([before[i] for i in removed], "#ae2438"), ([after[i] for i in added], "#16745b")])
        item["corridor_changes"] = save(fig, directory, f"{path.stem}-{method}-changes", atlas) | {
            "removed_ids": removed, "added_ids": added}
    return case, rows


def summaries(root, rows):
    groups = []
    backwards = {row["case"]: row for row in rows if row["method"] == "strict_backward"}
    for terrain in TERRAIN_LABELS:
        for method in METHODS:
            group = [row for row in rows if row["terrain"] == terrain and row["method"] == method]
            valid = [row for row in group if row["status"] == "valid"]
            out = {"terrain": terrain, "method": method, "evaluated": len(group), "valid": len(valid)}
            for key in MEASURES:
                source = group if key in ("accessible_holes", "excluded_unassigned", "candidates") else valid
                observations = [row[key] for row in source if row.get(key) is not None]
                if observations:
                    out.update({f"{key}_mean": mean(observations), f"{key}_min": min(observations),
                                f"{key}_max": max(observations), f"{key}_n": len(observations)})
            if method in METHODS[-2:]:
                comparable = [r for r in valid if backwards[r["case"]]["status"] == "valid"]
                out["comparable"] = len(comparable)
                for cost in ("angular_cost_mean", "metric_cost_mean"):
                    out[f"{cost}_improves"] = sum(r[cost] < backwards[r["case"]][cost] - 1e-9 for r in comparable)
                out["both_improve"] = sum(all(r[cost] < backwards[r["case"]][cost] - 1e-9
                                             for cost in ("angular_cost_mean", "metric_cost_mean")) for r in comparable)
            groups.append(out)
    write_table(root / "terrain-summary.csv", groups)
    pairs = []
    for a, b in combinations(TERRAIN_LABELS, 2):
        for seed in SEEDS:
            for method in METHODS:
                x, y = (next(r for r in rows if r["terrain"] == t and r["seed"] == seed and r["method"] == method)
                        for t in (a, b))
                delta = {k: y[k] - x[k] for k in MEASURES if x.get(k) is not None and y.get(k) is not None
                         and (k in ("accessible_holes", "excluded_unassigned", "candidates")
                              or x["status"] == y["status"] == "valid")}
                pairs.append({"seed": seed, "terrain_a": a, "terrain_b": b, "method": method,
                              "status_a": x["status"], "status_b": y["status"], **delta})
    write_table(root / "paired-terrain-differences.csv", pairs)
    return groups


def report(root, rows, groups):
    statuses = Counter(row["status"] for row in rows)
    lines = ["# Extended corrected facewise terrain benchmark", "",
             f"The benchmark covers {len(rows)//5} settlements and {len(rows)} method evaluations. "
             + ", ".join(f"{count} {status}" for status, count in sorted(statuses.items())) + ".",
             "Hill and Converging Valleys use the immutable corrected records from the published benchmark.",
             "", "## Terrain comparison", "",
             "| Terrain | Holes, mean (range) | Excluded unassigned, mean (range) | Candidates, mean | Backward lines, mean (range) | Backward length | Angular mean | Metric mean |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]

    def value(record, key, bounds=False):
        if f"{key}_mean" not in record:
            return "—"
        result = f"{record[f'{key}_mean']:.2f}"
        return result + (f" ({record[f'{key}_min']}–{record[f'{key}_max']})" if bounds else "")

    for row in groups:
        if row["method"] == "strict_backward":
            cells = [value(row, key, key in ("accessible_holes", "excluded_unassigned", "lines"))
                     for key in ("accessible_holes", "excluded_unassigned", "candidates", "lines", "length",
                                 "angular_cost_mean", "metric_cost_mean")]
            lines.append("| " + " | ".join([TERRAIN_LABELS[row["terrain"]], *cells]) + " |")
    lines += ["", "## Corridor substitutions", "",
              "| Terrain | Method | Valid / evaluated | Angular improves | Metric improves | Both improve |",
              "|---|---|---:|---:|---:|---:|"]
    for row in groups:
        if row["method"] in METHODS[-2:]:
            lines.append(f"| {TERRAIN_LABELS[row['terrain']]} | {TITLES[row['method']]} | {row['valid']}/{row['evaluated']} | "
                         f"{row['angular_cost_mean_improves']} | {row['metric_cost_mean_improves']} | {row['both_improve']} |")
    lines += ["", "## Descriptive relationships", "",
              "These Spearman correlations describe the sampled configurations. The paired CSV reports within-seed differences. "
              "Seeds are shared across terrain types and the correlations are descriptive."]
    backward = [row for row in rows if row["method"] == "strict_backward" and row["status"] == "valid"]
    for a, b in (("accessible_holes", "lines"), ("required_regions", "lines"), ("singleton_regions", "lines"),
                 ("singleton_doorways", "lines"), ("excluded_unassigned", "accessible_holes"),
                 ("lines", "angular_absolute_mean"), ("lines", "metric_absolute_mean")):
        values = [(r[a], r[b]) for r in backward if r.get(a) is not None and r.get(b) is not None]
        if len(values) >= 3 and all(len(set(col)) > 1 for col in zip(*values)):
            x, y = zip(*values)
            lines.append(f"- {a.replace('_', ' ')} and {b.replace('_', ' ')} · ρ {spearmanr(x, y).statistic:.3f}, n {len(x)}")
    for method in METHODS[-2:]:
        for cost in ("angular_cost_mean", "metric_cost_mean"):
            values = [(row["corridor_aspect_ratio"], row[cost] - base[cost])
                      for row in rows if row["method"] == method and row["status"] == "valid"
                      and "corridor_aspect_ratio" in row and (base := next((r for r in backward
                                                                            if r["case"] == row["case"]), None))]
            if len(values) >= 3 and all(len(set(col)) > 1 for col in zip(*values)):
                x, y = zip(*values)
                lines.append(f"- {TITLES[method]} band aspect ratio and {cost.split('_')[0]} change "
                             f"against strict backward · ρ {spearmanr(x, y).statistic:.3f}, n {len(x)}")
    lines += ["", "## Seed-level extremes", ""]
    for terrain in TERRAIN_LABELS:
        group = [r for r in backward if r["terrain"] == terrain]
        if group:
            low, high = min(group, key=lambda r: r["lines"]), max(group, key=lambda r: r["lines"])
            lines.append(f"- {TERRAIN_LABELS[terrain]} · seed {low['seed']} retained {low['lines']} backward lines, "
                         f"and seed {high['seed']} retained {high['lines']}.")
            centre = median(r["lines"] for r in group)
            deviations = [abs(r["lines"] - centre) for r in group]
            mad = median(deviations)
            flagged = [r for r, deviation in zip(group, deviations, strict=True)
                       if deviation > 3 * mad and deviation > 0]
            if flagged:
                lines.append(f"- {TERRAIN_LABELS[terrain]} · beyond three within-terrain median absolute deviations: "
                             + ", ".join(f"seed {r['seed']} ({r['lines']} lines)" for r in flagged) + ".")
    lines += ["", "## Computational performance", "",
              "| Terrain | Mean generation seconds | Mean candidate seconds | Mean analysis seconds | Mean worker peak MiB |",
              "|---|---:|---:|---:|---:|"]
    for row in groups:
        if row["method"] == "full_pool":
            cells = [value(row, key) for key in ("generation_seconds", "candidate_seconds", "analysis_seconds",
                                                "peak_worker_rss_mib")]
            lines.append("| " + " | ".join([TERRAIN_LABELS[row["terrain"]], *cells]) + " |")
    discrepancies = [r["case"] for r in rows if r["method"] == "full_pool" and r["rank_hole_count_agrees"] is False]
    if discrepancies:
        lines += ["", "The independent geometric hole count and occupied-block winding requirement differ for "
                  + ", ".join(discrepancies) + "."]
    aggregation_notes = [r for r in rows if r["method"] == "full_pool" and
                         (r["completed_dyads"] < 100 or r["seed_component_recovery"])]
    if aggregation_notes:
        lines += ["", "## Aggregation and accessible component exceptions", ""]
        for row in aggregation_notes:
            if row["completed_dyads"] < 100:
                lines.append(f"- {row['case']} completed {row['completed_dyads']} dyads · {row['aggregation_termination']}.")
            if row["seed_component_recovery"]:
                lines.append(f"- {row['case']} uses the open component reached from the original dyad seed. "
                             "The initial largest-component checkpoint is preserved in its journal. "
                             "Its largest component contained no assigned open cells.")
    failures = [r for r in rows if r["status"] != "valid"]
    if failures:
        lines += ["", "## Validation failures and unsupported outcomes", ""]
        lines.extend(f"- {r['case']} · {TITLES[r['method']]} · {r['status']} · {r['reason']}" for r in failures)
    lines += ["", "## Methods and reproducibility", "",
              "Flat elevation differences are zero. The unchanged slope and contour scores therefore rank eligible neighbors "
              "by their seeded random terms. The sorted clipped-face inventory makes the random draw sequence reproducible.",
              "Angular depth uses 90° turn units and zero-cost doorway entry via incident regions. Metric distances apply "
              "to the finite certified attachment and axial graph. Peak memory refers to worker high-water RSS. "
              "Archived Hill and Y records may lack the finer timing fields collected in the extension. "
              "Corridor selection runtime covers the shared bounded search. A map's routing time covers its evaluated network.",
              "", "Run the new cases and resume their journals with `python -m experiments.extended_terrain --workers 4` "
              "from the repository with `PYTHONPATH=src:.`. Export the completed cohort with "
              "`python -m experiments.extended_terrain_export`.",
              "", "[Statistics](statistics.csv) · [Terrain summaries](terrain-summary.csv) · "
              "[Paired differences](paired-terrain-differences.csv) · [Vector atlas](numbered-axial-atlas.pdf) · "
              "[Visual index](visual-index.json)"]
    atomic_write(root / "report.md", ("\n".join(lines) + "\n").encode())


def export_morphology(root):
    """Publish topology checkpoints independently of the longer axial batch."""
    verify_previous()
    rows = []
    path = root / "numbered-topology-atlas.pdf"
    with PdfPages(path.with_suffix(".tmp")) as atlas:
        for terrain, label in TERRAIN_LABELS.items():
            origin = PREVIOUS if terrain in PREVIOUS_TERRAINS else root
            store = BatchStore(origin)
            for seed in SEEDS:
                journal = json.loads(case_path(origin, terrain, seed).read_bytes())
                stages = journal["stages"]
                settlement = store.load(stages["settlement"]["record"])[1]
                topology = store.load(stages["topology"]["record"])[1]["topology"]
                polygons = {int(cell): from_wkb(wkb) for cell, wkb in settlement["polygons_wkb"].items()}
                assigned = set(settlement["dyad_open_cells"])
                main = set(topology["main_open_cells"])
                excluded = set(topology["excluded_open_cells"])
                internal = len(topology["internal_blocks"])
                holes = len(topology["circulation_holes"])
                certificate = settlement["aggregation_certificate"]
                rows.append({"case": journal["case"], "terrain": terrain, "seed": seed,
                             "dyads": certificate["completed_dyads"], "valid": certificate["valid"],
                             "termination": certificate.get("termination"),
                             "seed_component_recovery": bool(journal.get("earlier_attempts", {}).get("topology")),
                             "assigned_components": certificate["assigned_open_components"],
                             "accessible_open": len(main), "accessible_unassigned": len(main - assigned),
                             "excluded_assigned": len(excluded & assigned), "excluded_unassigned": len(excluded - assigned),
                             "internal_blocks": internal, "geometric_holes": holes, "required_rank": internal,
                             "rank_hole_count_agrees": internal == holes,
                             "settlement_record": stages["settlement"]["record"], "topology_record": stages["topology"]["record"]})
                fig, axes = plt.subplots(1, 3, figsize=(15, 6))
                fig.suptitle(f"{label} · seed {seed}")
                diagnostic_maps(fig, axes, settlement, topology, polygons, {}, [])
                axes[2].set_visible(False)
                atlas.savefig(fig, bbox_inches="tight")
                plt.close(fig)
    path.with_suffix(".tmp").replace(path)
    write_table(root / "topology-statistics.csv", rows)
    lines = ["# Extended terrain morphology checkpoints", "",
             "The topology atlas covers the 24 newly generated settlements and 12 archived Hill and Y settlements. "
             "Axial selection and movement results are exported after the axial batch.", "",
             "| Terrain | Dyads | Holes, range | Excluded unassigned, range |",
             "|---|---:|---:|---:|"]
    for terrain, label in TERRAIN_LABELS.items():
        group = [row for row in rows if row["terrain"] == terrain]
        holes = [row["geometric_holes"] for row in group]
        excluded = [row["excluded_unassigned"] for row in group]
        lines.append(f"| {label} | {sum(row['dyads'] for row in group)} | {min(holes)}–{max(holes)} | "
                     f"{min(excluded)}–{max(excluded)} |")
    for row in rows:
        if row["dyads"] < 100:
            lines.extend(["", f"{row['case']} stopped at {row['dyads']} dyads ({row['termination']})."])
        if row["seed_component_recovery"]:
            lines.extend(["", f"{row['case']} uses the growth-seed component for doorway analysis. "
                          "The largest-component checkpoint is retained in its case journal."])
    lines.extend(["", "[Topology CSV](topology-statistics.csv) · [Numbered topology atlas](numbered-topology-atlas.pdf)"])
    atomic_write(root / "topology-report.md", ("\n".join(lines) + "\n").encode())
    print(f"{len(rows)} topology checkpoints exported.", flush=True)


def export(root):
    verify_previous()
    pending = [f"{t}-{s}" for t, s in NEW_CASES if not terminal(root, t, s)]
    if pending:
        raise ValueError("Incomplete cases: " + ", ".join(pending))
    directory = root / "numbered-maps"
    directory.mkdir(exist_ok=True)
    atlas_path = root / "numbered-axial-atlas.pdf"
    cases, rows = [], []
    with PdfPages(atlas_path.with_suffix(".tmp")) as atlas:
        for terrain, label in TERRAIN_LABELS.items():
            fig = plt.figure(figsize=(8, 9))
            fig.text(.5, .54, label, ha="center", fontsize=30)
            fig.text(.5, .47, "Corrected facewise growth · seeds 40–45", ha="center", fontsize=12)
            atlas.savefig(fig)
            plt.close(fig)
            for seed in SEEDS:
                case, stats = export_case(root, terrain, seed, atlas)
                cases.append(case)
                rows.extend(stats)
                print(case["case"], "maps exported", flush=True)
    if len(cases) != 36 or len(rows) != 180:
        raise ValueError("The atlas does not contain the complete benchmark.")
    atlas_path.with_suffix(".tmp").replace(atlas_path)
    write_table(root / "statistics.csv", rows)
    groups = summaries(root, rows)
    report(root, rows, groups)
    atomic_write(root / "visual-index.json", encode({"atlas": atlas_path.name, "case_count": len(cases),
                                                    "method_count": len(rows), "cases": cases}))
    files = sorted([*directory.glob("*"), *root.glob("*.csv"), *root.glob("*-atlas.pdf"),
                    *root.glob("*report.md"), *(root / "cases").glob("*.json"),
                    *(root / "route-references").glob("*.json"),
                    root / "benchmark.json", root / "visual-index.json"])
    atomic_write(root / "export-record.json", encode({str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
                                                      for path in files}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--topology-only", action="store_true")
    args = parser.parse_args()
    if args.output.resolve() in (PREVIOUS.resolve(), (PREVIOUS.parent / "pilot-1").resolve()):
        parser.error("Use a separate directory for the extended benchmark.")
    if args.wait:
        while any(not terminal(args.output, terrain, seed) for terrain, seed in NEW_CASES):
            sleep(30)
    (export_morphology if args.topology_only else export)(args.output)


if __name__ == "__main__":
    main()
