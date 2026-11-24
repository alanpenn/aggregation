"""Prune the seven restored certified pools by occupied-block corner direction."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
from hashlib import sha256
from io import StringIO
import json
from math import atan2, degrees
from pathlib import Path
from statistics import median, quantiles

import networkx as nx
from shapely import from_wkb
from shapely.geometry.polygon import orient

from experiments.constructive_axial import CASES, ROOT as CONTROLS, load
from experiments.vertex_directional_pruning import TOLERANCES, families
from voronoi_app.angular import LineClearance, _cross, _direction, _exact_point, _on_segment
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import Geometry

OUTPUT = CONTROLS.parent / "occupied-vertex-pruning-1"
TARGETS = (957, 1244, 1355, 865, 1189, 1190, 1208, 1354)


def read(path):
    return json.loads(path.read_bytes())


def boundary_index(topology, polygons, labels, lines):
    members = defaultdict(list)
    for cell, label in sorted(labels.items()):
        for index, p in enumerate(polygons[cell].exterior.coords[:-1]):
            members[_exact_point(p)].append({"cell": cell, "label": label, "vertex_index": index})
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


def length_distribution(ids, lines):
    values = sorted(lines[i].length for i in ids)
    if not values:
        return {}
    return {"min": values[0], "max": values[-1], "median": median(values),
            "quartiles": quantiles(values, method="inclusive") if len(values)>1 else values*3}


def case_run(case, output):
    inputs, source, _ = load(case)
    if source != read(CONTROLS / case / "source.json"):
        raise ValueError(f"{case} does not match archived lineage.")
    pool = exact_pool_from_dict(inputs["candidates"]["pool"])
    lines = pool.candidates
    measure_path = CONTROLS / case / "geometry.json"
    measure_bytes = measure_path.read_bytes()
    if sha256(measure_bytes).hexdigest() != read(CONTROLS / "export-checksums.json")[f"{case}/geometry.json"]:
        raise ValueError(f"{case} candidate measures differ from the published export.")
    measures = json.loads(measure_bytes)["candidates"]
    if [r["id"] for r in measures] != [line.line_id for line in lines]:
        raise ValueError(f"{case} candidate IDs differ from archived measures.")
    polygons, _, _ = _settlement(inputs)
    labels = {int(k): v for k, v in inputs["settlement"]["building_labels"].items()}
    vertices, support, boundary = boundary_index(inputs["topology"], polygons, labels, lines)
    if case == "flat-40":
        old = read(CONTROLS.parent / "vertex-axial-1/vertices.json")["vertices"]
        by_point = {tuple(row["point"]): row for row in old}
        differences = [{"vertex": v["id"], "new_only": sorted(set(v["supported"]) - set(old_row["supported"])),
                        "old_only": sorted(set(old_row["supported"]) - set(v["supported"]))}
                       for v in vertices if (old_row := by_point.get(tuple(v["point"]))) is not None
                       and v["supported"] != old_row["supported"]]
    else:
        differences = []
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from((r["id"], j) for r in measures for j in r["intersections"])
    baseline = inputs["analysis"]["maps"]["full_pool"]
    if graph.number_of_edges() != baseline["intersections"]:
        raise ValueError(f"{case} archived intersection count differs.")
    regions, doors = incidence_sets(inputs["analysis"]["incidence"])
    for i, candidates in regions.items():
        if candidates != {k for k, covers in enumerate(pool.covers) if i in covers}:
            raise ValueError(f"{case} strict incidence differs from certified region {i}.")
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible, obstacles, original_obstacles=occupied.values()))
    geometry = Geometry(inputs, lines, graph, clearance)
    vectors = [_direction(*sorted((line.start,line.end))) for line in lines]
    areas = [dx*dx+dy*dy for dx,dy in vectors]
    angles = [degrees(atan2(float(dy),float(dx))) % 180 for dx,dy in vectors]
    ids = set(graph)
    unindexed = ids - support.keys()
    provenance = {i: [{"source": p.source, "points": [list(map(str, q)) for q in (p.start,p.end)],
                       "boundary_turns": [[(turn>0)-(turn<0) for _,_,turn in boundary.get(q,())]
                                          for q in (p.start,p.end)],
                       "seed_vertex_references": [[[v.building_id,v.vertex_index] for v in refs]
                                                  for refs in (p.start_vertices,p.end_vertices)]}
                      for p in lines[i].provenance] for i in sorted(unindexed)}
    threshold = quantiles([line.length for line in lines],method="inclusive")[2]
    long_ids = {line.line_id for line in lines if line.length >= threshold}
    transverse = {(i,int(j)): tuple(p) for i in sorted(long_ids)
                  for j,p in measures[i]["transverse"].items() if int(j) in long_ids and i<int(j)}
    results = {}
    for tolerance in TOLERANCES:
        groups = {v["id"]: families(v["supported"],angles,areas,tolerance) for v in vertices}
        reps = {g["representative"] for fs in groups.values() for g in fs}
        retained = reps | unindexed
        eliminated = ids - retained
        components = sorted(map(sorted,nx.connected_components(graph.subgraph(retained))),key=lambda c:(-len(c),c))
        missing_regions = {i: sorted(members) for i,members in regions.items() if not retained & members}
        missing_doors = {i: sorted(members) for i,members in enumerate(doors) if not retained & members}
        bridges = {}
        if len(components)>1:
            by_line = {i: k for k, component in enumerate(components) for i in component}
            for i in sorted(eliminated):
                adjacent = sorted({by_line[j] for j in graph[i] if j in by_line})
                if len(adjacent)>1:
                    bridges[i]=adjacent
        kept_crossings = {p for (i,j),p in transverse.items() if i in retained and j in retained}
        lost_pairs = [[i,j,list(p),[k for k in (i,j) if k in eliminated]]
                      for (i,j),p in transverse.items() if i in eliminated or j in eliminated]
        targets = {i: {"retained": i in retained, "provisional": i in unindexed,
                       "families": [{"vertex": v, **g, "representative_length": lines[g["representative"]].length}
                                    for v in support[i] for g in groups[v] if i in g["candidate_ids"]]}
                   for i in TARGETS} if case == "flat-40" else {}
        print(case,tolerance,len(retained),"checking winding",flush=True)
        winding = geometry.geometry(frozenset(retained))
        rank = winding["independent_circulation_rank"]
        required = winding["required_circulation_rank"]
        results[tolerance] = {
            "retained": sorted(retained), "eliminated": sorted(eliminated),
            "reduction_percent": 100*len(eliminated)/len(lines), "retained_lengths": length_distribution(retained,lines),
            "eliminated_lengths": length_distribution(eliminated,lines),
            "family_count": sum(map(len,groups.values())), "unique_representatives": len(reps),
            "vertex_families": groups, "targets": targets,
            "regions_total": len(regions), "doorways_total": len(doors),
            "missing_region_restorers": missing_regions, "missing_doorway_restorers": missing_doors,
            "components": components, "single_line_bridges": bridges,
            "winding_rank": rank, "required_winding_rank": required,
            "winding": winding, "long_transverse_pairs": len(transverse),
            "lost_long_transverse_pairs": lost_pairs,
            "long_transverse_sites": len(set(transverse.values())),
            "retained_long_transverse_sites": len(kept_crossings),
        }
        print(case,tolerance,rank,required,flush=True)
    result = {"case": case, "source": source, "original_count": len(lines), "vertices": vertices,
              "incidences": sum(map(len,support.values())), "unindexed": provenance,
              "constituent_index_disagreements": differences, "long_threshold": threshold,
              "lines": [{"id": line.line_id, "start": list(map(str,line.start)), "end":list(map(str,line.end)),
                         "direction":list(map(str,vectors[i])), "angle":angles[i],"length":line.length,
                         "squared_length":str(areas[i]),"support":support[i]}
                        for i,line in enumerate(lines)],"results":results}
    atomic_write(output / f"{case}.json",encode(result))


def export_statistics(output):
    rows = []
    for case in CASES:
        data = read(output / f"{case}.json")
        for tolerance, result in data["results"].items():
            rows.append({
                "case": case, "tolerance_degrees": tolerance,
                "original": data["original_count"], "vertices": len(data["vertices"]),
                "vertex_line_incidences": data["incidences"],
                "unindexed_retained": len(data["unindexed"]), "families": result["family_count"],
                "unique_representatives": result["unique_representatives"],
                "retained": len(result["retained"]), "eliminated": len(result["eliminated"]),
                "reduction_percent": result["reduction_percent"],
                "retained_median_length": result["retained_lengths"].get("median"),
                "eliminated_median_length": result["eliminated_lengths"].get("median"),
                "regions_missing": len(result["missing_region_restorers"]),
                "doorways_missing": len(result["missing_doorway_restorers"]),
                "intersection_components": len(result["components"]),
                "winding_rank": result["winding_rank"], "winding_required": result["required_winding_rank"],
                "long_transverse_pairs": result["long_transverse_pairs"],
                "lost_long_transverse_pairs": len(result["lost_long_transverse_pairs"]),
                "long_transverse_sites": result["long_transverse_sites"],
                "retained_long_transverse_sites": result["retained_long_transverse_sites"],
            })
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(output / "statistics.csv", stream.getvalue().encode())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=OUTPUT)
    parser.add_argument("--case",choices=CASES)
    parser.add_argument("--workers",type=int,default=3)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    case_run(args.case or CASES[0],args.output)
    if not args.case:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for future in [pool.submit(case_run,case,args.output) for case in CASES[1:]]:
                future.result()
        export_statistics(args.output)


if __name__ == "__main__":
    main()
