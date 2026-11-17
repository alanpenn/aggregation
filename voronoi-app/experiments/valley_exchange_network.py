"""Build a fixed-terminal exact candidate network for the Valley exchange study."""

import argparse
import json
import time
from fractions import Fraction
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, _direction, _exact_point, _on_segment
from voronoi_app.angular_optimisation import _component_geometries, _obstacles
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import ExactCandidate, _component_groups, region_coverage
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_boundary_candidates import canonical_interval


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    state = args.data_dir
    snapshot = json.loads(args.snapshot.read_text())
    opened, buildings, _, _, _ = load_axial_snapshot(snapshot)
    baseline_data = json.loads((state / "baseline.json").read_text())
    boundary = json.loads((state / "boundary.json").read_text())
    pool = exact_pool_from_dict(baseline_data)
    originals = [buildings[i] for i in sorted(buildings)]
    occupied = unary_union(originals)
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=originals)
    regions = convex_regions(accessible)
    lines = list(pool.candidates)
    records = [{"baseline": item, "boundary": []} for item in baseline_data["candidates"]]
    index = {canonical_interval(line.start, line.end): i for i, line in enumerate(lines)}
    for item in boundary["candidates"]:
        start, end = (tuple(map(Fraction, item[key])) for key in ("start", "end"))
        key = canonical_interval(start, end)
        if key not in index:
            i = len(lines)
            index[key] = i
            lines.append(ExactCandidate(i, start, end, start, end, "boundary-experiment"))
            records.append({"baseline": None, "boundary": []})
        records[index[key]]["boundary"].append(item)
    print("combined", len(lines), "baseline", len(pool.candidates),
          "boundary", len(boundary["candidates"]), flush=True)
    start_time = time.monotonic()
    for i, line in enumerate(lines):
        if not clearance.permits_exact(line.start, line.end):
            raise ValueError(f"Exact clearance failed for candidate {i}")
    print("clearance checked", len(lines), "seconds",
          round(time.monotonic() - start_time, 2), flush=True)
    groups = _component_groups(accessible, lines)
    components = {i: c for c, group in enumerate(groups) for i in group}
    if len(components) != len(lines):
        raise ValueError("A candidate has no unique accessible component")
    component_geometry = _component_geometries(accessible)
    if len(component_geometry) != len(groups):
        raise ValueError("Candidate and domain component counts disagree")
    saved_reference = json.loads(args.reference.read_text())
    samples = [_exact_point(sample) for sample in saved_reference["samples"]]
    for c, group in enumerate(groups):
        bins = {}
        min_x, min_y, max_x, max_y = component_geometry[c].bounds
        for i in sorted(group, key=lambda j: (-lines[j].length, j)):
            line = lines[i]
            point = tuple((line.start[k] + line.end[k]) / 2 for k in range(2))
            x, y = map(float, point)
            cell = (min(3, max(0, int((x - min_x) / (max_x - min_x) * 4))),
                    min(3, max(0, int((y - min_y) / (max_y - min_y) * 4))))
            bins.setdefault(cell, point)
        samples.extend(bins[cell] for cell in sorted(bins))
    samples = list(dict.fromkeys(samples))
    geometries = [LineString([(float(x), float(y)) for x, y in (line.start, line.end)])
                  for line in lines]
    attachments = []
    for number, sample in enumerate(samples):
        if not clearance.permits_exact(sample, sample):
            raise ValueError(f"Sample {number} is outside accessible space")
        matches = [i for i, line in enumerate(lines)
                   if _on_segment(sample, line.start, line.end)]
        if matches:
            i, point = min(matches), sample
        else:
            order = sorted(range(len(lines)),
                           key=lambda i: (geometries[i].distance(
                               Point(float(sample[0]), float(sample[1]))), i))
            for i in order:
                line = lines[i]
                direction = _direction(line.start, line.end)
                t = sum((sample[k] - line.start[k]) * direction[k] for k in range(2))
                t /= sum(value * value for value in direction)
                t = min(Fraction(1), max(Fraction(0), t))
                point = tuple(line.start[k] + t * direction[k] for k in range(2))
                if clearance.permits_exact(sample, point):
                    break
            else:
                raise ValueError(f"No clear fixed attachment for sample {number}")
        attachments.append({"sample": [str(v) for v in sample],
                            "point": [str(v) for v in point],
                            "line_id": i, "component": components[i]})
    covers = pool.covers + region_coverage(lines[len(pool.candidates):], regions)
    if set().union(*covers) != set(regions):
        raise ValueError("The combined pool does not cover all convex regions")
    bounds = accessible.bounds
    tolerance = max(((bounds[2] - bounds[0]) ** 2 + (bounds[3] - bounds[1]) ** 2) ** .5 * 1e-9,
                    1e-12)
    witnesses, _ = _obstacles(accessible, occupied, tolerance)
    output = {
        "records": records, "covers": [sorted(value) for value in covers],
        "components": [components[i] for i in range(len(lines))],
        "attachments": attachments, "regions": len(regions),
        "ring_candidates": sorted(pool.ring_candidates),
        "obstacles": [[point.x, point.y] for point in witnesses],
        "baseline_count": len(pool.candidates),
    }
    with (state / "prepared.json").open("x") as file:
        json.dump(output, file)
    print("samples", len(samples), "pinned", len({a["line_id"] for a in attachments}),
          "components", [len(group) for group in groups], "regions", len(regions),
          "rings", len(witnesses), flush=True)


if __name__ == "__main__":
    main()
