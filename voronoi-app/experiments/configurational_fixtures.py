"""Independent exhaustive paths on small physical segment fixtures."""

from fractions import Fraction
from itertools import combinations
from math import atan2, degrees, hypot, isclose

from voronoi_app.configurational import axial_graph, segment_graph
from voronoi_app.configurational_traversal import Traversal, SCALE

FIXTURES = {
    "straight": [((0, 0), (1, 0)), ((1, 0), (2, 0)), ((2, 0), (3, 0))],
    "corner": [((0, 0), (1, 0)), ((1, 0), (1, 1))],
    "tee": [((-1, 0), (0, 0)), ((0, 0), (1, 0)), ((0, 0), (0, 1))],
    "cross": [((-1, 0), (0, 0)), ((0, 0), (1, 0)), ((0, 0), (0, 1)), ((0, 0), (0, -1))],
    "loop": [((0, 0), (4, 0)), ((4, 0), (4, 2)), ((4, 2), (0, 2)), ((0, 2), (0, 0))],
    "unequal_length_tie": [((-1, 0), (0, 0)), ((5, 0), (6, 0)), ((0, 0), (0, 2)),
                           ((0, 2), (5, 2)), ((5, 2), (5, 0)), ((0, 0), (0, -4)),
                           ((0, -4), (5, -4)), ((5, -4), (5, 0))],
    "same_junction": [((0, 0), (4, -1)), ((-4, 0), (0, 0)), ((0, 0), (4, 1))],
    "reversal": [((0, 0), (1, 0))],
}


def build(edges):
    return segment_graph(axial_graph(dict(enumerate(edges))))


def brute(travel, start, destination, mode):
    """Enumerate simple directed routes independently from endpoint coordinates."""
    best, solutions = None, []

    def visit(path, angle, length):
        nonlocal best, solutions
        previous = path[-1]
        a, b = travel.points[previous]
        if mode == "angular":
            cost = angle, len(path) - 1, 0
        elif mode == "metric":
            cost = length, len(path) - 1, 0
        else:
            cost = angle, length, len(path) - 1
        if best is not None and cost > best:
            return
        if previous in destination:
            if best is None or cost < best:
                best, solutions = cost, []
            solutions.append(path)
            return
        u = float(b[0]-a[0]), float(b[1]-a[1])
        for following, (c, d) in enumerate(travel.points):
            if c != b or following in path:
                continue
            v = float(d[0]-c[0]), float(d[1]-c[1])
            turn = abs(degrees(atan2(u[0]*v[1]-u[1]*v[0], u[0]*v[0]+u[1]*v[1])))
            distance = sum(max(1, round(hypot(*vector) * SCALE)) for vector in (u, v))
            visit(path + [following], angle + round(turn * SCALE), length + distance)

    for state in start:
        visit([state], 0, 0)
    return best, solutions


def fixture_result(edges, mode):
    graph = build(edges)
    travel = Traversal(graph)
    sums = [Fraction(0)] * len(graph)
    pairs = []
    for source in range(len(graph)):
        start = [2*source, 2*source+1]
        distances, counts, _, _ = travel.paths(start, mode)
        for target in range(source + 1, len(graph)):
            ends = travel.terminals(distances, target)
            expected, paths = brute(travel, start, {2*target, 2*target+1}, mode)
            actual = distances[ends[0]]
            assert actual == expected
            assert sum(counts[i] for i in ends) == len(paths)
            for path in paths:
                for node in {state//2 for state in path} - {source, target}:
                    sums[node] += Fraction(1, len(paths))
            pairs.append(dict(source=source, target=target, expected_cost=expected, actual_cost=actual,
                              expected_paths=len(paths), actual_paths=sum(counts[i] for i in ends),
                              witness_paths=paths))
    rows = travel.measures(graph, mode)
    normal = (len(graph)-1)*(len(graph)-2)/2
    expected_choice = [float(x/normal) if normal else 0.0 for x in sums]
    assert all(isclose(rows[i]["choice"], expected_choice[i], abs_tol=1e-12) for i in graph)
    return {"geometry": edges, "states": travel.points, "pairs": pairs,
            "expected_choice": expected_choice, "actual_choice": [rows[i]["choice"] for i in graph]}
