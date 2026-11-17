"""Optional replay of the saved combined-pool connectivity experiment."""

import gzip
import json
import os
from fractions import Fraction
from pathlib import Path

import networkx as nx
import pytest
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_connectivity_selection import (
    connectivity_cover, improve_topology, structural_failure,
)


@pytest.mark.skipif(not os.environ.get("VALLEY_CONNECTIVITY_DATA")
                    or not os.environ.get("VALLEY_EXCHANGE_DATA"),
                    reason="Set both Valley experiment data directories to replay this result")
def test_saved_connectivity_selection_and_exchanges_replay():
    prepared = json.loads((Path(os.environ["VALLEY_EXCHANGE_DATA"]) / "prepared.json").read_text())
    state = Path(os.environ["VALLEY_CONNECTIVITY_DATA"])
    results = json.loads((state / "selection-results.json").read_text())
    with gzip.open(state / "candidate-graph.json.gz", "rt") as file:
        saved = json.load(file)
    snapshot = json.loads(gzip.decompress(
        (Path(__file__).parent / "fixtures/exact_y/axial-648f8da1364449a6aa70fd24038eea21.json.gz")
        .read_bytes()
    ))
    opened, buildings, _, _, _ = load_axial_snapshot(snapshot)
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    lines = []
    for i, record in enumerate(prepared["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from(saved["edges"])
    assert [graph.degree[i] for i in range(len(lines))] == saved["degrees"]
    covers = [set(values) for values in prepared["covers"]]
    targets = set(range(prepared["regions"]))
    groups = [{i for i, c in enumerate(prepared["components"]) if c == component}
              for component in range(len(set(prepared["components"])))]
    assert connectivity_cover(lines, covers, targets, graph) == set(
        results["connectivity_cover"]["selected"]
    )
    for name, target in (("greedy", "greedy_exchange"),
                         ("connectivity", "connectivity_exchange")):
        initial = set(results[name]["selected"])
        assert structural_failure(lines, covers, targets, groups, graph,
                                  prepared["obstacles"], initial) is None
        replay = improve_topology(lines, covers, targets, groups, graph, prepared["obstacles"],
                                  initial, clearance, **results["metadata"]["settings"])
        assert replay.selected == set(results[target]["selected"])
        assert [[list(remove), list(add)] for remove, add in replay.exchanges] == (
            results[target]["exchanges"]
        )
