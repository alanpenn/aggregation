"""Complementary tangents on the live settlement's exact certified intervals."""

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
from math import atan2, degrees
from time import monotonic

import networkx as nx
from shapely import from_wkb
from shapely.geometry import LineString
from shapely.geometry.polygon import orient

from .angular import LineClearance, _cross, _direction, _exact_point, _on_segment
from .batch_methods import _domain, _settlement, derive_topology, exact_greedy
from .batch_routing_reference import MasterNetwork, describe
from .batch_store import encode
from .complementary_completion import StructuralCompletion, local_geometry, rankings
from .complementary_reduction import StructuralReduction
from .convex_metric_experiment import build_master_doors
from .dynamic_winding import CycleSignatures
from .exact_axial import candidate_graph
from .exact_enumeration import exact_pool_from_dict, exact_pool_to_dict, generate_fresh_exact_candidate_pool
from .experimental_visibility import IndexedClearance
from .region_incidence_angular import angular_depth, build_incidence
from .sheaf_experiment import DEFAULTS, detect_sheaves
from .strict_coverage_experiment import incidence_sets
from .strict_generalisation import Geometry, RegionalNetwork, extract_doors


SETTINGS = DEFAULTS | {"minimum_line_length": 0.0}


def no_progress(stage, detail=None):
    pass


def axial_angle(a, b):
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return degrees(atan2(float(abs(_cross(a, b))), float(abs(dot))))


def settlement_snapshot(polygons, labels, dyads, doors):
    return {"polygons_wkb": {str(i): polygon.wkb_hex for i, polygon in sorted(polygons.items())},
            "building_labels": {str(i): int(label) for i, label in sorted(labels.items())},
            "dyad_open_cells": sorted(map(int, dyads)),
            "doors": [list(map(int, pair)) for pair in doors]}


def settlement_key(snapshot, version):
    return sha256(encode({"algorithm": version, "settlement": snapshot})).hexdigest()


def boundary_index(topology, polygons, labels, lines):
    members = defaultdict(list)
    for cell, label in sorted(labels.items()):
        shape = polygons[cell]
        parts = [shape] if shape.geom_type == "Polygon" else shape.geoms
        offset = 0
        for part in parts:
            for ring in (part.exterior, *part.interiors):
                for index, p in enumerate(ring.coords[:-1], start=offset):
                    members[_exact_point(p)].append({"cell": cell, "label": label, "vertex_index": index})
                offset += len(ring.coords) - 1
    corners = defaultdict(list)
    for block, wkb in sorted(topology["blocks_wkb"].items()):
        shape = from_wkb(wkb)
        parts = [shape] if shape.geom_type == "Polygon" else shape.geoms
        for part in parts:
            part = orient(part)
            for ring in (part.exterior, *part.interiors):
                points = list(map(_exact_point, ring.coords[:-1]))
                for i, p in enumerate(points):
                    rays = _direction(p, points[i-1]), _direction(p, points[(i+1) % len(points)])
                    corners[p].append((block, rays, -_cross(*rays)))
    incidence = defaultdict(list)
    vertices = []
    for p, branches in sorted(corners.items()):
        convex = [(block, rays) for block, rays, turn in branches if turn > 0]
        if not convex:
            continue
        supported = []
        for line in lines:
            a, b = line.start, line.end
            if all(min(x,y) <= z <= max(x,y) for x,y,z in zip(a,b,p)) and _on_segment(p,a,b):
                direction = _direction(a,b)
                if any(_cross(direction,u)*_cross(direction,v) >= 0 for _, (u,v) in convex):
                    supported.append(line.line_id)
                    incidence[line.line_id].append(len(vertices))
        vertices.append({"id": len(vertices), "point": list(map(str,p)), "members": members[p],
                         "blocks": sorted({block for block, _ in convex}), "supported": supported})
    return vertices, incidence, corners


def preselect(study, progress):
    labels={int(k):v for k,v in study.inputs["settlement"]["building_labels"].items()}
    vertices,support,_=boundary_index(study.inputs["topology"],study.polygons,labels,study.lines)
    progress("Complementary tangent selection")
    directions=[_direction(line.start,line.end) for line in study.lines]
    lengths=[sum(x*x for x in d) for d in directions]
    retained=set(study.graph)-support.keys()
    anchors=[set() for _ in study.lines]
    pairs=[]
    def score(pair):
        i,j=pair
        a,b=study.neighbors[i],study.neighbors[j]
        distance=Fraction(len(a^b),len(a|b)) if a|b else Fraction(0)
        return min(len(a),len(b))*(1+distance)/2,axial_angle(directions[i],directions[j]),len(a)+len(b),lengths[i]+lengths[j],-i,-j
    for v in vertices:
        ids=v["supported"]
        chosen=max(combinations(sorted(ids),2),key=score) if len(ids)>1 else tuple(ids)
        for i in chosen:
            anchors[i].add(v["id"])
        retained.update(chosen)
        if len(chosen)==2:
            pairs.append(axial_angle(*(directions[i] for i in chosen)))
    return retained,anchors,vertices,pairs


def repair(study, selected, trace, progress):
    for r,ids in sorted(study.regions.items()):
        if selected.isdisjoint(ids):
            if not ids:
                raise ValueError(f"No certified interval traverses strict convex region {r}.")
            candidate=min(ids,key=lambda i:(study.length[i],i))
            selected.add(candidate)
            trace.append({"stage":"strict-region","region":r,"add":[candidate]})
    rank=study.winding.rank(selected) if study.connected(selected) else None
    if rank!=study.winding.required or any(selected.isdisjoint(g) for g in study.doors):
        engine=StructuralCompletion(study.inputs,study.lines,study.graph,study.measures,study.clearance,
                                    progress=lambda: progress("Structural completion", "Testing bounded repair proposals"))
        return engine.complete(selected,rankings(study.measures)["D"],trace)
    return None


def catalog(study, selected, anchors):
    masks=[sum(1<<x for x in r) for r in study.cover]
    groups,detail=detect_sheaves(selected,study.segments,masks,study.neighbors,SETTINGS)
    def across(i,j):
        return any(a!=b for a in anchors[i] for b in anchors[j])
    groups=[g for g in groups if any(across(i,j) for i,j in combinations(g,2))]
    for g in groups:
        for i in g:
            study.sheaf[i].update(set(g)-{i})
    for (i,j),(a,f,g,*_) in detail.items():
        if across(i,j):
            study.geometric[i][j]=study.geometric[j][i]=f/(1+a/21+g/3)
    return groups


@dataclass
class Preparation:
    stages: dict
    summaries: dict
    repairs: list
    vertices: list
    anchors: list
    seconds: float
    failure: str | None = None


@dataclass
class SelectionResult:
    ids: tuple
    summary: dict
    seconds: float
    winding_checks: int
    deletions: list
    exchanges: list
    failure: str | None = None

    @property
    def certified(self):
        return self.summary["certified"] and self.failure is None


class ComplementaryStudy(StructuralReduction):
    """Cacheable settlement analysis independent of Streamlit and research files."""

    def __init__(self, inputs, *, graph=None, measures=None, original_obstacles=None):
        self.inputs = inputs
        pool = exact_pool_from_dict(inputs["candidates"]["pool"])
        self.lines = pool.candidates
        if not self.lines or [line.line_id for line in self.lines] != list(range(len(self.lines))):
            raise ValueError("Expected a nonempty canonical certified candidate pool.")
        self.graph = graph if graph is not None else candidate_graph(self.lines)
        self.polygons, _, _ = _settlement(inputs)
        _, occupied, accessible, union = _domain(inputs)
        obstacles = occupied.values() if original_obstacles is None else original_obstacles
        self.clearance = IndexedClearance(
            LineClearance(accessible, union, original_obstacles=obstacles))
        self.geometry = Geometry(inputs, self.lines, self.graph, self.clearance)
        self.winding = CycleSignatures(self.lines, self.graph, self.polygons, self.geometry.blocks)
        self.regions, self.doors = incidence_sets(inputs["analysis"]["incidence"])
        if self.regions != {int(i): frozenset(j for j, covers in enumerate(pool.covers) if int(i) in covers)
                            for i in inputs["candidates"]["regions_wkb"]}:
            raise ValueError("The certified pool and strict positive-interior incidence disagree.")
        self.measures = measures if measures is not None else local_geometry(
            self.lines, self.graph, self.regions, self.doors)
        self.neighbors = [set(self.graph[i]) for i in range(len(self.lines))]
        self.segments = [LineString([line.start, line.end]) for line in self.lines]
        self.length = [line.length for line in self.lines]
        self.cover = pool.covers
        self.by_line = [set() for _ in self.lines]
        for index, members in enumerate([*self.regions.values(), *self.doors]):
            for i in members:
                self.by_line[i].add(index)
        self.sheaf = [set() for _ in self.lines]
        self.geometric = [{} for _ in self.lines]
        self.safe_ids = {line.line_id for line in self.lines if self.clearance.permits(line.start, line.end)}
        if len(self.safe_ids) != len(self.lines):
            raise ValueError("The candidate pool failed its independent exact clearance screen.")
        self.counts = Counter()
        self.timings = Counter()
        self.corridor_cache = {}
        self.historical_exchange = False
        self.progress = no_progress
        self.stage = ""

    @classmethod
    def from_settlement(cls, snapshot, progress=no_progress):
        progress("Certified candidate generation", "Classifying the main accessible component")
        inputs = {"settlement": snapshot}
        inputs["topology"] = derive_topology(inputs, {}).output
        opened, occupied, accessible, union = _domain(inputs)
        if not opened or not occupied:
            raise ValueError("The settlement needs accessible open space and occupied building blocks.")
        problem, _ = generate_fresh_exact_candidate_pool(
            opened, occupied, progress=lambda done, total, _: progress(
                "Certified candidate generation", f"Examined {done:,} of {total:,} corner pairs"))
        lines = problem.pool.candidates
        if not lines:
            raise ValueError("No certified candidates were generated.")
        progress("Certified candidate generation", "Calculating strict regions and doorway incidence")
        inputs["candidates"] = {
            "pool": exact_pool_to_dict(problem.pool),
            "obstacle_witnesses": problem.obstacles,
            "regions_wkb": {str(i): polygon.wkb_hex for i, polygon in problem.regions.items()},
        }
        clearance = IndexedClearance(LineClearance(accessible, union, original_obstacles=occupied.values()))
        polygons, _, _ = _settlement(inputs)
        doors, excluded = extract_doors(inputs, clearance, opened, polygons)
        incident, traversals, _ = build_incidence(lines, problem.regions, doors)
        inputs["analysis"] = {
            "holes": len(inputs["topology"]["topology"]["internal_blocks"]),
            "incidence": {"doorways": doors, "doorway_regions": incident,
                          "region_lines": {str(i): sorted(ids) for i, ids in traversals.items()}},
            "excluded_doorways": excluded,
        }
        progress("Certified candidate generation", "Building the exact intersection graph")
        return cls(inputs)

    def summary(self, ids, *, independent=False):
        ids = set(ids)
        missing_regions = [r for r, lines in self.regions.items() if ids.isdisjoint(lines)]
        missing_doors = [i for i, lines in enumerate(self.doors) if ids.isdisjoint(lines)]
        components = nx.number_connected_components(self.graph.subgraph(ids))
        rank = self.winding.rank(ids) if components == 1 else None
        winding = self.geometry.geometry(frozenset(ids)) if independent or rank is None else None
        if winding is not None:
            rank = winding["independent_circulation_rank"]
        clear = len(ids & self.safe_ids)
        if winding is not None:
            clear = winding["effective_clearance_line_count"]
        valid = (not missing_regions and not missing_doors and components == 1
                 and rank == self.winding.required and clear == len(ids))
        return {"count": len(ids), "length": sum(self.length[i] for i in sorted(ids)),
                "regions": len(self.regions) - len(missing_regions), "required_regions": len(self.regions),
                "doorways": len(self.doors) - len(missing_doors), "required_doorways": len(self.doors),
                "missing_regions": missing_regions, "missing_doorways": missing_doors,
                "components": components, "rank": rank, "required_rank": self.winding.required,
                "clear": clear, "certified": bool(independent and valid and winding["circulation_constraints_satisfied"]),
                "winding": winding}

    def prepare(self, progress=no_progress):
        started = monotonic()
        progress("Convex-vertex indexing")
        raw, anchors, vertices, _ = preselect(self, progress)
        progress("Structural completion", "Checking strict incidence and circulation")
        completed = set(raw)
        full = set(self.graph)
        full_summary = self.summary(full)
        repairs = []
        try:
            failure = repair(self, completed, repairs, progress)
        except (ValueError, nx.NetworkXException, TimeoutError) as error:
            failure = str(error)
        final_summary = self.summary(completed, independent=not failure)
        if not final_summary["certified"] and not failure:
            failure = "Structural completion did not pass the independent face validator."
        if not failure:
            progress("Structural completion", "Preparing the complete-link corridor catalogue")
            catalog(self, completed, anchors)
        return Preparation({"full": tuple(sorted(full)), "complementary": tuple(sorted(raw)),
                            "completed": tuple(sorted(completed))},
                           {"full": full_summary, "complementary": self.summary(raw),
                            "completed": final_summary}, repairs, vertices, anchors,
                           monotonic() - started, failure)

    def reduce_prepared(self, prepared, order, progress=no_progress):
        if order not in ("shortest", "sheaf"):
            raise ValueError(f"Unknown reduction order: {order}")
        if prepared.failure:
            raise ValueError(prepared.failure)
        current = set(prepared.stages["completed"])
        return self._run_selection(current, order, progress, exchange=False)

    def improve(self, reduced, order, progress=no_progress, *, historical=False):
        if not reduced.certified:
            raise ValueError("Exchanges require an independently certified reduced map.")
        return self._run_selection(set(reduced.ids), order, progress, exchange=True, historical=historical)

    def _run_selection(self, ids, order, progress, *, exchange, historical=False):
        started = monotonic()
        self.progress = progress
        self.stage = "Geometric exchanges" if exchange else "Dynamic structural reduction"
        self.historical_exchange = historical
        self.counts.clear()
        self.timings.clear()
        deletions, exchanges = [], []
        progress(self.stage)
        try:
            if exchange:
                exchanges = self.exchange(ids, order)
            else:
                self.reduce(ids, order, deletions)
            progress("Independent final validation")
            summary = self.summary(ids, independent=True)
            failure = None if summary["certified"] else "The final map did not pass independent structural validation."
            return SelectionResult(tuple(sorted(ids)), summary, monotonic() - started,
                                   self.counts["dynamic_validator"], deletions, exchanges, failure)
        except TimeoutError as error:
            return SelectionResult(tuple(sorted(ids)), self.summary(ids), monotonic() - started,
                                   self.counts["dynamic_validator"], deletions, exchanges, str(error))
        finally:
            self.historical_exchange = False
            self.progress = no_progress
            self.stage = ""

    def reference_map(self, method):
        if method == "full":
            ids = tuple(sorted(self.graph))
        elif method == "greedy":
            if "obstacle_witnesses" not in self.inputs["candidates"]:
                raise ValueError("The exact greedy comparator needs certified obstacle witnesses.")
            ids = tuple(exact_greedy(self.inputs, {}).output["line_ids"])
        else:
            raise ValueError(f"Unknown exact comparator: {method}")
        summary = self.summary(ids, independent=True)
        failure = None if summary["certified"] else "The reference map failed strict structural validation."
        return SelectionResult(ids, summary, 0, 0, [], [], failure)

    def movement(self, result, progress=no_progress):
        if not result.certified:
            raise ValueError("Doorway movement requires an independently certified map.")
        incidence = self.inputs["analysis"]["incidence"]
        doors = incidence["doorways"]
        pairs = list(combinations(range(len(doors)), 2))
        if not pairs:
            raise ValueError("At least two eligible doorways are required.")
        progress("Certified doorway movement", "Constructing exact regional connectors")
        ids = result.ids
        remap = {i: j for j, i in enumerate(ids)}
        lines = [replace(self.lines[i], line_id=j) for j, i in enumerate(ids)]
        restricted = incidence | {"region_lines": {r: [remap[i] for i in members if i in remap]
                                                    for r, members in incidence["region_lines"].items()}}
        regions = {int(i): from_wkb(wkb) for i, wkb in self.inputs["candidates"]["regions_wkb"].items()}
        axial = MasterNetwork(lines, [])
        stops, _, _ = build_master_doors(lines, restricted, regions, self.clearance)
        network = RegionalNetwork(axial, stops)
        chosen = frozenset(range(len(lines)))
        _, links = incidence_sets(restricted)
        progress("Certified doorway movement", "Calculating angular and metric doorway routes")
        angular, _ = angular_depth(axial, chosen, links, pairs)
        metric = network.route(chosen, False)
        return {"angular": describe(angular), "metric": describe(metric), "pairs": pairs,
                "angular_routes": angular, "metric_routes": metric,
                "valid": None not in angular and None not in metric}
