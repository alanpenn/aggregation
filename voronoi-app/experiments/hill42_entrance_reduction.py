"""Reduce Hill 42 using all valid building entrance pairs as depth terminals."""

import argparse
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from shapely import wkt
from shapely.ops import unary_union

from experiments.doorway_backbone import reconstruct
from experiments.hill42_clique_reduction import read
from voronoi_app.experimental_entrance_reduction import (
    entrance_depth, entrance_seed, fixed_terminal_attachments, improve_entrance_depth,
    shared_faces, summary, union_mask, visibility_masks,
)
from voronoi_app.angular import LineClearance
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import _bounds, candidate_graph
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_circulation_topology import analyse_circulation_topology
from voronoi_app.experimental_visibility import IndexedClearance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "hill-data", "pool", "topology", "reduction", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--connector-limit", type=int, default=64)
    parser.add_argument("--budget", type=int, default=130)
    args = parser.parse_args()
    snapshot, hill, topology = read(args.snapshot), read(args.hill_data), read(args.topology)
    opened, buildings, _, _, paired = load_axial_snapshot(snapshot)
    labels = {int(i): label for i, label in hill["building_labels"].items()}
    polygons = {int(i): wkt.loads(value) for i, value in hill["polygons"].items()}
    if set(polygons) != set(opened) | set(buildings) or any(
        not polygons[i].equals_exact(p, 0) for i, p in {**opened, **buildings}.items()
    ):
        raise ValueError("Entrance snapshot does not match Hill candidate geometry")
    doors = reconstruct(snapshot, opened, buildings, paired, labels).doors
    main_open = set(topology["main_open_cells"])
    occupied = unary_union([polygons[i] for i in topology["effective_occupied_cells"]])
    accessible = unary_union([polygons[i] for i in sorted(main_open)]).difference(occupied)
    clearance = IndexedClearance(LineClearance(
        accessible, occupied, original_obstacles=[polygons[i] for i in topology["effective_occupied_cells"]],
    ))
    records, points = [], []
    for open_id, building_id in doors:
        faces = shared_faces(opened[open_id], buildings[building_id])
        record = {"open_cell": int(open_id), "building": int(labels[building_id])}
        if open_id not in main_open:
            record["status"] = "outside-main-space"
        elif len(faces) != 1:
            record["status"] = "missing-face" if not faces else "ambiguous-face"
        else:
            point = tuple((a + b) / 2 for a, b in zip(*faces[0]))
            if clearance.permits(point, point):
                record.update(status="valid", point=list(map(str, point)))
                points.append(point)
            else:
                record["status"] = "blocked"
        records.append(record)
    print("Entrances", dict(Counter(r["status"] for r in records)), flush=True)
    if len({r["building"] for r in records}) != len(records):
        raise ValueError("Expected one entrance per Hill building")
    pool = exact_pool_from_dict(read(args.pool)["pool"])
    lines = pool.candidates
    fixed = fixed_terminal_attachments(
        points, lines, SimpleNamespace(permits_exact=clearance.permits), args.connector_limit,
    )
    links = [{link.line_id for link in options} for options in fixed]
    for record, options in zip((r for r in records if r["status"] == "valid"), fixed, strict=True):
        record["connectors"] = [{"line": a.line_id, "point": list(map(str, a.point))} for a in options]
    print("Certified fixed connectors", sum(map(len, links)), flush=True)
    graph = candidate_graph(lines)
    previous = read(args.reduction)
    witnesses = set(previous["mandatory_ring_lines"])
    regions = convex_regions(accessible)
    covers = visibility_masks(lines, pool.covers, regions, [_bounds(line) for line in lines])
    target = sum(1 << i for i in regions)
    maps = {"full": set(graph)}
    maps.update({name: set(entry["selected"]) for name, entry in previous["maps"].items()})
    maps["degree-with-five-shortcuts"] = maps["degree"] | {1085, 802, 557, 358, 560}
    compact, door_masks = entrance_seed(graph, links, witnesses, covers, target)
    maps["entrance-compact"] = compact
    selected, trail = improve_entrance_depth(graph, lines, links, door_masks, compact, args.budget)
    maps["entrance-depth-guided"] = selected

    result = {"entrances": records, "connector_limit": args.connector_limit,
              "depth_growth": trail, "maps": {}}
    reference = entrance_depth(graph, maps["full"], links)
    for name, selected in maps.items():
        values = entrance_depth(graph, selected, links)
        entry = summary(values, sum(bool(o & selected) for o in links))
        both = np.isfinite(values) & np.isfinite(reference)
        entry.update(lines=len(selected), selected=sorted(selected),
                     worse_by_two_or_more=int(np.count_nonzero(values[both] - reference[both] >= 2)),
                     covered_regions=union_mask(covers, selected).bit_count())
        if name.startswith("entrance-"):
            check = analyse_circulation_topology(
                polygons, buildings, paired, [lines[i] for i in sorted(selected)],
            )
            if not check["circulation_constraints_satisfied"] or check["lines_crossing_effective_occupied_space"]:
                raise ValueError(f"{name} failed exact circulation certification")
            entry["winding_rank"] = check["independent_circulation_rank"]
        result["maps"][name] = entry
        print(name, {k: v for k, v in entry.items() if k != "selected"}, flush=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
