"""Versioned experiments on preserved axial maps and fixed doorway connectors."""

from collections import Counter
from dataclasses import replace
from fractions import Fraction
from functools import cache
from itertools import combinations
from math import acos, degrees, hypot
from time import monotonic
from types import SimpleNamespace

import networkx as nx
import numpy as np
from shapely import from_wkb
from shapely.geometry import LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .angular import LineClearance, SampleAttachment, _intersections, _on_segment, _ring_location
from .batch_export import statistics
from .batch_methods import _settlement
from .batch_store import StageResult
from .exact_axial import _bounds, candidate_graph, region_coverage
from .exact_enumeration import exact_pool_from_dict
from .experimental_angular_selection import angular_reference
from .experimental_circulation_topology import (
    _circulation_block_witnesses, _ring_covers_cells, analyse_circulation_topology,
    bounded_face_rings, evaluate_circulation_lines,
)
from .experimental_entrance_reduction import entrance_depth, summary, union_mask, visibility_masks
from .experimental_structural_routes import distance, segment_network
from .experimental_visibility import _outward_bounds


DEFAULTS = {
    "minimum_line_length": 22.0,
    "maximum_angle": 21.0,
    "maximum_gap": 3.0,
    "minimum_overlap": 0.48,
    "minimum_coverage_similarity": 0.25,
    "minimum_external_similarity": 0.22,
    "complete_sheaf_size": 5,
    "large_sheaf_trials": 36,
    "sheaf_passes": 2,
    "exchange_candidates_per_sheaf": 6,
    "exchange_trials": 72,
    "maximum_exchange_removals": 3,
}
ORDERS = ("shortest", "longest", "lowest-connectivity", "marginal-external", "geometry")


def interval(line):
    return tuple(sorted((line.start, line.end)))


def bits(mask):
    while mask:
        next_bit = mask & -mask
        yield next_bit.bit_length() - 1
        mask ^= next_bit


def similarity(a, b):
    return len(a & b) / max(1, len(a | b))


def overlap(a, b):
    """Shorter-line overlap along the longer line's axis and local separation."""
    if a.length < b.length:
        a, b = b, a
    x, y = a.coords[0]
    ex, ey = a.coords[-1]
    ux, uy = (ex - x) / a.length, (ey - y) / a.length
    coordinates = [((px - x) * ux + (py - y) * uy, -(px-x) * uy + (py-y) * ux)
                   for px, py in b.coords]
    (p, h), (q, k) = sorted(coordinates)
    lo, hi = max(0.0, p), min(a.length, q)
    angle = degrees(acos(min(1.0, abs(q - p) / b.length)))
    if hi <= lo or p == q:
        return angle, 0.0, float("inf")
    offsets = [abs(h + (v-p) / (q-p) * (k-h)) for v in (lo, hi)]
    return angle, (hi-lo) / b.length, sum(offsets) / 2


def detect_sheaves(selected, segments, covers, neighbors, settings):
    long_lines = sorted(i for i in selected if segments[i].length >= settings["minimum_line_length"])
    pairs = []
    for i,j in combinations(long_lines, 2):
        angle, fraction, gap = overlap(segments[i], segments[j])
        if (angle <= settings["maximum_angle"] and fraction >= settings["minimum_overlap"]
                and gap <= settings["maximum_gap"]):
            pairs.append((i,j,angle,fraction,gap))
    spatial = nx.Graph()
    spatial.add_nodes_from(long_lines)
    spatial.add_edges_from((i,j) for i,j,*_ in pairs)
    compatible = nx.Graph()
    compatible.add_nodes_from(long_lines)
    diagnostics = {}
    for i,j,angle,fraction,gap in pairs:
        local = {i,j} | set(spatial[i]) | set(spatial[j])
        a,b = (neighbors[k] & selected - local for k in (i,j))
        external = similarity(a,b)
        coverage = similarity(set(bits(covers[i])),set(bits(covers[j])))
        if (coverage >= settings["minimum_coverage_similarity"]
                and external >= settings["minimum_external_similarity"]):
            compatible.add_edge(i,j)
            diagnostics[i,j] = [angle,fraction,gap,coverage,external]
    # Complete-link bundles avoid chaining through increasingly divergent lines.
    remaining = set(long_lines)
    groups = []
    while remaining:
        lead = min(remaining,key=lambda i:(-len(set(compatible[i])&remaining),-segments[i].length,i))
        group = {lead}
        options = set(compatible[lead]) & remaining
        while options:
            added = min(options,key=lambda i:(-len(set(compatible[i])&options),-segments[i].length,i))
            group.add(added)
            options &= set(compatible[added])
        remaining -= group
        if len(group)>1:
            groups.append(sorted(group))
    return sorted(groups,key=lambda g:(-len(g),-sum(segments[i].length for i in g),g)), diagnostics


class Experiment:
    def __init__(self, inputs, settings):
        self.settings = settings
        self.pool = exact_pool_from_dict(inputs["candidates"]["pool"])
        ordered = sorted(self.pool.candidates,key=interval)
        self.original_ids = [line.line_id for line in ordered]
        remap = {line_id:i for i,line_id in enumerate(self.original_ids)}
        self.lines = [replace(line,line_id=i,start=interval(line)[0],end=interval(line)[1])
                      for i,line in enumerate(ordered)]
        if len(set(map(interval, self.lines))) != len(self.lines):
            raise ValueError("Canonical candidate intervals must be unique.")
        self.segments = [LineString([tuple(map(float,p)) for p in interval(line)]) for line in self.lines]
        self.selected = frozenset(remap[i] for i in inputs["selection"]["line_ids"])
        self.polygons,self.buildings,self.dyads = _settlement(inputs)
        self.labels = inputs["settlement"]["building_labels"]
        self.domain = inputs["topology"]["topology"]
        self.graph = candidate_graph(self.lines)
        self.neighbors = [set(self.graph[i]) for i in range(len(self.lines))]
        regions = {int(i):from_wkb(p) for i,p in inputs["candidates"]["regions_wkb"].items()}
        self.covers = visibility_masks(self.lines,region_coverage(self.lines,regions),regions,
                                       [_bounds(line) for line in self.lines])
        self.target = sum(1<<i for i in regions)
        self.entrances = inputs["measures"]["entrances"]
        self.links = [{remap[a["line"]] for a in e["connectors"]} for e in self.entrances]
        if len(self.links)<2:
            raise ValueError("The experiment requires at least two valid saved doorway terminals.")
        self.fixed = [
            [SampleAttachment(tuple(map(Fraction,e["point"])),tuple(map(Fraction,a["point"])),
                              remap[a["line"]]) for a in sorted(e["connectors"],key=lambda a:remap[a["line"]])]
            for e in self.entrances
        ]
        self.cache = {}
        self.clearance_key = None
        self.cached_clearance = None
        self.crossings = {}
        self.face_bounds = {}
        self.enclosure_cache = {}
        if not self.domain:
            self.domain = analyse_circulation_topology(
                self.polygons, self.buildings, self.dyads, [],
            )
        open_cells = self.domain["main_open_cells"]
        occupied_cells = [self.polygons[i] for i in self.domain["effective_occupied_cells"]]
        self.domain_clearance = self.clearance_factory(
            unary_union([self.polygons[i] for i in open_cells]),
            unary_union(occupied_cells), original_obstacles=occupied_cells,
        )
        self.blocks = self.domain["occupied_blocks"]
        self.block_witnesses = _circulation_block_witnesses(
            self.polygons, [block for block in self.blocks if block["kind"] != "boundary"],
        )
        self.calls = Counter()
        self.groups,self.pair_diagnostics = detect_sheaves(
            self.selected,self.segments,self.covers,self.neighbors,self.settings,
        )

    def clearance_factory(self, accessible, occupied, *, original_obstacles):
        obstacles = tuple(original_obstacles)
        key = (accessible.wkb, occupied.wkb, tuple(p.wkb for p in obstacles))
        if key != self.clearance_key:
            clearance = LineClearance(accessible, occupied, original_obstacles=obstacles)
            self.cached_clearance = SimpleNamespace(permits_exact=cache(clearance.permits_exact))
            self.clearance_key = key
        return self.cached_clearance

    def cached_faces(self, lines):
        nodes = {line.line_id: {line.start, line.end} for line in lines}
        ids = set(nodes)
        for i in sorted(ids):
            for j in sorted(self.neighbors[i] & ids):
                if j <= i:
                    continue
                key = (i, j)
                if key not in self.crossings:
                    self.crossings[key] = _intersections(
                        *interval(self.lines[i]), *interval(self.lines[j]),
                    )
                nodes[i].update(self.crossings[key])
                nodes[j].update(self.crossings[key])
        graph = nx.Graph()
        for points in nodes.values():
            ordered = sorted(points)
            graph.add_edges_from(zip(ordered, ordered[1:]))
        return bounded_face_rings(lines, segment_graph=graph)

    def face_location(self, ring, point):
        key = id(ring)
        if key not in self.face_bounds:
            xs, ys = zip(*ring)
            self.face_bounds[key] = (min(xs), min(ys), max(xs), max(ys))
        x, y, xmax, ymax = self.face_bounds[key]
        if not (x <= point[0] <= xmax and y <= point[1] <= ymax):
            return -1
        return _ring_location(ring, point)

    def face_coverage(self, ring, cells, polygons):
        path = ring[:-1]
        start = min(range(len(path)), key=path.__getitem__)
        canonical = path[start:] + path[:start]
        key = (canonical, tuple(sorted(cells)))
        if key not in self.enclosure_cache:
            self.enclosure_cache[key] = _ring_covers_cells(ring, cells, polygons)
        return self.enclosure_cache[key]

    def geometry(self, selected, witness=False):
        self.face_bounds.clear()
        lines = [self.lines[i] for i in sorted(selected)]
        if witness:
            return analyse_circulation_topology(
                self.polygons, self.buildings, self.dyads, lines, include_witness_faces=True,
            )
        return evaluate_circulation_lines(
            self.polygons, lines, self.blocks, self.domain_clearance, face_builder=self.cached_faces,
            face_location=self.face_location, face_coverage=self.face_coverage,
            block_witnesses=self.block_witnesses,
        )

    def validate(self, selected):
        """Apply necessary filters, then the same exact full-map winding validator."""
        key=frozenset(selected)
        self.calls["proposals"]+=1
        if key in self.cache:
            self.calls["cache_hits"]+=1
            return self.cache[key]
        if union_mask(self.covers,key)!=self.target:
            result={"status":"coverage"}
        elif not key or not nx.is_connected(self.graph.subgraph(key)):
            result={"status":"connectivity"}
        elif any(not key & links for links in self.links):
            result={"status":"entrance-attachment"}
        else:
            self.calls["exact_validations"]+=1
            check=self.geometry(key)
            status=("clearance" if check["lines_crossing_effective_occupied_space"] else
                    "circulation" if not check["circulation_constraints_satisfied"] else "valid")
            result={"status":status,"rank":check["independent_circulation_rank"],
                    "required_rank":check["required_circulation_rank"]}
        self.calls[result["status"]]+=1
        self.cache[key]=result
        return result

    def witnesses(self, selected):
        topology=self.geometry(selected,True)
        ids=sorted(selected)
        tree=STRtree([_bounds(self.lines[i]) for i in ids])
        result=[]
        for cycle in topology["circulation_cycles"]:
            ring=topology["witness_faces"][cycle["face_index"]]
            support=set()
            for a,b in zip(ring,ring[1:]):
                support.update(i for k in tree.query(_outward_bounds(a,b)) for i in (ids[int(k)],)
                               if _on_segment(a,*interval(self.lines[i]))
                               and _on_segment(b,*interval(self.lines[i])))
            result.append({"blocks":cycle["enclosed_blocks"],"lines":sorted(support),
                           "ring":[list(map(str,p)) for p in ring]})
        return result

    def diagnose(self):
        selected=self.selected
        witnesses=self.witnesses(selected)
        groups=[]
        for lines in self.groups:
            group=set(lines)
            exterior=selected-group
            count=Counter(j for i in group for j in bits(self.covers[i]))
            entry={
                "lines":lines,"regions":sorted(count),
                "shared_regions":sorted(j for j,n in count.items() if n>1),
                "internal_edges":[[i,j] for i,j in combinations(lines,2) if j in self.neighbors[i]],
                "external_edges":[[i,j] for i in lines for j in sorted(self.neighbors[i]&exterior)],
                "circulation_supports":[{"blocks":w["blocks"],"lines":sorted(group&set(w["lines"]))}
                                        for w in witnesses if group&set(w["lines"])],
                "pair_geometry":[{"lines":[i,j],"angle_overlap_gap_coverage_external":
                                  self.pair_diagnostics[i,j]} for i,j in combinations(lines,2)],
                "members":[],
            }
            for i in lines:
                outside=self.neighbors[i]&exterior
                competing=set().union(*(self.neighbors[j] for j in group-{i}))
                entry["members"].append({
                    "id":i,"source_id":self.original_ids[i],"length":self.lines[i].length,
                    "full_degree":len(self.neighbors[i]),"selected_degree":len(self.neighbors[i]&selected),
                    "internal_degree":len(self.neighbors[i]&group),"external_degree":len(outside),
                    "unique_sheaf_regions":[j for j in bits(self.covers[i]) if count[j]==1],
                    "unique_map_regions":list(bits(self.covers[i]&~union_mask(self.covers,selected-{i}))),
                    "unique_external_lines":sorted(outside-competing),
                })
            groups.append(entry)
        return {"selected":sorted(selected),"sheaves":groups,"witnesses":witnesses,
                "canonical_intervals":[[list(map(str,p)) for p in interval(line)] for line in self.lines],
                "source_ids":self.original_ids}

    def weight(self, selected):
        return len(selected),sum(self.lines[i].length for i in sorted(selected)),tuple(sorted(selected))

    def backward(self, selected, order):
        selected=frozenset(selected)
        seen=set()
        group={i:set(g) for g in self.groups for i in g}
        trace=[]
        while True:
            margin={}
            if order=="marginal-external":
                for i in selected:
                    others=set().union(*(self.neighbors[j] for j in (group.get(i,{i})&selected)-{i}))
                    margin[i]=len((self.neighbors[i]&selected)-group.get(i,{i})-others)
            priority={
                "shortest":lambda i:(self.lines[i].length,i),
                "longest":lambda i:(-self.lines[i].length,i),
                "lowest-connectivity":lambda i:(len(self.neighbors[i]),i),
                "marginal-external":lambda i:(margin[i],self.lines[i].length,i),
                "geometry":lambda i:(i,),
            }[order]
            for i in sorted(selected,key=priority):
                trial=selected-{i}
                if trial in seen:
                    continue
                seen.add(trial)
                if self.validate(trial)["status"]=="valid":
                    selected=trial
                    trace.append(i)
                    break
            else:
                return selected,trace

    def group_search(self, selected):
        current=frozenset(selected)
        trace=[]
        for _ in range(self.settings["sheaf_passes"]):
            changed=False
            for index,group in enumerate(self.groups):
                inside=sorted(current&set(group))
                rest=current-set(inside)
                if not inside:
                    continue
                if len(inside)<=self.settings["complete_sheaf_size"]:
                    proposals=[tuple(x) for size in range(len(inside)+1) for x in combinations(inside,size)]
                    exhaustive=True
                else:
                    exhaustive=False
                    proposals=[tuple(sorted(set(inside)-set(remove)))
                               for size in (3,2,1) for remove in combinations(inside,size)]
                    proposals=sorted(proposals,key=lambda s:self.weight(rest|set(s)))[:self.settings["large_sheaf_trials"]]
                best=current
                for replacement in proposals:
                    trial=rest|set(replacement)
                    if self.validate(trial)["status"]=="valid" and self.weight(trial)<self.weight(best):
                        best=trial
                trace.append({"sheaf":index+1,"tested":len(proposals),"exhaustive":exhaustive,
                              "removed":sorted(current-best)})
                changed|=best!=current
                current=best
            if not changed:
                break
        return current,trace

    def exchanges(self, selected):
        current=frozenset(selected)
        trace=[]
        tried=0
        per_group=max(1,self.settings["exchange_trials"]//max(1,len(self.groups)))
        for index,group in enumerate(self.groups):
            members=current&set(group)
            if not members:
                continue
            alternatives=[]
            for j,segment in enumerate(self.segments):
                if j in current or segment.length<self.settings["minimum_line_length"]:
                    continue
                matches=[overlap(segment,self.segments[i]) for i in group]
                qualified=[fraction for angle,fraction,gap in matches
                           if angle<=self.settings["maximum_angle"] and fraction>=self.settings["minimum_overlap"]
                           and gap<=self.settings["maximum_gap"]]
                if qualified:
                    coverage=(self.covers[j]&union_mask(self.covers,group)).bit_count()
                    alternatives.append((-coverage,-len(self.neighbors[j]&(current-members)),-max(qualified),j))
            proposals=[]
            for *_,j in sorted(alternatives)[:self.settings["exchange_candidates_per_sheaf"]]:
                for size in range(1,min(len(members),self.settings["maximum_exchange_removals"])+1):
                    for removed in combinations(sorted(members),size):
                        trial=(current-set(removed))|{j}
                        if self.weight(trial)<self.weight(current):
                            proposals.append((self.weight(trial),removed,j,trial))
            best=current
            tested=[]
            for _,removed,j,trial in sorted(proposals)[:min(per_group,self.settings["exchange_trials"]-tried)]:
                status=self.validate(trial)["status"]
                tested.append({"remove":list(removed),"add":j,"status":status})
                if status=="valid" and self.weight(trial)<self.weight(best):
                    best=trial
            tried+=len(tested)
            trace.append({"sheaf":index+1,"tested":len(tested),"proposals":tested,
                          "removed":sorted(current-best),"added":sorted(best-current)})
            current=best
        return current,trace

    def measures(self, selected, *, detailed=False):
        topology=self.validate(selected)
        if topology["status"]!="valid":
            raise ValueError(f"Result failed validation: {topology}")
        depth=entrance_depth(self.graph,selected,self.links)
        by_line={str(i):sum(d.values())/max(1,len(d)-1)
                 for i,d in nx.all_pairs_shortest_path_length(self.graph.subgraph(selected))}
        result={"ids":sorted(selected),"source_ids":[self.original_ids[i] for i in sorted(selected)],
                "line_count":len(selected),"length":self.weight(selected)[1],
                "removed":sorted(self.selected-selected),"added":sorted(selected-self.selected),
                "constraints":{**topology,"coverage_regions":self.target.bit_count(),"components":1,
                               "clearance_rejections":0},
                "axial_depth":statistics(list(by_line.values())),"axial_by_line":by_line,
                "entrance_depth":summary(depth,len(self.links)),
                "entrance_pair_depths":depth.tolist()}
        if detailed:
            result.update(self.route_metrics(selected))
        return result

    def route_metrics(self, selected):
        lines=[self.lines[i] for i in sorted(selected)]
        options=[[a for a in items if a.line_id in selected] for items in self.fixed]
        attachments=[a for items in options for a in items]
        owner=[i for i,items in enumerate(options) for a in items]
        network,_=segment_network(lines,attachments)
        metric=[]
        for i,items in enumerate(options):
            source=object()
            for a in items:
                network.add_edge(source,a.point,weight=distance(a.sample,a.point))
            lengths=nx.single_source_dijkstra_path_length(network,source,weight="weight")
            network.remove_node(source)
            metric.extend(min(lengths[a.point]+distance(a.sample,a.point) for a in others)
                          for others in options[i+1:])
        angular=angular_reference(lines,attachments,[0]*len(attachments)).depths
        minima={}
        for (a,b),value in angular.items():
            i,j=owner[a],owner[b]
            if i!=j:
                pair=tuple(sorted((i,j)))
                minima[pair]=min(minima.get(pair,float("inf")),value)
        angles=[minima.get(pair) for pair in combinations(range(len(options)),2)]
        return {"metric":statistics(metric),"angular":statistics([v for v in angles if v is not None]),
                "metric_pair_lengths":metric,"angular_pair_depths":angles,
                "unavailable_angular_pairs":angles.count(None)}


def diagnostics(inputs, parameters):
    return StageResult(Experiment(inputs,DEFAULTS|parameters.get("settings",{})).diagnose())


def backward_order(inputs, parameters):
    experiment = Experiment(inputs, DEFAULTS | parameters.get("settings", {}))
    order = parameters["order"]
    started = monotonic()
    selected, trace = experiment.backward(experiment.selected, order)
    return StageResult({
        "order": order, "map": experiment.measures(selected), "trace": trace,
        "seconds": monotonic() - started,
    })


def reduction(inputs, parameters):
    settings=DEFAULTS|parameters.get("settings",{})
    experiment=Experiment(inputs,settings)
    original=experiment.selected
    reports = parameters.get("saved_orders", {})
    if reports and set(reports) != set(ORDERS):
        raise ValueError("All five backward order results are needed.")
    if not reports:
        for order in ORDERS:
            start=monotonic()
            chosen,trace=experiment.backward(original,order)
            reports[order]={"map":experiment.measures(chosen),"trace":trace,"seconds":monotonic()-start}
            print(parameters.get("case"),order,len(chosen),flush=True)
    best_order=min(ORDERS,key=lambda o:experiment.weight(reports[o]["map"]["ids"]))
    best=frozenset(reports[best_order]["map"]["ids"])
    start=monotonic()
    c,trace_c=experiment.group_search(original)
    c_time=monotonic()-start
    start=monotonic()
    d,trace_d=experiment.backward(c,best_order)
    d_time=monotonic()-start
    start=monotonic()
    e,trace_e=experiment.exchanges(d)
    e_time=monotonic()-start
    choices={"A":(original,0,[]),"B":(best,reports[best_order]["seconds"],reports[best_order]["trace"]),
             "C":(c,c_time,trace_c),"D":(d,c_time+d_time,trace_d),"E":(e,c_time+d_time+e_time,trace_e)}
    metrics={}
    strategies={}
    for name,(chosen,seconds,trace) in choices.items():
        if chosen not in metrics:
            start=monotonic()
            metrics[chosen]=experiment.measures(chosen,detailed=True),monotonic()-start
        evaluated,route_seconds=metrics[chosen]
        strategies[name]={**evaluated,"search_seconds":seconds,"evaluation_seconds":route_seconds,
                          "trace":trace}
        print(parameters.get("case"),name,len(chosen),flush=True)
    return StageResult({"settings":settings,"best_order":best_order,"orders":reports,
                        "strategies":strategies,"search_counts":dict(experiment.calls),
                        "sheaves":experiment.groups,"source_ids":experiment.original_ids,
                        "canonical_intervals":[[list(map(str,p)) for p in interval(line)]
                                               for line in experiment.lines],
                        "entrance_order":[e["building_cell"] for e in experiment.entrances],
                        "final_witnesses":experiment.witnesses(e)})


def order_route_measures(inputs, parameters):
    """Evaluate metric and angular routes for each distinct saved greedy result."""
    experiment = Experiment(inputs, DEFAULTS | parameters.get("settings", {}))
    ids = {source: i for i, source in enumerate(experiment.original_ids)}
    routes = {}
    results = {}
    for order, source_ids in parameters["orders"].items():
        selected = frozenset(ids[i] for i in source_ids)
        if selected not in routes:
            started = monotonic()
            values = experiment.measures(selected, detailed=True)
            routes[selected] = {
                key: value for key, value in values.items()
                if key in ("metric", "angular", "metric_pair_lengths", "angular_pair_depths",
                           "unavailable_angular_pairs")
            } | {"seconds": monotonic() - started}
        results[order] = routes[selected]
    return StageResult({"orders": results})
