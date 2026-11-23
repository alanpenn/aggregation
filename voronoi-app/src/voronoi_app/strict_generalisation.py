"""Strict, connector-independent angular analysis for generated settlement pilots."""
from bisect import bisect_right
from collections import defaultdict
from functools import cache
from itertools import combinations
import json
from pathlib import Path
import resource
import sys
from math import hypot
from time import monotonic
from types import SimpleNamespace

import networkx as nx
from shapely import from_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union

from .angular import LineClearance
from .batch_methods import _domain, _settlement
from .batch_routing_reference import MasterNetwork, describe
from .batch_store import StageResult, atomic_write, encode
from .convex_metric_experiment import build_master_doors, worst
from .exact_enumeration import exact_pool_from_dict
from .experimental_circulation_topology import _circulation_block_witnesses
from .experimental_entrance_reduction import _ring_witnesses, entrance_seed, improve_entrance_depth, shared_faces, union_mask
from .experimental_structural_routes import distance
from .experimental_visibility import IndexedClearance
from .extreme_diagonal_experiment import membership, opposed_pairs, span
from .region_incidence_angular import angular_depth, build_incidence
from .sheaf_experiment import Experiment
from .strict_corridor_experiment import physical_profile
from .strict_coverage_experiment import compare_pairs, verify_monotone


class Geometry(Experiment):
    """Reuse the exact winding validator and its memoised face predicates."""
    def __init__(self, inputs, lines, graph, clearance):
        self.lines = lines
        self.neighbors = [set(graph[i]) for i in range(len(lines))]
        self.polygons,self.buildings,self.dyads = _settlement(inputs)
        self.blocks = inputs["topology"]["topology"]["occupied_blocks"]
        self.domain_clearance = SimpleNamespace(permits_exact=cache(clearance.permits))
        self.crossings,self.face_bounds,self.enclosure_cache = {},{},{}
        self.block_witnesses = _circulation_block_witnesses(
            self.polygons,[b for b in self.blocks if b["kind"]!="boundary"])


class RegionalNetwork(MasterNetwork):
    """Split the existing exact atomic edges at certified metric stops."""
    def __init__(self, axial, doors):
        self.lines,self.graph,self.doors = axial.lines,axial.graph,doors
        nodes = list(axial.nodes)
        self.nodes = dict(axial.nodes)
        stops = defaultdict(set)
        for door in doors:
            for i,p in door["connectors"]:
                if p not in self.nodes:
                    stops[i].add(p)
        splits = defaultdict(set)
        for i,points in sorted(stops.items()):
            edges = axial.edges_by_line[i]
            starts = [nodes[axial.edges[e][0]] for e in edges]
            for p in points:
                index = bisect_right(starts,p)-1
                if index<0:
                    raise ValueError("A certified metric stop precedes its line.")
                edge = edges[index]
                a,b,_,_,_ = axial.edges[edge]
                if not nodes[a]<p<nodes[b]:
                    raise ValueError("A certified metric stop leaves its atomic edge.")
                splits[edge].add(p)
        self.edges = []
        self.edges_by_line = [[] for _ in self.lines]
        for i,(a,b,length,vector,owners) in enumerate(axial.edges):
            intermediates = sorted(splits.get(i,()))
            segment = [a]
            for p in intermediates:
                if p not in self.nodes:
                    self.nodes[p] = len(nodes)
                    nodes.append(p)
                segment.append(self.nodes[p])
            segment.append(b)
            for j,k in zip(segment,segment[1:]):
                index=len(self.edges)
                self.edges.append((j,k,distance(nodes[j],nodes[k]) if intermediates else length,vector,owners))
                for owner in owners:
                    self.edges_by_line[owner].append(index)


def extract_doors(inputs, clearance, opened, polygons):
    doors, excluded = [], []
    for open_cell, building in inputs["settlement"]["doors"]:
        faces = shared_faces(polygons[open_cell],polygons[building]) if open_cell in opened else []
        p = tuple((a+b)/2 for a,b in zip(*faces[0],strict=True)) if len(faces)==1 else None
        identity = {"open_cell":open_cell,"building_cell":building}
        if p is not None and clearance.permits(p,p):
            doors.append(identity | {"point":list(map(str,p)),
                                     "shared_face":[list(map(str,q)) for q in faces[0]]})
        else:
            excluded.append(identity | {"reason":"outside-main-space" if open_cell not in opened else
                                        "missing-face" if not faces else "ambiguous-face" if p is None else "blocked"})
    return doors,excluded


def corridor_bands(lines, occupied):
    """Use the longest unassigned axial axes to propose banked physical bands."""
    corridors = []
    assigned = set()
    for line in sorted(lines,key=lambda x:(-x.length,x.start,x.end)):
        if line.length<20:
            break
        if line.line_id in assigned:
            continue
        axis = [tuple(map(float,p)) for p in sorted((line.start,line.end))]
        profile = physical_profile(axis,occupied)
        if profile["two_banks"]<7:
            continue
        a,b=axis
        normal=(-(b[1]-a[1])/line.length,(b[0]-a[0])/line.length)
        centres=[]
        for i,(left,right) in enumerate(profile["samples"],1):
            if left is not None and right is not None:
                t=i/10
                centres.append((t,tuple(a[k]+t*(b[k]-a[k])+(right-left)/2*normal[k]
                                         for k in range(2))))
        mean_t=sum(t for t,_ in centres)/len(centres)
        variance=sum((t-mean_t)**2 for t,_ in centres)
        slopes=[sum((t-mean_t)*p[k] for t,p in centres)/variance for k in range(2)]
        head=[sum(p[k] for _,p in centres)/len(centres)-mean_t*slopes[k] for k in range(2)]
        axis=[head,[p+d for p,d in zip(head,slopes,strict=True)]]
        length=hypot(*slopes)
        if length<20:
            continue
        profile=physical_profile(axis,occupied)
        width = profile["median_banked_width"]
        if profile["two_banks"]<7 or not width or length/width<3:
            continue
        band=max(2.5,min(5.,width/2))
        members=membership(axis,lines,band)
        if not members or any(len(members & c["members"])>.5*min(len(members),len(c["members"]))
                              for c in corridors):
            continue
        assigned.update(members)
        pairs=opposed_pairs(axis,lines,members,width=band)
        corridors.append({"axis":axis,"members":members,"length":length,"width":width,
                          "length_to_width":length/width,"profile":profile,"pairs":pairs})
    return corridors


def analyze(inputs,parameters):
    started=monotonic()
    case=inputs["settlement"]["configuration"]
    title=(case["terrain_provider"],case["seed"])
    strict_routes = parameters.get("require_metric_reachability",
                                   case["aggregation_strategy"] == "slope_preference_facewise_v1")
    opened,occupied,accessible,obstacles=_domain(inputs)
    clearance=IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    polygons,_,_=_settlement(inputs)
    doors,excluded=extract_doors(inputs,clearance,opened,polygons)
    topology=inputs["topology"]["topology"]
    holes=sum(b["kind"]!="boundary" for b in topology["occupied_blocks"])
    pool=exact_pool_from_dict(inputs["candidates"]["pool"])
    lines=pool.candidates
    regions={int(i):from_wkb(wkb) for i,wkb in inputs["candidates"]["regions_wkb"].items()}
    incident,members,checked=build_incidence(lines,regions,doors)
    saved={"doorways":doors,"doorway_regions":incident,
           "region_lines":{str(i):sorted(group) for i,group in members.items()}}
    links=[set().union(*(members[i] for i in groups)) for groups in incident]
    original={"holes":holes,"accessible_holes":len(topology["circulation_holes"]),
              "main_open_cells":len(opened),"excluded_open_cells":topology["excluded_open_cells"],
              "candidates":len(lines),"regions":len(regions),"doorways":doors,"excluded_doors":excluded,
              "incidence":saved,"checked_door_regions":checked}
    failures=[]
    if len(doors)<2: failures.append("fewer than two eligible doors")
    if any(not group for group in links): failures.append("unattached full-pool doorway")
    if any(not group for group in members.values()): failures.append("missing full-pool strict coverage")
    if any(not clearance.permits(line.start,line.end) for line in lines): failures.append("independent line clearance")
    axial=MasterNetwork(lines,[])
    graph=axial.graph
    if not nx.is_connected(graph): failures.append("full-pool axial graph disconnected")
    geometry=Geometry(inputs,lines,graph,clearance)
    master=frozenset(graph)
    witnesses=frozenset(pool.ring_candidates)
    ring_certificate=geometry.geometry(witnesses)
    proof="exact ring-seed subset"
    if not ring_certificate["circulation_constraints_satisfied"] and not failures:
        ring_certificate=geometry.geometry(master,witness=True)
        proof="full exact face evaluation"
        if ring_certificate["circulation_constraints_satisfied"]:
            witnesses=frozenset(_ring_witnesses(lines,ring_certificate,polygons))
    if not ring_certificate["circulation_constraints_satisfied"]:
        failures.append("full winding rank could not be established")
    if failures:
        rejected_pool = {"status": "invalid", "reason": "; ".join(failures),
                         "line_ids": sorted(master), "line_count": len(lines),
                         "length": sum(line.length for line in lines),
                         "intersections": graph.number_of_edges(),
                         "constraints": {"components": nx.number_connected_components(graph),
                                         "missing_regions": [i for i, group in members.items() if not group],
                                         "required_rank": holes,
                                         "rank": ring_certificate["independent_circulation_rank"]}}
        return StageResult(original | {"failure_reasons":failures,"maps":{"full_pool": rejected_pool},
                                      "seconds":monotonic()-started},valid=False)
    print(*title,"qualified full pool",len(lines),holes,flush=True)
    # Independently confirm the certified axial endpoints of all full-pool transitions.
    from .angular import _on_segment
    nodes=list(axial.nodes)
    for a,b,_,_,owners in axial.edges:
        if any(not _on_segment(nodes[a],lines[i].start,lines[i].end) or
               not _on_segment(nodes[b],lines[i].start,lines[i].end) for i in owners):
            raise ValueError("An atomic transition left its certified interval.")
    connector_started = monotonic()
    metric_doors,evidence,rejected=build_master_doors(lines,saved,regions,clearance)
    metric_graph=RegionalNetwork(axial,metric_doors)
    pairs=list(combinations(range(len(doors)),2))
    reference_path = Path(parameters["reference_path"]) if "reference_path" in parameters else None
    identity = {"candidate_record": parameters.get("candidate_record"), "doorways": doors,
                "pairs": [list(pair) for pair in pairs]}
    connector_seconds = monotonic() - connector_started
    reference_started = monotonic()
    if reference_path is not None and reference_path.exists():
        reference = json.loads(reference_path.read_bytes())
        if reference["identity"] != identity:
            raise ValueError("Saved route reference does not match candidate and doorway identity.")
        full_angular, full_metric = reference["angular"], reference["metric"]
        reference_seconds = reference.get("routing_seconds")
    else:
        full_angular,status=angular_depth(axial,master,links,pairs)
        if not strict_routes and any(value != "reachable" for value in status):
            raise ValueError("The validated full-pool angular graph failed reachability.")
        full_metric=metric_graph.route(master,False)
        reference_seconds = monotonic() - reference_started
        if reference_path is not None:
            atomic_write(reference_path, encode({"identity": identity, "angular": full_angular,
                                                "metric": full_metric, "routing_seconds": reference_seconds}))
    print(*title,"full routes",len(pairs),"metric unreachable",full_metric.count(None),flush=True)
    cover=[0]*len(lines)
    for i, group in members.items():
        for j in group: cover[j] |= 1<<i
    target=sum(1<<i for i in regions)
    door_labels=[inputs["settlement"]["building_labels"][str(d["building_cell"])] for d in doors]
    full_routing={"angular":full_angular,"metric":full_metric}
    stats={k:describe(v) for k,v in full_routing.items()}

    @cache
    def structural(chosen):
        missing=target & ~union_mask(cover,chosen)
        omitted=[i for i, group in enumerate(links) if not chosen & group]
        components=nx.number_connected_components(graph.subgraph(chosen))
        if missing or omitted or components!=1:
            return {"valid":False,"missing_regions":[i for i in regions if missing & (1<<i)],
                    "unattached_doors":omitted,"components":components}
        topo=geometry.geometry(chosen) if chosen!=master else ring_certificate
        return {"valid":topo["circulation_constraints_satisfied"] and
                not topo["lines_crossing_effective_occupied_space"],
                "missing_regions":[],"unattached_doors":[],"components":components,
                "rank":topo["independent_circulation_rank"],"required_rank":holes,
                "missing_rings":topo["missing_axial_rings"],
                "clearance_rejections":topo["lines_crossing_effective_occupied_space"]}

    @cache
    def evaluate(chosen):
        evaluation_started = monotonic()
        validated=structural(chosen)
        value={"status":"valid" if validated["valid"] else "invalid","constraints":validated,
               "line_ids":sorted(chosen),"line_count":len(chosen),
               "length":sum(lines[i].length for i in sorted(chosen))}
        if strict_routes:
            value["intersections"] = graph.subgraph(chosen).number_of_edges()
            value["mean_connectivity"] = 2 * value["intersections"] / len(chosen) if chosen else 0.0
        if not validated["valid"]:
            if strict_routes:
                value.update(reason="Failed structural validation.",
                             evaluation_seconds=monotonic() - evaluation_started)
            return value
        routing_started = monotonic()
        if chosen==master:
            routes=full_routing
        else:
            angular,status=angular_depth(axial,chosen,[link & chosen for link in links],pairs)
            if not strict_routes and any(s!="reachable" for s in status):
                raise ValueError("A strict map failed angular reachability.")
            routes={"angular":angular,"metric":metric_graph.route(chosen,False)}
        routing_seconds = monotonic() - routing_started if chosen != master else reference_seconds
        comparisons={}
        for k, values in routes.items():
            verify_monotone(full_routing[k],values)
            ratios=[(b-a)/a for a,b in zip(full_routing[k],values,strict=True) if a and b is not None]
            changes = [abs(b-a) for a,b in zip(full_routing[k],values,strict=True)
                       if a is not None and b is not None]
            comparisons[k]={"cost":describe(values),
                            "absolute":describe(changes) if strict_routes else compare_pairs(full_routing[k],values),
                            "proportional":describe(ratios)}
        if strict_routes:
            unreachable = {key: sum(item is None for item in costs) for key, costs in routes.items()}
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            value.update(evaluation_seconds=monotonic() - evaluation_started, unreachable_pairs=unreachable,
                         routing_seconds=routing_seconds,
                         evaluation_peak_rss_mib=peak/(1024**2 if sys.platform == "darwin" else 1024))
            if any(unreachable.values()):
                value.update(status="invalid", reason="Incomplete doorway route reachability.")
        return value | {"routes":routes,"routing":comparisons,
                        "metric_unattached_doors":[i for i,x in enumerate(metric_graph.options(chosen)) if not x]}

    # The seed uses exact ring-boundary supports. If they fail, start reduction from the proven pool.
    guided_started = monotonic()
    compact,door_masks=entrance_seed(graph,links,witnesses,cover,target)
    guided,trail=improve_entrance_depth(graph,lines,links,door_masks,compact,len(compact)+8)
    guided=frozenset(guided)
    guided_seconds = monotonic() - guided_started
    maps={"full_pool":evaluate(master) | {"selection_seconds": 0.0},
          "strict_entrance_guided":evaluate(guided) | {"selection_seconds": guided_seconds}}
    # If line arrangement changes lose complete winding, retain that failed guided result
    # and use the certified full pool only when sized for the bounded deletion search.
    if not maps["strict_entrance_guided"]["constraints"]["valid"]:
        return StageResult(original | {"maps":maps,"pairs":pairs,"metric_connector_rejections":rejected,
                                      "circulation_proof":proof,"seconds":monotonic()-started},valid=False)
    backward_started = monotonic()
    order=sorted(guided,key=lambda i:(lines[i].length,lines[i].start,lines[i].end))
    selected=guided
    trace=[]
    while True:
        n=len(selected)
        for i in order:
            if i in selected and structural(selected-{i})["valid"]:
                selected=selected-{i}
                trace.append(i)
        if len(selected)==n: break
    backward_seconds = monotonic() - backward_started
    maps["strict_backward"]=evaluate(selected) | {"selection_seconds": backward_seconds}
    base=evaluate(selected)
    print(*title,"selection",len(guided),len(selected),flush=True)
    corridor_started = monotonic()
    corridors=corridor_bands(lines,obstacles)
    tested={"geometric_extreme":[],"route_ranked":[]}
    details=[]
    for corridor in corridors:
        pairs_in_band=corridor["pairs"]
        member_set=corridor["members"]
        exterior=selected-member_set
        transverse=set()
        for i in exterior:
            (x0,y0),(x1,y1),_=span(corridor["axis"],lines[i])
            if abs(y1-y0)>.65*abs(x1-x0):transverse.add(i)

        def contacts(line_ids):
            return set().union(*(set(graph[i]) & transverse for i in line_ids))
        old_contacts=contacts(selected & member_set)
        attempts=[]
        for pair in pairs_in_band[:8]:
            trial=evaluate(exterior | set(pair))
            current=contacts(pair)
            row=trial | {"pair":list(pair),"lost_transverse":sorted(old_contacts-current),
                         "gained_transverse":sorted(current-old_contacts)}
            if trial["status"]=="valid":
                row["worst_changes"]={k:worst(pairs,base["routes"][k],trial["routes"][k],door_labels)
                                      for k in ("angular","metric")}
            attempts.append(row)
        valid=[x for x in attempts if x["status"]=="valid"]
        best=min(valid,key=lambda r:(r["routing"]["angular"]["cost"]["mean"],r["length"],r["pair"])) if valid else None
        details.append({k:v for k,v in corridor.items() if k not in ("members","pairs")} |
                       {"members":sorted(member_set),"qualifying_pairs":len(pairs_in_band),
                        "selected_members":sorted(selected&member_set),"extreme":attempts[0] if attempts else None,
                        "best_ranked":best,"trials":[{k:v for k,v in x.items() if k!="routes"} for x in attempts]})
        if attempts: tested["geometric_extreme"].append(attempts[0])
        if attempts: tested["route_ranked"].append(best or attempts[0])
    for method, entries in tested.items():
        valid=[row for row in entries if row["status"]=="valid"]
        maps[method]=min(valid,key=lambda r:(r["line_count"],r["routing"]["angular"]["cost"]["mean"],
                                            r["length"],r["pair"])) if valid else {
            "status":"invalid" if entries else "unsupported",
            "reason":"no feasible pair" if entries else "no qualifying opposed pair"}
    if strict_routes:
        for method, entries in tested.items():
            if maps[method]["status"] == "invalid" and entries:
                maps[method]["attempted_line_ids"] = entries[0]["line_ids"]
    return StageResult(original | {"maps":maps,"pairs":pairs,"corridors":details,"deletion_trace":trace,
                                  "entrance_growth":trail,"circulation_proof":proof,
                                  "connector_seconds": connector_seconds, "shared_corridor_seconds": monotonic() - corridor_started,
                                  "metric_connector_rejections":rejected,"metric_connectors":evidence,
                                  "full_pair_counts":{k:d["reachable"] for k,d in stats.items()},
                                  "seconds":monotonic()-started})


def screen_physical_bands(inputs,parameters):
    """Distinguish centreline proposals from physically supported straight bands."""
    polygons,buildings,_ = _settlement(inputs)
    frontages=unary_union([polygons[i] for i in sorted(buildings)])
    occupied=from_wkb(inputs["topology"]["occupied_wkb"])
    rows=[]
    for axis in parameters["axes"]:
        start,end=axis
        spine=LineString([tuple(p+t*(q-p) for p,q in zip(start,end,strict=True)) for t in (.1,.9)])
        crosses=occupied.relate_pattern(spine,"T********")
        banks=physical_profile(axis,frontages)
        rows.append({"accepted":not crosses and banks["two_banks"]>=7,
                     "crosses_occupied_interior":crosses,
                     "building_banked_sections":banks["two_banks"],
                     "median_building_width":banks["median_banked_width"]})
    winners={}
    for method,options in parameters["options"].items():
        choices=[i for i,value in enumerate(options,1) if value is not None and rows[i-1]["accepted"]]
        winners[method]=min(choices,key=lambda i:options[i-1]) if choices else None
    return StageResult({"bands":rows,"winners":winners})
