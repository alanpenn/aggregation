"""Evaluate successful targeted exchanges using the saved fixed terminals."""

import argparse
import gzip
import json
import math
from fractions import Fraction
from pathlib import Path

import networkx as nx

from voronoi_app.angular import SampleAttachment
from voronoi_app.exact_axial import ExactCandidate, closed_routes
from experiments.valley_connectivity_terminals import map_depths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((args.data_dir / "prepared.json").read_text())
    maps = json.loads((args.output_dir / "selection-results.json").read_text())
    probes = json.loads((args.output_dir / "targeted-probes.json").read_text())
    with gzip.open(args.output_dir / "fixed-terminals.json.gz", "rt") as file:
        raw = json.load(file)
    with gzip.open(args.output_dir / "candidate-graph.json.gz", "rt") as file:
        graph_data = json.load(file)
    fixed = [[SampleAttachment(tuple(map(Fraction, a["sample"])),
                               tuple(map(Fraction, a["point"])), a["line_id"])
              for a in options] for options in raw]
    components = [item["component"] for item in data["attachments"]]
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from(graph_data["edges"])
    output = {}
    for name, candidates in probes["tangents"].items():
        initial = set(maps[name]["selected"])
        baseline, _ = map_depths([lines[i] for i in sorted(initial)], fixed, components)
        for candidate, details in candidates.items():
            if not details.get("exchanges"):
                continue
            exchange = details["exchanges"][0]
            selected = initial.difference(exchange["removed"]).union(exchange["added"])
            depths, available = map_depths([lines[i] for i in sorted(selected)], fixed, components)
            finite = [value for value in depths.values() if math.isfinite(value)]
            common = [pair for pair in depths if math.isfinite(depths[pair])
                      and math.isfinite(baseline[pair])]
            output[f"{name}:{candidate}"] = {
                "selected": sorted(selected), "selected_count": len(selected),
                "length": sum(lines[i].length for i in selected),
                "coverage": len(set().union(*(set(data["covers"][i]) for i in selected))),
                "graph_edges": graph.subgraph(selected).number_of_edges(),
                "rings": len(closed_routes([lines[i] for i in sorted(selected)], data["obstacles"])),
                "available_samples": available,
                "unreachable_pairs": len(depths) - len(finite),
                "mean_depth": sum(finite) / len(finite) if finite else None,
                "max_depth": max(finite) if finite else None,
                "common_pairs": len(common),
                "mean_change_on_common_pairs": (
                    sum(depths[pair] - baseline[pair] for pair in common) / len(common)
                    if common else None
                ),
                "max_increase_on_common_pairs": (
                    max(depths[pair] - baseline[pair] for pair in common) if common else None
                ),
            }
    with (args.output_dir / "targeted-evaluated.json").open("x") as file:
        json.dump(output, file, allow_nan=False)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
