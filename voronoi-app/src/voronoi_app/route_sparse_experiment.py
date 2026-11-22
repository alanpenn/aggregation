"""Bounded route-aware reduction on the preserved exact routing benchmark."""

from collections import Counter
from itertools import combinations
from time import monotonic
from types import SimpleNamespace

import networkx as nx
import numpy as np

from .angular import LineClearance
from .batch_methods import _domain
from .batch_routing_reference import MasterNetwork, describe, point
from .batch_store import StageResult, digest, encode
from .exact_enumeration import exact_pool_from_dict
from .experimental_entrance_reduction import fixed_terminal_attachments, union_mask
from .experimental_visibility import IndexedClearance
from .sheaf_experiment import DEFAULTS, Experiment, overlap

MEASURES = ("metric", "angular")


def doors_from_reference(reference):
    return [{**d, "point": point(d["point"]),
             "connectors": [(i, point(stop)) for i, stop in d["connectors"]]}
            for d in reference["doorways"]]


def compare_routes(baseline, routes):
    results = {}
    for k in MEASURES:
        changes = [b - a if b is not None and a is not None else None
                   for a, b in zip(baseline[k], routes[k], strict=True)]
        percentages = [100 * change / a if a and change is not None else None
                       for a, change in zip(baseline[k], changes, strict=True)]
        results[k] = {"cost": describe(routes[k]), "absolute": describe(changes),
                      "percent": describe(percentages)}
    return results


def angular_bands(baseline, selected):
    return {
        f"[{lo},{hi})": compare_routes(
            {"metric": [], "angular": [a for a, _ in group]},
            {"metric": [], "angular": [b for _, b in group]},
        )["angular"]
        for lo, hi in [(0, .1), (.1, .5), (.5, 1), (1, float("inf"))]
        if (group := [(a, b) for a, b in zip(baseline, selected, strict=True)
                      if a is not None and lo <= a < hi])
    }


def sensitivity(inputs, parameters):
    """Rebuild a separate master with the original attachment rule at each cap."""
    reference = parameters["reference"]
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    original = doors_from_reference(reference)
    _, obstacles, accessible, occupied = _domain(inputs)
    checker = IndexedClearance(LineClearance(accessible, occupied, original_obstacles=obstacles.values()))
    maximum = max(parameters["limits"])
    options = fixed_terminal_attachments(
        [d["point"] for d in original], lines, SimpleNamespace(permits_exact=checker.permits), maximum,
    )
    if any(set(d["connectors"]) != {(a.line_id, a.point) for a in group[:64]}
           for d, group in zip(original, options, strict=True)):
        raise ValueError("The reconstructed cap-64 inventory differs from the saved master.")
    results = {}
    inventories = {}
    for limit in parameters["limits"]:
        started = monotonic()
        doors = [{**d, "connectors": [(a.line_id, a.point) for a in group[:limit]]}
                 for d, group in zip(original, options, strict=True)]
        network = MasterNetwork(lines, doors)
        maps = {}
        for name in ("full", "A", "B"):
            selected = frozenset(reference["maps"][name]["line_ids"])
            routes = {k: network.route(selected, k == "angular") for k in MEASURES}
            maps[name] = {"routes": routes, "relative_to_saved_cap":
                          compare_routes(reference["maps"][name]["routes"], routes)}
        for result in maps.values():
            result["relative_to_own_full"] = compare_routes(maps["full"]["routes"], result["routes"])
        inventories[str(limit)] = [
            [[i, list(map(str, stop))] for i, stop in d["connectors"]] for d in doors
        ]
        results[str(limit)] = {"maps": maps, "connectors": sum(len(d["connectors"]) for d in doors),
                               "seconds": monotonic() - started}
        print(parameters["case"], "connector cap", limit, flush=True)
    return StageResult({"limits": results, "inventories": inventories})


class SparseSearch:
    def __init__(self, inputs, parameters):
        self.p = parameters
        self.reference = parameters["reference"]
        candidates = inputs["candidates"]["pool"]["candidates"]
        if digest(encode({"candidate_records": candidates, "doorways": self.reference["doorways"]})
                  ) != self.reference["master_geometry_sha256"]:
            raise ValueError("Saved route reference and candidate geometry differ.")
        identities = [(d["open_cell"], d["building_cell"], d["point"]) for d in self.reference["doorways"]]
        if identities != [(d["open_cell"], d["building_cell"], d["point"]) for d in inputs["measures"]["entrances"]]:
            raise ValueError("Saved doorway identity or ordering differs.")
        if any({(a["line"], tuple(a["point"])) for a in original["connectors"]}
               != {(i, tuple(stop)) for i, stop in saved["connectors"]}
               for original, saved in zip(inputs["measures"]["entrances"], self.reference["doorways"], strict=True)):
            raise ValueError("Saved connector inventory differs from its parent.")
        lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
        self.network = MasterNetwork(lines, doors_from_reference(self.reference))
        pair_order = list(combinations(range(len(identities)), 2))
        if (list(map(tuple, self.reference["pairs"])) != pair_order
                or len(self.network.nodes) != self.reference["node_count"]
                or len(self.network.edges) != self.reference["segment_count"]):
            raise ValueError("Pair order or master noding differs.")
        self.archived = {name: frozenset(entry["line_ids"]) for name, entry in self.reference["maps"].items()}
        self.start = self.archived["A"]
        overrides = {"selection": {"line_ids": sorted(self.start)}, "measures": {"entrances": [
            {**d, "connectors": [{"line": i, "point": stop} for i, stop in d["connectors"]]}
            for d in self.reference["doorways"]
        ]}}
        self.exp = Experiment(inputs | overrides, DEFAULTS)
        self.source = dict(enumerate(self.exp.original_ids))
        self.canonical = {v: k for k, v in self.source.items()}
        self.groups = [frozenset(self.canonical[i] for i in g) for g in parameters["sheaves"]]
        if any(not group <= self.canonical_ids(self.start) for group in self.groups):
            raise ValueError("Archived sheaf contains a line outside entrance-guided map A.")
        self.baseline = self.reference["maps"]["full"]["routes"]
        self.origins = sorted(set(np.linspace(0, len(identities) - 2, parameters["sample_origins"], dtype=int).tolist()))
        sample_origins = set(self.origins)
        self.pair_indices = [i for i, (a, _) in enumerate(pair_order) if a in sample_origins]
        self.sample_baseline = {k: [self.baseline[k][i] for i in self.pair_indices] for k in MEASURES}
        self.complete = {}
        self.sampled = {}
        self.seconds = {}
        self.tallies = Counter()

    def canonical_ids(self, chosen):
        return frozenset(self.canonical[i] for i in chosen)

    def source_ids(self, chosen):
        return frozenset(self.source[i] for i in chosen)

    def evaluate(self, chosen, sampled=False):
        cache = self.sampled if sampled else self.complete
        if chosen not in cache:
            started = monotonic()
            if sampled and chosen in self.complete:
                full = self.complete[chosen][0]
                routes = {k: [full[k][i] for i in self.pair_indices] for k in MEASURES}
            else:
                routes = {k: self.network.route(chosen, k == "angular",
                                               origins=self.origins if sampled else None)
                          for k in MEASURES}
            baseline = self.sample_baseline if sampled else self.baseline
            metrics = compare_routes(baseline, routes)
            for k in MEASURES:
                if any(b is not None and a is not None and
                       b < a - (1e-8 + 1e-9 * max(abs(a), abs(b)))
                       for a, b in zip(baseline[k], routes[k], strict=True)):
                    raise ValueError(f"{k} costs below the certified full-pool reference.")
            cache[chosen] = (routes, metrics)
            self.seconds[chosen, sampled] = monotonic() - started
        return cache[chosen][1]

    def structural(self, chosen, *, diagnostic=False):
        ids = self.canonical_ids(chosen)
        result = self.exp.validate(ids)
        if not diagnostic:
            return result["status"] == "valid"
        coverage = union_mask(self.exp.covers, ids)
        if "rank" not in result:
            topology = self.exp.geometry(ids)
            result = result | {"rank": topology["independent_circulation_rank"],
                               "required_rank": topology["required_circulation_rank"]}
        return result | {"coverage_regions": coverage.bit_count(),
                         "required_regions": self.exp.target.bit_count(),
                         "missing_regions": [i for i in range(self.exp.target.bit_length())
                                             if (self.exp.target & ~coverage) >> i & 1],
                         "components": nx.number_connected_components(self.exp.graph.subgraph(ids)),
                         "unattached_doors": sum(not ids & links for links in self.exp.links)}

    def report(self, chosen, relative=None):
        metrics = self.evaluate(chosen)
        return {"line_ids": sorted(chosen), "line_count": len(chosen),
                "length": self.exp.weight(self.canonical_ids(chosen))[1],
                "constraints": self.structural(chosen, diagnostic=True), "routing": metrics,
                "relative_to_start": compare_routes(relative, self.complete[chosen][0]) if relative else None,
                "route_seconds": self.seconds[chosen, False]}

    def marginal(self):
        original = self.complete[self.start][0]
        result = []
        for i in sorted(self.start):
            proposal = self.start - {i}
            entry = self.report(proposal, original)
            entry["removed"] = i
            entry["classification"] = ("structurally_indispensable"
                if entry["constraints"]["status"] != "valid" or
                entry["routing"]["metric"]["cost"]["unreachable"] else "removable")
            result.append(entry)
        return result

    def sheaves(self):
        alternatives = []
        for group_id, group in enumerate(self.groups, 1):
            others = self.exp.selected - group
            proposals = []
            for removed in sorted(group):
                proposals.append((self.exp.selected - {removed}, "single deletion"))
            for removed in list(combinations(sorted(group), 2))[:self.p["sheaf_double_trials"]]:
                proposals.append((self.exp.selected - set(removed), "double deletion"))
            for keep in sorted(group):
                proposals.append((others | {keep}, "single representative"))
            # Use overlap and direction relative to the closest member, then tie-break canonically.
            ranking = []
            for i in sorted(set(range(len(self.exp.lines))) - self.exp.selected):
                scores = [overlap(self.exp.segments[i], self.exp.segments[j]) for j in sorted(group)]
                similar = [(-overlap_ratio, gap, angle, j)
                           for j, (angle, overlap_ratio, gap) in zip(sorted(group), scores, strict=True)
                           if angle <= 21 and overlap_ratio >= .48 and gap <= 3]
                if similar:
                    ranking.append((min(similar), i))
            for (score, i) in sorted(ranking)[:self.p["sheaf_replacements"]]:
                closest = score[-1]
                proposals.append(((self.exp.selected - {closest}) | {i}, "one-for-one exchange"))
                proposals.append((others | {i}, "replacement representative"))
            records = []
            seen = set()
            for canonical, kind in proposals:
                chosen = self.source_ids(canonical)
                if chosen in seen:
                    continue
                seen.add(chosen)
                if self.structural(chosen):
                    entry = self.report(chosen, self.complete[self.start][0])
                else:
                    entry = {"line_ids": sorted(chosen), "constraints": self.exp.validate(canonical)}
                records.append({"kind": kind, **entry})
            alternatives.append({"group": group_id, "members": sorted(self.source_ids(group)),
                                 "alternatives": records})
        return alternatives

    def mean_excess(self, chosen, sampled=False):
        metrics = self.evaluate(chosen, sampled)
        return tuple(metrics[k]["absolute"]["mean"] for k in MEASURES)

    def beam(self, priority, substitutions):
        budgets = self.p["mean_excess_budgets"]
        beams = {name: [self.start] for name in budgets}
        traces = []
        accepted = {self.start}
        for iteration in range(self.p["beam_rounds"]):
            next_beams = {}
            diagnostics = {}
            for name, states in beams.items():
                bounds = budgets[name]
                children = set()
                for state in states:
                    order = [i for i in priority if i in state]
                    window = order[:self.p["proposal_window"]]
                    proposals = [state - {i} for i in window]
                    # Consecutive blocks let the search reach earlier sparse counts in finite time.
                    for size in self.p["block_sizes"]:
                        proposals += [state - set(window[i:i + size])
                                      for i in range(0, len(window) - size + 1, size)]
                    for remove, added in substitutions[:self.p["beam_exchanges"]]:
                        if remove <= state and added.isdisjoint(state):
                            exchange = (state - remove) | added
                            # Couple a substitution with a deletion to keep each beam step descending.
                            proposals.extend(exchange - {i} for i in window[:3] if i not in remove)
                    children.update(c for c in proposals if len(c) < len(state) and self.structural(c))
                if not children:
                    continue

                def rank(chosen, sampled):
                    values = self.mean_excess(chosen, sampled)
                    if any(value is None for value in values):
                        return (float("inf"),)
                    penalty = sum(max(0, v / bound - 1) for v, bound in zip(values, bounds))
                    count, length, identities = self.exp.weight(self.canonical_ids(chosen))
                    return penalty, count, length, sum(v / b for v, b in zip(values, bounds)), identities

                ranked = sorted(children, key=lambda c: rank(c, True))
                shortlist = ranked[:self.p["complete_shortlist"]]
                # Audit the sample against complete ranking within the first round's entire proposal set.
                audit = ranked if iteration == 0 else shortlist
                complete = sorted(audit, key=lambda c: rank(c, False))

                def feasible(chosen):
                    metrics = self.evaluate(chosen)
                    return all(metrics[k]["cost"]["unreachable"] == 0 and
                               metrics[k]["absolute"]["mean"] <= b
                               for k, b in zip(MEASURES, bounds))

                winners = [c for c in complete if feasible(c)][:self.p["beam_width"]]
                sampled_winners = sorted((c for c in shortlist if feasible(c)),
                                         key=lambda c: rank(c, False))[:self.p["beam_width"]]
                diagnostics[name] = {"proposals": len(children), "complete_compared": len(audit),
                                     "sample_rank_changed": bool(complete and ranked[0] != complete[0]),
                                     "sample_shortlist_changed_survivors": winners != sampled_winners,
                                     "survivors": [sorted(c) for c in winners]}
                if winners:
                    next_beams[name] = winners
                    accepted.update(winners)
            traces.append(diagnostics)
            if not next_beams:
                break
            beams = next_beams
            if iteration % 5 == 0:
                print(self.p["case"], "beam round", iteration + 1,
                      {k: [len(c) for c in v] for k, v in beams.items()}, flush=True)
        return accepted, traces


def pareto(maps):
    """Keep maps non-dominated in count and both mean absolute excesses."""
    def objective(entry):
        return (entry["line_count"], *(entry["routing"][k]["absolute"]["mean"] for k in MEASURES))

    return [
        i for i, entry in enumerate(maps)
        if not any(
            all(a <= b for a, b in zip(objective(other), objective(entry))) and
            (objective(other) != objective(entry) or other["length"] < entry["length"])
            for other in maps
        )
    ]


def sparse_routes(inputs, parameters):
    started = monotonic()
    search = SparseSearch(inputs, parameters)
    if not search.structural(search.start):
        raise ValueError("Saved entrance-guided map failed the full validator.")
    search.evaluate(search.start)
    if any(not np.allclose(search.complete[search.start][0][k],
                           search.reference["maps"]["A"]["routes"][k], rtol=1e-9, atol=1e-8)
           for k in MEASURES):
        raise ValueError("Rebuilt master did not reproduce the saved entrance-guided routing.")
    base = search.report(search.start)
    marginal = search.marginal()
    print(parameters["case"], "marginal complete", len(marginal), flush=True)
    sheaves = search.sheaves()
    origin = set(search.start)
    substitutions = []
    for group in sheaves:
        for row in group["alternatives"]:
            if row["kind"] == "one-for-one exchange" and "routing" in row:
                current = set(row["line_ids"])
                substitutions.append((sum(row["routing"][k]["absolute"]["mean"] for k in MEASURES),
                                      frozenset(origin - current), frozenset(current - origin)))
    substitutions.sort(key=lambda item: (item[0], sorted(item[1]), sorted(item[2])))
    order = sorted(marginal, key=lambda item: (
        item["classification"] != "removable",
        sum(item["relative_to_start"][k]["absolute"]["mean"] or 0 for k in MEASURES),
        -search.network.lines[item["removed"]].length, item["removed"],
    ))
    accepted, traces = search.beam([r["removed"] for r in order],
                                   [(r, a) for _, r, a in substitutions])
    maps = []
    for chosen in sorted(accepted, key=lambda c: (len(c), sorted(c))):
        entry = search.report(chosen)
        entry["name"] = "A" if chosen == search.start else "beam"
        if entry["constraints"]["status"] != "valid" or any(
            entry["routing"][k]["cost"]["unreachable"] for k in MEASURES
        ):
            raise ValueError("An accepted beam map failed final validation.")
        maps.append(entry)
    for name, entry in search.reference["maps"].items():
        if name not in ("full", "A"):
            maps.append({"name": name, "line_ids": entry["line_ids"], "line_count": len(entry["line_ids"]),
                         "length": entry["total_length"],
                         "constraints": search.structural(search.archived[name], diagnostic=True),
                         "routing": compare_routes(search.baseline, entry["routes"]),
                         "route_seconds": entry["routes"]["seconds"]})
    frontier = pareto(maps)
    angular = {name: angular_bands(search.baseline["angular"], entry["routes"]["angular"])
               for name, entry in search.reference["maps"].items() if name != "full"}
    return StageResult({"base": base, "marginal": marginal, "sheaves": sheaves, "maps": maps,
                        "pareto_indices": frontier, "angular_bands": angular, "beam_trace": traces,
                        "sample_pair_indices": search.pair_indices, "sample_origins": search.origins,
                        "route_counts": {"complete": len(search.complete), "sampled": len(search.sampled)},
                        "structural_validation_counts": dict(search.exp.calls),
                        "seconds": monotonic() - started})
