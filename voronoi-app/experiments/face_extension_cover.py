"""Experimental exact planar arrangement and overlapping convex cover."""
from collections import Counter, defaultdict
from functools import cmp_to_key
from fractions import Fraction as F
from hashlib import sha256
from itertools import combinations

import networkx as nx
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from experiments.flat40_region257_inspection import (
    convex_intersection, exact_area, interpolate, packed, ring, shared_parts,
)
from voronoi_app.angular import _cross, _direction, _exact_point, _inside_prepared, _intersections, _prepare_polygon, _ring_location
from voronoi_app.batch_store import encode
from voronoi_app.exact_axial import _compare_directions
from voronoi_app.experimental_visibility import _outward_bounds
from voronoi_app.region_incidence_angular import halfplanes


def edge(a,b):
    return tuple(sorted((a,b)))


def rings(p):
    return [list(map(_exact_point,r.coords)) for r in (p.exterior,*p.interiors)]


def segments(p):
    return [edge(a,b) for r in rings(p) for a,b in zip(r,r[1:])]


def bounds(seg):
    a,b=seg
    return _outward_bounds(tuple(map(min,zip(a,b))),tuple(map(max,zip(a,b))))


def hull(points):
    ordered=sorted(set(points))
    def chain(sequence):
        out=[]
        for p in sequence:
            while len(out)>1 and _cross(_direction(out[-2],out[-1]),_direction(out[-1],p))<=0:
                out.pop()
            out.append(p)
        return out[:-1]
    return tuple(chain(ordered)+chain(reversed(ordered)))


def arrangement(segments):
    graph=nx.Graph()
    keys=sorted(segments)
    tree=STRtree([bounds(s) for s in keys])
    knots=[set(s) for s in keys]
    for i,(a,b) in enumerate(keys):
        for j in tree.query(bounds((a,b))):
            if j<=i:
                continue
            meets=_intersections(a,b,*keys[j])
            if meets:
                knots[i].update(meets)
                knots[j].update(meets)
    for i,s in enumerate(keys):
        ordered=sorted(knots[i])
        for a,b in zip(ordered,ordered[1:]):
            if not graph.has_edge(a,b):
                graph.add_edge(a,b,sources=set())
            graph[a][b]["sources"].update(segments[s])
    return graph


def extensions(part, block_parts):
    boundary=sorted(set(segments(part)))
    prepared=_prepare_polygon(part)
    extent=F(max(part.bounds[2]-part.bounds[0],part.bounds[3]-part.bounds[1]))+1
    tree=STRtree([bounds(s) for s in boundary])
    raw=defaultdict(set)
    for i,s in enumerate(boundary):
        raw[s].add(f"domain-edge:{i}")
    faces={}
    lines={}
    for name,shape in block_parts:
        for i,(a,b) in enumerate(segments(shape)):
            for j in sorted(tree.query(bounds((a,b)))):
                hits=sorted(_intersections(a,b,*boundary[j]))
                if len(hits)!=2:
                    continue
                p,q=hits
                identifier=f"{name}:{i}:{j}"
                faces[identifier]={"block":name,"boundary_edge":int(j),"face":packed(hits)}
                raw[edge(p,q)].add(identifier)
                for direction,(u,v) in enumerate(((p,q),(q,p))):
                    dx,dy=_direction(u,v)
                    scale=extent/max(abs(dx),abs(dy))
                    tip=(v[0]+scale*dx,v[1]+scale*dy)
                    axis=0 if dx else 1
                    hits={}
                    for k in tree.query(bounds((v,tip))):
                        for hit in _intersections(v,tip,*boundary[k]):
                            if hit!=v:
                                t=(hit[axis]-v[axis])/(tip[axis]-v[axis])
                                hits.setdefault(t,set()).add(int(k))
                    if not hits:
                        continue
                    t=min(hits)
                    if not _inside_prepared(interpolate(v,tip,t/2),prepared):
                        continue
                    end=interpolate(v,tip,t)
                    line=f"{identifier}/extension:{direction}"
                    lines[line]={"face":identifier,"direction":direction,"interval":packed((v,end)),
                                 "terminal_boundary_edges":sorted(hits[t])}
                    raw[edge(v,end)].add(line)
    building_edges={record["boundary_edge"] for record in faces.values()}
    minx,miny,maxx,maxy=map(F,part.bounds)
    for record in lines.values():
        terminal=record["terminal_boundary_edges"]
        point=tuple(map(F,record["interval"][1]))
        record["termination"] = ("occupied_face" if building_edges.intersection(terminal) else
                                 "component_bounding_box" if point[0] in (minx,maxx) or point[1] in (miny,maxy)
                                 else "other_accessible_boundary")
    return raw,faces,lines


def crawl(graph):
    angles={a:sorted(graph[a],key=cmp_to_key(lambda u,v:_compare_directions(
        _direction(a,u),_direction(a,v)))) for a in graph}
    recorded={}
    walks={}
    for hand,step in (("right",-1),("left",1)):
        visited={}
        for a in sorted(graph):
            for b in angles[a]:
                start=(a,b)
                if start in visited:
                    continue
                state=start
                path=[]
                local=set()
                while state not in local and state not in visited:
                    local.add(state)
                    path.append(state)
                    u,v=state
                    order=angles[v]
                    state=(v,order[(order.index(u)+step)%len(order)])
                key=len(walks)
                walks[key]=(hand,path,state==start)
                visited.update((s,key) for s in path)
        recorded[hand]=visited
    return walks,recorded,angles


def atoms_and_starts(graph, walks, states, faces, domain):
    prepared=_prepare_polygon(domain)
    statuses=Counter()
    atoms={}
    walk_atoms={}
    for k,(hand,path,closed) in walks.items():
        vertices=[a for a,b in path]
        signed=sum((_cross(a,b) for a,b in path),F(0))
        if not closed:
            statuses["not_closed"]+=1
            continue
        if (hand=="right")!=(signed>0) or not signed:
            statuses["unbounded_or_zero"]+=1
            continue
        if len(vertices)!=len(set(vertices)):
            statuses["repeated_vertex"]+=1
            continue
        p=Polygon([(float(x),float(y)) for x,y in vertices])
        if not p.is_valid or p.is_empty:
            statuses["invalid_simple_polygon"]+=1
            continue
        mark=_exact_point(p.representative_point().coords[0])
        if _ring_location(vertices+vertices[:1],mark)!=1 or not _inside_prepared(mark,prepared):
            statuses["outside_accessible"]+=1
            continue
        ordered=tuple(vertices if signed>0 else reversed(vertices))
        first=min(range(len(ordered)),key=ordered.__getitem__)
        key=ordered[first:]+ordered[:first]
        atom=atoms.setdefault(key,len(atoms))
        walk_atoms[k]=atom
        statuses["accessible_cycle"]+=1
    provenance=defaultdict(list)
    for a,b,data in graph.edges(data=True):
        for source in sorted(set(faces)&data["sources"]):
            for hand,index in states.items():
                for direction,(u,v) in enumerate(((a,b),(b,a))):
                    walk=index[u,v]
                    if walk in walk_atoms:
                        provenance[walk_atoms[walk]].append((source,hand,direction,walk))
    return list(atoms),walk_atoms,provenance,statuses


def generated(atoms, graph, walks, walk_atoms, provenance):
    touching=[set() for _ in atoms]
    edges=defaultdict(set)
    for k,(_,path,_) in walks.items():
        if k in walk_atoms:
            for s in path:
                edges[edge(*s)].add(walk_atoms[k])
    for members in edges.values():
        for a,b in combinations(members,2):
            touching[a].add(b)
            touching[b].add(a)
    areas=[exact_area(list(a)) for a in atoms]
    results={}
    for seed,vertices in enumerate(atoms):
        if exact_area(list(hull(vertices)))!=areas[seed]:
            continue
        for reverse in (False,True):
            members={seed}
            shape=hull(vertices)
            area=areas[seed]
            front=set(touching[seed])
            while front:
                for candidate in sorted(front,reverse=reverse):
                    joined=hull((*shape,*atoms[candidate]))
                    if exact_area(list(joined))==area+areas[candidate]:
                        shape=joined
                        area+=areas[candidate]
                        members.add(candidate)
                        front=(front|touching[candidate])-members
                        break
                else:
                    break
            results.setdefault(shape,{"atoms":sorted(members),"starts":[]})["starts"].append(
                {"seed":seed,"reverse_growth_order":reverse,"face_states":provenance[seed]})
    # Every valid larger candidate has already passed convex union by area.
    # Keep inclusion-maximal candidate atom sets within this component.
    accepted={}
    sets=[]
    for poly,item in sorted(results.items(),key=lambda value:(-len(value[1]["atoms"]),value[0])):
        membership=set(item["atoms"])
        if any(membership<other for other in sets):
            continue
        sets.append(membership)
        key=sha256(encode(packed(poly))).hexdigest()[:16]
        accepted[key]=item|{"vertices":packed(poly),"area":str(exact_area(list(poly)))}
    return accepted


def examine_component(part, block_parts, occupied, *, arrangement_observer=None):
    raw,faces,lines=extensions(part,block_parts)
    graph=arrangement(raw)
    if arrangement_observer:
        arrangement_observer(graph, faces, lines)
    walks,states,angles=crawl(graph)
    atoms,walk_atoms,provenance,statuses=atoms_and_starts(graph,walks,states,faces,part)
    print("Arrangement",len(faces),"faces",len(lines),"extensions",len(atoms),"accessible atoms",flush=True)
    areas=[exact_area(list(a)) for a in atoms]
    region_map=generated(atoms,graph,walks,walk_atoms,provenance)
    print("Growth",len(region_map),"regions",flush=True)
    candidates={}
    rejections={}
    obstacle_rings={i:ring(p) for i,p in occupied.items()}
    obstacle_index=STRtree(list(occupied.values()))
    ids=list(occupied)
    prepared=_prepare_polygon(part)
    multiplicity=[0]*len(atoms)
    for key,record in region_map.items():
        points=[tuple(map(F,q)) for q in record["vertices"]]
        polygon=Polygon([(float(x),float(y)) for x,y in points])
        planes=halfplanes(points+points[:1])
        rejected=[]
        for index in obstacle_index.query(bounds((tuple(map(min,zip(*points))),tuple(map(max,zip(*points)))))):
            i=ids[index]
            if exact_area(convex_intersection(obstacle_rings[i],planes)):
                rejected.append(i)
        # Size/containment by noded accessible-face union was tested exactly
        # during convex growth. Check a rational interior point independently.
        centre=tuple(sum(v)/len(points) for v in zip(*points))
        if rejected or not _inside_prepared(centre,prepared):
            rejections[key]={"occupied_cells":rejected,"interior_point_in_domain":_inside_prepared(centre,prepared)}
            continue
        candidates[key]=record
        for i in record["atoms"]:
            multiplicity[i]+=1
    domain_area=exact_area(rings(part)[0])-sum(exact_area(r) for r in rings(part)[1:])
    atom_edges=Counter(edge(a,b) for vertices in atoms
                       for a,b in zip(vertices,vertices[1:]+vertices[:1]))
    bad_edges=[packed((a,b)) for a,b,row in graph.edges(data=True)
               if atom_edges[edge(a,b)]!=(1 if any(s.startswith("domain-edge:") for s in row["sources"]) else 2)]
    partition=nx.is_connected(graph) and domain_area==sum(areas) and not bad_edges
    area_bands=defaultdict(F)
    for m,area in zip(multiplicity,areas):
        area_bands[m]+=area
    edge_records=[{"edge":packed((a,b)),"sources":sorted(row["sources"])}
                  for a,b,row in graph.edges(data=True)]
    for name,row in lines.items():
        row["intersects_sources"]=sorted({source for a,neighbors in graph.adjacency()
            if any(name in record["sources"] for record in neighbors.values())
            for record in neighbors.values() for source in record["sources"] if source!=name})
    starts=defaultdict(list)
    for a,b,row in graph.edges(data=True):
        for source in sorted(set(faces)&row["sources"]):
            for hand,index in states.items():
                for direction,(u,v) in enumerate(((a,b),(b,a))):
                    starts[source].append({"hand":hand,"direction":int(u>v),"edge":packed((u,v)),
                                           "walk":index[u,v],"atom":walk_atoms.get(index[u,v])})
    return {"domain_area":str(domain_area),"atom_area":str(sum(areas)),"partition_certified":partition,"partition_edge_disagreements":bad_edges,
            "faces":faces,"extensions":lines,"edges":edge_records,
            "angles":[{"point":packed([p])[0],"incident_ccw":packed(neighbors)} for p,neighbors in angles.items()],
            "walks":{str(k):{"hand":h,"path":packed([a for a,b in path]),"closed":closed,
                             "atom":walk_atoms.get(k)} for k,(h,path,closed) in walks.items()},
            "face_starts":dict(starts),"statuses":dict(statuses),"regions":candidates,
            "rejected":rejections,"area_by_multiplicity":{str(k):str(v) for k,v in area_bands.items()},
            "atoms":[{"vertices":packed(a),"area":str(area),"multiplicity":m}
                     for a,area,m in zip(atoms,areas,multiplicity)]}
