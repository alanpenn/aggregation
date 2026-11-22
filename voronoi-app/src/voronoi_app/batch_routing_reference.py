"""Fixed-master routing baselines using exact noding and independent path costs."""

from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from math import isfinite
from time import monotonic

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.strtree import STRtree

from .angular import (
    LineClearance, _direction, _intersections, _on_segment, angular_turn_cost,
)
from .batch_methods import _domain
from .batch_store import StageResult, digest, encode
from .exact_axial import _bounds, candidate_graph
from .exact_enumeration import exact_pool_from_dict
from .experimental_angular_selection import _unit
from .experimental_entrance_reduction import entrance_depth
from .experimental_structural_routes import distance
from .experimental_visibility import (
    IndexedClearance, _outward_bounds, build_visibility_graph, component_for_point, shortest_paths,
)


def point(value):
    return tuple(map(Fraction, value))


def interval(line):
    return tuple(sorted((point(line["start"]), point(line["end"]))))


def describe(values):
    finite = [x for x in values if x is not None and isfinite(x)]
    return {
        "reachable": len(finite), "unreachable": len(values) - len(finite),
        "mean": float(np.mean(finite)) if finite else None,
        "median": float(np.median(finite)) if finite else None,
        "min": min(finite, default=None), "max": max(finite, default=None),
        "p95": float(np.percentile(finite, 95)) if finite else None,
    }


class MasterNetwork:
    def __init__(self, lines, doors):
        self.lines = lines
        self.graph = candidate_graph(lines)
        self.doors = doors
        nodes = [{line.start, line.end} for line in lines]
        for i, j in self.graph.edges:
            intersections = _intersections(lines[i].start, lines[i].end, lines[j].start, lines[j].end)
            nodes[i].update(intersections)
            nodes[j].update(intersections)
        tree = STRtree([_bounds(line) for line in lines])
        for terminal in doors:
            for _, stop in terminal["connectors"]:
                for raw in tree.query(_outward_bounds(stop, stop)):
                    i = int(raw)
                    if _on_segment(stop, lines[i].start, lines[i].end):
                        nodes[i].add(stop)
        ownership = defaultdict(set)
        for i, stops in enumerate(nodes):
            ordered = sorted(stops)
            for a, b in zip(ordered, ordered[1:]):
                ownership[a, b].add(i)
        points = sorted(set().union(*nodes))
        self.nodes = {p: i for i, p in enumerate(points)}
        self.edges = [
            (self.nodes[a], self.nodes[b], distance(a, b), _unit(_direction(a, b)), owners)
            for (a, b), owners in sorted(ownership.items())
        ]
        self.edges_by_line = [[] for _ in lines]
        for index, edge in enumerate(self.edges):
            for owner in edge[4]:
                self.edges_by_line[owner].append(index)

    def options(self, selected):
        return [
            {stop for line, stop in entry["connectors"] if line in selected}
            for entry in self.doors
        ]

    def depths(self, selected):
        links = [{i for i, _ in d["connectors"]} for d in self.doors]
        return json_values(entrance_depth(self.graph, selected, links))

    def route(self, selected, angular, *, origins=None, trace_pairs=None):
        active = [self.edges[i] for i in sorted({
            edge for line in selected for edge in self.edges_by_line[line]
        })]
        options = self.options(selected)
        n = len(options)
        core = 2 * len(active) if angular else len(self.nodes)
        rows, cols, weights = [], [], []

        def add(a, b, weight):
            rows.append(a)
            cols.append(b)
            weights.append(weight)

        if angular:
            incoming = defaultdict(list)
            for i, (a, b, _, vector, _) in enumerate(active):
                incoming[b].append((2 * i, vector))
                incoming[a].append((2 * i + 1, tuple(-v for v in vector)))
            for states in incoming.values():
                for a, direction in states:
                    for b, reverse in states:
                        add(a, b ^ 1, angular_turn_cost(direction, tuple(-v for v in reverse)))
            by_stop = defaultdict(list)
            for i, stops in enumerate(options):
                origin = self.doors[i]["point"]
                for stop in sorted(stops):
                    direction = _direction(origin, stop) if stop != origin else None
                    for state, arrival in incoming[self.nodes[stop]]:
                        depart = tuple(-v for v in arrival)
                        turn = angular_turn_cost(direction, depart) if direction is not None else 0.0
                        add(core + i, state ^ 1, turn)
                        add(state, core + n + i, turn)
                    by_stop[stop].append((i, direction))
            direct = {}
            direct_stop = {}
            for stop, items in by_stop.items():
                for (i, approach), (j, other) in combinations(items, 2):
                    turn = (angular_turn_cost(approach, tuple(-v for v in other))
                            if approach is not None and other is not None else 0.0)
                    key = i, j
                    if turn < direct.get(key, float("inf")):
                        direct[key] = turn
                        direct_stop[key] = stop
            for (i, j), value in direct.items():
                add(core + i, core + n + j, value)
                add(core + j, core + n + i, value)
        else:
            for a, b, length, _, _ in active:
                add(a, b, length)
                add(b, a, length)
            for i, stops in enumerate(options):
                origin = self.doors[i]["point"]
                for stop in sorted(stops):
                    node = self.nodes[stop]
                    length = distance(origin, stop)
                    add(core + i, node, length)
                    add(node, core + n + i, length)
        size = core + 2 * n
        graph = coo_matrix((weights, (rows, cols)), shape=(size, size)).tocsr()
        if trace_pairs is not None:
            points = list(self.nodes)
            traces = {}
            for i, j in trace_pairs:
                _, previous = dijkstra(graph, indices=core + i, directed=True, return_predecessors=True)
                state = previous[core + n + j]
                if state < 0:
                    traces[i, j] = None
                    continue
                path = [self.doors[j]["point"]]
                if angular and state == core + i:
                    path.append(direct_stop[min(i, j), max(i, j)])
                while state != core + i:
                    if angular:
                        # An even state arrives at the second endpoint of its atomic edge.
                        edge = active[state // 2]
                        node = edge[0] if state % 2 else edge[1]
                    else:
                        node = state
                    path.append(points[node])
                    if angular and previous[state] == core + i:
                        departure = edge[1] if state % 2 else edge[0]
                        path.append(points[departure])
                    state = previous[state]
                path.append(self.doors[i]["point"])
                traces[i, j] = list(reversed(path))
            return traces
        result = []
        for i in range(n - 1) if origins is None else origins:
            values = dijkstra(graph, indices=core + i, directed=True)
            result.extend(json_values(values[core + n + i + 1:]))
        return result


def json_values(values):
    return [float(v) if isfinite(v) else None for v in values]


def excess(baseline, selected, absolute_tolerance, relative_tolerance):
    rows, violations, newly_unreachable = [], [], []
    for i, (full, reduced) in enumerate(zip(baseline, selected, strict=True)):
        difference = reduced - full if full is not None and reduced is not None else None
        percentage = difference / full * 100 if difference is not None and full != 0 else None
        if full is None and reduced is not None or (
            difference is not None
            and difference < -(absolute_tolerance + relative_tolerance * max(abs(full), abs(reduced)))
        ):
            violations.append(i)
        if full is not None and reduced is None:
            newly_unreachable.append(i)
        rows.append({"baseline": full, "selected": reduced, "excess": difference, "percent_excess": percentage})
    return {
        "pairs": rows, "violations": violations, "newly_unreachable": newly_unreachable,
        "absolute_statistics": describe([row["excess"] for row in rows]),
        "percent_statistics": describe([row["percent_excess"] for row in rows]),
    }


def _door_key(door):
    return door["open_cell"], door["building_cell"], point(door["point"])


def routing_reference(inputs, parameters):
    pool = exact_pool_from_dict(inputs["candidates"]["pool"])
    candidate_records = inputs["candidates"]["pool"]["candidates"]
    exact_ids = {interval(line): line["id"] for line in candidate_records}
    if len(exact_ids) != len(candidate_records):
        raise ValueError("The master pool contains duplicate exact intervals.")
    original = inputs["measures"]["entrances"]
    master = {
        _door_key(door): {(a["line"], point(a["point"])) for a in door["connectors"]}
        for door in original
    }
    if len(master) != len(original) or not master:
        raise ValueError("Expected a unique inventory of valid doorway positions.")
    for key, connectors in parameters["additional_connectors"]:
        identity = key[0], key[1], point(key[2])
        if identity not in master:
            raise ValueError("Projected connector inventory has a different doorway position.")
        master[identity].update((exact_ids[interval(line)], point(stop)) for line, stop in connectors)
    _, occupied, accessible, occupied_union = _domain(inputs)
    clearance = IndexedClearance(LineClearance(
        accessible, occupied_union, original_obstacles=occupied.values(),
    ))
    doors = []
    for open_cell, building_cell, origin in master:
        connectors = sorted(master[open_cell, building_cell, origin])
        for line_id, stop in connectors:
            line = pool.candidates[line_id]
            if not _on_segment(stop, line.start, line.end) or not clearance.permits(origin, stop):
                raise ValueError(f"Uncertified master connector {building_cell} to line {line_id}")
        doors.append({"open_cell": open_cell, "building_cell": building_cell,
                      "point": origin, "connectors": connectors})
    serialized_doors = [{**d, "point": list(map(str, d["point"])),
                         "connectors": [[i, list(map(str, stop))] for i, stop in d["connectors"]]}
                        for d in doors]
    pairs = [[i, j] for i, j in combinations(range(len(doors)), 2)]
    master_hash = digest(encode({"candidate_records": candidate_records, "doorways": serialized_doors}))
    saved = parameters.get("saved_reference")
    if saved is not None and (
        saved["master_geometry_sha256"] != master_hash
        or any(len(saved["routes"][name]) != len(pairs)
               for name in ("metric", "angular", "topological"))
    ):
        raise ValueError("Saved costs use a different master graph or doorway inventory.")
    print(parameters["case"], "certified connectors", sum(len(x["connectors"]) for x in doors), flush=True)
    network = MasterNetwork(pool.candidates, doors)
    print(parameters["case"], "master graph", len(network.nodes), len(network.edges), flush=True)
    variants = {"full": candidate_records, **parameters["maps"]}
    computed = {frozenset(exact_ids.values()): saved["routes"]} if saved is not None else {}
    output = {}
    for name, lines in variants.items():
        selected = frozenset(exact_ids[interval(line)] for line in lines)
        if selected not in computed:
            started = monotonic()
            computed[selected] = {
                "metric": network.route(selected, angular=False),
                "angular": network.route(selected, angular=True),
                "topological": network.depths(selected),
                "seconds": monotonic() - started,
            }
        routes = computed[selected]
        stats = {k: describe(routes[k]) for k in ("metric", "angular", "topological")}
        print(parameters["case"], name, len(selected), stats, flush=True)
        output[name] = {"line_ids": sorted(selected), "line_count": len(selected),
                        "total_length": sum(pool.candidates[i].length for i in sorted(selected)),
                        "statistics": stats, "routes": routes}
    violations = 0
    atol, rtol = parameters["absolute_tolerance"], parameters["relative_tolerance"]
    continuous = parameters.get("continuous_metric")
    for name, result in output.items():
        result["excess_over_full"] = {
            k: excess(output["full"]["routes"][k], result["routes"][k], atol, rtol)
            for k in ("metric", "angular", "topological")
        }
        violations += sum(len(v["violations"]) for v in result["excess_over_full"].values())
        if continuous is not None:
            result["excess_over_continuous"] = excess(continuous, result["routes"]["metric"], atol, rtol)
            violations += len(result["excess_over_continuous"]["violations"])
    return StageResult({
        "doorways": serialized_doors, "pairs": pairs, "master_geometry_sha256": master_hash,
        "maps": output, "violations": violations,
        "node_count": len(network.nodes), "segment_count": len(network.edges),
        "continuous_statistics": describe(continuous) if continuous is not None else None,
    }, valid=not violations)


def continuous_visibility_reference(inputs, parameters):
    _, occupied, accessible, occupied_union = _domain(inputs)
    clearance = IndexedClearance(LineClearance(
        accessible, occupied_union, original_obstacles=occupied.values(),
    ))
    graph = build_visibility_graph(accessible, occupied)
    print(parameters["case"], "continuous graph", len(graph.vertices), len(graph.edges), flush=True)
    doors = inputs["measures"]["entrances"]
    points = [point(d["point"]) for d in doors]
    terminals = [(p, component_for_point(p, graph.components)) for p in points]
    paths = shortest_paths(graph, terminals, terminals, clearance, same_set=True)
    lookup = {(p["source"], p["destination"]): p for p in paths}
    lengths = [lookup[i, j].get("length") for i, j in combinations(range(len(doors)), 2)]
    return StageResult({
        "doorways": [{k: d[k] for k in ("open_cell", "building_cell", "point")} for d in doors],
        "metric": lengths, "statistics": describe(lengths),
        "graph_vertices": len(graph.vertices), "graph_edges": len(graph.edges),
    })
