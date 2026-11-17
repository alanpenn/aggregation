"""Replay the live convex selector from a saved Valley diagnostic snapshot."""

import argparse
import json
import time
from math import hypot
from pathlib import Path

from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from voronoi_app.axial_generator import _parts, _select_axial_candidates
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions, line_region_coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    opened, buildings, generated, _, _ = load_axial_snapshot(snapshot)
    live = generated.candidate_lines
    if [line.line_id for line in live] != list(range(len(live))):
        raise ValueError("Live candidate IDs are not consecutive indices")
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    min_x, min_y, max_x, max_y = accessible.bounds
    tolerance = max(hypot(max_x - min_x, max_y - min_y) * 1e-9, 1e-12)
    support_index = {}
    for line in live:
        for support in line.attributes["supports"]:
            key = (support["source"], tuple(support["start"]), tuple(support["end"]))
            if key in support_index and support_index[key] != line.line_id:
                raise ValueError("A live support maps to multiple candidates")
            support_index[key] = line.line_id
    obstacles = []
    ring_candidates = set()
    missing_edges = []
    for part in _parts(accessible):
        if not isinstance(part, Polygon):
            continue
        for ring in orient(part, sign=1.0).interiors:
            components = [
                component for component in _parts(Polygon(ring).intersection(occupied))
                if isinstance(component, Polygon) and component.area > tolerance * tolerance
            ]
            if not components:
                continue
            obstacles.extend(component.representative_point() for component in components)
            vertices = list(ring.coords)[:-1]
            for i, start in enumerate(vertices):
                end = vertices[(i + 1) % len(vertices)]
                if hypot(end[0] - start[0], end[1] - start[1]) <= tolerance:
                    continue
                key = ("boundary", tuple(start), tuple(end))
                if key in support_index:
                    ring_candidates.add(support_index[key])
                else:
                    missing_edges.append((start, end))
    if missing_edges:
        raise ValueError(f"{len(missing_edges)} occupied-hole edges lack live support")
    lines = [LineString((line.start, line.end)) for line in live]
    regions = convex_regions(accessible)
    covers = line_region_coverage(lines, regions)
    print("live candidates", len(lines), "regions", len(regions), "rings", len(obstacles),
          "ring candidates", len(ring_candidates), flush=True)
    started = time.monotonic()
    selected = _select_axial_candidates(lines, covers, set(regions), ring_candidates,
                                         accessible, obstacles, tolerance,
                                         coverage_model="convex")
    output = {"selected": sorted(selected.selected), "ring_candidates": sorted(ring_candidates),
              "regions": len(regions), "rings": len(obstacles),
              "seconds": time.monotonic() - started}
    with (args.data_dir / "live-selection.json").open("x") as file:
        json.dump(output, file)
    print("live selected", len(selected.selected), "seconds", round(output["seconds"], 2),
          flush=True)


if __name__ == "__main__":
    main()
