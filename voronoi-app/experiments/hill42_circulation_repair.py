"""Diagnose and construct exact Hill-42 circulation witnesses without changing selection."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely import wkt
from shapely.geometry import Polygon
from shapely.ops import unary_union

from voronoi_app.angular import (
    LineClearance, _crosses_polygon_interior_exact, _exact_point, _on_segment,
    _ring_location,
)
from voronoi_app.axial_generator import _parts
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_circulation_topology import (
    _matrix_rank, _ring_covers_cells, analyse_circulation_topology,
    bounded_face_rings,
)


EXPECTED_HASHES = {
    "hill-data": "8600caead6af8243a95e0203fe76f755bc03440042c28bd8e72246a94fd2812c",
    "hill-map": "b501c9490771a56d71c8fba5d5d2379766cf15fd0058cb580589924069502af5",
}

TARGET_REPAIR_IDS = {
    "label-2": (15536, 140, 606, 700, 12109, 13776, 13924),
    "label-17": (14270, 105, 560, 561, 13807, 13984, 14540, 15339, 15414),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def interval_key(line):
    return tuple(sorted((line.start, line.end)))


def point_json(point):
    return [str(value) for value in point]


def line_json(line):
    return {
        "candidate_id": line.line_id,
        "start": point_json(line.start),
        "end": point_json(line.end),
        "length": line.length,
        "source": line.source,
    }


def exact_candidate(line_id, start, end, source, clearance):
    return ExactCandidate.from_seed(line_id, start, end, source, clearance)


def pool_line(candidate_id, record, source):
    start, end = _exact_point(record["start"]), _exact_point(record["end"])
    return ExactCandidate(candidate_id, start, end, start, end, source)


def blocked_reason(line, clearance, effective_cells, polygons, labels):
    blockers = [
        cell for cell in sorted(effective_cells)
        if _crosses_polygon_interior_exact(line.start, line.end, polygons[cell])
    ]
    leaves_main = any(
        _crosses_polygon_interior_exact(line.start, line.end, outside)
        for outside in clearance.outside
    )
    if blockers:
        reason = "crosses_effectively_occupied_cell_interiors"
    elif leaves_main:
        reason = "leaves_main_open_component_or_enters_excluded_open_space"
    else:
        reason = "exact_clearance_rejection_without_interior_witness"
    return {
        "candidate_id": line.line_id,
        "reason": reason,
        "blocking_cells": blockers,
        "blocking_building_labels": [labels[cell] for cell in blockers if cell in labels],
        "leaves_main_open_component": leaves_main,
        "start": point_json(line.start),
        "end": point_json(line.end),
    }


def face_support_ids(face, lines):
    result = []
    for line in lines:
        if any(_on_segment(start, line.start, line.end)
               and _on_segment(end, line.start, line.end)
               for start, end in zip(face, face[1:])):
            result.append(line.line_id)
    return sorted(set(result))


def geometry_inputs(data_path, map_path):
    data = json.loads(data_path.read_text())
    map_data = json.loads(map_path.read_text())
    polygons = {int(cell): wkt.loads(value) for cell, value in data["polygons"].items()}
    labels = {int(cell): int(label) for cell, label in data["building_labels"].items()}
    buildings = set(labels)
    dyads = set(map(int, data["dyad_open_cells"]))
    candidates = {int(item["id"]): item for item in data["candidates"]}
    selected_records = sorted(map_data["lines"], key=lambda item: int(item["candidate_id"]))
    return data, polygons, labels, buildings, dyads, candidates, selected_records


def _draw_background(ax, polygons, topology, labels, block_labels, show_block_labels=True):
    main = set(topology["main_open_cells"])
    excluded = set(topology["excluded_open_cells"])
    block_for_cell = {
        cell: block["id"]
        for block in topology["occupied_blocks"] if block["kind"] != "boundary"
        for cell in block["cells"]
    }
    block_colors = plt.get_cmap("tab20")
    for cell, polygon in sorted(polygons.items()):
        color = "#f8f6f0" if cell in main else (
            "#e6a84b" if cell in excluded else "#a5a8ad"
        )
        ax.fill(*polygon.exterior.xy, facecolor=color, edgecolor="#e1dfd7",
                linewidth=.25, zorder=0)
        block_id = block_for_cell.get(cell)
        if block_id is not None:
            ax.plot(*polygon.exterior.xy, color=block_colors(
                int(block_id.rsplit("-", 1)[1]) % 20
            ), linewidth=1.1, zorder=3)
        if cell in labels and labels[cell] in (2, 17):
            point = polygon.representative_point()
            ax.text(point.x, point.y, str(labels[cell]), fontsize=6,
                    color="#111111", weight="bold", ha="center", va="center", zorder=6)
    if show_block_labels:
        for block in topology["occupied_blocks"]:
            if block["kind"] == "boundary":
                continue
            geometries = [polygons[cell] for cell in block["cells"]]
            point = unary_union(geometries).representative_point()
            ax.text(point.x, point.y, block_labels[block["id"]], fontsize=6,
                    ha="center", va="center", color="#20152b", weight="bold", zorder=7)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def _plot_lines(ax, lines, color, linewidth, linestyle="-", alpha=.9):
    for line in lines:
        ax.plot([float(line.start[0]), float(line.end[0])],
                [float(line.start[1]), float(line.end[1])],
                color=color, linewidth=linewidth, linestyle=linestyle,
                alpha=alpha, zorder=4)


def draw_diagnostic(path, polygons, labels, topology, original_lines, valid_original,
                    cycles_by_block):
    block_labels = {}
    for block in topology["occupied_blocks"]:
        if block["kind"] == "boundary":
            continue
        displayed = sorted(labels[cell] for cell in block["cells"] if cell in labels)
        special = f" (label {displayed[0]})" if displayed in ([2], [17]) else ""
        block_labels[block["id"]] = f"{block['id'].rsplit('-', 1)[1]}{special}"

    fig, axes = plt.subplots(1, 3, figsize=(18, 8), squeeze=False)
    axes = axes[0]
    all_bounds = [
        min(polygon.bounds[0] for polygon in polygons.values()),
        min(polygon.bounds[1] for polygon in polygons.values()),
        max(polygon.bounds[2] for polygon in polygons.values()),
        max(polygon.bounds[3] for polygon in polygons.values()),
    ]
    colors = plt.get_cmap("tab20")
    for index, ax in enumerate(axes):
        _draw_background(
            ax, polygons, topology, labels, block_labels, show_block_labels=index == 0
        )
    for line in original_lines:
        if line.line_id in valid_original:
            _plot_lines(axes[0], [valid_original[line.line_id]], "#29384a", .65, alpha=.72)
        else:
            _plot_lines(axes[0], [line], "#c43b32", .45, linestyle=(0, (3, 2)), alpha=.42)
    for index, (_, cycle_lines) in enumerate(cycles_by_block.items()):
        _plot_lines(axes[0], cycle_lines, colors(index % 20), .9, alpha=.85)
    axes[0].set(xlim=(all_bounds[0], all_bounds[2]), ylim=(all_bounds[1], all_bounds[3]),
                title="Hill 42 — all 11 block circuits")

    cell_for_label = {label: cell for cell, label in labels.items()}
    for ax, label, title in zip(
        axes[1:], (2, 17), ("Block around displayed building 2", "Block around displayed building 17")
    ):
        cell = cell_for_label[label]
        block = next(item for item in topology["occupied_blocks"]
                     if cell in item["cells"] and item["kind"] != "boundary")
        geometry = unary_union([polygons[item] for item in block["cells"]])
        min_x, min_y, max_x, max_y = geometry.bounds
        margin = max(max_x - min_x, max_y - min_y, 1) * 6
        ax.set(xlim=(min_x - margin, max_x + margin),
               ylim=(min_y - margin, max_y + margin), title=title)
        for line in original_lines:
            if line.line_id in valid_original:
                _plot_lines(ax, [valid_original[line.line_id]], "#29384a", .8, alpha=.8)
            else:
                _plot_lines(ax, [line], "#c43b32", .55, linestyle=(0, (3, 2)), alpha=.55)
        _plot_lines(ax, cycles_by_block[block["id"]], "#15803d", 1.6)

    handles = [
        Patch(facecolor="#f8f6f0", edgecolor="#e1dfd7", label="Main accessible open space"),
        Patch(facecolor="#a5a8ad", edgecolor="#e1dfd7", label="Building / occupied block"),
        Patch(facecolor="#e6a84b", edgecolor="#e1dfd7", label="Excluded open cell"),
        Line2D([0], [0], color="#29384a", lw=1.2, label="Selected legacy line (exact-clearance valid)"),
        Line2D([0], [0], color="#c43b32", lw=1.1, ls=(0, (3, 2)),
               label="Selected legacy line rejected by amended clearance"),
        Line2D([0], [0], color="#15803d", lw=1.8,
               label="Proposed exact cycle (overview color-coded by block)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Hill seed 42 — exact full-block circulation repair diagnostic", y=.98)
    fig.tight_layout(rect=(0, .08, 1, .95))
    with path.open("xb") as stream:
        fig.savefig(stream, format="png", dpi=180)
    plt.close(fig)


def run(data_path, map_path, output_dir):
    hashes = {"hill-data": sha256(data_path), "hill-map": sha256(map_path)}
    if hashes != EXPECTED_HASHES:
        raise ValueError(f"Preserved Hill input SHA-256 mismatch: {hashes}")
    data, polygons, labels, buildings, dyads, pool_records, map_records = geometry_inputs(
        data_path, map_path
    )
    selected_ids = set(map(int, data["selected"]))
    if selected_ids != {int(record["candidate_id"]) for record in map_records}:
        raise ValueError("Hill selected IDs differ between the saved map and polygon data")
    raw_selected = [
        ExactCandidate(
            int(record["candidate_id"]),
            _exact_point(record["start"]), _exact_point(record["end"]),
            _exact_point(record["start"]), _exact_point(record["end"]),
            "saved-hill-axial-map",
        )
        for record in map_records
    ]

    topology_without_lines = analyse_circulation_topology(polygons, buildings, dyads, [])
    main_open = set(topology_without_lines["main_open_cells"])
    effective_cells = buildings | set(topology_without_lines["excluded_open_cells"])
    accessible = unary_union([polygons[cell] for cell in sorted(main_open)])
    effective_occupied = unary_union([polygons[cell] for cell in sorted(effective_cells)])
    clearance = LineClearance(
        accessible, effective_occupied,
        original_obstacles=[polygons[cell] for cell in sorted(effective_cells)],
    )
    block_records = [
        block for block in topology_without_lines["occupied_blocks"]
        if block["kind"] != "boundary"
    ]
    block_for_cell = {
        cell: block["id"] for block in block_records for cell in block["cells"]
    }
    label_for_block = {
        block["id"]: sorted(labels[cell] for cell in block["cells"] if cell in labels)
        for block in block_records
    }
    label_to_cell = {label: cell for cell, label in labels.items()}
    target_blocks = {
        label: block_for_cell[label_to_cell[label]] for label in (2, 17)
    }

    selected_result = analyse_circulation_topology(
        polygons, buildings, dyads, raw_selected
    )
    valid_selected = {}
    rejected_selected = []
    for line in raw_selected:
        if clearance.permits_exact(line.start, line.end):
            valid_selected[line.line_id] = exact_candidate(
                line.line_id, line.start, line.end, line.source, clearance
            )
        else:
            rejected_selected.append(blocked_reason(
                line, clearance, effective_cells, polygons, labels
            ))

    exact_pool_safe_count = 0
    for record in pool_records.values():
        start, end = _exact_point(record["start"]), _exact_point(record["end"])
        exact_pool_safe_count += int(clearance.permits_exact(start, end))

    ring_candidate_ids = set(map(int, data["ring_candidates"]))
    ring_lines = [
        pool_line(candidate_id, pool_records[candidate_id], "saved-ring-candidate")
        for candidate_id in sorted(ring_candidate_ids)
    ]
    ring_safe_count = sum(
        clearance.permits_exact(line.start, line.end) for line in ring_lines
    )
    saved_ring_result = analyse_circulation_topology(
        polygons, buildings, dyads, ring_lines
    )

    stage_results = {}
    for stage_name in ("before_dominance", "before_collective", "selected"):
        candidate_ids = (
            selected_ids if stage_name == "selected"
            else set(map(int, data[stage_name]))
        )
        stage_lines = [
            pool_line(candidate_id, pool_records[candidate_id],
                      f"saved-selection-stage:{stage_name}")
            for candidate_id in sorted(candidate_ids)
        ]
        stage_result = analyse_circulation_topology(
            polygons, buildings, dyads, stage_lines
        )
        stage_results[stage_name] = {
            "line_count": len(stage_lines),
            "clearance_valid_line_count": stage_result["effective_clearance_line_count"],
            "bounded_faces_after_clearance": stage_result["bounded_axial_faces"],
            "independent_circulation_rank":
                stage_result["independent_circulation_rank"],
            "required_rank": stage_result["required_circulation_rank"],
            "missing_blocks": stage_result["missing_axial_rings"],
            "missing_independent_classes":
                stage_result["missing_independent_circulation_classes"],
        }

    dominance_removed = sorted(
        set(map(int, data["before_dominance"]))
        - set(map(int, data["before_collective"]))
    )
    collective_removed = sorted(
        set(map(int, data["before_collective"])) - selected_ids
    )

    pool_lines = {}
    for candidate_id in sorted(set().union(*map(set, TARGET_REPAIR_IDS.values()))):
        record = pool_records[candidate_id]
        pool_lines[candidate_id] = exact_candidate(
            candidate_id, record["start"], record["end"],
            "saved-pool-repair-seed", clearance,
        )
    target_cycles = {
        target_blocks[2]: [pool_lines[item] for item in TARGET_REPAIR_IDS["label-2"]],
        target_blocks[17]: [pool_lines[item] for item in TARGET_REPAIR_IDS["label-17"]],
    }

    target_repair_lines = [
        line for lines in target_cycles.values() for line in lines
    ]
    target_only_result = analyse_circulation_topology(
        polygons, buildings, dyads, target_repair_lines
    )
    target_augmentation_result = analyse_circulation_topology(
        polygons, buildings, dyads, raw_selected + target_repair_lines
    )

    hole_parts = [
        part for part in _parts(accessible) if isinstance(part, Polygon)
    ]
    next_boundary_id = 20000
    boundary_cycles = {}
    all_boundary_lines = {}
    for hole in topology_without_lines["internal_circulation_holes"]:
        block_ids = hole["associated_blocks"]
        if len(block_ids) != 1:
            raise ValueError(f"Expected a single block for {hole['id']}: {block_ids}")
        block_id = block_ids[0]
        if block_id in target_cycles:
            continue
        ring = hole_parts[hole["polygon_component"]].interiors[hole["ring_index"]]
        cycle_lines = []
        for start, end in zip(ring.coords, tuple(ring.coords)[1:]):
            line = exact_candidate(
                next_boundary_id, start, end, f"hole-boundary:{hole['id']}", clearance
            )
            next_boundary_id += 1
            key = interval_key(line)
            if key not in all_boundary_lines:
                all_boundary_lines[key] = line
            cycle_lines.append(all_boundary_lines[key])
        boundary_cycles[block_id] = list({
            interval_key(line): line for line in cycle_lines
        }.values())

    cycles_by_block = {**boundary_cycles, **target_cycles}
    repaired_by_interval = {}
    for lines in cycles_by_block.values():
        for line in lines:
            repaired_by_interval.setdefault(interval_key(line), line)
    repaired_lines = list(repaired_by_interval.values())
    repaired_result = analyse_circulation_topology(
        polygons, buildings, dyads, repaired_lines
    )
    if repaired_result["lines_crossing_effective_occupied_space"]:
        raise AssertionError("A proposed repair line crosses effective occupied space")
    if not repaired_result["circulation_constraints_satisfied"]:
        raise AssertionError("Proposed Hill repair fails full-block circulation rank")
    for lines in cycles_by_block.values():
        for line in lines:
            if not clearance.permits_exact(line.start, line.end):
                raise AssertionError(f"Repair candidate {line.line_id} fails exact clearance")

    original_faces = bounded_face_rings(raw_selected)
    old_point_vectors = []
    old_full_vectors = []
    old_face_records = []
    for face_index, face in enumerate(original_faces):
        points_inside = []
        full_blocks = []
        for block in block_records:
            geometry = unary_union([polygons[cell] for cell in block["cells"]])
            witness = _exact_point(geometry.representative_point().coords[0])
            if _ring_location(face, witness) >= 0:
                points_inside.append(block["id"])
                if _ring_covers_cells(face, block["cells"], polygons):
                    full_blocks.append(block["id"])
        if points_inside:
            old_point_vectors.append([
                int(block["id"] in points_inside) for block in block_records
            ])
        if full_blocks:
            old_full_vectors.append([
                int(block["id"] in full_blocks) for block in block_records
            ])
        support_ids = face_support_ids(face, raw_selected)
        if target_blocks[2] in points_inside and target_blocks[17] in points_inside:
            old_face_records.append({
                "face_index": face_index,
                "point_enclosed_blocks": points_inside,
                "whole_block_enclosed_blocks": full_blocks,
                "supporting_selected_candidate_ids": support_ids,
                "boundary_supports": [
                    blocked_reason(
                        next(line for line in raw_selected if line.line_id == line_id),
                        clearance, effective_cells, polygons, labels,
                    ) if not clearance.permits_exact(
                        next(line for line in raw_selected if line.line_id == line_id).start,
                        next(line for line in raw_selected if line.line_id == line_id).end,
                    ) else {
                        "candidate_id": line_id,
                        "reason": "exact_clearance_valid",
                        "blocking_cells": [],
                        "blocking_building_labels": [],
                        "leaves_main_open_component": False,
                    }
                    for line_id in support_ids
                ],
            })

    if not old_face_records:
        raise AssertionError("No legacy face encloses both target-block representative points")
    all_block_cycle_data = []
    for block in block_records:
        block_id = block["id"]
        cycle_lines = cycles_by_block[block_id]
        all_block_cycle_data.append({
            "block": block_id,
            "cells": sorted(block["cells"]),
            "displayed_building_labels": label_for_block[block_id],
            "associated_holes": block["associated_holes"],
            "witness_candidate_ids": sorted(line.line_id for line in cycle_lines),
            "witness_line_count": len(cycle_lines),
            "witness_length": sum(line.length for line in cycle_lines),
            "added_unique_lines": sum(
                interval_key(line) not in {
                    interval_key(base) for base in valid_selected.values()
                }
                for line in cycle_lines
            ),
        })

    target_added = {
        interval_key(line): line
        for lines in target_cycles.values() for line in lines
        if interval_key(line) not in {
            interval_key(base) for base in valid_selected.values()
        }
    }
    all_added = {
        interval_key(line): line for line in repaired_lines
        if interval_key(line) not in {
            interval_key(base) for base in valid_selected.values()
        }
    }
    result = {
        "input_sha256": hashes,
        "input_counts": {
            "voronoi_cells": len(polygons),
            "building_cells": len(buildings),
            "full_saved_candidate_pool": len(pool_records),
            "saved_selected_lines": len(raw_selected),
            "exact_clearance_valid_saved_lines": len(valid_selected),
            "exact_clearance_rejected_saved_lines": len(rejected_selected),
            "saved_pool_candidates_passing_exact_clearance": exact_pool_safe_count,
            "saved_pool_candidates_rejected_by_exact_clearance":
                len(pool_records) - exact_pool_safe_count,
            "saved_ring_candidate_count": len(ring_candidate_ids),
            "saved_ring_candidates_passing_exact_clearance": ring_safe_count,
            "saved_ring_candidates_rejected_by_exact_clearance":
                len(ring_candidate_ids) - ring_safe_count,
        },
        "topology": {
            "main_open_cells": topology_without_lines["main_open_component_size"],
            "excluded_open_components": topology_without_lines["excluded_open_component_sizes"],
            "internal_blocks": len(block_records),
            "independent_holes": len(topology_without_lines["internal_circulation_holes"]),
        },
        "targets": {
            str(label): {
                "block": target_blocks[label],
                "cells": next(block["cells"] for block in block_records
                              if block["id"] == target_blocks[label]),
                "all_displayed_labels_in_block": label_for_block[target_blocks[label]],
                "candidate_ids": list(TARGET_REPAIR_IDS[f"label-{label}"]),
            }
            for label in (2, 17)
        },
        "legacy_map": {
            "bounded_faces_without_clearance_filter": len(original_faces),
            "old_point_covered_block_count": sum(
                any(vector[index] for vector in old_point_vectors)
                for index in range(len(block_records))
            ),
            "old_point_winding_rank": _matrix_rank(old_point_vectors),
            "old_full_block_winding_rank": _matrix_rank(old_full_vectors),
            "valid_line_count_after_new_clearance": len(valid_selected),
            "selection_stages": stage_results,
            "dominance_removed_candidate_ids": dominance_removed,
            "collective_removed_candidate_ids": collective_removed,
            "saved_ring_candidate_clearance_result": {
                "effective_clearance_line_count":
                    saved_ring_result["effective_clearance_line_count"],
                "independent_circulation_rank":
                    saved_ring_result["independent_circulation_rank"],
                "required_rank": saved_ring_result["required_circulation_rank"],
                "missing_blocks": saved_ring_result["missing_axial_rings"],
                "missing_independent_classes":
                    saved_ring_result["missing_independent_circulation_classes"],
            },
            "rejected_line_diagnostics": rejected_selected,
            "shared_target_point_face_diagnostics": old_face_records,
            "corrected_selected_map": selected_result,
        },
        "target_repairs_only": {
            "additional_distinct_lines": len(target_added),
            "additional_total_length": sum(line.length for line in target_added.values()),
            "independent_circulation_rank": target_only_result["independent_circulation_rank"],
            "required_rank": target_only_result["required_circulation_rank"],
            "missing_blocks": target_only_result["missing_axial_rings"],
            "missing_independent_classes":
                target_only_result["missing_independent_circulation_classes"],
            "repair_network_line_count": len(target_repair_lines),
            "repair_network_length": sum(line.length for line in target_repair_lines),
            "saved_map_plus_repairs_rank":
                target_augmentation_result["independent_circulation_rank"],
            "saved_map_plus_repairs_missing_blocks":
                target_augmentation_result["missing_axial_rings"],
        },
        "all_11_block_repairs": {
            "added_distinct_lines": len(all_added),
            "added_total_length": sum(line.length for line in all_added.values()),
            "total_network_lines": len(repaired_lines),
            "total_network_length": sum(line.length for line in repaired_lines),
            "independent_circulation_rank": repaired_result["independent_circulation_rank"],
            "required_rank": repaired_result["required_circulation_rank"],
            "missing_axial_rings": repaired_result["missing_axial_rings"],
            "missing_independent_classes":
                repaired_result["missing_independent_circulation_classes"],
            "circulation_constraints_satisfied":
                repaired_result["circulation_constraints_satisfied"],
            "clearance_rejections": repaired_result["lines_crossing_effective_occupied_space"],
            "generated_boundary_candidate_count": len(all_boundary_lines),
            "legacy_clearance_valid_lines_included": 0,
            "block_cycle_witnesses": all_block_cycle_data,
        },
        "proposed_candidates": [line_json(line) for line in repaired_lines],
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    draw_diagnostic(
        output_dir / "hill42-circulation-repair-diagnostic.png",
        polygons, labels, topology_without_lines, raw_selected, valid_selected,
        cycles_by_block,
    )
    with (output_dir / "hill42-circulation-repair-results.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hill-data", type=Path, required=True)
    parser.add_argument("--hill-map", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.hill_data, args.hill_map, args.output_dir)
    print(json.dumps({
        "input_counts": result["input_counts"],
        "topology": result["topology"],
        "legacy_map": {
            key: value for key, value in result["legacy_map"].items()
            if key not in ("rejected_line_diagnostics", "shared_target_point_face_diagnostics",
                           "corrected_selected_map")
        },
        "target_repairs_only": {
            key: value for key, value in result["target_repairs_only"].items()
            if key != "block_witnesses"
        },
        "all_11_block_repairs": {
            key: value for key, value in result["all_11_block_repairs"].items()
            if key != "block_cycle_witnesses"
        },
    }, indent=2))


if __name__ == "__main__":
    main()
