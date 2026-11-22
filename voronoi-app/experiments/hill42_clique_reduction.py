"""Compare clique-guided and degree-guided Hill 42 candidate reductions."""

import argparse
import json
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely import wkt
from shapely.ops import unary_union
from shapely.strtree import STRtree

from voronoi_app.angular import _exact_point, _intersections, _on_segment
from voronoi_app.convex_coverage import convex_regions
from voronoi_app.exact_axial import _bounds, candidate_graph
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_circulation_topology import (
    _ring_covers_cells, analyse_circulation_topology, bounded_face_rings,
)
from voronoi_app.experimental_visibility import _outward_bounds


def read(path):
    return json.loads(path.read_text())


def ring_seed(lines, topology, tree, polygons, hints):
    faces = bounded_face_rings(lines)
    if len(faces) != topology["bounded_axial_faces"]:
        raise ValueError("Saved topology and candidate faces differ")
    result = set()
    blocks = {block["id"]: block["cells"] for block in topology["occupied_blocks"]}
    for witness in topology["circulation_cycles"]:
        block_ids = witness["enclosed_blocks"]
        cells = [cell for block in block_ids for cell in blocks[block]]
        hinted = set(hints.get(block_ids[0], ())) if len(block_ids) == 1 else set()

        def encloses(chosen):
            return any(_ring_covers_cells(ring, cells, polygons)
                       for ring in bounded_face_rings([lines[i] for i in sorted(chosen)]))

        if hinted and encloses(hinted):
            result.update(hinted)
            continue
        face = faces[witness["face_index"]]
        supports = set()
        for a, b in zip(face, face[1:]):
            members = {int(i) for i in tree.query(_outward_bounds(a, b))
                       if _on_segment(a, lines[i].start, lines[i].end)
                       and _on_segment(b, lines[i].start, lines[i].end)}
            if not members:
                raise ValueError("A circulation face edge has no candidate support")
            if not supports & members:
                supports.add(min(members))
        for i in sorted(supports, key=lambda i: (-lines[i].length, i)):
            trial = supports - {i}
            if encloses(trial):
                supports = trial
        result.update(supports)
    return result


def visibility_masks(lines, interior, regions, line_bounds):
    ids = sorted(regions)
    search = STRtree([regions[i].envelope for i in ids])
    rings = {i: list(map(_exact_point, regions[i].exterior.coords)) for i in ids}
    masks = []
    for line, known, bounds in zip(lines, interior, line_bounds):
        seen = set(known)
        for raw in search.query(bounds):
            i = ids[int(raw)]
            if i not in seen and any(_intersections(line.start, line.end, a, b)
                                     for a, b in zip(rings[i], rings[i][1:])):
                seen.add(i)
        masks.append(sum(1 << i for i in seen))
    return masks


def union_mask(masks, chosen):
    result = 0
    for i in chosen:
        result |= masks[i]
    return result


def local_clique(node, neighbors):
    """Find a deterministic maximal clique containing this candidate."""
    clique = {node}
    remaining = set(neighbors[node])
    while remaining:
        best = max(remaining, key=lambda i: (len(neighbors[i] & remaining), -i))
        clique.add(best)
        remaining &= neighbors[best]
    return clique


def reduce_map(graph, witnesses, covers, target, cliques, use_cliques):
    neighbors = dict(graph.adjacency())
    reach = [sum(1 << j for j in (*neighbors[i], i)) for i in graph]
    all_lines = sum(1 << i for i in graph)
    selected = set(witnesses)
    trace = []

    def priority(i, uncovered, unattached):
        adjacency = sum(j in selected for j in neighbors[i])
        clique_size = len(cliques[i] & selected) if use_cliques else 0
        return ((covers[i] & uncovered).bit_count() + (reach[i] & unattached).bit_count(),
                clique_size, adjacency, len(neighbors[i]), -i)

    while True:
        uncovered = target & ~union_mask(covers, selected)
        unattached = all_lines & ~union_mask(reach, selected)
        if not uncovered and not unattached and nx.is_connected(graph.subgraph(selected)):
            break
        available = {j for i in selected for j in neighbors[i] if j not in selected}
        if not available:
            raise ValueError("Cannot complete the candidate network from the ring witnesses")
        best = max(available, key=lambda i: priority(i, uncovered, unattached))
        selected.add(best)
        trace.append(best)

    grown = len(selected)
    while True:
        removed = False
        order = sorted(selected - witnesses, key=lambda i: (
            len(cliques[i] & selected) if use_cliques else 0,
            sum(j in selected for j in neighbors[i]), i))
        for i in order:
            trial = selected - {i}
            if (union_mask(covers, trial) == target and union_mask(reach, trial) == all_lines
                    and nx.is_connected(graph.subgraph(trial))):
                selected = trial
                removed = True
        if not removed:
            break
    return selected, grown, trace


def depth(graph, selected):
    """Count line changes between every pair, with retained lines as intermediates."""
    count = len(graph)
    indexes = {line: count + index for index, line in enumerate(sorted(selected))}
    sink = count + len(indexes)
    rows, columns, costs = [], [], []

    def add(i, j, cost):
        rows.append(i)
        columns.append(j)
        costs.append(cost)

    for i, core in indexes.items():
        add(i, core, 0)
        add(core, sink + i, 0)
        for j in graph[i]:
            if j in selected:
                add(core, indexes[j], 1)
            else:
                add(j, core, 1)
                add(core, sink + j, 1)
    matrix = coo_matrix((costs, (rows, columns)), shape=(sink + count, sink + count)).tocsr()
    triangle = np.triu_indices(count, k=1)
    values = dijkstra(matrix, directed=True, indices=np.arange(count))[:, sink:][triangle]
    finite = values[np.isfinite(values)]
    return {"pairs": len(values), "unreachable": len(values) - len(finite),
            "mean": float(finite.mean()), "max": int(finite.max()),
            "p95": float(np.percentile(finite, 95))}


def depth_exchanges(graph, selected, witnesses, covers, target, cliques, limit=12):
    """Try a bounded set of same-size exchanges, scored on all fixed pairs."""
    reach = [sum(1 << j for j in (*graph[i], i)) for i in graph]
    all_lines = (1 << len(graph)) - 1
    best, best_depth = selected, depth(graph, selected)
    optional = sorted(selected - witnesses)
    alternatives = sorted(set(graph) - selected, key=lambda i: (
        -len(cliques[i] & selected), -sum(j in selected for j in graph[i]),
        -len(graph[i]), i))
    tried = 0
    for i in alternatives:
        for removed in optional:
            trial = (selected - {removed}) | {i}
            if (union_mask(covers, trial) != target or union_mask(reach, trial) != all_lines
                    or not nx.is_connected(graph.subgraph(trial))):
                continue
            score = depth(graph, trial)
            tried += 1
            if (score["mean"], score["max"]) < (best_depth["mean"], best_depth["max"]):
                best, best_depth = trial, score
            if tried == limit:
                return best, best_depth, tried
    return best, best_depth, tried


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pool", "topology", "hill-data", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--ring-hints", type=Path,
                        help="Optional map from internal block IDs to candidate IDs")
    args = parser.parse_args()
    data, topology, settlement = read(args.pool), read(args.topology), read(args.hill_data)
    pool = exact_pool_from_dict(data["pool"])
    lines = pool.candidates
    polygons = {int(cell): wkt.loads(value) for cell, value in settlement["polygons"].items()}
    occupied = unary_union([polygons[i] for i in topology["effective_occupied_cells"]])
    accessible = unary_union([polygons[i] for i in topology["main_open_cells"]]).difference(occupied)
    regions = convex_regions(accessible)
    bounds = [_bounds(line) for line in lines]
    hints = read(args.ring_hints) if args.ring_hints else {}
    witnesses = ring_seed(lines, topology, STRtree(bounds), polygons, hints)
    print("Recovered ring witness lines", len(witnesses), flush=True)
    covers = visibility_masks(lines, pool.covers, regions, bounds)
    target = sum(1 << i for i in regions)
    graph = candidate_graph(lines)
    if not nx.is_connected(graph) or union_mask(covers, graph) != target:
        raise ValueError("Full pool is disconnected or fails visibility coverage")
    neighbors = {i: set(graph[i]) for i in graph}
    cliques = {i: local_clique(i, neighbors) for i in graph}
    output = {"mandatory_ring_lines": sorted(witnesses),
              "full_pool_depth": depth(graph, set(graph)), "maps": {}}
    print("Full pool depth", output["full_pool_depth"], flush=True)
    for name, use_cliques in (("degree", False), ("clique", True)):
        selected, grown, added = reduce_map(graph, witnesses, covers, target, cliques, use_cliques)
        before_exchange = depth(graph, selected)
        after_exchange = before_exchange
        tried = 0
        if use_cliques:
            selected, after_exchange, tried = depth_exchanges(
                graph, selected, witnesses, covers, target, cliques)
        certified = analyse_circulation_topology(
            polygons, map(int, settlement["building_labels"]), settlement["dyad_open_cells"],
            [lines[i] for i in sorted(selected)],
        )
        if (not certified["circulation_constraints_satisfied"]
                or certified["lines_crossing_effective_occupied_space"]):
            raise ValueError(f"{name} map failed exact circulation or clearance")
        result = {"lines": len(selected), "selected": sorted(selected),
                  "before_deletion": grown, "growth_order": added,
                  "winding_rank": certified["independent_circulation_rank"],
                  "covered_convex_regions": union_mask(covers, selected).bit_count(),
                  "depth_before_exchange": before_exchange, "exchanges_tested": tried,
                  "depth": after_exchange}
        output["maps"][name] = result
        print(name, {k: v for k, v in result.items() if k not in ("selected", "growth_order")},
              flush=True)
    with args.output.open("x") as stream:
        json.dump(output, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
