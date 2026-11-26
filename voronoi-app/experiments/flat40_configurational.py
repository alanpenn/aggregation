"""Run the Flat 40 configurational pilot from authenticated saved inputs."""

import argparse
import csv
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import os
import platform
import sys

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import networkx as nx
import numpy as np
from shapely import from_wkb

from voronoi_app import configurational
from voronoi_app.configurational import axial_graph, convex_graph, measures, pearson, polygon_area, segment_graph


BASE = Path("diagnostics/strict-generalisation")
COVER = BASE / "flat40-exhaustive-convex-1"
SELECTION = BASE / "flat40-maximal-convex-axial-selection-1"
MINIMUM = BASE / "flat40-maximal-convex-minimum-1"
REGISTRY = Path("research/flat40/maximal-regions.json")
TRANSFER = Path("research/flat40/transfer.json")
CONFIG = Path(__file__).with_name("flat40_configurational_config.json")
METRICS = ("connectivity", "mean_depth", "integration", "choice")
PRIMARY = "31-H"
SENSITIVITY = "29-H"


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def exact_points(rows):
    return tuple(tuple(map(Fraction, point)) for point in rows)


def authenticated_inputs(records, data, evidence):
    pointer = read(records / TRANSFER)
    manifest_file = data / pointer["shared_location"] / pointer["archive"].replace(".tar.gz", ".json")
    manifest_bytes = manifest_file.read_bytes()
    check(sha256(manifest_bytes).hexdigest() == pointer["manifest_sha256"], "Transfer manifest hash mismatch")
    manifest = json.loads(manifest_bytes)
    check(manifest["sha256"] == pointer["archive_sha256"], "Transfer pointer mismatch")
    provenance = read(records / SELECTION / "provenance.json")
    migration_bytes = (data / "migration-sha256-2026-11-24.json").read_bytes()
    check(sha256(migration_bytes).hexdigest() == provenance["manifest_sha256"], "Migration inventory hash mismatch")
    migration = json.loads(migration_bytes)
    hashes = {"transfer_manifest": pointer["manifest_sha256"], "transfer_archive": pointer["archive_sha256"],
              "migration_inventory": provenance["manifest_sha256"]}

    def verified(path, relative, digest):
        raw = path.read_bytes()
        observed = sha256(raw).hexdigest()
        check(observed == digest, f"Hash mismatch: {relative}")
        hashes[str(relative)] = observed
        return json.loads(raw)

    def transferred(relative):
        return verified(records / relative, relative, manifest["files"][str(relative)])

    def source(relative):
        check(provenance["verified_inputs"][relative] == migration[relative], f"Source manifest mismatch: {relative}")
        return verified(data / relative, relative, migration[relative])

    outputs = {}
    for name in ("candidates", "topology", "settlement"):
        stage = provenance["lineage"][name]
        relative = next(k for k in provenance["verified_inputs"] if k.endswith(f'/{stage["id"]}/output.json'))
        outputs[name] = source(relative)
    pool = outputs["candidates"]["pool"]
    check(sha256(canonical(pool)).hexdigest() == provenance["candidate_pool_sha256"], "Candidate pool mismatch")
    lines = {row["id"]: exact_points((row["start"], row["end"])) for row in pool["candidates"]}
    check(set(lines) == set(range(1534)), "Unexpected frozen candidate IDs")
    coverage_path = COVER / "coverage-maximal.json"
    check(manifest["files"][str(coverage_path)] == provenance["cover_files"][coverage_path.name],
          "Coverage provenance mismatch")
    coverage = verified(evidence / coverage_path, coverage_path, manifest["files"][str(coverage_path)])
    check(coverage["full_coverage"] and Fraction(coverage["uncovered_area"]) == 0, "Coverage certificate invalid")
    registry_raw = (records / REGISTRY).read_bytes()
    hashes[str(REGISTRY)] = sha256(registry_raw).hexdigest()
    registry = json.loads(registry_raw)["regions"]
    check(len(registry) == 596, "Expected 596 maximal regions")
    polygons = {}
    for key, row in registry.items():
        check(sha256(canonical(row["vertices"])).hexdigest() == key and row["maximality"]["status"] == "proved_global"
              and Fraction(row["area"]) > 0, f"Invalid convex certificate {key}")
        polygons[key] = exact_points(row["vertices"])
        check(polygon_area(polygons[key]) == Fraction(row["area"]), f"Convex area mismatch {key}")
    inventory = {}
    for label in ("H", "S"):
        selected = transferred(SELECTION / f"B-C-{label}.json")
        cert = selected["certificate"]
        check(len(set(selected["ids"])) == 31 and cert["effective_clearance_line_count"] == 31
              and cert["independent_circulation_rank"] == 24 and cert["circulation_constraints_satisfied"],
              f"Invalid 31-{label} certificate")
        inventory[f"31-{label}"] = selected["ids"]
    smaller = transferred(MINIMUM / "combined-results.json")["smaller"]
    best = [(position, row) for position, row in enumerate(smaller, 1) if len(set(row["ids"])) == 29]
    check(len(best) == 2, "Expected two 29-line selections")
    for (_, row), label in zip(best, ("H", "S")):
        cert = row["certificate"]
        check((cert["coverage"], cert["doorways"], cert["components"]) == (596, 100, 1)
              and cert["winding"]["independent_circulation_rank"] == 24
              and cert["winding"]["effective_clearance_line_count"] == 29, f"Invalid 29-{label} certificate")
        inventory[f"29-{label}"] = row["ids"]
    position, row = best[0]
    check(any(origin["origin"] == "followup-02" for origin in row["origins"]), "Unexpected 29-H lineage")
    control = source(str(BASE.relative_to("diagnostics") / "cross-terrain-constructive-1/flat-40/C-H.json"))
    structural = source("strict-generalisation/cross-terrain-constructive-1/flat-40/structural.json")
    check(len(set(control["ids"])) == 34 and control["ids"] == structural["methods"]["C-H"]["ids"],
          "34-H control mismatch")
    inventory["34-H"] = control["ids"]
    frozen = source("strict-generalisation/constructive-axial-3/flat-40/geometry.json")["candidates"]
    movement_path = MINIMUM / "movement.json"
    movement = verified(evidence / movement_path, movement_path, manifest["files"][str(movement_path)])
    check(movement["pairs"] == [list(pair) for pair in combinations(range(100), 2)], "Unexpected doorway pairs")
    routes = {}
    for label, key in (("31-H", "B-C-H"), ("29-H", f"smaller-{position:02}")):
        row = movement["methods"][key]["final"]
        arrays = [np.asarray(row[f"{mode}_routes"], dtype=float) for mode in ("angular", "metric")]
        check(row["valid"] and row["count"] == len(inventory[label])
              and all(values.shape == (4950,) and np.isfinite(values).all() for values in arrays),
              f"Invalid saved doorway arrays for {label}")
        routes[label] = dict(zip(("angular", "metric"), map(np.mean, arrays)))
    return lines, polygons, inventory, frozen, outputs, routes, hashes


def description(values):
    if not values:
        return None
    q = np.quantile(values, [0, .25, .5, .75, 1])
    return dict(zip(("min", "q1", "median", "q3", "max"), map(float, q))) | {
        "count": len(values), "mean": float(np.mean(values)), "population_sd": float(np.std(values))}


def summary(graph, rows):
    return {"nodes": len(graph), "edges": graph.number_of_edges(),
            "density": nx.density(graph), "component_sizes": sorted(map(len, nx.connected_components(graph)), reverse=True),
            "intelligibility": pearson([row["connectivity"] for row in rows.values()],
                                       [row["integration"] for row in rows.values()]),
            "metrics": {metric: description([row[metric] for row in rows.values() if row[metric] is not None])
                        for metric in METRICS}}


def json_file(path, data):
    def encode(value):
        if isinstance(value, Fraction):
            return str(value)
        raise TypeError(f"Unsupported type {type(value)}")
    path.write_text(json.dumps(data, indent=2, default=encode, allow_nan=False) + "\n")


def compare(left, right, key):
    first, second = ({key(graph, node): results[node] for node in graph}
                     for graph, results in (left, right))
    common = sorted(first.keys() & second.keys())
    paired = {metric: [i for i in common if first[i][metric] is not None and second[i][metric] is not None]
              for metric in METRICS}
    return {"matched": len(common), "primary_only": len(first) - len(common),
            "sensitivity_only": len(second) - len(common),
            "metrics": {metric: {"pearson": pearson([first[i][metric] for i in nodes],
                                                    [second[i][metric] for i in nodes]),
                                 "change": description([second[i][metric] - first[i][metric] for i in nodes])}
                        for metric, nodes in paired.items()}}


def coordinates(points):
    return [tuple(map(float, point)) for point in points]


def atlas(path, datasets, domain, buildings):
    with PdfPages(path) as pdf:
        for family, names in (("Axial", ["31-H axial", "29-H axial", "34-H axial"]),
                              ("Segment", ["31-H segment", "29-H segment", "34-H segment"]),
                              ("Convex", ["Maximal convex"]), ("Angular segment", ["31-H angular", "29-H angular"])):
            for metric in METRICS:
                panels = names * 2 if family == "Convex" else names
                fig, axes = plt.subplots(1, len(panels), figsize=(5.2 * len(panels), 5.7), squeeze=False,
                                         layout="constrained")
                values = [row[metric] for name in names for row in datasets[name][1].values() if row[metric] is not None]
                norm = Normalize(min(values), max(values))
                mapper = ScalarMappable(norm=norm, cmap="viridis")
                for index, (ax, name) in enumerate(zip(axes[0], panels)):
                    graph, rows = datasets[name]
                    geoms = [coordinates(graph.nodes[node]["points"]) for node in graph]
                    colours = [mapper.to_rgba(rows[node][metric]) if rows[node][metric] is not None else "#aaaaaa"
                               for node in graph]
                    ax.add_collection(PolyCollection(buildings, facecolors="#e2dfdc", edgecolors="#aaa39e",
                                                     linewidths=.35))
                    if family == "Convex":
                        if index == 0:
                            ax.add_collection(PolyCollection(geoms, facecolors=colours, edgecolors=colours,
                                                             alpha=.13, linewidths=.45))
                            name = "Overlapping polygon footprints"
                        else:
                            centres = np.asarray([np.mean(geom, axis=0) for geom in geoms])
                            ax.scatter(*centres.T, c=colours, s=12, linewidths=.15, edgecolors="white")
                            name = "Individual polygon scores"
                    else:
                        ax.add_collection(LineCollection(geoms, colors=colours, linewidths=1.6))
                    for part in domain.geoms if domain.geom_type == "MultiPolygon" else (domain,):
                        ax.plot(*part.exterior.xy, color="#918b85", linewidth=.5, zorder=0)
                    x0, y0, x1, y1 = domain.bounds
                    ax.set(xlim=(x0, x1), ylim=(y0, y1), aspect="equal", title=name)
                    ax.set_axis_off()
                fig.suptitle(f"Flat 40 · {family} · {metric.replace('_', ' ').title()}")
                fig.colorbar(mapper, ax=list(axes[0]), shrink=.55, orientation="horizontal")
                pdf.savefig(fig)
                plt.close(fig)
            fig, axes = plt.subplots(2, 3, figsize=(12, 7), layout="constrained")
            for ax, metric in zip(axes.flat, METRICS):
                series = [[row[metric] for row in datasets[name][1].values() if row[metric] is not None] for name in names]
                bins = np.histogram_bin_edges(np.concatenate(series), bins=18)
                for name, values in zip(names, series):
                    ax.hist(values, bins=bins, weights=np.ones(len(values)) / len(values), histtype="step", label=name)
                ax.set(title=metric.replace("_", " ").title(), ylabel="Fraction of nodes")
            for name in names:
                _, rows = datasets[name]
                x = [r["connectivity"] for r in rows.values()]
                y = [r["integration"] for r in rows.values()]
                axes.flat[4].scatter(x, y, s=9, alpha=.45, label=f"{name} · r={pearson(x, y):.3f}")
            axes.flat[4].set(xlabel="Connectivity", ylabel="Integration", title="Intelligibility")
            axes.flat[4].legend(fontsize=7)
            axes.flat[5].axis("off")
            axes.flat[0].legend(fontsize=7)
            fig.suptitle(f"Flat 40 · {family} distributions")
            pdf.savefig(fig)
            plt.close(fig)


def report(path, summaries, paired, routes, inventory):
    lines = ["# Flat 40 configurational pilot", "",
             "All three graph representations use the corrected Flat 40 settlement. The common metric is global hop distance. The segment-only angular supplement uses minimum summed turn angle with hops as a secondary criterion.",
             "", "| Graph | Nodes | Edges | Components | Mean degree | Mean depth | Mean integration | Mean choice | Intelligibility r |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, result in summaries.items():
        values = [result["metrics"][metric]["mean"] for metric in METRICS]
        lines.append(f"| {name} | {result['nodes']} | {result['edges']} | {len(result['component_sizes'])} | " +
                     " | ".join(f"{value:.5f}" for value in [*values, result["intelligibility"]]) + " |")
    removed = sorted(set(inventory[PRIMARY]) - set(inventory[SENSITIVITY]))
    added = sorted(set(inventory[SENSITIVITY]) - set(inventory[PRIMARY]))
    lines += ["", "## Reduction sensitivity", "",
              f"Relative to 31-H, 29-H removes candidate IDs {removed} and adds {added}. Changes below use only identical candidate IDs or identical rational segment endpoints.",
              "", "| Comparison | Matched nodes | 31-H only | 29-H only | Mean integration change | Integration Pearson r |",
              "|---|---:|---:|---:|---:|---:|"]
    for name, row in paired.items():
        integration = row["metrics"]["integration"]
        lines.append(f"| {name} | {row['matched']} | {row['primary_only']} | {row['sensitivity_only']} | "
                     f"{integration['change']['mean']:+.6f} | {integration['pearson']:.4f} |")
    lines += ["", "The 29-H map has lower integration on the axial-line graph and higher integration on the "
              "hop-based segment graph. Angular segment integration falls. The matched-node comparisons "
              "show the same directions of change, so they persist when comparing the same lines or segments. "
              "Axial intelligibility changes little, while the angular segment model shows a weaker degree–integration "
              "relationship than the hop-based segment model on either selection.",
              "", f"The archived doorway mean angular cost moves from {routes[PRIMARY]['angular']:.5f} to "
              f"{routes[SENSITIVITY]['angular']:.5f}, and mean metric cost moves from {routes[PRIMARY]['metric']:.5f} to "
              f"{routes[SENSITIVITY]['metric']:.5f}. Both arrays contain all 4,950 pairs. These are external checks on interpretation, independent of the graph measures.",
              "", "## Validation", "",
              "The source candidate pool and selected inventories passed SHA-256 checks. The three axial "
              "graphs reproduced the selected edges in the frozen candidate intersection archive. The "
              "596 polygon IDs, exact areas and global maximality records were checked against the registry, "
              "and the archived uncovered area is exactly zero.",
              "", "## Interpretation and limits", "",
              "Raw node counts and degrees reflect different representations. Normalisation does not make an axial hop, segment hop and convex overlap interchangeable. Angular segment depth is in degrees and cannot be compared numerically to hop depth. The undirected segment adjacency supplement measures relations among segments and can permit consecutive transitions at the same junction. Convex polygon transparency reveals overlapping footprints. Interior dots represent individual polygon scores where fills blend. Pearson coefficients are descriptive within this settlement. One seed cannot establish a terrain effect, general transferability or superiority of a line inventory.",
              "", "[Frozen configuration](configuration.json) · [Spatial atlas and distributions](atlas.pdf) · "
              "[Graph statistics](statistics.json) · [Node scores](nodes.csv) · [Exact graph geometry and edges](graphs.json) · [Source hashes](inputs.json)"]
    path.write_text("\n".join(lines) + "\n")


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True, help="Checkout containing the compact certified inputs")
    parser.add_argument("--evidence", type=Path, required=True, help="Root with verified transfer members under diagnostics/")
    parser.add_argument("--data", type=Path, default=os.environ.get("AGGREGATION_DATA_ROOT"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if args.data is None:
        parser.error("Set AGGREGATION_DATA_ROOT or supply --data.")
    config_bytes = CONFIG.read_bytes()
    check(json.loads(config_bytes)["version"] == 1, "Unsupported analysis specification")
    inputs = authenticated_inputs(args.records, args.data, args.evidence)
    lines, polygons, inventory, frozen, outputs, routes, hashes = inputs
    datasets = {}
    graphs = {}
    for label in (PRIMARY, SENSITIVITY, "34-H"):
        ids = set(inventory[label])
        axial = axial_graph({i: lines[i] for i in ids})
        expected = {tuple(sorted((i, j))) for i in ids for j in frozen[i]["intersections"] if j in ids}
        check({tuple(sorted(edge)) for edge in axial.edges} == expected, f"Frozen graph mismatch for {label}")
        segment = segment_graph(axial)
        check(nx.is_connected(axial) and nx.is_connected(segment), f"Disconnected {label} geometry")
        for kind, graph in (("axial", axial), ("segment", segment)):
            name = f"{label} {kind}"
            datasets[name] = (graph, measures(graph))
            graphs[name] = graph
        if label != "34-H":
            datasets[f"{label} angular"] = (segment, measures(segment, angular=True))
    convex = convex_graph(polygons)
    datasets["Maximal convex"] = (convex, measures(convex))
    graphs["Maximal convex"] = convex
    summaries = {name: summary(*pair) for name, pair in datasets.items()}
    paired = {kind: compare(datasets[f"{PRIMARY} {kind}"], datasets[f"{SENSITIVITY} {kind}"],
                            (lambda g, i: i) if kind == "axial" else (lambda g, i: g.nodes[i]["points"]))
              for kind in ("axial", "segment", "angular")}
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    (out / "configuration.json").write_bytes(config_bytes)
    json_file(out / "inputs.json", {"source_revision": args.source_revision, "files": hashes,
                                    "config_sha256": sha256(config_bytes).hexdigest(), "inventories": inventory,
                                    "analysis_source_sha256": {
                                        path.name: sha256(path.read_bytes()).hexdigest()
                                        for path in (Path(__file__), Path(configurational.__file__))},
                                    "runtime": {"python": platform.python_version(), "networkx": nx.__version__,
                                                "numpy": np.__version__}})
    json_file(out / "statistics.json", {"graphs": summaries, "paired_sensitivity": paired, "archived_doorway_means": routes})
    json_file(out / "graphs.json", {name: nx.node_link_data(graph, edges="edges") for name, graph in graphs.items()})
    with (out / "nodes.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["graph", "node", *METRICS, "reachable"])
        writer.writeheader()
        for name, (_, rows) in datasets.items():
            writer.writerows({"graph": name, "node": node, **rows[node]} for node in sorted(rows))
    domain = from_wkb(outputs["topology"]["accessible_wkb"])
    settlement = outputs["settlement"]
    buildings = [list(from_wkb(settlement["polygons_wkb"][key]).exterior.coords)
                 for key in settlement["building_labels"]]
    atlas(out / "atlas.pdf", datasets, domain, buildings)
    report(out / "report.md", summaries, paired, routes, inventory)
    print(f"Completed {len(datasets)} analyses in {out}")


if __name__ == "__main__":
    main()
