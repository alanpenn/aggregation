"""Flat 40 vertex-supported construction using immutable certified inputs."""
from hashlib import sha256
import json
from math import atan2, degrees
from pathlib import Path
from statistics import mean, median

from experiments.constructive_axial import (
    ROOT as CONSTRUCTIVE, Selection, candidate_graph, checkpoint, construct, evaluate, families, load, normalize,
)
from voronoi_app.angular import LineClearance, _direction, _on_segment
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.exact_enumeration import _supports, _vertices, exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance

ROOT = Path("diagnostics/strict-generalisation/vertex-axial-1")
CASE = "flat-40"
DESIGN = {"extended_length": "settlement median", "orientation_bin_degrees": 15,
          "vertex_weights": [.35, .30, .20, .15], "line_weights": [.55, .45]}


def vertex_index(polygons, labels, lines, measures):
    points, faces = _vertices(polygons)
    edges = {}
    for left, right in faces:
        key = tuple(sorted((left.point, right.point)))
        edges.setdefault(key, set()).add(left.reference.building_id)
    duplicates = [set(row["redundant"]) for row in measures]
    limit = median(line.length for line in lines)
    records, supports = [], [[] for _ in lines]
    bounds = [(min(l.start[0],l.end[0]), max(l.start[0],l.end[0]),
               min(l.start[1],l.end[1]), max(l.start[1],l.end[1])) for l in lines]
    for index, (point, vertices) in enumerate(sorted(points.items())):
        members = []
        supported = set()
        for vertex in vertices:
            adjacent = (vertex.previous, vertex.following)
            contact = any(len(edges[tuple(sorted((point, p)))]) > 1 for p in adjacent)
            owner = vertex.reference.building_id
            members.append({"cell": owner, "label": labels[owner], "vertex_index": vertex.reference.vertex_index,
                            "adjacent_directions": [list(map(str, _direction(point,p))) for p in adjacent],
                            "face_contact": contact,
                            "coincident_vertex_contact": any(v.reference.building_id != owner for v in vertices),
                            "vertex_only_neighbors": sorted({v.reference.building_id for v in vertices} - {owner} -
                                set().union(*(edges[tuple(sorted((point,p)))] for p in adjacent)))})
        memberships = {}
        for line,(x0,x1,y0,y1) in zip(lines,bounds,strict=True):
            if not (x0 <= point[0] <= x1 and y0 <= point[1] <= y1 and _on_segment(point,line.start,line.end)):
                continue
            direction_point = line.end if point != line.end else line.start
            qualifying = [i for i,v in enumerate(vertices) if _supports(v,direction_point)]
            if qualifying:
                supported.add(line.line_id)
                supports[line.line_id].append(index)
                memberships[line.line_id] = qualifying
        extended = {i for i in supported if lines[i].length >= limit}
        groups = families(extended,duplicates)
        orientation = {int((degrees(atan2(*reversed(_direction(lines[i].start,lines[i].end)))) % 180)
                           // DESIGN["orientation_bin_degrees"]) for i in extended}
        best = max((lines[i].length for i in extended),default=0)
        diversity = mean(len(measures[i]["families"]) for i in extended) if extended else 0
        records.append({"id":index,"point":list(map(str,point)),"members":members,
                        "supported":sorted(supported),"support_members":memberships,"extended":sorted(extended),
                        "families":groups,"direction_bins":sorted(orientation),
                        "features":[len(groups),len(orientation),best,diversity]})
    columns = [normalize(list(column)) for column in zip(*(r["features"] for r in records),strict=True)]
    for record, values in zip(records,zip(*columns,strict=True),strict=True):
        record["score"] = sum(a*b for a,b in zip(DESIGN["vertex_weights"],values,strict=True))
    return records,supports,limit


def vertex_ranking(records, supports, measures):
    scores = []
    for row, vertices in zip(measures,supports,strict=True):
        length,families_,spread,coverage,redundancy = row["normalized"]
        local = .30*length+.25*families_+.20*spread+.20*coverage-.05*redundancy
        vertex = max((records[i]["score"] for i in vertices),default=0)
        scores.append(DESIGN["line_weights"][0]*vertex+DESIGN["line_weights"][1]*local)
    return sorted(range(len(scores)),key=lambda i:(-scores[i],i)),scores


def main():
    ROOT.mkdir(exist_ok=True)
    inputs,source,reference = load(CASE)
    archived = CONSTRUCTIVE/CASE
    if json.loads((archived/"source.json").read_bytes()) != source:
        raise ValueError("D and E require identical archived inputs.")
    design = DESIGN | {"source_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
                       "common_design_sha256":sha256((CONSTRUCTIVE/"design.json").read_bytes()).hexdigest()}
    path = ROOT/"design.json"
    if path.exists() and json.loads(path.read_bytes()) != design:
        raise ValueError("Design changed for this experimental directory.")
    checkpoint(path,design)
    checkpoint(ROOT/"source.json",source)
    polygons,buildings,_ = _settlement(inputs)
    labels = {int(cell):label for cell,label in inputs["settlement"]["building_labels"].items()}
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    measures = json.loads((archived/"geometry.json").read_bytes())["candidates"]
    path=ROOT/"vertices.json"
    if not path.exists():
        records,supports,limit = vertex_index({i:polygons[i] for i in buildings},labels,lines,measures)
        ranking,scores=vertex_ranking(records,supports,measures)
        checkpoint(path,{"vertices":records,"candidate_supports":supports,"extended_threshold":limit,
                         "ranking":ranking,"candidate_scores":scores})
    data=json.loads(path.read_bytes())
    print(len(data["vertices"]),"exact vertices indexed",flush=True)
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance=IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    path=ROOT/"E.json"
    if not path.exists():
        selection=Selection(inputs,lines,candidate_graph(lines),measures,clearance)
        checkpoint(path,construct(selection,"E",data["ranking"]))
    result=json.loads(path.read_bytes())
    print("E",result.get("error"),{k:len(ids) for k,ids in result.get("maps",{}).items()},flush=True)
    path=ROOT/"movement.json"
    if not path.exists():
        if result.get("maps"):
            movement=evaluate(inputs,lines,clearance,reference,{"E":result})
        else:
            movement={"methods":{"E":{}}}
        checkpoint(path,movement)


if __name__ == "__main__":
    main()
