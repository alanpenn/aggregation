"""Reduce certified Flat 40 complementary tangents within overlapping sheaves."""
from fractions import Fraction
from itertools import combinations

import networkx as nx
from shapely.geometry import LineString
from shapely.strtree import STRtree

from experiments.constructive_axial import ROOT, load
from experiments.occupied_vertex_pruning import OUTPUT, boundary_index, read
from experiments.vertex_connectivity_complements import axial_angle
from voronoi_app.angular import LineClearance, _on_segment
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_axial import _bounds
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_circulation_topology import evaluate_circulation_lines
from voronoi_app.experimental_visibility import IndexedClearance, _outward_bounds
from voronoi_app.sheaf_experiment import DEFAULTS, detect_sheaves, interval
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import Geometry


def run():
    saved = read(OUTPUT / "flat-40-connectivity-complements.json")
    vertex_data = read(OUTPUT / "flat-40.json")
    inputs, source, _ = load("flat-40")
    if source != saved["source"] or source != vertex_data["source"]:
        raise ValueError("Certified input records and complementary selection differ.")
    pool = exact_pool_from_dict(inputs["candidates"]["pool"])
    lines = pool.candidates
    geometry_rows = read(ROOT / "flat-40/geometry.json")["candidates"]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(lines)))
    graph.add_edges_from((row["id"], j) for row in geometry_rows for j in row["intersections"])
    neighbors = [set(graph[i]) for i in range(len(lines))]
    if any(neighbors[i] != set(saved["intersection_neighbors"][str(i)]) for i in graph):
        raise ValueError("Saved intersection sets differ from the certified graph.")
    if any((line.line_id, list(map(str,line.start)), list(map(str,line.end))) !=
           (row["id"], row["start"], row["end"]) for line,row in zip(lines,vertex_data["lines"],strict=True)):
        raise ValueError("Saved exact intervals differ from the restored candidates.")
    polygons, _, _ = _settlement(inputs)
    labels = {int(k): v for k,v in inputs["settlement"]["building_labels"].items()}
    vertices, support, _ = boundary_index(inputs["topology"],polygons,labels,lines)
    if vertices != vertex_data["vertices"]:
        raise ValueError("Saved support differs from exact block tangency.")
    selected = {row[key] for row in saved["pairs"] for key in ("first","second") if key in row}
    directions = [tuple(map(Fraction,row["direction"])) for row in vertex_data["lines"]]
    lengths = [Fraction(row["squared_length"]) for row in vertex_data["lines"]]

    def score(i,j):
        a,b = neighbors[i],neighbors[j]
        distance = Fraction(len(a^b),len(a|b)) if a|b else Fraction(0)
        return (min(len(a),len(b))*(1+distance)/2, axial_angle(directions[i],directions[j]),
                len(a)+len(b),lengths[i]+lengths[j],-i,-j)

    anchors = {i:set() for i in graph}
    for row in saved["pairs"]:
        v = row["vertex"]
        ids = vertices[v]["supported"]
        chosen = sorted(row[k] for k in ("first","second") if k in row)
        expected = list(max(combinations(ids,2),key=lambda pair:score(*pair))) if len(ids)>1 else ids
        if chosen != expected:
            raise ValueError(f"Complementary choices changed at vertex {v}.")
        for i in chosen:
            anchors[i].add(v)
    original = set(saved["retained"])
    if original != selected | set(saved["provisional"]) or set(saved["provisional"]) != set(graph)-support.keys():
        raise ValueError("Complementary union or provisional candidates changed.")

    regions, doors = incidence_sets(inputs["analysis"]["incidence"])
    if any(members != {i for i,covers in enumerate(pool.covers) if r in covers}
           for r,members in regions.items()):
        raise ValueError("Exact region incidence differs from candidate certificates.")
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    geometry = Geometry(inputs,lines,graph,clearance)

    def certificate(ids, *, capture_faces=False):
        builder = geometry.cached_faces
        faces = []

        def capture(valid_lines):
            faces[:] = builder(valid_lines)
            return faces

        if capture_faces:
            geometry.face_bounds.clear()
            winding = evaluate_circulation_lines(
                polygons,[lines[i] for i in sorted(ids)],geometry.blocks,geometry.domain_clearance,
                face_builder=capture,face_location=geometry.face_location,face_coverage=geometry.face_coverage,
                block_witnesses=geometry.block_witnesses)
        else:
            winding = geometry.geometry(frozenset(ids))
        return {"count": len(ids), "length": sum(lines[i].length for i in sorted(ids)),
                "missing_regions": [r for r,members in regions.items() if ids.isdisjoint(members)],
                "missing_doorways": [j for j,members in enumerate(doors) if ids.isdisjoint(members)],
                "components": nx.number_connected_components(graph.subgraph(ids)),
                "winding": winding},faces

    def passes(cert):
        return (not cert["missing_regions"] and not cert["missing_doorways"] and cert["components"]==1
                and cert["winding"]["circulation_constraints_satisfied"]
                and not cert["winding"]["lines_crossing_effective_occupied_space"])

    baseline,_ = certificate(original)
    if len(baseline["missing_regions"])!=1 or baseline["missing_doorways"]:
        raise ValueError("The baseline is different from the recorded Flat 40 case.")
    hole = baseline["missing_regions"][0]
    repair = min(regions[hole],key=lambda i:(lengths[i],i))
    repaired = original | {repair}
    repaired_cert,faces = certificate(repaired,capture_faces=True)
    if not passes(repaired_cert):
        raise ValueError("A single shortest certified coverage repair was insufficient.")
    print("Verified baseline and one-line repair",repair,flush=True)

    # Preserve complete exact cycles as constructive certificates of winding
    # while testing local deletions. The final full validator checks the result.
    ids = sorted(repaired)
    tree = STRtree([_bounds(lines[i]) for i in ids])
    protected = {repair}
    witnesses = []
    for cycle in repaired_cert["winding"]["circulation_cycles"]:
        ring = faces[cycle["face_index"]]
        support_ids = set()
        for a,b in zip(ring,ring[1:]):
            options = [i for k in tree.query(_outward_bounds(a,b)) for i in (ids[int(k)],)
                       if _on_segment(a,*interval(lines[i])) and _on_segment(b,*interval(lines[i]))]
            support_ids.add(min(options,key=lambda i:(i not in protected,i)))
        protected.update(support_ids)
        witnesses.append({"blocks":cycle["enclosed_blocks"],"line_ids":sorted(support_ids)})

    segments = [LineString(interval(line)) for line in lines]
    covers = [sum(1<<r for r in covered) for covered in pool.covers]
    settings = DEFAULTS | {"minimum_line_length": 0.0}
    groups, pair_data = detect_sheaves(repaired,segments,covers,neighbors,settings)

    def across_vertices(i, j):
        return any(a != b for a in anchors[i] for b in anchors[j])

    matches = {i: [] for i in repaired}
    for (i, j), diagnostic in pair_data.items():
        if across_vertices(i, j):
            matches[i].append({"line": j, "diagnostics": diagnostic})
            matches[j].append({"line": i, "diagnostics": diagnostic})
    groups = [g for g in groups if any(across_vertices(i, j) for i,j in combinations(g,2))]
    current = set(repaired)
    trace = []
    for group in groups:
        alternatives = set(group)
        while len(alternatives)>1:
            removed = False
            for i in sorted(alternatives-protected,key=lambda i:(lengths[i],i)):
                other = alternatives-{i}
                substitutes = sorted(j for j in other if across_vertices(i, j))
                if not substitutes:
                    continue
                trial = current-{i}
                missing_regions = [r for r,members in regions.items() if trial.isdisjoint(members)]
                missing_doors = [j for j,members in enumerate(doors) if trial.isdisjoint(members)]
                connected = nx.is_connected(graph.subgraph(trial))
                accepted = not missing_regions and not missing_doors and connected
                trace.append({"sheaf":group,"removed_candidate":i,"remaining_cross_anchor_substitutes":substitutes,
                              "accepted":accepted,"missing_regions":missing_regions,
                              "missing_doorways":missing_doors,"connected":connected})
                if accepted:
                    current=trial
                    alternatives.remove(i)
                    removed=True
                    break
            if not removed:
                break
    final,_ = certificate(current)
    if not passes(final):
        raise ValueError("Reduced pool failed full exact validation.")
    result = {"source":source,"baseline_ids":sorted(original),"baseline":baseline,
              "repair":{"candidate":repair,"region":hole,"alternatives":sorted(regions[hole])},
              "repaired_ids":sorted(repaired),"repaired":repaired_cert,
              "settings":settings,"cross_vertex_matches":matches,
              "sheaves":[{"ids":g,"pair_diagnostics":[[i,j,pair_data[i,j]]
                            for i,j in combinations(g,2)]} for g in groups],
              "protected_winding_lines":sorted(protected-{repair}),"witnesses":witnesses,"trace":trace,
              "retained":sorted(current),"eliminated":sorted(repaired-current),"reduced":final}
    path = OUTPUT.parent / "complementary-sheaf-reduction-1"
    path.mkdir(exist_ok=True)
    atomic_write(path/"flat-40.json",encode(result))
    print("Sheaves",len(groups),"lines",len(original),len(repaired),len(current),flush=True)


if __name__=="__main__":
    run()
