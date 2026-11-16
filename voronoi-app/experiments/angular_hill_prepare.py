import argparse
import json
import time
from fractions import Fraction
from math import hypot
from pathlib import Path

import networkx as nx
from shapely import wkt
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, _direction, _on_segment
from voronoi_app.angular_optimisation import _component_geometries, _obstacles
from voronoi_app.exact_axial import (
    ExactCandidate, _component_groups, candidate_graph, region_coverage,
)
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_boundary_candidates import canonical_interval


parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
state = parser.parse_args().data_dir
started = time.monotonic()
saved = json.loads((state / "hill42-corridor-pool.json").read_text())
base_data = json.loads((state / "hill42-fresh-exact-baseline.json").read_text())
boundary = json.loads((state / "boundary-hill42.json").read_text())
pool = exact_pool_from_dict(base_data)
polygons = {int(i): wkt.loads(p) for i, p in saved["polygons"].items()}
building = {int(i) for i in saved["building_labels"]}
originals = [polygons[i] for i in sorted(building)]
occupied = unary_union(originals)
accessible = unary_union([p for i, p in polygons.items() if i not in building]).difference(occupied)
clearance = LineClearance(accessible, occupied, original_obstacles=originals)
regions = {int(i): wkt.loads(value) for i, value in saved["regions"].items()}
lines = list(pool.candidates)
index = {canonical_interval(line.start, line.end): i for i, line in enumerate(lines)}
records = [{"baseline": base_data["candidates"][i], "boundary": []}
           for i in range(len(lines))]
for item in boundary["candidates"]:
    start = tuple(map(Fraction, item["start"]))
    end = tuple(map(Fraction, item["end"]))
    key = canonical_interval(start, end)
    if key not in index:
        index[key] = len(lines)
        lines.append(ExactCandidate(len(lines), start, end, start, end, "boundary-experiment"))
        records.append({"baseline": None, "boundary": []})
    records[index[key]]["boundary"].append(item)
print("merged", len(lines), "seconds", round(time.monotonic() - started, 1), flush=True)
bad = []
for i, line in enumerate(lines):
    if not clearance.permits_exact(line.start, line.end):
        bad.append(i)
    if i % 500 == 0:
        print("certified", i, "bad", bad, "seconds",
              round(time.monotonic() - started, 1), flush=True)
if bad:
    raise ValueError(f"Exact clearance failed: {bad}")
groups = _component_groups(accessible, lines)
component = {i: c for c, group in enumerate(groups) for i in group}
components = _component_geometries(accessible)
main = max(range(len(components)), key=lambda c: components[c].area)
print("groups", [len(group) for group in groups], "main", main, flush=True)

old = []
for identifier in saved["selected"]:
    for support in saved["candidates"][identifier]["supports"]:
        if clearance.permits_exact(support["start"], support["end"]):
            old.append(ExactCandidate.from_seed(identifier, support["start"], support["end"],
                                                 support["source"], clearance))
            break
    else:
        raise ValueError(f"No valid support for historical line {identifier}")
graph = candidate_graph(old)
largest = max(nx.connected_components(graph), key=len)
old_main = [line for i, line in enumerate(old) if i in largest]
if len(old_main) != 39:
    raise ValueError(f"Unexpected historical main-component count {len(old_main)}")
samples = [tuple((line.start[k] + line.end[k]) / 2 for k in range(2))
           for line in old_main[:36]]
selected_exact = [index[canonical_interval(line.start, line.end)] for line in old
                  if canonical_interval(line.start, line.end) in index]
print("historical", len(old), "exact pooled", len(selected_exact),
      "seconds", round(time.monotonic() - started, 1), flush=True)
for c, group in enumerate(groups):
    subset = sorted(group, key=lambda i: (-lines[i].length, i))
    if c == main:
        bins = {}
        minx, miny, maxx, maxy = components[c].bounds
        for i in subset:
            line = lines[i]
            point = tuple((line.start[k] + line.end[k]) / 2 for k in range(2))
            x, y = map(float, point)
            cell = (min(3, int((x - minx) / (maxx - minx) * 4)),
                    min(3, int((y - miny) / (maxy - miny) * 4)))
            bins.setdefault(cell, point)
        samples.extend(bins[k] for k in sorted(bins))
    else:
        a, b = lines[subset[0]].start, lines[subset[0]].end
        samples.extend(tuple((a[k] * (3 - t) + b[k] * t) / 3 for k in range(2))
                       for t in (1, 2))
attachment_records = []
geometries = [LineString([(float(x), float(y)) for x, y in (line.start, line.end)])
              for line in lines]
for number, sample in enumerate(samples):
    matches = [i for i, line in enumerate(lines) if _on_segment(sample, line.start, line.end)]
    if matches:
        i = min(matches)
        point = sample
    else:
        distances = sorted(range(len(lines)),
                           key=lambda i: (geometries[i].distance(
                               Point(float(sample[0]), float(sample[1]))), i))
        for i in distances:
            line = lines[i]
            v = _direction(line.start, line.end)
            t = sum((sample[k] - line.start[k]) * v[k] for k in range(2)) / sum(x*x for x in v)
            t = min(Fraction(1), max(Fraction(0), t))
            point = tuple(line.start[k] + t * v[k] for k in range(2))
            if clearance.permits_exact(sample, point):
                break
        else:
            raise ValueError(f"No clear fixed connector for sample {number}")
    attachment_records.append({"sample": [str(v) for v in sample],
                               "point": [str(v) for v in point],
                               "line_id": i, "component": component[i]})
print("samples", len(samples), "by_component",
      [sum(item["component"] == c for item in attachment_records) for c in range(len(groups))],
      "nonzero_connectors", sum(item["sample"] != item["point"] for item in attachment_records),
      "seconds", round(time.monotonic() - started, 1), flush=True)
covers = pool.covers + region_coverage(lines[len(pool.candidates):], regions)
print("coverage missing", sorted(set(regions) - set().union(*covers)), flush=True)
tolerance = max(hypot(accessible.bounds[2] - accessible.bounds[0],
                      accessible.bounds[3] - accessible.bounds[1]) * 1e-9, 1e-12)
obstacles, _ = _obstacles(accessible, occupied, tolerance)
result = {
    "records": records, "covers": [sorted(value) for value in covers],
    "components": [component[i] for i in range(len(lines))],
    "attachments": attachment_records, "regions": len(regions),
    "ring_candidates": sorted(pool.ring_candidates),
    "obstacles": [[p.x, p.y] for p in obstacles],
    "old_selected_in_pool": selected_exact,
    "old_selected_count": len(old),
    "exact_clearance_failures": bad,
    "baseline_count": len(pool.candidates),
}
(state / "angular-hill-prepared.json").write_text(json.dumps(result))
print("saved preparation", "witnesses", len(obstacles), "seconds",
      round(time.monotonic() - started, 1), flush=True)
