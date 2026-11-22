"""Experimental geometric and route-aware corridor replacements."""

from itertools import combinations
from math import hypot, tan, radians
from time import monotonic

from .angular import _intersections
from .batch_routing_reference import describe
from .batch_store import StageResult
from .route_sparse_experiment import MEASURES, SparseSearch, compare_routes


def ends(line):
    return tuple(sorted((line.start, line.end)))


def span(axis, line):
    a, b = axis
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = hypot(dx, dy)
    points = [((x-a[0])*dx/length+(y-a[1])*dy/length,
               (y-a[1])*dx/length-(x-a[0])*dy/length)
              for x, y in map(lambda p: tuple(map(float, p)), ends(line))]
    lo, hi = sorted(points)
    return lo, hi, length


def membership(axis, lines, width, minimum=.28):
    members = []
    for line in lines:
        (x0, y0), (x1, y1), length = span(axis, line)
        run = x1-x0
        overlap = min(x1, length)-max(x0, 0)
        if run <= 0 or overlap < minimum*length or abs(y1-y0) > tan(radians(32))*run:
            continue
        ys = [y0+(x-x0)*(y1-y0)/run for x in (max(0, x0), min(length, x1))]
        if max(map(abs, ys)) <= width:
            members.append(line.line_id)
    return frozenset(members)


def opposed_pairs(axis, lines, members, *, minimum=.60, width=2):
    """Rank intersecting, opposite-signed diagonals by geometric extent."""
    positive, negative = [], []
    for i in sorted(members):
        (x0, y0), (x1, y1), length = span(axis, lines[i])
        run = x1-x0
        if min(x1, length)-max(x0, 0) < minimum*length or abs(y1-y0) < .2*width:
            continue
        # A diagonal must cross the corridor axis, allowing small axis-fit error.
        if min(y0, y1) > .12*width or max(y0, y1) < -.12*width:
            continue
        (positive if y1 > y0 else negative).append(i)
    ranked = []
    for i in positive:
        for j in negative:
            if not _intersections(*ends(lines[i]), *ends(lines[j])):
                continue
            lengths = [lines[k].length for k in (i, j)]
            pair = tuple(sorted((i, j)))
            ranked.append(((-sum(lengths), -min(lengths), tuple(sorted(ends(lines[k]) for k in pair))), pair))
    return [pair for _, pair in sorted(ranked)]


def worst_pairs(pairs, baseline, selected, limit=5):
    result = {}
    for k in MEASURES:
        rows = [(b-a, i, j) for (i, j), a, b in zip(pairs, baseline[k], selected[k], strict=True)
                if a is not None and b is not None and b-a > 1e-9]
        result[k] = [{"increase": delta, "doors": [i, j]}
                     for delta, i, j in sorted(rows, key=lambda row: (-row[0], row[1:]))[:limit]]
    result["unreachable"] = [[i, j] for (i, j), a, b in zip(
        pairs, baseline["metric"], selected["metric"], strict=True) if a is not None and b is None]
    return result


def analyze_corridor(network, start, archived, full_routes, routes, checks, axis, width, settings,
                     *, local_axes=()):
    lines = network.lines
    members = membership(axis, lines, width)
    local_members = [membership(local, lines, band) for local, band in local_axes]
    members = members.union(*local_members)
    original = start & members
    exterior = start - members
    geometry = opposed_pairs(axis, lines, members, width=width)
    pair = frozenset(geometry[0]) if geometry else None
    baseline = routes(start)
    transverse = set()
    for i in exterior:
        (x0, y0), (x1, y1), _ = span(axis, lines[i])
        if abs(y1-y0) > .65 * abs(x1-x0):
            transverse.add(i)

    def contacts(reps):
        return sorted({j for i in reps for j in network.graph[i] if j in exterior})

    def evaluation(reps):
        if reps is None:
            return {"status": "unavailable"}
        selected = exterior | reps
        structural = checks(selected)
        raw = routes(selected)
        lost = worst_pairs(list(combinations(range(len(network.doors)), 2)), baseline, raw)
        edge_ids = contacts(reps)
        return {"status": "valid" if structural["status"] == "valid" and not
                any(x is None for x in raw["metric"] + raw["angular"]) else "invalid",
                "representatives": sorted(reps), "line_count": len(selected),
                "length": sum(lines[i].length for i in sorted(selected)), "constraints": structural,
                "external_connections": edge_ids, "transverse_connections": sorted(transverse & set(edge_ids)),
                "route": compare_routes(full_routes, raw), "deterioration": compare_routes(baseline, raw),
                "affected_pairs": lost}

    def quick(reps):
        result = checks(exterior | reps, diagnostic=False)
        return result["status"] == "valid"

    order = sorted(members, key=lambda i: (-len(contacts({i})), -lines[i].length, ends(lines[i])))
    repairs = None
    trials = {}
    if pair is not None:
        options = sorted(members - pair, key=lambda i: (
            -len(set(contacts({i})) & transverse - set(contacts(pair))), -len(contacts({i})),
            -lines[i].length, ends(lines[i])))[:settings["repair_shortlist"]]
        for n in range(settings["repair_limit"]+1):
            valid = []
            for extra in combinations(options, n):
                trial = pair | frozenset(extra)
                if quick(trial):
                    valid.append(trial)
            trials[str(n)] = {"tested": len(list(combinations(options, n))), "valid": len(valid)}
            if valid:
                repairs = min(valid, key=lambda r: (sum(lines[i].length for i in sorted(r)), sorted(r)))
                break

    ranked = list(dict.fromkeys([*order[:settings["pair_shortlist"]], *sorted(pair or ())]))
    valid_pairs = []
    for candidate in combinations(ranked, 2):
        reps = frozenset(candidate)
        if quick(reps):
            valid_pairs.append(reps)
    # Score every feasible shortlisted pair on all fixed doorway pairs.
    valid_results = [evaluation(r) for r in valid_pairs]
    valid_results = [r for r in valid_results if r["status"] == "valid"]

    mean_full = {k: describe(full_routes[k])["mean"] for k in MEASURES}

    def score(entry):
        return (sum(entry["route"][k]["cost"]["mean"] / mean_full[k] for k in MEASURES),
                entry["length"], entry["representatives"])

    longest = sorted(members, key=lambda i: (-lines[i].length, ends(lines[i])))[:2]
    variants = {
        "A": evaluation(original), "B": evaluation(pair), "C": evaluation(repairs),
        "D": min(valid_results, key=score) if valid_results else {"status": "unavailable"},
        "E": evaluation(archived & members) if archived is not None else {"status": "unavailable"},
        "length": evaluation(frozenset(longest)) if len(longest) == 2 else {"status": "unavailable"},
        "connectivity": evaluation(frozenset(order[:2])) if len(order) >= 2 else {"status": "unavailable"},
    }
    local_pairs = []
    if local_axes:
        for (local, band), group in zip(local_axes, local_members, strict=True):
            ranked_local = opposed_pairs(local, lines, group, width=band)
            local_pairs.append(ranked_local[0] if ranked_local else None)
        combined = frozenset(i for p in local_pairs if p for i in p)
        variants["overlapping"] = evaluation(combined) if all(local_pairs) else {"status": "unavailable"}
    return {"axis": axis, "half_band": width, "members": sorted(members),
            "original_members": sorted(original), "exterior": sorted(exterior),
            "transverse": sorted(transverse), "opposed_pairs": len(geometry),
            "extreme_pair": sorted(pair) if pair is not None else None,
            "selected_pair_members": len(pair & start) if pair is not None else None,
            "repair_trials": trials, "pair_trials": len(list(combinations(ranked, 2))),
            "valid_two_line_trials": len(valid_results), "local_axes": local_axes,
            "local_pairs": local_pairs, "variants": variants}


def preserved(inputs, parameters):
    start_time = monotonic()
    search = SparseSearch(inputs, parameters)
    network = search.network
    lines = network.lines
    candidates = sorted(
        (max(g, key=lambda i: (lines[i].length, ends(lines[i]))) for g in parameters["sheaves"]),
        key=lambda i: (-lines[i].length, ends(lines[i])),
    )
    axes = []
    for i in candidates:
        axis = tuple(tuple(map(float, p)) for p in ends(lines[i]))
        width = max(2.5, min(5.0, lines[i].length*.11))
        members = membership(axis, lines, width)
        if any(i in other or len(members & other) > .48 * min(len(other), len(members))
               for _, _, other in axes):
            continue
        axes.append((axis, width, members))
        if len(axes) == parameters["corridor_limit"]:
            break

    def checks(selected, diagnostic=True):
        if not diagnostic:
            return {"status": "valid" if search.structural(selected) else "invalid"}
        result = search.structural(selected, diagnostic=True)
        topology = search.exp.geometry(search.canonical_ids(selected))
        return result | {"clearance_rejected": topology["lines_crossing_effective_occupied_space"]}

    def routes(selected):
        search.evaluate(selected)
        return search.complete[selected][0]

    corridors = []
    for axis, width, _ in axes:
        corridors.append(analyze_corridor(network, search.start, search.archived["B"], search.baseline,
                                          routes, checks, axis, width, parameters))
        print(parameters["case"], "corridor", len(corridors), flush=True)
    return StageResult({"corridors": corridors, "doorways": parameters["reference"]["doorways"],
                        "intervals": [[list(map(str, p)) for p in ends(line)] for line in lines],
                        "settlement": inputs["settlement"], "seconds": monotonic()-start_time})
