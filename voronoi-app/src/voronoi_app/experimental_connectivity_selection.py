"""Experimental exact-connectivity ordering and topology-only exchanges."""

from dataclasses import dataclass
from itertools import combinations

import networkx as nx

from .exact_axial import _connect_exact_selected, closed_routes
from .experimental_boundary_candidates import canonical_interval


@dataclass(frozen=True)
class ExchangeResult:
    selected: frozenset[int]
    exchanges: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]
    checks: int


def connectivity_order(lines, graph):
    """Rank by fixed full-pool degree, length, then exact interval identity."""
    if set(graph) != set(range(len(lines))):
        raise ValueError("The full candidate graph must index every candidate")
    keys = [canonical_interval(line.start, line.end) for line in lines]
    if len(set(keys)) != len(keys):
        raise ValueError("Candidate intervals must be unique")
    squared_lengths = [sum((line.end[k] - line.start[k]) ** 2 for k in range(2))
                       for line in lines]
    return sorted(range(len(lines)),
                  key=lambda i: (-graph.degree[i], -squared_lengths[i], keys[i]))


def connectivity_cover(lines, covers, targets, graph):
    """Traverse the fixed ranking, selecting only candidates with new coverage."""
    if len(lines) != len(covers) or any(not cover <= targets for cover in covers):
        raise ValueError("Candidate coverage does not match the target regions")
    selected, covered = set(), set()
    for i in connectivity_order(lines, graph):
        if covers[i] - covered:
            selected.add(i)
            covered.update(covers[i])
        if covered == targets:
            return selected
    raise ValueError(f"Candidates cannot cover regions: {sorted(targets - covered)}")


def structural_failure(lines, covers, targets, groups, graph, obstacles, selected):
    if not selected <= set(range(len(lines))):
        return "candidate membership"
    covered = set().union(*(covers[i] for i in selected)) if selected else set()
    if covered != targets:
        return "convex coverage"
    for group in groups:
        nodes = selected & group
        if not nodes or not nx.is_connected(graph.subgraph(nodes)):
            return "component connectivity"
    membership = {i: component for component, group in enumerate(groups) for i in group}
    if any(membership[a] != membership[b] for a, b in graph.subgraph(selected).edges):
        return "cross-component connection"
    if len(closed_routes([lines[i] for i in sorted(selected)], obstacles)) != len(obstacles):
        return "ring witnesses"
    return None


def repair_selection(lines, covers, targets, groups, graph, obstacles, selected, ring_seed):
    """Add certified ring and connection candidates; then trim redundant additions."""
    selected = set(selected)
    if len(closed_routes([lines[i] for i in sorted(selected)], obstacles)) != len(obstacles):
        ring_added = set(ring_seed) - selected
        selected.update(ring_added)
    else:
        ring_added = set()
    connected = _connect_exact_selected(lines, selected, groups)
    connection_added = connected - selected
    selected = connected
    failure = structural_failure(lines, covers, targets, groups, graph, obstacles, selected)
    if failure:
        raise ValueError(f"Topology repair failed: {failure}")
    removed = set()
    for i in sorted(ring_added | connection_added,
                    key=lambda j: (lines[j].length, canonical_interval(lines[j].start, lines[j].end))):
        trial = selected - {i}
        if structural_failure(lines, covers, targets, groups, graph, obstacles, trial) is None:
            selected = trial
            removed.add(i)
    return selected, {"ring_added": len(ring_added), "connection_added": len(connection_added),
                      "repair_additions_trimmed": len(removed)}


def improve_topology(lines, covers, targets, groups, graph, obstacles, selected, clearance, *,
                     addition_limit=400, checks_limit=300, rounds_limit=8,
                     three_for_two_limit=40, additions=None,
                     exchange_sizes=((2, 1), (3, 2))):
    """Bounded deterministic 2-for-1, then 3-for-2, with no angular constraint."""
    if min(addition_limit, checks_limit, rounds_limit) <= 0 or three_for_two_limit < 0:
        raise ValueError("Invalid exchange search budget")
    if not exchange_sizes or any(size not in ((2, 1), (3, 2)) for size in exchange_sizes):
        raise ValueError("Only 2-for-1 and 3-for-2 exchanges are supported")
    selected = set(selected)
    failure = structural_failure(lines, covers, targets, groups, graph, obstacles, selected)
    if failure:
        raise ValueError(f"Initial selection fails {failure}")
    for i in selected:
        if not clearance.permits_exact(lines[i].start, lines[i].end):
            raise ValueError(f"Candidate {i} fails exact clearance")
    order = connectivity_order(lines, graph)
    if additions is not None:
        allowed = set(additions)
        if not allowed <= set(range(len(lines))):
            raise ValueError("Exchange additions must belong to the candidate pool")
        order = [i for i in order if i in allowed]
    indices = {region: i for i, region in enumerate(sorted(targets))}
    masks = [sum(1 << indices[region] for region in cover) for cover in covers]
    target_mask = (1 << len(indices)) - 1
    exchanges, checks = [], 0

    def search(remove_count, add_count, limit):
        nonlocal checks
        available = [i for i in order if i not in selected][:limit]
        for remove in combinations(sorted(selected), remove_count):
            remaining = selected.difference(remove)
            covered = 0
            for i in remaining:
                covered |= masks[i]
            missing = target_mask & ~covered
            useful = [i for i in available if not missing or masks[i] & missing]
            for add in combinations(useful, add_count):
                supplied = 0
                for i in add:
                    supplied |= masks[i]
                if missing & ~supplied:
                    continue
                for i in add:
                    if not clearance.permits_exact(lines[i].start, lines[i].end):
                        raise ValueError(f"Candidate {i} fails exact clearance")
                checks += 1
                trial = remaining.union(add)
                if structural_failure(lines, covers, targets, groups, graph, obstacles, trial) is None:
                    return trial, (remove, add)
                if checks >= checks_limit:
                    return None
        return None

    for _ in range(rounds_limit):
        if checks >= checks_limit:
            break
        found = None
        for remove_count, add_count in exchange_sizes:
            limit = addition_limit if add_count == 1 else three_for_two_limit
            if limit >= add_count and checks < checks_limit:
                found = search(remove_count, add_count, limit)
                if found is not None:
                    break
        if found is None:
            break
        selected, exchange = found
        exchanges.append(exchange)
    return ExchangeResult(frozenset(selected), tuple(exchanges), checks)
