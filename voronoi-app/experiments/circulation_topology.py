"""Validate circulation holes after classifying disconnected open cells as occupied."""

import argparse
import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely import wkt

from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_circulation_topology import analyse_circulation_topology


EXPECTED_HASHES = {
    "hill-data": "8600caead6af8243a95e0203fe76f755bc03440042c28bd8e72246a94fd2812c",
    "hill-map": "b501c9490771a56d71c8fba5d5d2379766cf15fd0058cb580589924069502af5",
    "y-snapshot": "55f48c21d92b43d6896304e6918c716e212a673cdf2dfeb2e9dcdf26d9438597",
    "y-prepared": "bf501a185a940dc5b70535696cb8ee8e7921fe4093aef57d4f7f8f5287bf48d6",
    "y-settlement": "9365cdfb6bfc8cd83afde32a63c30ae4beb5f2bfd0b71dd7b94b44f9f36b4d59",
    "y-selection": "e7bf59439e7692252e183c9b5b9759912867cdfbca1ec8eed338358c9ffcc6e9",
    "y-structural": "42a27781612440f6f20088b770f08e415d6ea2f4caf249befe751fbdb3743be5",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_candidate(line_id, start, end, source):
    a = tuple(Fraction(value) for value in start)
    b = tuple(Fraction(value) for value in end)
    return ExactCandidate(line_id, a, b, a, b, source)


def hill_input(data_path, map_path):
    data = json.loads(data_path.read_text())
    map_data = json.loads(map_path.read_text())
    polygons = {int(cell): wkt.loads(value) for cell, value in data["polygons"].items()}
    buildings = set(map(int, data["building_labels"]))
    dyads = set(map(int, data["dyad_open_cells"]))
    selected_ids = set(map(int, data["selected"]))
    lines_by_id = {int(line["candidate_id"]): line for line in map_data["lines"]}
    if selected_ids != set(lines_by_id):
        raise ValueError("Hill selected IDs differ between the saved map and polygon data")
    lines = [exact_candidate(int(line["candidate_id"]), line["start"], line["end"],
                             "saved-hill-axial-map")
             for line in sorted(map_data["lines"], key=lambda item: int(item["candidate_id"]))]
    labels = {int(cell): int(label) for cell, label in data["building_labels"].items()}
    return polygons, buildings, dyads, {"Hill saved 41-line map": lines}, labels


def y_input(snapshot_path, prepared_path, selection_path, structural_path, settlement_path):
    snapshot = json.loads(snapshot_path.read_text())
    opened, buildings, _, _, dyads = load_axial_snapshot(snapshot)
    polygons = {**opened, **buildings}
    prepared = json.loads(prepared_path.read_text())
    settlement = json.loads(settlement_path.read_text())
    selection = json.loads(selection_path.read_text())
    with gzip.open(structural_path, "rt") as stream:
        structural = json.load(stream)
    candidates = []
    for candidate_id, record in enumerate(prepared["records"]):
        source = record["baseline"] or record["boundary"][0]
        candidates.append(exact_candidate(candidate_id, source["start"], source["end"],
                                          "saved-certified-candidate"))
    maps = {}
    for name in ("greedy", "connectivity"):
        ids = selection[name]["selected"]
        maps[f"Y {name} 29-line map"] = [candidates[i] for i in ids]
    ids = structural["maps"]["gain-0.25%-completed"]["selected"]
    maps["Y completed structural 66-line map"] = [candidates[i] for i in ids]
    labels = {int(cell): int(label) for cell, label in settlement["building_labels"].items()}
    return polygons, set(buildings), dyads, maps, labels


def figure(path, title, polygons, map_results, labels, selected_maps):
    fig, axes = plt.subplots(
        1, len(selected_maps),
        figsize=(11 if len(selected_maps) == 1 else 6.4 * len(selected_maps), 10),
        squeeze=False, sharex=True, sharey=True,
    )
    axes = axes[0]
    buildings = set(map(int, labels))
    bounds = (
        min(polygon.bounds[0] for polygon in polygons.values()),
        min(polygon.bounds[1] for polygon in polygons.values()),
        max(polygon.bounds[2] for polygon in polygons.values()),
        max(polygon.bounds[3] for polygon in polygons.values()),
    )
    for ax, (name, lines) in zip(axes, selected_maps.items()):
        result = map_results[name]
        main = set(result["main_open_cells"])
        excluded = set(result["excluded_open_cells"])
        block_cells = {
            cell for block in result["occupied_blocks"] if block["kind"] != "boundary"
            for cell in block["cells"]
        }
        for cell, polygon in sorted(polygons.items()):
            color = "#f5f2e9" if cell in main else (
                "#e6a84b" if cell in excluded else "#8d929a"
            )
            ax.fill(*polygon.exterior.xy, facecolor=color, edgecolor="#e1dfd7",
                    linewidth=.25, zorder=0)
            if cell in buildings:
                point = polygon.representative_point()
                ax.text(point.x, point.y, str(labels[cell]), fontsize=4.2,
                        ha="center", va="center", color="white", zorder=3)
        for cell in block_cells:
            x, y = polygons[cell].exterior.xy
            ax.plot(x, y, color="#8c3c82", linewidth=.65, zorder=2)
        rejected = set(result["lines_crossing_effective_occupied_space"])
        for line in lines:
            is_rejected = line.line_id in rejected
            ax.plot(
                [float(line.start[0]), float(line.end[0])],
                [float(line.start[1]), float(line.end[1])],
                color="#c43b32" if is_rejected else "#126c9b",
                linewidth=.7 if is_rejected else .9,
                linestyle=(0, (3, 2)) if is_rejected else "-",
                alpha=.72 if is_rejected else .9,
                zorder=1,
            )
        kept_count = len(lines) - len(rejected)
        rank = result["independent_circulation_rank"]
        required = result["required_circulation_rank"]
        ax.set_aspect("equal")
        ax.set(
            xlim=(bounds[0], bounds[2]), ylim=(bounds[1], bounds[3]),
            title=(f"{name}\n{kept_count}/{len(lines)} clearance-valid lines; "
                   f"winding rank {rank}/{required}"),
        )
        ax.set_xticks([])
        ax.set_yticks([])
    legend = [
        Patch(facecolor="#f5f2e9", edgecolor="#e1dfd7", label="Main accessible component"),
        Patch(facecolor="#8d929a", edgecolor="#e1dfd7", label="Building / occupied block"),
        Patch(facecolor="#e6a84b", edgecolor="#e1dfd7", label="Excluded open cell"),
        Line2D([0], [0], color="#8c3c82", lw=1.2, label="Internal occupied block"),
        Line2D([0], [0], color="#126c9b", lw=1.4, label="Clearance-valid axial line"),
        Line2D([0], [0], color="#c43b32", lw=1.2, ls=(0, (3, 2)),
               label="Rejected by amended clearance"),
    ]
    fig.legend(handles=legend, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(title, y=.98)
    fig.tight_layout(rect=(0, .08, 1, .95))
    with path.open("xb") as stream:
        fig.savefig(stream, format="png", dpi=170)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hill-data", type=Path, required=True)
    parser.add_argument("--hill-map", type=Path, required=True)
    parser.add_argument("--y-snapshot", type=Path, required=True)
    parser.add_argument("--y-prepared", type=Path, required=True)
    parser.add_argument("--y-settlement", type=Path, required=True)
    parser.add_argument("--y-selection", type=Path, required=True)
    parser.add_argument("--y-structural", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source_paths = {
        "hill-data": args.hill_data, "hill-map": args.hill_map,
        "y-snapshot": args.y_snapshot, "y-prepared": args.y_prepared,
        "y-settlement": args.y_settlement,
        "y-selection": args.y_selection,
        "y-structural": args.y_structural,
    }
    hashes = {}
    for name, path in source_paths.items():
        actual = sha256(path)
        if actual != EXPECTED_HASHES[name]:
            raise ValueError(f"Preserved {name} input SHA-256 mismatch")
        hashes[name] = actual
    datasets = {
        "hill": hill_input(args.hill_data, args.hill_map),
        "y": y_input(args.y_snapshot, args.y_prepared, args.y_selection, args.y_structural,
                     args.y_settlement),
    }
    results = {"input_sha256": hashes, "datasets": {}}
    for name, (polygons, buildings, dyads, maps, metadata) in datasets.items():
        dataset_result = {
            "input": {"cell_count": len(polygons), "building_cells": len(buildings),
                      "dyad_open_cells": len(dyads),
                      "unfilled_open_cells": len(set(polygons) - buildings - dyads)},
            "maps": {},
        }
        for map_name, lines in maps.items():
            topology = analyse_circulation_topology(polygons, buildings, dyads, lines)
            topology["summary"] = {
                "main_component_size": topology["main_open_component_size"],
                "excluded_open_components": topology["excluded_open_component_sizes"],
                "occupied_block_count": len(topology["occupied_blocks"]),
                "internal_occupied_blocks": len(topology["internal_blocks"]),
                "independent_circulation_holes": len(topology["circulation_holes"]),
                "independent_circulation_rank": topology["independent_circulation_rank"],
                "required_circulation_rank": topology["required_circulation_rank"],
                "missing_independent_circulation_classes":
                    topology["missing_independent_circulation_classes"],
                "circulation_constraints_satisfied":
                    topology["circulation_constraints_satisfied"],
                "missing_axial_rings": len(topology["missing_axial_rings"]),
                "unassociated_internal_blocks": len(topology["unassociated_internal_blocks"]),
                "selected_lines_rejected_by_effective_clearance":
                    len(topology["lines_crossing_effective_occupied_space"]),
            }
            topology["selected_lines"] = [
                {"line_id": line.line_id, "start": [str(value) for value in line.start],
                 "end": [str(value) for value in line.end]}
                for line in lines
            ]
            dataset_result["maps"][map_name] = topology
        results["datasets"][name] = dataset_result
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, (polygons, buildings, dyads, maps, metadata) in datasets.items():
        dataset_result = results["datasets"][name]
        figure(args.output_dir / f"{name}-circulation-topology.png",
               f"{name.upper()} seed 42 axial maps under amended topology rules",
               polygons, dataset_result["maps"], metadata, maps)
    with (args.output_dir / "topology-results.json").open("x") as stream:
        json.dump(results, stream, indent=2, allow_nan=False)
    print(json.dumps({
        name: {map_name: data["summary"] for map_name, data in entry["maps"].items()}
        for name, entry in results["datasets"].items()
    }, indent=2))


if __name__ == "__main__":
    main()
