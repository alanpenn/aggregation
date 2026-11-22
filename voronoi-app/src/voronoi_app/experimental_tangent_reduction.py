"""Experimental hard tangent constraints and bounded topology-preserving reduction."""

from itertools import combinations

from .experimental_connectivity_selection import connectivity_order, structural_failure


def tangent_masks(count, tangent):
    masks = [0] * count
    for edge_index, edge in enumerate(tangent):
        for candidate in edge["candidates"]:
            if not 0 <= candidate < count:
                raise ValueError("Tangent references an absent candidate")
            masks[candidate] |= 1 << edge_index
    return masks


def represented(selected, masks):
    result = 0
    for candidate in selected:
        result |= masks[candidate]
    return result


def weight(mask, weights):
    total = 0
    while mask:
        bit = mask & -mask
        total += weights[bit.bit_length() - 1]
        mask -= bit
    return total


def minimum_cover(masks, required, initial=0):
    """Prove a minimum-cardinality cover of the required bits by dynamic programming."""
    needed = required & ~initial
    best_for_mask = {}
    for i, mask in enumerate(masks):
        mask &= needed
        if mask and mask not in best_for_mask:
            best_for_mask[mask] = i
    states = {0: ()}
    for mask, candidate in sorted(best_for_mask.items(), key=lambda item: item[1]):
        for covered, chosen in list(states.items()):
            combined = covered | mask
            proposed = chosen + (candidate,)
            if combined not in states or (len(proposed), proposed) < (
                len(states[combined]), states[combined]
            ):
                states[combined] = proposed
    if needed not in states:
        raise ValueError("Required tangent segments cannot be represented by this pool")
    return states[needed]


def augment_weighted(selected, masks, weights, minimum, order):
    selected = set(selected)
    if minimum < 0 or minimum > sum(weights):
        raise ValueError("Invalid required tangent weight")
    additions = []
    current = represented(selected, masks)
    rank = {candidate: i for i, candidate in enumerate(order)}
    while weight(current, weights) < minimum:
        available = set(order) - selected
        if not available:
            raise ValueError("Candidate pool cannot meet the required tangent weight")
        best = min(available, key=lambda i: (-weight(masks[i] & ~current, weights), rank[i]))
        if not masks[best] & ~current:
            raise ValueError("Candidate pool cannot meet the required tangent weight")
        selected.add(best)
        additions.append(best)
        current |= masks[best]
    return selected, additions


def reduce_tangent(lines, covers, targets, groups, graph, obstacles, selected, clearance,
                   masks, weights, required, minimum, *, addition_limit=60, pair_limit=16,
                   removal_limit=400, check_limit=60, rounds=3):
    """Strictly reduce count while preserving clearance, topology and tangent constraints."""
    if len(masks) != len(lines) or len(weights) == 0:
        raise ValueError("Invalid tangent data")
    selected = set(selected)
    order = connectivity_order(lines, graph)
    rank = {candidate: i for i, candidate in enumerate(order)}
    indices = {region: i for i, region in enumerate(sorted(targets))}
    cover_masks = [sum(1 << indices[region] for region in cover) for cover in covers]
    target_mask = (1 << len(indices)) - 1

    def tangent_ok(chosen):
        mask = represented(chosen, masks)
        return mask & required == required and weight(mask, weights) >= minimum

    if not tangent_ok(selected):
        raise ValueError("Initial selection fails tangent constraints")
    failure = structural_failure(lines, covers, targets, groups, graph, obstacles, selected)
    if failure:
        raise ValueError(f"Initial selection fails {failure}")
    for i in selected:
        if not clearance.permits_exact(lines[i].start, lines[i].end):
            raise ValueError(f"Selected candidate {i} fails exact clearance")
    exchanges = []
    stats = {"removal_sets": 0, "feasibility_checks": 0, "bounded_modes": [],
             "searches": {"1-for-0": 0, "2-for-1": 0, "3-for-2": 0}}
    addition_pool = set(order[:160]) | {i for i, mask in enumerate(masks) if mask}
    stats["addition_pool"] = len(addition_pool)

    def search(remove_count, add_count, limit):
        mode = f"{remove_count}-for-{add_count}"
        stats["searches"][mode] += 1
        removed_count = checked = 0
        available = [i for i in order if i in addition_pool and i not in selected]
        for remove in combinations(sorted(selected), remove_count):
            if removed_count >= removal_limit:
                stats["bounded_modes"].append(mode)
                return None
            removed_count += 1
            stats["removal_sets"] += 1
            remainder = selected.difference(remove)
            covered = 0
            for i in remainder:
                covered |= cover_masks[i]
            missing = target_mask & ~covered
            have = represented(remainder, masks)
            missing_tangents = required & ~have
            candidates = sorted(available, key=lambda i: (
                -(masks[i] & missing_tangents).bit_count(),
                -weight(masks[i] & ~have, weights), rank[i]))[:limit]
            options = [()] if add_count == 0 else combinations(candidates, add_count)
            for add in options:
                supplied = 0
                for i in add:
                    supplied |= cover_masks[i]
                trial = remainder.union(add)
                if missing & ~supplied or not tangent_ok(trial):
                    continue
                if checked >= check_limit:
                    stats["bounded_modes"].append(mode)
                    return None
                for i in add:
                    if not clearance.permits_exact(lines[i].start, lines[i].end):
                        raise ValueError(f"Exchange candidate {i} fails exact clearance")
                checked += 1
                stats["feasibility_checks"] += 1
                if structural_failure(lines, covers, targets, groups, graph, obstacles, trial) is None:
                    return trial, (remove, add)
        return None

    def singles():
        nonlocal selected
        while True:
            found = search(1, 0, 0)
            if not found:
                return
            selected, exchange = found
            exchanges.append(exchange)

    singles()
    for remove_count, add_count, limit in ((2, 1, addition_limit), (3, 2, pair_limit)):
        for _ in range(rounds):
            found = search(remove_count, add_count, limit)
            if not found:
                break
            selected, exchange = found
            exchanges.append(exchange)
            singles()
    return selected, exchanges, stats
