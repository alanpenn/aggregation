"""Probe named tangents and bounded 3-for-2 moves without forcing their selection."""

import argparse
import gzip
import json
import time
from fractions import Fraction
from pathlib import Path

import networkx as nx
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_connectivity_selection import improve_topology


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((args.data_dir / "prepared.json").read_text())
    maps = json.loads((args.output_dir / "selection-results.json").read_text())
    with gzip.open(args.output_dir / "candidate-graph.json.gz", "rt") as file:
        saved = json.load(file)
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from(saved["edges"])
    if [graph.degree[i] for i in range(len(lines))] != saved["degrees"]:
        raise ValueError("Saved graph and connectivity values differ")
    covers = [set(values) for values in data["covers"]]
    groups = [{i for i, c in enumerate(data["components"]) if c == component}
              for component in range(len(set(data["components"])))]
    targets = set(range(data["regions"]))
    probes = {}
    for name in ("greedy", "connectivity", "connectivity_exchange"):
        initial = set(maps[name]["selected"])
        probes[name] = {}
        for candidate in (1183, 1391, 1392, 1303):
            if candidate in initial:
                probes[name][candidate] = {"already_selected": True}
                continue
            started = time.monotonic()
            result = improve_topology(
                lines, covers, targets, groups, graph, data["obstacles"], initial, clearance,
                additions=[candidate], exchange_sizes=((2, 1),), rounds_limit=1,
                checks_limit=1000,
            )
            exchanges = []
            for removed, added in result.exchanges:
                exchanges.append({"removed": removed, "added": added,
                                  "removed_lengths": [lines[i].length for i in removed],
                                  "added_length": lines[candidate].length})
            probes[name][candidate] = {"already_selected": False, "exchanges": exchanges,
                                        "checks": result.checks,
                                        "seconds": time.monotonic() - started}
        print("targeted", name, probes[name], flush=True)
    three = {}
    for name in ("greedy_exchange", "connectivity_exchange"):
        started = time.monotonic()
        result = improve_topology(
            lines, covers, targets, groups, graph, data["obstacles"], maps[name]["selected"],
            clearance, exchange_sizes=((3, 2),), rounds_limit=1, checks_limit=100,
            three_for_two_limit=40,
        )
        three[name] = {"selected": sorted(result.selected), "exchanges": result.exchanges,
                       "checks": result.checks, "seconds": time.monotonic() - started}
        print("3-for-2", name, three[name], flush=True)
    with (args.output_dir / "targeted-probes.json").open("x") as file:
        json.dump({"tangents": probes, "three_for_two": three}, file, allow_nan=False)


if __name__ == "__main__":
    main()
