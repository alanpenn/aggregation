"""Independently replay geometry and selected-network angular checks."""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from shapely import wkt
from shapely.ops import unary_union

from voronoi_app.angular import AngularNetwork, LineClearance, SampleAttachment
from voronoi_app.exact_axial import ExactCandidate, region_coverage
from voronoi_app.experimental_angular_selection import _structural_failure, angular_reference


parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--results", type=Path, default=Path("angular-hill-final-results.json"))
args = parser.parse_args()
state = args.data_dir
prepared = json.loads((state / "angular-hill-prepared.json").read_text())
reference = json.loads((state / "angular-hill-reference.json").read_text())
results = json.loads((state / args.results).read_text())
settlement = json.loads((state / "hill42-corridor-pool.json").read_text())
polygons = {int(i): wkt.loads(p) for i, p in settlement["polygons"].items()}
building = {int(i) for i in settlement["building_labels"]}
originals = [polygons[i] for i in sorted(building)]
occupied = unary_union(originals)
accessible = unary_union([p for i, p in polygons.items() if i not in building]).difference(occupied)
clearance = LineClearance(accessible, occupied, original_obstacles=originals)
regions = {int(i): wkt.loads(value) for i, value in settlement["regions"].items()}
lines = []
for i, record in enumerate(prepared["records"]):
    source = record["baseline"] or record["boundary"][0]
    start = tuple(map(Fraction, source["start"]))
    end = tuple(map(Fraction, source["end"]))
    lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
attachments = [SampleAttachment(tuple(map(Fraction, item["sample"])),
                                tuple(map(Fraction, item["point"])), item["line_id"])
               for item in prepared["attachments"]]
components = [item["component"] for item in prepared["attachments"]]
groups = [{i for i, value in enumerate(prepared["components"]) if value == component}
          for component in range(len(set(prepared["components"])))]
full = {(a, b): d for a, b, d in reference["depths"]}
coverage = [set(values) for values in prepared["covers"]]
checked_sets = {}
for entry in results:
    selected = frozenset(entry["best"]["selected"])
    if selected in checked_sets:
        continue
    print("validating", len(selected), "selected lines", flush=True)
    if not all(clearance.permits_exact(lines[i].start, lines[i].end) for i in selected):
        raise ValueError("Selected candidate failed exact clearance")
    selected_lines = [lines[i] for i in sorted(selected)]
    actual_coverage = region_coverage(selected_lines, regions)
    if set().union(*actual_coverage) != set(regions):
        raise ValueError("Recomputed exact convex coverage is incomplete")
    failure = _structural_failure(lines, coverage, set(regions), groups,
                                  prepared["obstacles"], selected)
    if failure:
        raise ValueError(f"Selected network fails {failure}")
    if any(item.line_id not in selected for item in attachments):
        raise ValueError("A fixed attachment candidate was removed")
    actual = angular_reference(selected_lines, attachments, components).depths
    if actual.keys() != full.keys():
        raise ValueError("Selected and reference ordered-pair sets differ")
    changes = {pair: actual[pair] - full[pair] for pair in full}
    for result in results:
        if frozenset(result["best"]["selected"]) == selected:
            if max(changes.values()) > result["epsilon"] + 1e-10:
                raise ValueError("Selected network exceeds its angular bound")
    # Independent reference implementation on a small, predetermined OD set.
    network = AngularNetwork.from_lines(selected_lines, [item.point for item in attachments])
    checks = [(0, 1), (1, 0), (0, 2), (17, 25), (25, 31), (31, 25),
              (52, 53), (54, 55)]
    for a, b in checks:
        value = network.shortest_depth(
            attachments[a].point, attachments[b].point,
            arrival=attachments[a].arrival, departure=attachments[b].departure,
        )
        if abs(value - actual[a, b]) > 1e-10:
            raise ValueError(f"Sparse angular result disagrees on pair {(a, b)}")
    checked_sets[selected] = {
        "lines": len(selected), "covered": len(set().union(*actual_coverage)),
        "rings": len(prepared["obstacles"]), "components": len(groups),
        "max_increase": max(changes.values()),
        "pair_count": len(changes), "independent_pairs": checks,
    }
    print("validated", checked_sets[selected], flush=True)
(state / "angular-hill-validation.json").write_text(json.dumps(list(checked_sets.values())))
