"""Construct axial selections from certified local geometry, independently of route costs."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from hashlib import sha256
from itertools import combinations
import json
from math import cos, pi, sin
from pathlib import Path
from statistics import mean
from time import monotonic

import networkx as nx
from shapely import from_wkb
from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree

from experiments.extended_terrain import ROOT as EXTENDED, PREVIOUS
from experiments.flat40_tangent_audit import OUTPUT as TANGENT_AUDIT
from experiments.strict_generalisation import rss_mib
from voronoi_app.angular import LineClearance, _direction, _intersections, _on_segment
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_routing_reference import MasterNetwork, describe
from voronoi_app.batch_store import BatchStore, atomic_write, encode
from voronoi_app.convex_metric_experiment import build_master_doors, worst
from voronoi_app.exact_axial import candidate_graph
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_circulation_topology import evaluate_circulation_lines
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.region_incidence_angular import angular_depth
from voronoi_app.strict_coverage_experiment import incidence_sets, omissions
from voronoi_app.strict_generalisation import Geometry, RegionalNetwork

ROOT = Path("diagnostics/strict-generalisation/constructive-axial-3")
CASES = ("flat-40", "hill-40", "converging_valleys-40", "ridge-40", "shoulder-40", "twin_peaks-40", "flat-41")
PARAMETERS = {
    "backbone_lines": 12, "near_distance": 2.0, "orientation_degrees": 10,
    "coverage_overlap": .55, "projected_overlap": .65, "transverse_degrees": 30,
    "B": [.30, .25, .20, .20, .05], "B-coverage": [.20, .20, .10, .45, .05],
    "D_geometry_shortlist": 4, "winding_bundle_shortlist": 2, "winding_bundle_cap": 18,
    "face_split_shortlist": 16, "face_split_pair_shortlist": 6,
    "exchange_additions": 10, "exchange_removals": 6, "exchange_passes": 1,
}


def load(case):
    origin = PREVIOUS if case.startswith(("hill-", "converging_valleys-")) else EXTENDED
    journal = json.loads((origin / "cases" / f"{case}.json").read_bytes())
    store = BatchStore(origin)
    inputs, records = {}, {}
    for stage, entry in journal["stages"].items():
        manifest, output, checksum = store.load(entry["record"])
        inputs[stage] = output
        records[stage] = {"id": manifest["id"], "sha256": checksum, "output": manifest["output_sha256"]}
    reference = json.loads((origin / "route-references" / f"{case}.json").read_bytes())
    if reference["identity"]["candidate_record"] != records["candidates"]["id"]:
        raise ValueError("Candidate pool and route reference do not share lineage.")
    if any(reference[key] != inputs["analysis"]["maps"]["full_pool"]["routes"][key] for key in ("angular", "metric")):
        raise ValueError("Archived route reference does not match the analysis record.")
    return inputs, records, reference


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


class Selection:
    def __init__(self, inputs, lines, graph, measures, clearance):
        self.inputs, self.lines, self.graph, self.measures = inputs, lines, graph, measures
        self.engine = Geometry(inputs, lines, graph, clearance)
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

    @cache
    def winding(self, chosen):
        return self.engine.geometry(chosen)

    @cache
    def validate(self, chosen):
        missing, doors = omissions(chosen, self.regions, self.doors)
        components = nx.number_connected_components(self.graph.subgraph(chosen))
        result = {"missing_regions": missing, "unattached_doors": doors, "components": components}
        if missing or doors or components != 1:
            return result | {"valid": False}
        w = self.winding(chosen)
        return result | {"valid": w["circulation_constraints_satisfied"] and not w["lines_crossing_effective_occupied_space"],
                         "rank": w["independent_circulation_rank"], "required_rank": self.required,
                         "missing_rings": w["missing_axial_rings"], "clearance_rejections": w["lines_crossing_effective_occupied_space"]}

    @cache
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

    def backbone(self, method, ranking, trace):
        selected = set()
        if method != "D":
            for i in ranking:
                if not selected & self.duplicates[i]:
                    selected.add(i)
                    trace.append({"stage":"backbone","add":[i],"rank":ranking.index(i)+1})
                    if len(selected) == PARAMETERS["backbone_lines"]:
                        break
            return selected
        priority = {i:len(ranking)-j for j,i in enumerate(ranking)}
        for _ in range(PARAMETERS["backbone_lines"]):
            covered = set().union(*(self.covers[i] for i in selected))
            access = set().union(*(self.access[i] for i in selected))
            components = {i:j for j,group in enumerate(nx.connected_components(self.graph.subgraph(selected))) for i in group}
            rank = self.winding(frozenset(selected))["independent_circulation_rank"] if selected else 0

            def marginal(i):
                bridge = max(0,len({components[j] for j in self.neighbors[i] & selected})-1)
                regions = len(self.covers[i]-covered)
                doors = len(self.access[i]-access)
                transverse = len(self.transverse[i]&selected)
                duplicate = len(self.duplicates[i]&selected)
                score = regions + doors + 2*transverse + 5*bridge - 5*duplicate - 1
                return score, [regions, doors, transverse, bridge, duplicate]

            terms = {i:marginal(i) for i in self.ids-selected}
            options = sorted(terms,key=lambda i:(-terms[i][0],-priority[i]))[:PARAMETERS["D_geometry_shortlist"]]
            gains = {i:self.winding(frozenset(selected | {i}))["independent_circulation_rank"]-rank for i in options}
            i = max(options,key=lambda i:(terms[i][0]+12*gains[i],priority[i]))
            selected.add(i)
            trace.append({"stage":"backbone","add":[i],"marginal":terms[i][1],"winding_gain":gains[i],
                          "shortlist":[{"id":j,"score_before_winding":terms[j][0],"rank_gain":gains[j]} for j in options]})
        return selected

    def reduce(self, selected, trace):
        order = sorted(selected,key=lambda i:(self.lines[i].length,self.lines[i].start,self.lines[i].end))
        checks = []
        while True:
            before = len(selected)
            for i in order:
                if i not in selected:
                    continue
                result = self.validate(frozenset(selected-{i}))
                checks.append({"id":i,"accepted":result["valid"],**result})
                if result["valid"]:
                    selected.remove(i)
                    trace.append({"stage":"reduction","remove":[i]})
            if before == len(selected):
                return checks

    def exchange(self, selected, ranking):
        start = frozenset(selected)
        priority = {i:len(ranking)-j for j,i in enumerate(ranking)}
        extras = [i for i in ranking if i not in start][:PARAMETERS["exchange_additions"]]
        attempts, matches = [], []
        def economy(ids):
            return (len(ids),-sum(priority[i] for i in ids),tuple(sorted(ids)))
        def attempt(added, removed):
            ids = (start | set(added))-set(removed)
            result = self.validate(ids)
            record = {"add":sorted(added),"remove":sorted(removed),**result}
            attempts.append(record)
            if result["valid"]:
                matches.append(ids)
        for i in extras:
            for j in sorted(start):
                attempt([i],[j])
        for n in (1,2):
            for added in combinations(extras,n):
                coverage = set().union(*(self.covers[i] for i in added))
                adjacent = set().union(*(self.neighbors[i] for i in added))
                removal = sorted(start,key=lambda i:(-len(coverage & self.covers[i]),i not in adjacent,
                                                    priority[i],i))[:PARAMETERS["exchange_removals"]]
                for removed in combinations(removal,n+1):
                    attempt(added,removed)
        best = min([start,*matches],key=economy)
        matched = min([start,*(ids for ids in matches if len(ids)==len(start))],key=economy)
        return best, matched, attempts


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


def construct(selector, method, ranking):
    started = monotonic()
    trace = []
    selected = selector.backbone(method,ranking,trace)
    backbone = sorted(selected)
    failure = selector.complete(selected,ranking,trace)
    if failure:
        return {"error":failure,"backbone":backbone,"partial":sorted(selected),"trace":trace,
                "validation":selector.validate(frozenset(selected)),"seconds":monotonic()-started}
    completed = sorted(selected)
    print(method, "completion", len(backbone), "→", len(completed), flush=True)
    checks = selector.reduce(selected,trace)
    final = frozenset(selected)
    print(method, "reduction", len(final), flush=True)
    exchanged, matched, trials = selector.exchange(final,ranking)
    variants = {"constructive":sorted(final),"exchanged":sorted(exchanged),"matched_exchange":sorted(matched)}
    target = len(selector.inputs["analysis"]["maps"]["strict_backward"]["line_ids"])
    comparable = min((ids for ids in (final,exchanged) if len(ids) <= target),key=lambda ids:(target-len(ids),sorted(ids)),default=None)
    if comparable is not None:
        for i in ranking:
            if len(comparable) == target:
                break
            if i not in comparable and selector.validate(comparable | {i})["valid"]:
                comparable |= {i}
        if len(comparable) == target:
            variants["archived_count"] = sorted(comparable)
    return {"backbone":backbone,"completed":completed,"trace":trace,"deletions_checked":checks,
            "exchanges_checked":trials,"maps":variants,
            "validation":{key:selector.validate(frozenset(ids)) for key,ids in variants.items()},
            "seconds":monotonic()-started,"peak_rss_mib":rss_mib()}


def evaluate(inputs, lines, clearance, reference, methods):
    started = monotonic()
    analysis = inputs["analysis"]
    regions = {int(i):from_wkb(wkb) for i,wkb in inputs["candidates"]["regions_wkb"].items()}
    _, links = incidence_sets(analysis["incidence"])
    pairs = [tuple(pair) for pair in analysis["pairs"]]
    labels = [inputs["settlement"]["building_labels"][str(d["building_cell"])] for d in analysis["doorways"]]
    if reference["identity"]["doorways"] != analysis["doorways"] or reference["identity"]["pairs"] != analysis["pairs"]:
        raise ValueError("Doorway identity or pair order changed.")
    axial = MasterNetwork(lines,[])
    stops, _, _ = build_master_doors(lines,analysis["incidence"],regions,clearance)
    metric = RegionalNetwork(axial,stops)

    @cache
    def routed(ids):
        time = monotonic()
        angle,status = angular_depth(axial,ids,[group & ids for group in links],pairs)
        distances = metric.route(ids,False)
        result = {"valid":all(s=="reachable" for s in status) and None not in distances,
                  "count":len(ids),"length":sum(lines[i].length for i in sorted(ids)),
                  "angular_routes":angle,"metric_routes":distances,"routing_seconds":monotonic()-time}
        for name, values in (("angular",angle),("metric",distances)):
            costs = reference[name]
            result[name] = describe(values)
            result[f"{name}_absolute_excess"] = mean(abs(b-a) for a,b in zip(costs,values,strict=True)
                                                       if a is not None and b is not None)
            result[f"{name}_worst_excess"] = worst(pairs,costs,values,labels)
        return result
    ids = frozenset(analysis["maps"]["strict_backward"]["line_ids"])
    baseline = routed(ids)
    for name in ("angular","metric"):
        assert abs(baseline[name]["mean"]-analysis["maps"]["strict_backward"]["routing"][name]["cost"]["mean"]) < 1e-9
    output = {"baseline":baseline | {"ids":sorted(ids)},"methods":{}}
    for method, result in methods.items():
        output["methods"][method] = {}
        for variant, ids in result.get("maps",{}).items():
            output["methods"][method][variant] = routed(frozenset(ids))
    output["seconds"],output["peak_rss_mib"] = monotonic()-started,rss_mib()
    return output


def checkpoint(path, value):
    atomic_write(path,encode(value))


def case_run(case, root):
    path = root / case
    path.mkdir(exist_ok=True)
    if (path/"movement.json").exists():
        return
    inputs, records, reference = load(case)
    source_path = path/"source.json"
    if source_path.exists() and json.loads(source_path.read_bytes()) != records:
        raise ValueError(f"Archived input changed for {case}.")
    checkpoint(source_path,records)
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    graph = candidate_graph(lines)
    geo_path = path/"geometry.json"
    if not geo_path.exists():
        started = monotonic()
        measures = local_geometry(lines,graph,*incidence_sets(inputs["analysis"]["incidence"]))
        checkpoint(geo_path,{"candidates":measures,"rankings":rankings(measures),"seconds":monotonic()-started,
                             "peak_rss_mib":rss_mib()})
    data = json.loads(geo_path.read_bytes())
    selector = Selection(inputs,lines,graph,data["candidates"],clearance)
    methods = {}
    for method, ranking in data["rankings"].items():
        output = path/f"{method}.json"
        if output.exists():
            methods[method] = json.loads(output.read_bytes())
        else:
            methods[method] = construct(selector,method,ranking)
            checkpoint(output,methods[method])
        print(case,method,{key:len(ids) for key,ids in methods[method].get("maps",{}).items()},
              methods[method].get("error",""),flush=True)
    checkpoint(path/"movement.json",evaluate(inputs,lines,clearance,reference,methods))
    print(case,"movement complete",flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT)
    parser.add_argument("--workers",type=int,default=3)
    parser.add_argument("--flat-only",action="store_true")
    args = parser.parse_args()
    if args.output.resolve() in (EXTENDED.resolve(),PREVIOUS.resolve(),TANGENT_AUDIT.resolve()):
        parser.error("Use a fresh experiment directory.")
    args.output.mkdir(parents=True,exist_ok=True)
    code = Path(__file__).read_bytes()
    design = {"parameters":PARAMETERS,"source_sha256":sha256(code).hexdigest(),
              "normalisation":"per-settlement min-max; constant features zero",
              "movement_in_ranking":False}
    design_path = args.output/"design.json"
    if design_path.exists() and json.loads(design_path.read_bytes()) != design:
        raise ValueError("The frozen design differs from the saved run. Use another versioned output directory.")
    checkpoint(design_path,design)
    case_run(CASES[0],args.output)
    if not args.flat_only:
        with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
            jobs = [pool.submit(case_run,case,args.output) for case in CASES[1:]]
            for job in jobs:
                job.result()


if __name__ == "__main__":
    main()
