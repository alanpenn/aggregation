"""Frozen geometric diagnostics and bounded repair for complementary axial selection."""

from functools import lru_cache
from itertools import combinations
from math import cos, pi, sin
from statistics import mean

import networkx as nx
from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree

from .angular import _direction, _intersections, _on_segment
from .experimental_circulation_topology import evaluate_circulation_lines
from .strict_coverage_experiment import incidence_sets, omissions
from .strict_generalisation import Geometry

PARAMETERS = {
    "backbone_lines": 12, "near_distance": 2.0, "orientation_degrees": 10,
    "coverage_overlap": .55, "projected_overlap": .65, "transverse_degrees": 30,
    "B": [.30, .25, .20, .20, .05], "B-coverage": [.20, .20, .10, .45, .05],
    "D_geometry_shortlist": 4, "winding_bundle_shortlist": 2, "winding_bundle_cap": 18,
    "face_split_shortlist": 16, "face_split_pair_shortlist": 6,
    "exchange_additions": 10, "exchange_removals": 6, "exchange_passes": 1,
}


def redundant(shape, other, direction, other_direction, regions, others, parameters=PARAMETERS):
    alignment = abs(sum(a*b for a,b in zip(direction, other_direction, strict=True)))
    if alignment < cos(pi * parameters["orientation_degrees"] / 180):
        return False
    common = len(regions & others)
    if not common or common / len(regions | others) < parameters["coverage_overlap"]:
        return False
    start = shape.coords[0]
    projections = sorted(sum((p-q)*d for p,q,d in zip(point, start, direction, strict=True)) for point in other.coords)
    overlap = min(shape.length, projections[1]) - max(0, projections[0])
    if overlap < parameters["projected_overlap"] * min(shape.length, other.length):
        return False
    # Compare offset at both ends of the overlap. Opposed diagonals that fan apart
    # survive even when their intersection makes the minimum separation zero.
    return all(other.distance(shape.interpolate(t)) <= parameters["near_distance"]
               for t in (max(0, projections[0]), min(shape.length, projections[1])))


def families(neighbors, duplicates):
    graph = nx.Graph()
    graph.add_nodes_from(neighbors)
    graph.add_edges_from((i, j) for i in neighbors for j in duplicates[i] & neighbors if j > i)
    return sorted([sorted(group) for group in nx.connected_components(graph)])


def normalize(values):
    low, high = min(values), max(values)
    return [(value-low)/(high-low) if high != low else 0.0 for value in values]


def local_geometry(lines, graph, region_sets, door_sets):
    ids = range(len(lines))
    regions, doors = [set() for _ in ids], [set() for _ in ids]
    for region, members in region_sets.items():
        for i in members:
            regions[i].add(region)
    for door, members in enumerate(door_sets):
        for i in members:
            doors[i].add(door)
    shapes = [LineString([line.start, line.end]) for line in lines]
    vectors = [tuple(float(x)/line.length for x in _direction(line.start, line.end)) for line in lines]
    tree = STRtree(shapes)
    duplicates = [set() for _ in ids]
    for i in ids:
        for raw in tree.query(shapes[i], predicate="dwithin", distance=PARAMETERS["near_distance"]):
            j = int(raw)
            if j > i and redundant(shapes[i], shapes[j], vectors[i], vectors[j], regions[i], regions[j]):
                duplicates[i].add(j)
                duplicates[j].add(i)
    transverse, positions = [set() for _ in ids], [{} for _ in ids]
    for i, j in graph.edges:
        a,b = vectors[i], vectors[j]
        # Use exact squared products at the inclusive threshold sin²(30°) = 1/4.
        if abs(a[0]*b[1]-a[1]*b[0]) < sin(pi/6) - 1e-12:
            continue
        u,v = (_direction(lines[k].start, lines[k].end) for k in (i,j))
        if 4*(u[0]*v[1]-u[1]*v[0])**2 < sum(x*x for x in u)*sum(x*x for x in v):
            continue
        points = sorted(_intersections(lines[i].start, lines[i].end, lines[j].start, lines[j].end))
        assert len(points) == 1
        point = points[0]
        for a,b in ((i,j),(j,i)):
            transverse[a].add(b)
            positions[a][b] = list(map(str, point))
    measures = []
    for i in ids:
        groups = families(transverse[i], duplicates)
        axis = 0 if lines[i].start[0] != lines[i].end[0] else 1
        from fractions import Fraction
        parameters = {j: float((Fraction(point[axis])-lines[i].start[axis]) /
                               (lines[i].end[axis]-lines[i].start[axis])) for j,point in positions[i].items()}
        centers = [mean(parameters[j] for j in family) for family in groups]
        spread = max(centers)-min(centers) if len(centers) > 1 else 0.0
        measures.append({"id": i, "length": lines[i].length, "regions": sorted(regions[i]), "doorways": sorted(doors[i]),
                         "intersections": sorted(graph[i]), "transverse": positions[i], "families": groups,
                         "family_span": spread, "redundant": sorted(duplicates[i])})
    columns = list(zip(*[normalize(values) for values in zip(*[
        (row["length"], len(row["families"]), row["family_span"], len(row["regions"]), len(row["redundant"]))
        for row in measures], strict=True)], strict=True))
    for row, features in zip(measures, columns, strict=True):
        row["normalized"] = features
    return measures


class StructuralCompletion:
    def __init__(self, inputs, lines, graph, measures, clearance, *, progress=lambda: None):
        self.inputs, self.lines, self.graph, self.measures = inputs, lines, graph, measures
        self.engine = Geometry(inputs, lines, graph, clearance)
        self.progress = progress
        self.winding = lru_cache(maxsize=64)(self.winding)
        self.ring_bundles = lru_cache(maxsize=1)(self.ring_bundles)
        self.regions, self.doors = incidence_sets(inputs["analysis"]["incidence"])
        self.neighbors = [set(graph[i]) for i in graph]
        self.covers = [set(row["regions"]) for row in measures]
        self.access = [set(row["doorways"]) for row in measures]
        self.duplicates = [set(row["redundant"]) for row in measures]
        self.transverse = [set(map(int,row["transverse"])) for row in measures]
        self.shapes = [LineString([line.start,line.end]) for line in lines]
        self.required = inputs["analysis"]["holes"]
        self.ids = frozenset(graph)
        self.forced = {next(iter(members)) for members in [*self.regions.values(), *self.doors] if len(members) == 1}

    def winding(self, chosen):
        self.progress()
        return self.engine.geometry(chosen)

    def ring_bundles(self):
        # Decompose the archived ring certificate into individual exact face
        # supports. They are available only during repair.
        ids = self.inputs["candidates"]["pool"]["ring_candidates"]
        engine = self.engine
        engine.face_bounds.clear()
        proof = evaluate_circulation_lines(
            engine.polygons, [self.lines[i] for i in ids], engine.blocks, engine.domain_clearance,
            face_builder=engine.cached_faces, face_location=engine.face_location,
            face_coverage=engine.face_coverage, block_witnesses=engine.block_witnesses,
            include_witness_faces=True)
        bundles = []
        for cycle in proof["circulation_cycles"]:
            face = proof["witness_faces"][cycle["face_index"]]
            members = set()
            for a,b in zip(face,face[1:]):
                matching = [i for i in ids if _on_segment(a,self.lines[i].start,self.lines[i].end)
                            and _on_segment(b,self.lines[i].start,self.lines[i].end)]
                if members.isdisjoint(matching):
                    members.add(min(matching))
            bundles.append((frozenset(members),frozenset(cycle["enclosed_blocks"])))
        return tuple(sorted(set(bundles),key=lambda item:(len(item[0]),sorted(item[0]),sorted(item[1]))))

    def split_candidates(self, selected, certificate, priority):
        """Propose lines separating occupied blocks currently enclosed together."""
        grouped = [(row["face_index"],row["enclosed_blocks"]) for row in certificate["circulation_cycles"]
                   if len(row["enclosed_blocks"]) > 1]
        if not grouped:
            return []
        faces = self.engine.cached_faces([self.lines[i] for i in sorted(selected)])
        targets = [(Polygon(faces[index]),[tuple(map(float,self.engine.block_witnesses[block])) for block in blocks])
                   for index,blocks in grouped]
        graph_candidates = []
        for i in self.ids-selected:
            contacts = len(self.neighbors[i] & selected)
            if contacts < 2:
                continue
            shape = self.shapes[i]
            (ax,ay),(bx,by) = shape.coords
            split = 0
            for face,blocks in targets:
                sides = [(bx-ax)*(y-ay)-(by-ay)*(x-ax) for x,y in blocks]
                if min(sides) < 0 < max(sides) and shape.relate_pattern(face,"T********"):
                    split += min(sum(d<0 for d in sides),sum(d>0 for d in sides))
            if split:
                graph_candidates.append((i,split,contacts))
        return [i for i,_,_ in sorted(graph_candidates,key=lambda row:(-row[1],-row[2],-priority[row[0]]))]

    def complete(self, selected, ranking, trace):
        priority = {i: len(ranking)-r for r,i in enumerate(ranking)}

        def add(ids, stage, **evidence):
            added = sorted(set(ids)-selected)
            if added:
                selected.update(added)
                trace.append({"stage":stage,"add":added,**evidence})

        add(self.forced, "singleton")
        while True:
            uncovered, unattached = omissions(selected, self.regions, self.doors)
            if not uncovered and not unattached:
                break
            def gain(i):
                return len(self.covers[i]&set(uncovered))+len(self.access[i]&set(unattached))
            i = max(self.ids-selected,key=lambda i:(gain(i),len(self.neighbors[i]&selected),priority[i]))
            if gain(i) == 0:
                raise ValueError("The candidate inventory cannot cover the remaining requirements.")
            add([i],"coverage",gain=gain(i))

        def connect():
            while not nx.is_connected(self.graph.subgraph(selected)):
                groups = sorted((sorted(group) for group in nx.connected_components(self.graph.subgraph(selected))))
                first = set(groups[0])
                distance, paths = nx.multi_source_dijkstra(self.graph, sorted(first))
                destination = min(selected-first,key=lambda i:(distance[i],-priority[i],i))
                add(paths[destination],"connectivity")
        connect()
        while True:
            w = self.winding(frozenset(selected))
            if w["circulation_constraints_satisfied"]:
                break
            rank = w["independent_circulation_rank"]
            missing = len(w["missing_axial_rings"])
            defects = set(w["missing_axial_rings"])
            improving = []

            def assess(options):
                for bundle in options:
                    trial = self.winding(frozenset(selected | bundle))
                    gain = trial["independent_circulation_rank"]-rank
                    repair = missing-len(trial["missing_axial_rings"])
                    if gain > 0 or (gain == 0 and repair > 0):
                        improving.append((gain,repair,bundle))
                        if len(improving) == PARAMETERS["winding_bundle_shortlist"]:
                            break

            strategy = "face separation"
            splits = self.split_candidates(selected,w,priority)[:PARAMETERS["face_split_shortlist"]]
            assess(frozenset({i}) for i in splits)
            if not improving:
                assess(map(frozenset,combinations(splits[:PARAMETERS["face_split_pair_shortlist"]],2)))
            if not improving:
                strategy = "certified face supports"
                cap = PARAMETERS["winding_bundle_cap"]
                remaining = sorted({(bundle-selected,len(blocks & defects)) for bundle,blocks in self.ring_bundles()
                                    if bundle-selected and len(bundle-selected) <= cap},
                                   key=lambda item:(-item[1],len(item[0]),-sum(priority[i] for i in item[0]),sorted(item[0])))
                proposals = list(dict.fromkeys(bundle for bundle,_ in remaining))
                assess(proposals)
                if not improving:
                    supplemental = {a|b for a,b in combinations(proposals[:4],2) if len(a|b) <= cap}
                    assess(sorted(supplemental,key=lambda bundle:(len(bundle),sorted(bundle))))
            if not improving:
                return "No bounded exact face bundle improved winding."
            gain, repair, bundle = max(improving,key=lambda item:(item[0]/len(item[2]),item[1],-len(item[2]),
                                                                 tuple(-i for i in sorted(item[2]))))
            add(bundle,"circulation",rank_before=rank,rank_gain=gain,missing_rings_repaired=repair,repair_strategy=strategy)
            connect()
        return None


def rankings(measures):
    ids = range(len(measures))
    output = {"A": sorted(ids,key=lambda i:(-measures[i]["length"],i))}
    for key in ("B","B-coverage"):
        a,b,c,d,e = PARAMETERS[key]
        def score(i):
            length, diversity, span, coverage, redundancy = measures[i]["normalized"]
            return a*length + b*diversity + c*span + d*coverage - e*redundancy
        output[key] = sorted(ids,key=lambda i:(-score(i),i))
    output["D"] = output["B"]
    return output
