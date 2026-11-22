"""Connectivity-first axial-map experiments; not used by production selection."""

from dataclasses import dataclass
from itertools import combinations
from math import atan2, pi

from .exact_axial import closed_routes
from .experimental_connectivity_selection import (
    connectivity_order, repair_selection, structural_failure,
)


@dataclass(frozen=True)
class Footprint:
    reach: int
    bounds: tuple
    directions: frozenset[int]


def direction_class(line, classes=12):
    dx, dy = line.end[0] - line.start[0], line.end[1] - line.start[1]
    return min(classes - 1, int((atan2(float(dy), float(dx)) % pi) * classes / pi))


def reach_masks(graph, count):
    if set(graph) != set(range(count)):
        raise ValueError("Candidate graph must index the entire pool")
    return [sum(1 << node for node in ({i} | set(graph[i]))) for i in range(count)]


def footprint(lines, masks, selected):
    selected = set(selected)
    if not selected:
        raise ValueError("A structural footprint requires at least one line")
    reach = 0
    points = []
    directions = set()
    for i in selected:
        reach |= masks[i]
        points.extend((lines[i].start, lines[i].end))
        directions.add(direction_class(lines[i]))
    return Footprint(reach, (min(p[0] for p in points), min(p[1] for p in points),
                             max(p[0] for p in points), max(p[1] for p in points)),
                     frozenset(directions))


def preserves_footprint(actual, required):
    return (actual.reach & required.reach == required.reach
            and actual.bounds[0] <= required.bounds[0]
            and actual.bounds[1] <= required.bounds[1]
            and actual.bounds[2] >= required.bounds[2]
            and actual.bounds[3] >= required.bounds[3]
            and actual.directions >= required.directions)


def grow_backbone(lines, graph, groups, obstacles, ring_candidates, minimum_gain):
    """Scan once in fixed degree order; accept connected structural contributions."""
    if minimum_gain <= 0 or not groups:
        raise ValueError("A positive marginal reach threshold and components are required")
    if set().union(*groups) != set(range(len(lines))) or sum(map(len, groups)) != len(lines):
        raise ValueError("Accessible components must partition the candidate pool")
    order = connectivity_order(lines, graph)
    masks = reach_masks(graph, len(lines))
    selected = set()
    reasons = {}
    for group in groups:
        first = next((i for i in order if i in group), None)
        if first is None:
            raise ValueError("A component has no candidates")
        selected.add(first)
        reasons[first] = ["component seed"]
    current = footprint(lines, masks, selected)
    rings = closed_routes([lines[i] for i in sorted(selected)], obstacles)
    for i in order:
        if i in selected:
            continue
        group = next(group for group in groups if i in group)
        if not (set(graph[i]) & selected & group):
            continue
        new = footprint(lines, masks, selected | {i})
        why = []
        if (masks[i] & ~current.reach).bit_count() >= minimum_gain:
            why.append("network reach")
        if new.bounds != current.bounds:
            why.append("spatial extent")
        if direction_class(lines[i]) not in current.directions:
            why.append("direction")
        new_rings = rings
        if i in ring_candidates and len(set(graph[i]) & selected) >= 2:
            new_rings = closed_routes([lines[j] for j in sorted(selected | {i})], obstacles)
            if new_rings - rings:
                why.append("witness circuit")
        if why:
            selected.add(i)
            reasons[i] = why
            current, rings = new, new_rings
    return selected, reasons


def complete_coverage(lines, covers, targets, groups, graph, obstacles, backbone, ring_seed):
    order = connectivity_order(lines, graph)
    rank = {i: position for position, i in enumerate(order)}
    selected = set(backbone)
    covered = set().union(*(covers[i] for i in selected))
    additions = []
    while covered != targets:
        if not covered <= targets:
            raise ValueError("Candidate coverage references unknown regions")
        available = set(range(len(lines))) - selected
        if not available:
            raise ValueError("Candidate pool cannot cover all required regions")
        candidate = min(available, key=lambda i: (-len(covers[i] - covered), rank[i]))
        if not covers[candidate] - covered:
            raise ValueError("Candidate pool cannot cover all required regions")
        selected.add(candidate)
        additions.append(candidate)
        covered |= covers[candidate]
    repaired, repair = repair_selection(lines, covers, targets, groups, graph, obstacles,
                                        selected, ring_seed)
    return repaired, additions, sorted(repaired - selected), repair


def reduce_selection(lines, covers, targets, groups, graph, obstacles, selected, clearance,
                     required, *, addition_limit=60, pair_limit=16,
                     removal_limit=2000, check_limit=100, rounds=5):
    """Bounded strict count reductions retaining the original structural footprint."""
    selected = set(selected)
    if structural_failure(lines, covers, targets, groups, graph, obstacles, selected):
        raise ValueError("Reduction requires a coverage- and topology-feasible selection")
    for i in selected:
        if not clearance.permits_exact(lines[i].start, lines[i].end):
            raise ValueError(f"Selected candidate {i} fails exact clearance")
    order = connectivity_order(lines, graph)
    masks = reach_masks(graph, len(lines))
    ids = {region: i for i, region in enumerate(sorted(targets))}
    cover_masks = [sum(1 << ids[r] for r in cover) for cover in covers]
    all_regions = (1 << len(ids)) - 1
    exchanges = []
    attempts = {"removal_sets": 0, "feasibility_checks": 0,
                "bounded_modes": [], "searches": {"1-for-0": 0, "2-for-1": 0, "3-for-2": 0}}

    def search(remove_count, add_count, limit):
        available = [i for i in order if i not in selected][:limit]
        removal_checks = feasibility_checks = 0
        mode = f"{remove_count}-for-{add_count}"
        attempts["searches"][mode] += 1
        for remove in combinations(sorted(selected), remove_count):
            if removal_checks >= removal_limit:
                attempts["bounded_modes"].append(mode)
                return None
            removal_checks += 1
            attempts["removal_sets"] += 1
            remainder = selected.difference(remove)
            covered = 0
            for i in remainder:
                covered |= cover_masks[i]
            missing = all_regions & ~covered
            useful = [i for i in available if not missing or cover_masks[i] & missing]
            additions = [()] if add_count == 0 else combinations(useful, add_count)
            for add in additions:
                supplied = 0
                for i in add:
                    supplied |= cover_masks[i]
                if missing & ~supplied:
                    continue
                trial = remainder.union(add)
                if not trial or not preserves_footprint(footprint(lines, masks, trial), required):
                    continue
                if feasibility_checks >= check_limit:
                    attempts["bounded_modes"].append(mode)
                    return None
                for i in add:
                    if not clearance.permits_exact(lines[i].start, lines[i].end):
                        raise ValueError(f"Exchange candidate {i} fails exact clearance")
                attempts["feasibility_checks"] += 1
                feasibility_checks += 1
                if structural_failure(lines, covers, targets, groups, graph, obstacles, trial) is None:
                    return trial, (remove, add)
        return None

    def remove_singles():
        nonlocal selected
        while True:
            found = search(1, 0, 0)
            if not found:
                return
            selected, exchange = found
            exchanges.append(exchange)

    remove_singles()
    for remove_count, add_count, limit in ((2, 1, addition_limit), (3, 2, pair_limit)):
        for _ in range(rounds):
            found = search(remove_count, add_count, limit)
            if not found:
                break
            selected, exchange = found
            exchanges.append(exchange)
            remove_singles()
    return selected, exchanges, attempts
