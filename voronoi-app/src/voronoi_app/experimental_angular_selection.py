"""Experimental angular-fidelity selection; not used by the production pipeline."""

from dataclasses import dataclass
from itertools import combinations
from math import inf, isfinite, nextafter, pi

import networkx as nx
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import box
from shapely.strtree import STRtree

from .angular import _direction, _exact_point, _intersections, _on_segment, angular_turn_cost
from .exact_axial import _bounds, _connect_exact_selected, candidate_graph, closed_routes


@dataclass(frozen=True)
class AngularResult:
    depths: dict[tuple[int, int], float]
    witness_lines: frozenset[int]


@dataclass(frozen=True)
class SelectionResult:
    selected: frozenset[int]
    depths: dict[tuple[int, int], float]
    attempted: int
    accepted: int


@dataclass(frozen=True)
class ExchangeResult:
    selected: frozenset[int]
    depths: dict[tuple[int, int], float]
    attempted: int
    exchanges: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]


def _unit(direction):
    scale = max(abs(value) for value in direction)
    if not scale:
        raise ValueError("A movement direction must be nonzero")
    return tuple(float(value / scale) for value in direction)


def angular_reference(lines, attachments, components, *, witness_turn_penalty=0.0):
    """Route fixed attachments on exact noded linework using a sparse state graph.

    Intersections, segment ownership and stop placement are rational. Costs are
    floating-point angles, following AngularNetwork's directional convention.
    Witness lines preserve one shortest path for every reachable ordered pair.
    A nonzero penalty is a search heuristic: returned depths then include that
    penalty and must not be used as the unpenalised angular reference.
    """
    if (not lines or len(attachments) != len(components)
            or not isfinite(witness_turn_penalty) or witness_turn_penalty < 0):
        raise ValueError("Lines and equally sized attachment/component lists are required")
    ids = {line.line_id: index for index, line in enumerate(lines)}
    if len(ids) != len(lines):
        raise ValueError("Candidate line IDs must be unique")
    endpoints = [(_exact_point(line.start), _exact_point(line.end)) for line in lines]
    points = [{a, b} for a, b in endpoints]
    bounds = [_bounds(line) for line in lines]
    tree = STRtree(bounds)
    for i, (start, end) in enumerate(endpoints):
        for raw in tree.query(bounds[i]):
            j = int(raw)
            if j <= i:
                continue
            shared = _intersections(start, end, *endpoints[j])
            if shared:
                points[i].update(shared)
                points[j].update(shared)
    stop_points = [_exact_point(attachment.point) for attachment in attachments]
    for attachment, point in zip(attachments, stop_points):
        if attachment.line_id not in ids or not _on_segment(
            point, *endpoints[ids[attachment.line_id]]
        ):
            raise ValueError("A fixed attachment must lie on its retained candidate")
        # A rounded point may fall outside a zero-width exact line's bounds.
        query = box(nextafter(float(point[0]), -inf), nextafter(float(point[1]), -inf),
                    nextafter(float(point[0]), inf), nextafter(float(point[1]), inf))
        for raw in tree.query(query):
            i = int(raw)
            if _on_segment(point, *endpoints[i]):
                points[i].add(point)

    nodes = {}
    edges = {}
    vectors = []
    for i, ((start, end), items) in enumerate(zip(endpoints, points)):
        ordered = sorted(items)
        vector = _unit(_direction(ordered[0], ordered[-1]))
        vectors.append(vector)
        node_ids = []
        for point in ordered:
            if point not in nodes:
                nodes[point] = len(nodes)
            node_ids.append(nodes[point])
        for a, b in zip(node_ids, node_ids[1:]):
            key = (min(a, b), max(a, b))
            edges.setdefault(key, (i, 1 if a < b else -1))
    incoming = [[] for _ in nodes]
    owner = np.empty(len(edges), dtype=np.int32)
    directions = np.empty((2 * len(edges), 2), dtype=np.float64)
    for edge, ((a, b), (line, sign)) in enumerate(edges.items()):
        state = 2 * edge
        owner[edge] = line
        directions[state] = np.asarray(vectors[line]) * sign
        directions[state + 1] = -directions[state]
        incoming[b].append(state)
        incoming[a].append(state + 1)

    count = sum(len(states) ** 2 for states in incoming)
    count += sum(2 * len(incoming[nodes[point]]) for point in stop_points)
    count += sum(1 for i in range(len(attachments)) for j in range(len(attachments))
                 if i != j and stop_points[i] == stop_points[j])
    rows = np.empty(count, dtype=np.int32)
    cols = np.empty(count, dtype=np.int32)
    costs = np.empty(count, dtype=np.float64)
    cursor = 0
    for states in incoming:
        if not states:
            continue
        ins = np.asarray(states, dtype=np.int32)
        outs = ins ^ 1
        n = len(ins)
        r = np.repeat(ins, n)
        c = np.tile(outs, n)
        a = directions[r]
        b = directions[c]
        rows[cursor:cursor + n * n] = r
        cols[cursor:cursor + n * n] = c
        turns = (
            2 * np.arctan2(np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]),
                           a[:, 0] * b[:, 0] + a[:, 1] * b[:, 1]) / pi
        )
        costs[cursor:cursor + n * n] = (
            turns + witness_turn_penalty * (turns > 1e-12)
        )
        cursor += n * n

    source_base = len(directions)
    sink_base = source_base + len(attachments)
    for i, (attachment, point) in enumerate(zip(attachments, stop_points)):
        ins = incoming[nodes[point]]
        for state in ins:
            outgoing = state ^ 1
            rows[cursor], cols[cursor] = source_base + i, outgoing
            costs[cursor] = (angular_turn_cost(attachment.arrival, directions[outgoing])
                             if attachment.arrival is not None else 0)
            cursor += 1
            rows[cursor], cols[cursor] = state, sink_base + i
            costs[cursor] = (angular_turn_cost(directions[state], attachment.departure)
                             if attachment.departure is not None else 0)
            cursor += 1
    for i, origin in enumerate(attachments):
        for j, destination in enumerate(attachments):
            if i == j or stop_points[i] != stop_points[j]:
                continue
            rows[cursor], cols[cursor] = source_base + i, sink_base + j
            costs[cursor] = (angular_turn_cost(origin.arrival, destination.departure)
                             if origin.arrival is not None and destination.departure is not None
                             else 0)
            cursor += 1
    assert cursor == count
    graph = coo_matrix((costs, (rows, cols)),
                       shape=(sink_base + len(attachments),) * 2).tocsr()
    del points, nodes, edges, incoming, directions, rows, cols, costs, vectors, tree, bounds
    depths = {}
    witnesses = {ids[attachment.line_id] for attachment in attachments}
    for i in range(len(attachments)):
        distances, predecessors = dijkstra(
            graph, directed=True, indices=source_base + i, return_predecessors=True
        )
        for j in range(len(attachments)):
            if i == j or components[i] != components[j]:
                continue
            sink = sink_base + j
            depth = float(distances[sink])
            depths[i, j] = depth
            if not np.isfinite(depth):
                continue
            state = int(predecessors[sink])
            while 0 <= state < source_base:
                witnesses.add(int(owner[state // 2]))
                state = int(predecessors[state])
    return AngularResult(depths, frozenset(witnesses))


def _structural_failure(lines, covers, targets, groups, obstacles, selected):
    covered = set().union(*(covers[i] for i in selected)) if selected else set()
    if covered != targets:
        return "convex coverage"
    ordered = sorted(selected)
    graph = candidate_graph([lines[i] for i in ordered])
    index = {line_index: position for position, line_index in enumerate(ordered)}
    for group in groups:
        nodes = [index[i] for i in sorted(selected & group)]
        if not nodes or not nx.is_connected(graph.subgraph(nodes)):
            return "component connectivity"
    group_for = {index[i]: component for component, group in enumerate(groups)
                 for i in selected & group}
    if any(group_for[a] != group_for[b] for a, b in graph.edges):
        return "cross-component connection"
    if len(closed_routes([lines[i] for i in ordered], obstacles)) != len(obstacles):
        return "ring witnesses"
    return None


def optimise_fidelity(lines, covers, targets, groups, obstacles, attachments,
                      sample_components, reference, epsilon, ring_seed, *,
                      attempt_limit=20, reverse_order=False, numerical_slack=1e-10,
                      seed_witnesses=None):
    """Bounded removal search; returns a feasible subset, not an optimality claim.

    The seed retains one full-network shortest-path witness per ordered pair.
    Ring seed lines are only a sufficient starting construction, not mandatory.
    """
    if (not isfinite(epsilon) or epsilon < 0 or not isfinite(numerical_slack)
            or numerical_slack < 0 or attempt_limit < 0):
        raise ValueError("Invalid tolerance or removal budget")
    if len(lines) != len(covers) or set().union(*groups) != set(range(len(lines))):
        raise ValueError("Coverage and groups must partition the candidate pool")
    if sum(map(len, groups)) != len(lines):
        raise ValueError("Candidate components must not overlap")
    ids = {line.line_id: i for i, line in enumerate(lines)}
    if len(ids) != len(lines):
        raise ValueError("Candidate line IDs must be unique")
    for attachment, component in zip(attachments, sample_components, strict=True):
        if (not isinstance(component, int) or not 0 <= component < len(groups)
                or attachment.line_id not in ids
                or ids[attachment.line_id] not in groups[component]):
            raise ValueError("Attachment is not on its declared candidate component")
    pinned = {ids[item.line_id] for item in attachments}
    selected = set(reference.witness_lines if seed_witnesses is None else seed_witnesses)
    selected |= pinned | set(ring_seed)
    if not selected <= set(range(len(lines))):
        raise ValueError("Seed contains a non-candidate index")
    covered = set().union(*(covers[i] for i in selected))
    while covered != targets:
        if not covered <= targets:
            raise ValueError("Candidate coverage contains an unknown region")
        remaining = set(range(len(lines))) - selected
        if not remaining:
            raise ValueError("The candidate pool does not cover every region")
        best = max(remaining, key=lambda i: (len(covers[i] - covered), lines[i].length, -i))
        if not covers[best] - covered:
            raise ValueError("The candidate pool does not cover every region")
        selected.add(best)
        covered.update(covers[best])
    selected = _connect_exact_selected(lines, selected, groups)
    failure = _structural_failure(lines, covers, targets, groups, obstacles, selected)
    if failure:
        raise ValueError(f"Initial selection fails {failure}")

    def depths_for(indices):
        return angular_reference([lines[i] for i in sorted(indices)], attachments,
                                 sample_components).depths

    def angular_ok(depths):
        if depths.keys() != reference.depths.keys():
            return False
        for pair, full in reference.depths.items():
            actual = depths[pair]
            if isfinite(full):
                if not isfinite(actual) or actual > full + epsilon + numerical_slack:
                    return False
            elif isfinite(actual):
                return False
        return True

    depths = depths_for(selected)
    if not angular_ok(depths):
        raise ValueError("The initial shortest-path witness selection is not angularly feasible")
    candidates = sorted(selected - pinned,
                        key=lambda i: (len(covers[i]), lines[i].length, i),
                        reverse=reverse_order)
    attempted = accepted = 0
    for index in candidates[:attempt_limit]:
        attempted += 1
        trial = selected - {index}
        if _structural_failure(lines, covers, targets, groups, obstacles, trial):
            continue
        trial_depths = depths_for(trial)
        if angular_ok(trial_depths):
            selected = trial
            depths = trial_depths
            accepted += 1
    return SelectionResult(frozenset(selected), depths, attempted, accepted)


def improve_fidelity(lines, covers, targets, groups, obstacles, attachments,
                     sample_components, reference, epsilon, selected, clearance, *,
                     additions, attempt_limit=100, removal_limit=20, numerical_slack=1e-10):
    """Try bounded 2-for-1 and 3-for-2 exchanges on a feasible exact selection.

    Candidate indices in ``additions`` are examined in the supplied order.
    Removals are restricted to unpinned selected lines intersecting an addition;
    this is a heuristic search, not an exhaustive local-optimality certificate.
    """
    if (not isfinite(epsilon) or epsilon < 0 or not isfinite(numerical_slack)
            or numerical_slack < 0 or attempt_limit < 0 or removal_limit < 2):
        raise ValueError("Invalid tolerance or exchange budget")
    if len(lines) != len(covers) or set().union(*groups) != set(range(len(lines))):
        raise ValueError("Coverage and groups must partition the candidate pool")
    if sum(map(len, groups)) != len(lines):
        raise ValueError("Candidate components must not overlap")
    ids = {line.line_id: i for i, line in enumerate(lines)}
    if len(ids) != len(lines) or len(attachments) != len(sample_components):
        raise ValueError("Unique line IDs and attachment components are required")
    for attachment, component in zip(attachments, sample_components, strict=True):
        if (not isinstance(component, int) or not 0 <= component < len(groups)
                or attachment.line_id not in ids
                or ids[attachment.line_id] not in groups[component]):
            raise ValueError("Attachment is not on its declared candidate component")
    pinned = {ids[item.line_id] for item in attachments}
    chosen = set(selected)
    if not chosen <= set(range(len(lines))) or not pinned <= chosen:
        raise ValueError("Initial selection must contain all fixed attachment candidates")
    additions = tuple(dict.fromkeys(additions))
    if any(i not in range(len(lines)) for i in additions):
        raise ValueError("An exchange candidate is outside the candidate pool")
    for i in chosen | set(additions):
        if not clearance.permits_exact(lines[i].start, lines[i].end):
            raise ValueError(f"Candidate {i} fails exact clearance")

    def depths_for(indices):
        return angular_reference([lines[i] for i in sorted(indices)], attachments,
                                 sample_components).depths

    def angular_ok(depths):
        if depths.keys() != reference.depths.keys():
            return False
        return all(
            (isfinite(depths[pair]) and depths[pair] <= full + epsilon + numerical_slack)
            if isfinite(full) else full == inf and depths[pair] == inf
            for pair, full in reference.depths.items()
        )

    failure = _structural_failure(lines, covers, targets, groups, obstacles, chosen)
    if failure:
        raise ValueError(f"Initial selection fails {failure}")
    depths = depths_for(chosen)
    if not angular_ok(depths):
        raise ValueError("Initial selection is not angularly feasible")

    attempted = 0
    accepted = []
    while attempted < attempt_limit:
        changed = False
        available = [i for i in additions if i not in chosen]
        for add_count in (1, 2):
            for add in combinations(available, add_count):
                add_coverage = set().union(*(covers[i] for i in add))
                neighbours = [
                    i for i in chosen - pinned
                    if any(_intersections(lines[i].start, lines[i].end,
                                          lines[j].start, lines[j].end) for j in add)
                ]
                neighbours.sort(key=lambda i: (-len(covers[i] & add_coverage),
                                                lines[i].length, i))
                for remove in combinations(neighbours[:removal_limit], add_count + 1):
                    if attempted >= attempt_limit:
                        break
                    attempted += 1
                    trial = chosen.difference(remove).union(add)
                    if _structural_failure(lines, covers, targets, groups, obstacles, trial):
                        continue
                    trial_depths = depths_for(trial)
                    if not angular_ok(trial_depths):
                        continue
                    chosen, depths = trial, trial_depths
                    accepted.append((tuple(remove), tuple(add)))
                    changed = True
                    break
                if changed or attempted >= attempt_limit:
                    break
            if changed or attempted >= attempt_limit:
                break
        if not changed:
            break
    return ExchangeResult(frozenset(chosen), depths, attempted, tuple(accepted))
