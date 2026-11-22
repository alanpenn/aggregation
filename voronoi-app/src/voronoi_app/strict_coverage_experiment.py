"""Batch-only strict coverage audits and bounded doorway-incidence repairs."""

from collections import Counter, deque
from itertools import combinations
from time import monotonic

import networkx as nx
from shapely import from_wkb

from .batch_routing_reference import MasterNetwork, describe, interval
from .batch_store import StageResult
from .exact_axial import ExactCandidate, _bounds, region_coverage
from .exact_enumeration import exact_pool_from_dict
from .experimental_entrance_reduction import union_mask, visibility_masks
from .region_incidence_angular import angular_depth
from .route_sparse_experiment import doors_from_reference
from .sheaf_experiment import DEFAULTS, Experiment


def incidence_sets(saved):
    regions = {int(i): frozenset(group) for i, group in saved["region_lines"].items()}
    doors = [frozenset().union(*(regions[i] for i in group)) for group in saved["doorway_regions"]]
    return regions, doors


def omissions(selected, regions, doors):
    return ([i for i, group in regions.items() if not selected & group],
            [i for i, group in enumerate(doors) if not selected & group])


def audit(inputs, parameters):
    saved = parameters["incidence"]
    region_groups, door_groups = incidence_sets(saved)
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    regions = {int(i): from_wkb(v) for i,v in inputs["candidates"]["regions_wkb"].items()}
    if regions.keys() != region_groups.keys():
        raise ValueError("Saved incidence regions differ from the benchmark.")
    strict = [set() for _ in lines]
    for i, ids in region_groups.items():
        for j in ids:
            strict[j].add(i)
    extras = parameters["extra_intervals"]
    for row in extras:
        a, b = interval(row)
        lines.append(ExactCandidate(len(lines), a, b, a, b, "external-archive"))
    strict.extend(region_coverage(lines[len(strict):], regions))
    old = visibility_masks(lines, strict, regions, [_bounds(line) for line in lines])
    cache = {}
    output = {}
    for item in parameters["maps"]:
        selected = frozenset(item["line_ids"])
        if selected not in cache:
            covered = set().union(*(strict[i] for i in selected))
            loose = union_mask(old, selected)
            missing = sorted(regions.keys()-covered)
            unattached = [i for i, group in enumerate(saved["doorway_regions"])
                          if covered.isdisjoint(group)]
            boundary = [i for i in missing if loose & (1 << i)]
            cache[selected] = {"lines": len(selected), "old_coverage": loose.bit_count(),
                               "strict_coverage": len(covered), "missing_regions": missing,
                               "boundary_only_regions": boundary, "unattached_doors": unattached}
        output[item["name"]] = item | cache[selected]
    return StageResult({"maps": output, "distinct_selections": len(cache),
                        "doors": saved["doorways"], "doorway_regions": saved["doorway_regions"],
                        "required_regions": len(regions),
                        "region_repair_candidates": saved["region_lines"],
                        "door_repair_candidates": [sorted(s) for s in door_groups],
                        "outside_master_intervals": extras})


def compare_pairs(full, reduced):
    differences = [b-a for a,b in zip(full, reduced, strict=True) if a is not None and b is not None]
    return describe(differences)


def verify_monotone(full, subset):
    for a,b in zip(full, subset, strict=True):
        if b is not None and (a is None or b < a-(1e-8+1e-9*max(abs(a),abs(b)))):
            raise ValueError("Subset angular depth beats the full-pool incidence baseline.")


class Repair:
    def __init__(self, inputs, parameters):
        self.saved = parameters["incidence"]
        self.regions, self.doors = incidence_sets(self.saved)
        self.start = frozenset(self.saved["maps"][parameters["start"]]["line_ids"])
        self.lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
        measures = inputs["measures"]
        self.exp = Experiment(inputs | {"selection": {"line_ids": sorted(self.start)}}, DEFAULTS)
        self.ids = {original: i for i,original in enumerate(self.exp.original_ids)}
        self.graph = nx.relabel_nodes(self.exp.graph, dict(enumerate(self.exp.original_ids)))
        self.metric_doors = doors_from_reference(parameters["reference"])
        identities = ("open_cell", "building_cell", "point")
        if ([[d[k] for k in identities] for d in measures["entrances"]]
                != [[d[k] for k in identities] for d in self.saved["doorways"]]):
            raise ValueError("Incidence doorway inventory differs from archived geometry.")
        self.angular = MasterNetwork(self.lines, [])
        self.metric = MasterNetwork(self.lines, self.metric_doors)
        if [len(self.angular.nodes), len(self.angular.edges)] != [self.saved["exact_nodes"], self.saved["exact_atomic_edges"]]:
            raise ValueError("Directed angular master geometry differs from the audited baseline.")
        self.pairs = list(map(tuple, self.saved["pairs"]))
        self.angular_cache = {}
        self.validation = {}
        self.counts = Counter()
        self.scan_passes = parameters.get("scan_passes", True)

    def geometry_key(self, i):
        line = self.lines[i]
        return tuple(sorted((line.start,line.end)))

    def valid(self, chosen):
        if chosen not in self.validation:
            missing, lost = omissions(chosen, self.regions, self.doors)
            if missing or lost:
                self.validation[chosen] = False
                self.counts["incidence_rejections"] += 1
            elif not chosen or not nx.is_connected(self.graph.subgraph(chosen)):
                self.validation[chosen] = False
                self.counts["connectivity_rejections"] += 1
            else:
                self.counts["exact_winding_checks"] += 1
                topology = self.exp.geometry({self.ids[i] for i in chosen})
                self.validation[chosen] = bool(topology["circulation_constraints_satisfied"] and
                                               not topology["lines_crossing_effective_occupied_space"])
                if not self.validation[chosen]:
                    self.counts["winding_or_clearance_rejections"] += 1
        return self.validation[chosen]

    def angular_costs(self, selected):
        if selected not in self.angular_cache:
            values, statuses = angular_depth(self.angular, selected, [d & selected for d in self.doors], self.pairs)
            verify_monotone(self.saved["maps"]["full"]["angular"], values)
            if any(s != "reachable" for s in statuses):
                raise ValueError("A strict-valid map has unreachable incidence-angular pairs.")
            self.angular_cache[selected] = values
        return self.angular_cache[selected]

    def rank(self, i, base, rule):
        return ((-self.lines[i].length,) if rule == "longest" else
                (-len(self.graph[i].keys() & base), -self.lines[i].length)) + (self.geometry_key(i),)

    def additions(self, base, rule, forced=None):
        chosen = base | ({forced} if forced is not None else set())
        chosen = frozenset(chosen)
        while missing := omissions(chosen, self.regions, self.doors)[0]:
            gains = Counter(i for region in missing for i in self.regions[region] if i not in chosen)
            if not gains:
                raise ValueError("Full certified pool cannot repair missing strict coverage.")
            i = min(gains, key=lambda j: (-gains[j], self.rank(j, chosen, rule)))
            chosen = chosen | {i}
        return self.connect(chosen, base)

    def connect(self, chosen, base):
        """Bridge isolated repair lines by the fewest extra candidate intersections."""
        connected = set(nx.node_connected_component(self.graph.subgraph(chosen), min(base)))
        while chosen - connected:
            previous = dict.fromkeys(connected)
            queue = deque(sorted(connected, key=self.geometry_key))
            target = None
            while queue and target is None:
                node = queue.popleft()
                for neighbor in sorted(self.graph[node], key=self.geometry_key):
                    if neighbor in previous:
                        continue
                    previous[neighbor] = node
                    if neighbor in chosen:
                        target = neighbor
                        break
                    queue.append(neighbor)
            if target is None:
                raise ValueError("An isolated repair line cannot connect to the archived map.")
            while target not in connected:
                chosen |= {target}
                target = previous[target]
            connected = set(nx.node_connected_component(self.graph.subgraph(chosen), min(base)))
        return chosen

    def backward(self, chosen, priority, *, preserve_metric=False):
        removals = []
        metric_sets = [{i for i, _ in d["connectors"]} for d in self.metric_doors]
        while True:
            start_count = len(chosen)
            def rank(i):
                length = self.lines[i].length
                value = {"shortest": length, "longest": -length,
                         "lowest-connectivity": len(self.graph[i].keys() & chosen)}[priority]
                return value, self.geometry_key(i)
            for i in sorted(chosen, key=rank):
                reduced = chosen - {i}
                if preserve_metric and any(not reduced & options for options in metric_sets):
                    continue
                if self.valid(reduced):
                    chosen = reduced
                    removals.append(i)
                    if not self.scan_passes:
                        break
            if len(chosen) == start_count:
                return chosen, removals

    def report(self, selected, old_metric):
        if not self.valid(selected):
            raise ValueError("Cannot report an invalid repair as feasible.")
        ids = {self.ids[i] for i in selected}
        # Independent uncached geometry path also verifies the final winding witnesses.
        topology = self.exp.geometry(ids, witness=True)
        if (not topology["circulation_constraints_satisfied"]
                or topology["lines_crossing_effective_occupied_space"]):
            raise ValueError("Independent topology audit rejected a retained map.")
        angular = self.angular_costs(selected)
        metric = self.metric.route(selected, angular=False)
        lines = [self.lines[i] for i in sorted(selected)]
        return {"line_ids": sorted(selected), "added": sorted(selected-self.start),
                "removed": sorted(self.start-selected), "length": sum(line.length for line in lines),
                "strict_coverage": len(self.regions), "components": 1,
                "winding_rank": topology["independent_circulation_rank"],
                "required_rank": topology["required_circulation_rank"], "unattached_doors": 0,
                "angular": angular, "angular_statistics": describe(angular),
                "angular_excess": compare_pairs(self.saved["maps"]["full"]["angular"], angular),
                "metric": metric, "metric_statistics": describe(metric),
                "metric_change": compare_pairs(old_metric, metric),
                "metric_newly_unreachable": sum(a is not None and b is None for a,b in zip(old_metric,metric))}


def repair(inputs, parameters):
    start_time = monotonic()
    test = Repair(inputs, parameters)
    base = test.start
    initial_missing, doors = omissions(base, test.regions, test.doors)
    old = parameters["reference"]["maps"][parameters["start"]]["routes"]["metric"]
    proposals = {name: test.additions(base, name) for name in ("longest", "connectivity")}
    shortlist = set()
    for group in [test.regions[i] for i in initial_missing] + [test.doors[i] for i in doors]:
        for rule in ("longest", "connectivity"):
            shortlist.update(sorted(group-base,key=lambda i: test.rank(i,base,rule))[:parameters["per_rule"]])
    candidates = set(proposals.values()) | {
        test.additions(base, rule, i) for i in shortlist for rule in ("longest", "connectivity")
    }
    start_options = [trial for trial in candidates if test.valid(trial)]
    if not start_options:
        raise ValueError(f"No feasible addition repair within the recorded shortlist. {dict(test.counts)}")
    def score(trial):
        return (sum(test.angular_costs(trial))/len(test.pairs), len(trial),
                sum(test.lines[i].length for i in sorted(trial)), tuple(sorted(trial)))
    choices = {"longest-additions": proposals["longest"], "connectivity-additions": proposals["connectivity"],
               "route-aware-additions": min(start_options,key=score)}
    attempted = len(candidates)
    added = choices["route-aware-additions"]
    # Try dropping one or two existing lines, with replacements held in the repaired set.
    eligible = sorted(base,key=lambda i:(test.lines[i].length,test.geometry_key(i)))[:parameters["swap_window"]]
    substitutions = set()
    for size in (1,2):
        for group in combinations(eligible,size):
            attempt = added - set(group)
            if test.valid(attempt):
                substitutions.add(attempt)
    if substitutions:
        choices["bounded-substitution"] = min(substitutions,key=lambda s:(len(s),score(s)))

    reduced = {}
    unique_seeds = {choices.get("bounded-substitution", choices["route-aware-additions"])}
    for seed in sorted(unique_seeds,key=lambda s:(len(s),sorted(s))):
        for priority in ("shortest","longest","lowest-connectivity"):
            final, trace = test.backward(seed,priority)
            reduced[f"backward-{len(reduced)+1}"] = {"selected": final, "order": priority,
                                                       "seed": sorted(seed),"trace":trace}
            print(parameters["case"], parameters["start"], priority, len(final), flush=True)
        print(parameters["case"],parameters["start"],"completed backward seed",len(seed),flush=True)
    results = {}
    cached_reports = {}
    for name, selected, extra in [(k,v,{}) for k,v in choices.items()] + [
        (k,v["selected"], {x:v[x] for x in ("order","seed","trace")}) for k,v in reduced.items()
    ]:
        if test.valid(selected):
            if selected not in cached_reports:
                cached_reports[selected] = test.report(selected, old)
            results[name] = cached_reports[selected] | extra
        else:
            results[name] = {"status":"invalid","line_ids":sorted(selected)}
    return StageResult({"start": parameters["start"],"missing_regions":initial_missing,
                        "unattached_doors":doors,"addition_trials":attempted,"feasible_additions":len(start_options),
                        "valid_substitutions":len(substitutions), "candidates_shortlisted":sorted(shortlist),
                        "results":results,"checks":dict(test.counts),"seconds":monotonic()-start_time})


def metric_control(inputs, parameters):
    started = monotonic()
    test = Repair(inputs, parameters)
    seed = frozenset(parameters["seed"])
    old = parameters["reference"]["maps"][parameters["start"]]["routes"]["metric"]
    if not test.valid(seed) or not all(test.metric.options(seed)):
        raise ValueError("The metric control requires a strict-valid seed with all geometric attachments.")
    results = {}
    for priority in ("shortest", "longest", "lowest-connectivity"):
        selected, trace = test.backward(seed, priority, preserve_metric=True)
        row = test.report(selected, old)
        if row["metric_statistics"]["unreachable"]:
            raise ValueError("The metric control lost geometric reachability.")
        results[priority] = row | {"order": priority, "trace": trace,
                                   "seed": sorted(seed)}
    return StageResult({"start": parameters["start"], "results": results,
                        "checks": dict(test.counts), "seconds": monotonic()-started})
