"""Strict-incidence reassessment of geometric corridor representatives."""

from itertools import combinations
from math import hypot
from statistics import median
from time import monotonic

import networkx as nx
from shapely import from_wkb
from shapely.geometry import LineString, Point

from .angular import LineClearance, _direction, _exact_point, _intersections, _ring_location
from .batch_methods import _domain
from .batch_routing_reference import describe, point
from .batch_store import StageResult
from .exact_enumeration import exact_pool_from_dict
from .experimental_entrance_reduction import fixed_terminal_attachments
from .extreme_diagonal_experiment import membership, opposed_pairs, span
from .strict_coverage_experiment import Repair, compare_pairs, omissions


def physical_profile(axis, occupied, radius=12):
    """Sample both banks of a previously proposed corridor axis."""
    a, b = axis
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = hypot(dx, dy)
    u, v = -dy/length, dx/length
    samples = []
    for i in range(1, 10):
        t = i/10
        x, y = a[0]+t*dx, a[1]+t*dy
        banks = []
        for sign in (-1, 1):
            ray = LineString([(x,y), (x+sign*radius*u,y+sign*radius*v)])
            contact = ray.intersection(occupied)
            banks.append(None if contact.is_empty else Point(x,y).distance(contact))
        samples.append(banks)
    widths = [sum(banks) for banks in samples if None not in banks]
    if len(widths) >= 7:
        classification = "mostly-two-sided"
    elif len(widths) >= 4:
        classification = "mixed-corridor-and-open-space"
    else:
        classification = "weakly-banked-geometric-band"
    return {"classification":classification, "samples":samples, "two_banks":len(widths),
            "median_banked_width":median(widths) if widths else None, "bank_search_radius":radius}


def interior_witness(line, ring):
    """Return a rational point strictly inside a traversed convex region."""
    a, b = line.start, line.end
    dx, dy = _direction(a,b)
    axis = 0 if dx else 1
    points = {a,b}
    for p,q in zip(ring,ring[1:]):
        points.update(_intersections(a,b,p,q))
    ordered = sorted(points, key=lambda p:p[axis])
    for p,q in zip(ordered,ordered[1:]):
        middle = tuple((s+t)/2 for s,t in zip(p,q,strict=True))
        if _ring_location(ring,middle) == 1:
            return middle
    raise ValueError("Strict incidence has no interior witness.")


class CorridorStudy:
    def __init__(self, inputs, parameters):
        self.engine = Repair(inputs, parameters | {"start":"A"})
        self.settings = parameters
        self.geometry = {}
        self.metric_cache = {}
        regions = inputs["candidates"]["regions_wkb"]
        self.rings = {int(i):list(map(_exact_point,from_wkb(wkb).exterior.coords))
                      for i,wkb in regions.items()}
        self.clearance = self.engine.exp.domain_clearance
        self.labels = inputs["settlement"]["building_labels"]
        self.saved = parameters["incidence"]
        self.full = self.saved["maps"]["full"]["angular"]
        self.metric_sets = [set(i for i,_ in d["connectors"]) for d in self.engine.metric_doors]

    def preliminary(self, selected):
        engine = self.engine
        missing, unattached = omissions(selected, engine.regions, engine.doors)
        components = nx.number_connected_components(engine.graph.subgraph(selected))
        return missing, unattached, components

    def check(self, chosen):
        if chosen not in self.geometry:
            engine = self.engine
            missing, unattached, components = self.preliminary(chosen)
            topo = engine.exp.geometry({engine.ids[i] for i in chosen})
            rejected = sorted(engine.exp.original_ids[i] for i in topo["lines_crossing_effective_occupied_space"])
            self.geometry[chosen] = {
                "missing_regions":missing, "unattached_doors":unattached, "components":components,
                "winding_rank":topo["independent_circulation_rank"],
                "required_rank":topo["required_circulation_rank"],
                "missing_rings":topo["missing_axial_rings"], "clearance_rejections":rejected,
                "valid":not missing and not unattached and components==1 and
                topo["circulation_constraints_satisfied"] and not rejected,
            }
        return self.geometry[chosen]

    def feasible(self, chosen):
        missing, unattached, components = self.preliminary(chosen)
        return not missing and not unattached and components==1 and self.check(chosen)["valid"]

    def metric_attached(self, chosen):
        return all(chosen & group for group in self.metric_sets)

    def metric(self, chosen):
        if chosen not in self.metric_cache:
            engine = self.engine
            costs = engine.metric.route(chosen, angular=False)
            lost = [i for i,group in enumerate(self.metric_sets) if not chosen & group]
            witnesses = []
            for i in lost:
                door = self.saved["doorways"][i]
                origin = point(door["point"])
                witness = None
                for region in self.saved["doorway_regions"][i]:
                    for line in sorted(engine.regions[region] & chosen):
                        end = interior_witness(engine.lines[line],self.rings[region])
                        if self.clearance.permits_exact(origin,end):
                            witness = {"line":line,"region":region,"point":list(map(str,end))}
                            break
                    if witness:
                        break
                witnesses.append({"door":i,"building":self.labels[str(door["building_cell"])],
                                  "certified_visible_interior_witness":witness})
            self.metric_cache[chosen] = {"routes":costs,"statistics":describe(costs),
                                         "unattached_doors":lost,"alternative_witnesses":witnesses}
        return self.metric_cache[chosen]

    def rank(self, selected):
        costs = self.engine.angular_costs(selected)
        return (sum(costs)/len(costs), sum(self.engine.lines[i].length for i in sorted(selected)),
                tuple(sorted(selected)))

    def run_corridor(self, base, original_record, descriptor):
        engine = self.engine
        axis, band = descriptor["axis"], descriptor["half_band"]
        members = membership(axis,engine.lines,band)
        if members != frozenset(descriptor["members"]):
            raise ValueError("Archived geometric band did not reproduce.")
        pairs = opposed_pairs(axis,engine.lines,members,width=band)
        initial = base & members
        exterior = base-members
        transverse = set()
        for i in exterior:
            (x0,y0),(x1,y1),_ = span(axis,engine.lines[i])
            if abs(y1-y0)>.65*abs(x1-x0):
                transverse.add(i)

        def contacts(selected):
            return sorted({j for i in selected-exterior for j in engine.graph[i] if j in transverse})

        before = set(contacts(base))
        old_angular = original_record["angular"]
        old_metric = original_record["metric"]
        if engine.angular_costs(base) != old_angular:
            raise ValueError("Archived strict-map angles did not reproduce.")

        def row(selected):
            if selected is None:
                return {"status":"unavailable"}
            check = self.check(selected)
            contact = contacts(selected)
            out = {"status":"valid" if check["valid"] else "invalid", "constraints":check,
                   "line_ids":sorted(selected),"members":sorted(selected-exterior),
                   "additional_outside_band":sorted((selected-exterior)-members),
                   "line_count":len(selected), "length":sum(engine.lines[i].length for i in sorted(selected)),
                   "transverse_contacts":contact, "lost_transverse_contacts":sorted(before-set(contact)),
                   "gained_transverse_contacts":sorted(set(contact)-before)}
            if not check["valid"]:
                return out
            depths = engine.angular_costs(selected)
            changes = sorted(((b-a,i,j) for (i,j),a,b in zip(engine.pairs,old_angular,depths,strict=True)),
                             key=lambda item:(-item[0],item[1:]))
            worst = [{"increase":d,"doors":[i,j],"buildings":[self.labels[str(self.saved["doorways"][k]["building_cell"])]
                      for k in (i,j)]} for d,i,j in changes[:5] if d>1e-9]
            metric = self.metric(selected)
            out.update(angular=depths, angular_statistics=describe(depths), angular_excess=compare_pairs(self.full,depths),
                       angular_change=compare_pairs(old_angular,depths), worst_angular_pairs=worst,
                       metric=metric, metric_change=compare_pairs(old_metric,metric["routes"]),
                       newly_unreachable_metric=sum(a is not None and b is None
                                                   for a,b in zip(old_metric,metric["routes"],strict=True)))
            return out

        original = row(base)
        if original["metric"]["routes"] != old_metric:
            raise ValueError("Archived geometric metric routes did not reproduce.")
        if not pairs:
            return {"variants":{"original":original,"extreme":{"status":"unavailable"},
                                "route_opposed":{"status":"unavailable"}}, "opposed_pairs":0,
                    "axis":axis,"band":band,"members":sorted(members),"selected_members":sorted(initial)}
        extreme = exterior | set(pairs[0])
        variants = {"original":original,"extreme":row(extreme)}
        valid_pairs = []
        for pair in pairs:
            chosen = exterior | set(pair)
            if self.feasible(chosen):
                valid_pairs.append(frozenset(chosen))
        combined_pairs = [trial for trial in valid_pairs if self.metric_attached(trial)]
        variants["route_opposed"] = row(min(valid_pairs,key=self.rank) if valid_pairs else None)
        variants["route_opposed_combined"] = row(min(combined_pairs,key=self.rank) if combined_pairs else None)

        # Restore required regions, corridor links and saved metric options around the extreme pair.
        missing, _, _ = self.preliminary(extreme)
        options = set(initial)-extreme
        for i in missing:
            group = engine.regions[i]-extreme
            options.update(sorted(group,key=lambda n:engine.rank(n,extreme,"connectivity"))[:3])
        for group in self.metric_sets:
            if not extreme & group:
                options.update(sorted(group-extreme,key=lambda n:engine.rank(n,extreme,"connectivity"))[:1])
        before_metrics = [group for group in self.metric_sets if not extreme & group]
        def repair_priority(i):
            return (i not in initial, -sum(i in engine.regions[j] for j in missing),
                    -len(set(engine.graph[i])&transverse), -sum(i in g for g in before_metrics),
                    engine.rank(i,extreme,"connectivity"))
        length = self.settings["repair_candidates"]
        options = sorted(options,key=repair_priority)[:length]
        can_complete_metric = self.metric_attached(extreme | set(options))
        feasible, combined, tested = [], [], 0
        for n in range(self.settings["repair_depth"]+1):
            for extra in combinations(options,n):
                trial = frozenset(extreme | set(extra))
                tested += 1
                angular_needed = not feasible or len(trial)==len(feasible[0])
                metric_complete = can_complete_metric and self.metric_attached(trial)
                if not angular_needed and not metric_complete:
                    continue
                if self.feasible(trial):
                    if angular_needed:
                        feasible.append(trial)
                    if metric_complete:
                        combined.append(trial)
            if feasible and (combined or not can_complete_metric):
                break
        fallback = frozenset(extreme|initial)
        if not feasible and self.feasible(fallback):
            feasible.append(fallback)
        if not combined and self.feasible(fallback) and self.metric_attached(fallback):
            combined.append(fallback)
        variants["repaired"] = row(min(feasible,key=self.rank) if feasible else None)
        variants["repaired_combined"] = row(min(combined,key=self.rank) if combined else None)
        return {"variants":variants,"opposed_pairs":len(pairs),"valid_pairs":len(valid_pairs),
                "metric_complete_pairs":len(combined_pairs),"repair_trials":tested,
                "repair_shortlist":options,"extreme_pair":list(pairs[0]),
                "axis":axis,"band":band,"members":sorted(members),"selected_members":sorted(initial)}


def reassess(inputs, parameters):
    started = monotonic()
    study = CorridorStudy(inputs,parameters)
    occupied = from_wkb(inputs["topology"]["occupied_wkb"])
    data = {}
    for name, reference in parameters["strict_maps"].items():
        base = frozenset(reference["line_ids"])
        if not study.feasible(base):
            raise ValueError(f"Saved strict reference {name} fails current checks.")
        data[name] = []
        for n, band in enumerate(parameters["corridors"],1):
            output = study.run_corridor(base,reference,band)
            output["physical_profile"] = physical_profile(band["axis"],occupied)
            data[name].append(output)
            print(parameters["case"],name,n,output["opposed_pairs"],
                  {k:(v["status"],v.get("line_count")) for k,v in output["variants"].items()},flush=True)
    return StageResult({"references":data, "seconds":monotonic()-started,
                        "angular_evaluations":len(study.engine.angular_cache),
                        "geometric_metric_evaluations":len(study.metric_cache)})


def audit_metric_protocol(inputs, parameters):
    """Distinguish the inventory cap from the nearest-point connector restriction."""
    _, occupied, accessible, union = _domain(inputs)
    clearance = LineClearance(accessible, union, original_obstacles=occupied.values())
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    labels = inputs["settlement"]["building_labels"]
    cache = {}
    output = []
    for item in parameters["selections"]:
        ids = tuple(item["line_ids"])
        selected = [lines[i] for i in ids]
        for failure in item["failures"]:
            i = failure["door"]
            if (ids,i) not in cache:
                doorway = parameters["doorways"][i]
                origin = point(doorway["point"])
                try:
                    found = fixed_terminal_attachments([origin],selected,clearance,len(selected))[0]
                except ValueError as error:
                    if str(error) != "No fixed visible attachments for sample 0":
                        raise
                    found = []
                cache[ids,i] = [[entry.line_id, list(map(str,entry.point))] for entry in found]
            uncapped = cache[ids,i]
            witness = failure["certified_visible_interior_witness"]
            output.append({"map":item["map"],"door":i,
                           "building":labels[str(parameters["doorways"][i]["building_cell"])],
                           "classification":"capped_inventory" if uncapped else
                           "nearest_point_restriction" if witness else "no_access_witness",
                           "uncapped_nearest":uncapped,"interior_witness":witness})
    return StageResult({"failures":output,"independent_projection_checks":len(cache)})
