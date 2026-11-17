"""Compare exact-pool greedy and connectivity-first Valley axial maps."""

import argparse
import gzip
import json
import time
from fractions import Fraction
from pathlib import Path

from shapely.ops import unary_union

from voronoi_app.angular import LineClearance
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import (
    ExactCandidate, ExactCandidateSet, candidate_graph, closed_routes, greedy_selection,
    region_coverage,
)
from voronoi_app.experimental_connectivity_selection import (
    connectivity_cover, improve_topology, repair_selection, structural_failure,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--additions", type=int, default=400)
    parser.add_argument("--checks", type=int, default=300)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--three-for-two-additions", type=int, default=40)
    args = parser.parse_args()
    data = json.loads((args.data_dir / "prepared.json").read_text())
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    groups = [{i for i, c in enumerate(data["components"]) if c == component}
              for component in range(len(set(data["components"])))]
    covers = [set(values) for values in data["covers"]]
    regions = convex_regions(accessible)
    targets = set(regions)
    if targets != set(range(data["regions"])) or region_coverage(lines, regions) != covers:
        raise ValueError("Prepared and freshly computed exact convex coverage differ")
    for i, line in enumerate(lines):
        if not clearance.permits_exact(line.start, line.end):
            raise ValueError(f"Candidate {i} fails exact clearance")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    print("building full exact candidate graph", len(lines), flush=True)
    graph = candidate_graph(lines)
    graph_seconds = time.monotonic() - started
    with gzip.open(args.output_dir / "candidate-graph.json.gz", "xt") as file:
        json.dump({"degrees": [graph.degree[i] for i in range(len(lines))],
                   "edges": sorted([min(a, b), max(a, b)] for a, b in graph.edges),
                   "seconds": graph_seconds}, file)
    print("graph", graph.number_of_edges(), "edges", round(graph_seconds, 2), "seconds", flush=True)

    pool = ExactCandidateSet(lines, covers, set(data["ring_candidates"]), [], set())
    started = time.monotonic()
    greedy, greedy_groups, _ = greedy_selection(pool, regions, accessible, data["obstacles"])
    if greedy_groups != groups:
        raise ValueError("Greedy and prepared accessible components differ")
    greedy_seconds = time.monotonic() - started
    print("unified greedy", len(greedy), round(greedy_seconds, 2), flush=True)

    started = time.monotonic()
    cover = connectivity_cover(lines, covers, targets, graph)
    cover_seconds = time.monotonic() - started
    print("connectivity cover", len(cover), round(cover_seconds, 2), flush=True)
    started = time.monotonic()
    connected, repairs = repair_selection(
        lines, covers, targets, groups, graph, data["obstacles"], cover, pool.ring_candidates,
    )
    repair_seconds = time.monotonic() - started
    print("connectivity repair", len(connected), repairs, round(repair_seconds, 2), flush=True)

    results = {}
    settings = dict(addition_limit=args.additions, checks_limit=args.checks,
                    rounds_limit=args.rounds, three_for_two_limit=args.three_for_two_additions)
    for name, initial in (("greedy_exchange", greedy), ("connectivity_exchange", connected)):
        started = time.monotonic()
        improved = improve_topology(lines, covers, targets, groups, graph, data["obstacles"],
                                    initial, clearance, **settings)
        results[name] = {"selected": sorted(improved.selected), "exchanges": improved.exchanges,
                         "checks": improved.checks, "seconds": time.monotonic() - started}
        print(name, len(improved.selected), "exchanges", improved.exchanges,
              "checks", improved.checks, "seconds", round(results[name]["seconds"], 2), flush=True)

    results.update({
        "greedy": {"selected": sorted(greedy), "seconds": greedy_seconds},
        "connectivity_cover": {"selected": sorted(cover), "seconds": cover_seconds},
        "connectivity": {"selected": sorted(connected), "seconds": cover_seconds + repair_seconds,
                         "repair_seconds": repair_seconds, "repair": repairs},
    })
    for name in ("greedy", "connectivity", "greedy_exchange", "connectivity_exchange"):
        selected = set(results[name]["selected"])
        failure = structural_failure(lines, covers, targets, groups, graph, data["obstacles"], selected)
        if failure:
            raise ValueError(f"{name} fails {failure}")
        results[name].update({
            "length": sum(lines[i].length for i in selected),
            "coverage": len(set().union(*(covers[i] for i in selected))),
            "components": len(groups),
            "graph_edges": graph.subgraph(selected).number_of_edges(),
            "rings": len(closed_routes([lines[i] for i in sorted(selected)], data["obstacles"])),
        })
    results["metadata"] = {
        "candidates": len(lines), "regions": len(targets), "rings": len(data["obstacles"]),
        "full_graph_edges": graph.number_of_edges(), "full_graph_seconds": graph_seconds,
        "degrees": {str(i): graph.degree[i] for i in (1183, 1391, 1392, 1303)},
        "settings": settings,
    }
    with (args.output_dir / "selection-results.json").open("x") as file:
        json.dump(results, file, allow_nan=False)
    print("results saved", args.output_dir / "selection-results.json", flush=True)


if __name__ == "__main__":
    main()
