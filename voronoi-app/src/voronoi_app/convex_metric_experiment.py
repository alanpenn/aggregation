"""Batch-only convex-region metric attachments and joint corridor exchanges."""
from fractions import Fraction
from itertools import product
from time import monotonic

from shapely import from_wkb

from .angular import LineClearance, _cross, _direction, _exact_point, _on_segment, _ring_location
from .batch_methods import _domain
from .batch_routing_reference import MasterNetwork, describe, point
from .batch_store import StageResult
from .experimental_visibility import IndexedClearance
from .extreme_diagonal_experiment import span
from .region_incidence_angular import halfplanes, positive_interior
from .strict_corridor_experiment import CorridorStudy
from .strict_coverage_experiment import compare_pairs, verify_monotone


def clip_interval(a, b, planes):
    """Exact closed convex clipping, rejecting boundary-only intervals."""
    d = _direction(a,b)
    low, high = Fraction(0), Fraction(1)
    for p, inward in planes:
        offset = _cross(inward,_direction(p,a))
        rate = _cross(inward,d)
        if not rate:
            if offset <= 0:
                return None
        elif rate > 0:
            low = max(low,-offset/rate)
        else:
            high = min(high,-offset/rate)
        if low >= high:
            return None
    return low,high


def connector_points(origin, line, planes):
    """Include the clamped perpendicular and both exact regional exit points."""
    a,b = line.start,line.end
    limits = clip_interval(a,b,planes)
    if limits is None:
        raise ValueError("Certified line-region traversal has empty exact clipping.")
    low,high = limits
    direction = _direction(a,b)
    norm = sum(x*x for x in direction)
    projection = sum(x*y for x,y in zip(_direction(a,origin),direction,strict=True))/norm
    nearest = max(low,min(high,projection))
    return [(tuple(x+t*d for x,d in zip(a,direction,strict=True)),
             "nearest" if t==nearest else "region_boundary") for t in sorted({low,high,nearest})]


def build_master_doors(lines, saved, regions, clearance, *, exact_rings=None):
    rings = exact_rings if exact_rings is not None else {
        i:list(map(_exact_point,r.exterior.coords)) for i,r in regions.items()}
    planes = {i:halfplanes(ring) for i,ring in rings.items()}
    checked = set()
    doors, evidence, failures = [], [], []
    for number,(door,incident) in enumerate(zip(saved["doorways"],saved["doorway_regions"],strict=True)):
        origin = point(door["point"])
        options, details = set(), []
        for region in incident:
            ring = rings[region]
            if _ring_location(ring,origin)<0:
                raise ValueError(f"Door {number} is outside certified region {region}.")
            for i in saved["region_lines"][str(region)]:
                line = lines[i]
                if (i,region) not in checked:
                    if not positive_interior(line.start,line.end,planes[region]):
                        raise ValueError(f"Boundary-only incidence {i}/{region}.")
                    checked.add((i,region))
                valid = False
                for stop, kind in connector_points(origin,line,planes[region]):
                    if not _on_segment(stop,line.start,line.end) or _ring_location(ring,stop)<0:
                        raise ValueError(f"Connector endpoint outside certified interval {i}/{region}.")
                    if not clearance.permits(origin,stop):
                        failures.append({"door":number,"region":region,"line":i,"point":list(map(str,stop)),
                                         "reason":"connector fails independent accessible-space clearance"})
                        continue
                    valid = True
                    options.add((i,stop))
                    details.append({"line":i,"region":region,"point":list(map(str,stop)),"kind":kind,
                                    "length":float(sum((a-b)**2 for a,b in zip(origin,stop,strict=True)))**.5})
                if not valid:
                    failures.append({"door":number,"region":region,"line":i,"reason":"no certified attachment point"})
        doors.append(door | {"point":origin,"connectors":sorted(options)})
        evidence.append(details)
    return doors,evidence,failures


def combine(base, bands, choices):
    """Apply corridor choices simultaneously so overlaps are handled as sets."""
    removed = set().union(*(band for band, choice in zip(bands,choices,strict=True) if choice is not None))
    added = set().union(*(choice for choice in choices if choice is not None))
    return frozenset((base-removed)|added)


def metric_network(lines, doors):
    # Noding depends on stop coordinates; ownership and doorway options remain per door.
    stops = sorted({stop for door in doors for _,stop in door["connectors"]})
    network = MasterNetwork(lines,[{"connectors":[(None,stop) for stop in stops]}])
    network.doors = doors
    return network


def worst(pairs, before, after, labels):
    changes = sorted(((b-a,i,j) for (i,j),a,b in zip(pairs,before,after,strict=True)
                      if a is not None and b is not None and b>a+1e-9),
                     key=lambda r:(-r[0],r[1:]))
    return [{"buildings":[labels[i],labels[j]],"doors":[i,j],"increase":v} for v,i,j in changes[:5]]


def run(inputs, parameters):
    started = monotonic()
    study = CorridorStudy(inputs,parameters)
    engine = study.engine
    saved = parameters["incidence"]
    regions = {int(i):from_wkb(wkb) for i,wkb in inputs["candidates"]["regions_wkb"].items()}
    _,obstacles,accessible,occupied = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible,occupied,original_obstacles=obstacles.values()))
    doors,evidence,connector_failures = build_master_doors(engine.lines,saved,regions,clearance)
    print(parameters["case"],"certified convex connectors",sum(len(d["connectors"]) for d in doors),flush=True)
    network = metric_network(engine.lines,doors)
    master = frozenset(range(len(engine.lines)))
    full_metric = network.route(master,False)
    full_cost = {"angular":describe(study.full)["mean"],"metric":describe(full_metric)["mean"]}
    cache = {master:full_metric}
    labels = [study.labels[str(d["building_cell"])] for d in doors]
    print(parameters["case"],"full-pool metric depths",len(full_metric),flush=True)

    def metric(chosen):
        if chosen not in cache:
            cache[chosen] = network.route(chosen,False)
            verify_monotone(full_metric,cache[chosen])
        return cache[chosen]

    def row(chosen, angles, before=None):
        values = metric(chosen)
        result = {"line_ids":sorted(chosen),"line_count":len(chosen),
                  "length":sum(engine.lines[i].length for i in sorted(chosen)),
                  "metric":values,"metric_statistics":describe(values),
                  "metric_excess":compare_pairs(full_metric,values),
                  "unattached_metric_doors":[i for i,o in enumerate(network.options(chosen)) if not o],
                  "angular":angles,"angular_statistics":describe(angles),
                  "angular_excess":compare_pairs(study.full,angles)}
        if before is not None:
            result["worst_angular_pairs"] = worst(engine.pairs,before["angular"],angles,labels)
            result["worst_metric_pairs"] = worst(engine.pairs,before["metric"],values,labels)
        return result

    benchmark = {}
    for name, entry in parameters["benchmark"].items():
        chosen = frozenset(entry["line_ids"])
        angles = entry["angular"]
        if angles is None:
            angles = engine.angular_costs(chosen)
        result = row(chosen,angles)
        result["prior_metric_statistics"] = entry["prior_metric_statistics"]
        benchmark[name] = result
    repair_replay = []
    for failure in parameters["archived_failures"]:
        chosen = frozenset(failure["line_ids"])
        i = failure["door"]
        if engine.metric.options(chosen)[i]:
            raise ValueError("Archived fixed-connector failure did not reproduce.")
        options = network.options(chosen)[i]
        repaired_pairs = sum(metric(chosen)[j] is not None for j,pair in enumerate(engine.pairs) if i in pair)
        repair_replay.append({k:v for k,v in failure.items() if k!="line_ids"} |
                             {"new_attachment_count":len(options),"reachable_pairs_for_door":repaired_pairs,
                              "remaining_failure":not options})
    print(parameters["case"],"benchmark and failure replay finished",flush=True)

    combined = {}
    for name, bands in parameters["corridor_results"].items():
        base = frozenset(parameters["strict_maps"][name]["line_ids"])
        original = row(base,engine.angular_costs(base))
        sheaves = [frozenset(b["members"]) for b in bands]
        methods = ("extreme","route_opposed","route_opposed_combined")
        options = []
        named = {"original":base}
        for b in bands:
            options.append([None,*sorted({tuple(b["variants"][m]["members"]) for m in methods
                                         if b["variants"].get(m,{}).get("status")=="valid"})])
        for method in methods:
            chosen = [b["variants"].get(method,{}) for b in bands]
            named[method] = combine(base,sheaves,[set(v["members"]) if v.get("status")=="valid" else None for v in chosen])
        trial_maps = {}
        for choices in product(*options):
            selection = combine(base,sheaves,[set(c) if c is not None else None for c in choices])
            trial_maps.setdefault(selection,choices)

        evaluated = {}
        results = {}
        for chosen in sorted(trial_maps,key=lambda x:(len(x),sorted(x))):
            if not study.feasible(chosen):
                continue
            value = row(chosen,engine.angular_costs(chosen),original)
            value["constraints"] = study.check(chosen)
            value["band_choices"] = trial_maps[chosen]
            contacts = []
            exterior = base-set().union(*sheaves)
            for b,band in zip(bands,sheaves,strict=True):
                axis = b["axis"]
                transverse=set()
                for i in exterior:
                    (x0,y0),(x1,y1),_=span(axis,engine.lines[i])
                    if abs(y1-y0)>.65*abs(x1-x0): transverse.add(i)
                def touched(chosen):
                    return {j for i in chosen & band for j in engine.graph[i] if j in transverse}
                old,new=touched(base),touched(chosen)
                contacts.append({"lost":sorted(old-new),"gained":sorted(new-old)})
            value["transverse"] = contacts
            evaluated[chosen] = value
        for tag, chosen in named.items():
            results[tag] = evaluated.get(chosen,{"line_ids":sorted(chosen),"constraints":study.check(chosen),"status":"invalid"})
        def key(v):
            return (v["line_count"],v["angular_statistics"]["mean"]/full_cost["angular"]+
                    v["metric_statistics"]["mean"]/full_cost["metric"],v["length"],v["line_ids"])
        feasible = [v for v in evaluated.values() if not v["metric_statistics"]["unreachable"]]
        results["joint_economy"] = min(feasible,key=key) if feasible else {"status":"unavailable"}
        results["joint_best_routes"] = min(feasible,key=lambda v:key(v)[1:]) if feasible else {"status":"unavailable"}
        combined[name] = {"proposals":len(trial_maps),"valid":len(evaluated),"results":results,
                          "all_valid":[{k:v[k] for k in ("line_ids","line_count","length","angular_statistics",
                                        "metric_statistics","band_choices","transverse")} for v in evaluated.values()]}
        print(parameters["case"],name,"joint maps",len(trial_maps),len(evaluated),flush=True)
    return StageResult({"doorways":saved["doorways"],"connector_evidence":evidence,
                        "geometry_rejections":connector_failures,"failure_replay":repair_replay,
                        "benchmark":benchmark,"joint":combined,
                        "full_metric_statistics":describe(full_metric),"seconds":monotonic()-started})
