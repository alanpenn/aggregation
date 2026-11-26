"""Construct convex regions by crawling physical boundaries and straight extensions."""
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction as F
from functools import cache, cmp_to_key
from itertools import pairwise

from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from experiments.face_extension_cover import bounds, hull
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed
from voronoi_app.angular import (
    _cross, _direction, _exact_point, _inside_prepared, _intersections,
    _on_segment, _prepare_polygon,
)
from voronoi_app.region_incidence_angular import halfplanes, positive_interior
from voronoi_app.exact_axial import _compare_directions


@dataclass(frozen=True)
class Face:
    identifier: int
    a: tuple
    b: tuple
    blocks: tuple
    ring: int

    def signed(self, p):
        # Rings are canonically oriented with accessible interior on the left.
        return _cross(_direction(self.a,self.b),_direction(self.a,p))

    def record(self):
        dx,dy=_direction(self.a,self.b)
        return {"id":self.identifier,"endpoints":packed((self.a,self.b)),
                "occupied_blocks":self.blocks,"ring":self.ring,
                "outward_normal":list(map(str,(-dy,dx))),
                "directed_states":["anticlockwise","clockwise"]}


def physical_faces(domain, blocks=()):
    candidates=[]
    tags=[]
    for name,block in blocks:
        for boundary in (block.exterior,*block.interiors):
            for a,b in pairwise(list(map(_exact_point,boundary.coords))):
                candidates.append((a,b))
                tags.append(name)
    index=STRtree([bounds(s) for s in candidates])
    polygon=orient(domain,sign=1)
    records=[]
    for ring_id,boundary in enumerate((polygon.exterior,*polygon.interiors)):
        for a,b in pairwise(list(map(_exact_point,boundary.coords))):
            # Keep every real boundary endpoint, including face contact changes.
            vertices={a,b}
            overlaps=[]
            for i in index.query(bounds((a,b))):
                hit=_intersections(a,b,*candidates[i])
                if len(hit)==2:
                    ends=tuple(sorted(hit))
                    overlaps.append((ends,tags[i]))
                    vertices.update(hit)
            order=sorted(vertices,reverse=a>b)
            for p,q in pairwise(order):
                owners=tuple(sorted({tag for (u,v),tag in overlaps
                                     if _on_segment(p,u,v) and _on_segment(q,u,v)}))
                records.append(Face(len(records),p,q,owners,ring_id))
    return records


def permits_turn(incoming, outgoing, sign):
    turn=sign*_cross(incoming,outgoing)
    return turn>0 or (not turn and sum(x*y for x,y in zip(incoming,outgoing))>0)


class Crawler:
    def __init__(self,domain,blocks=()):
        self.faces=physical_faces(domain,blocks)
        self.domain=domain
        self.prepared=_prepare_polygon(domain)
        self.tree=STRtree([bounds((f.a,f.b)) for f in self.faces])
        self.extent=F(max(domain.bounds[2]-domain.bounds[0],domain.bounds[3]-domain.bounds[1]))+1

    def departures(self,p,sign,*,include_interior=False):
        for j in sorted(self.tree.query(bounds((p,p)))):
            face=self.faces[j]
            a,b=(face.a,face.b) if sign==1 else (face.b,face.a)
            if p==a or (include_interior and p!=b and _on_segment(p,a,b)):
                yield int(j),b

    @cache
    def ray_hit(self,p,incoming):
        d=tuple(t*self.extent/max(map(abs,incoming)) for t in incoming)
        tip=tuple(x+t for x,t in zip(p,d))
        axis=0 if d[0] else 1
        events={}
        for j in self.tree.query(bounds((p,tip))):
            for q in _intersections(p,tip,self.faces[j].a,self.faces[j].b):
                if q!=p:
                    t=(q[axis]-p[axis])/d[axis]
                    events.setdefault(t,set()).add(int(j))
        if not events:
            return None
        t=min(events)
        hit=tuple(x+t*y for x,y in zip(p,d))
        midpoint=tuple((x+y)/2 for x,y in zip(p,hit))
        if not _inside_prepared(midpoint,self.prepared):
            return None
        return hit,sorted(events[t])

    def walk(self,origin,sign, *, start=None):
        face=self.faces[origin]
        if start is None:
            start=face.a if sign==1 else face.b
        state=(start,origin)
        initial=state
        seen=set()
        supports=set()
        vertices=[start]
        path=[]

        def next_face(point, incoming, *, interior=False):
            candidates=[]
            for j,z in self.departures(point,sign,include_interior=interior):
                outgoing=_direction(point,z)
                if (permits_turn(incoming,outgoing,sign)
                        and all(self.faces[j].signed(v)>=0 for v in vertices)
                        and all(self.faces[k].signed(z)>=0 for k in supports)):
                    # Coordinates in the incoming ray's frame. Mirroring
                    # makes both handedness cases use the same exact order.
                    dot=sum(x*y for x,y in zip(incoming,outgoing))
                    candidates.append((j,z,(dot,sign*_cross(incoming,outgoing))))
            if not candidates:
                return None
            return min(candidates,key=cmp_to_key(
                lambda lhs,rhs:_compare_directions(lhs[2],rhs[2])) )[:2]

        while state not in seen:
            seen.add(state)
            p,i=state
            face=self.faces[i]
            q=face.b if sign==1 else face.a
            return_on_origin=i==origin and p!=start and _on_segment(start,p,q)
            if return_on_origin:
                q=start
            if any(face.signed(v)<0 for v in vertices) or any(self.faces[j].signed(q)<0 for j in supports):
                return None,path,"physical_halfplane_conflict"
            supports.add(i)
            vertices.append(q)
            incoming=_direction(p,q)
            path.append({"type":"physical_face","face":i,"interval":packed((p,q))})
            if return_on_origin:
                state=initial
                break
            choice=next_face(q,incoming)
            if choice:
                j,z=choice
                path.append({"type":"ordinary_corner" if _cross(incoming,_direction(q,z)) else "collinear_corner",
                             "point":packed([q])[0],"next_face":j})
                state=(q,j)
                continue
            if any(permits_turn(incoming,_direction(q,z),sign) for _,z in self.departures(q,sign)):
                return None,path,"ordinary_corner_conflicts_with_active_support"
            # A right turn would violate convexity in the left-interior walk.
            # A ray ignores all invented lines and ends at a physical boundary.
            hit=self.ray_hit(q,incoming)
            if not hit:
                return None,path,"reentrant_extension_blocked"
            r,contacts=hit
            path.append({"type":"straight_extension","trigger":"reentrant_corner","face":i,
                         "interval":packed((q,r)),"physical_hit_faces":contacts})
            for previous in path[:-1]:
                if previous["type"]!="straight_extension":
                    continue
                a,b=(tuple(map(F,p)) for p in previous["interval"])
                crossings=_intersections(q,r,a,b)-{q}
                if crossings:
                    path.append({"type":"meeting_active_extension","points":packed(sorted(crossings)),
                                 "other_interval":previous["interval"]})
                    return None,path,"extension_meets_active_path"
            if any(self.faces[j].signed(r)<0 for j in supports):
                return None,path,"extension_halfplane_conflict"
            vertices.append(r)
            choice=next_face(r,incoming,interior=True)
            if not choice:
                return None,path,"no_convex_departure_at_hit"
            j,_=choice
            path.append({"type":"resume_on_physical_boundary","point":packed([r])[0],"next_face":j})
            state=(r,j)
        if state!=initial or vertices[-1]!=start:
            return None,path,"revisited_other_directed_state"
        path.append({"type":"closed_directed_state","face":origin,"point":packed([start])[0]})
        if len(set(vertices[:-1]))!=len(vertices)-1:
            return None,path,"repeated_vertex_before_closure"
        shape=hull(vertices[:-1])
        walked_area=abs(sum(_cross(a,b) for a,b in pairwise(vertices)))/2
        if len(shape)<3 or walked_area<=0 or walked_area!=exact_area(list(shape)):
            return None,path,"not_simple_convex"
        # Check the unsimplified boundary as well as area and convex hull.
        segments=list(pairwise(vertices))
        for i,(a,b) in enumerate(segments):
            for j in range(i+1,len(segments)):
                if j==i+1 or (i==0 and j==len(segments)-1):
                    continue
                if _intersections(a,b,*segments[j]):
                    return None,path,"self_intersection"
        planes=halfplanes(list(shape)+[shape[0]])
        centre=tuple(sum(c)/len(shape) for c in zip(*shape))
        lo,hi=tuple(map(min,zip(*shape))),tuple(map(max,zip(*shape)))
        if (not _inside_prepared(centre,self.prepared) or any(
                positive_interior(self.faces[j].a,self.faces[j].b,planes)
                for j in self.tree.query(bounds((lo,hi))))):
            return None,path,"independent_domain_containment_failure"
        return shape,path,"closed"

    def face_records(self):
        records=[]
        segments={}
        for face in self.faces:
            record=face.record()
            record["boundary_kind"]="occupied_face" if face.blocks else "domain_boundary"
            record["supporting_line_extensions"]=[]
            for sign in (1,-1):
                a,b=(face.a,face.b) if sign==1 else (face.b,face.a)
                if hit:=self.ray_hit(b,_direction(a,b)):
                    identifier=f"{face.identifier}:{sign}"
                    segments[identifier]=(b,hit[0])
                    record["supporting_line_extensions"].append({
                        "id":identifier,"interval":packed((b,hit[0])),
                        "physical_hit_faces":hit[1],
                        "termination":"physical_boundary"})
            records.append(record)
        ids=list(segments)
        tree=STRtree([bounds(s) for s in segments.values()])
        for record in records:
            for extension in record["supporting_line_extensions"]:
                i=extension["id"]
                a,b=segments[i]
                contacts=[]
                for k in sorted(tree.query(bounds((a,b)))):
                    j=ids[k]
                    if i==j:
                        continue
                    if points:=_intersections(a,b,*segments[j]):
                        contacts.append({"extension":j,"geometry":packed(sorted(points)),
                                         "kind":"coincidence" if len(points)==2 else "point_contact"})
                extension["other_extensions_not_used_as_stops"]=contacts
        return records

    def construct(self):
        regions={}
        attempts=[]
        starts=set()
        for face in self.faces:
            for sign in (1,-1):
                a,b=(face.a,face.b) if sign==1 else (face.b,face.a)
                starts.add((face.identifier,sign,a))
                # A circuit may start partway through a physical face,
                # at the landing point of a straight wall extension.
                hit=self.ray_hit(b,_direction(a,b))
                if hit:
                    for j,_ in self.departures(hit[0],sign,include_interior=True):
                        starts.add((j,sign,hit[0]))
        for i,sign,start in sorted(starts,key=lambda row:(row[0],-row[1],row[2])):
            shape,path,status=self.walk(i,sign,start=start)
            attempt={"face":i,"start_point":packed([start])[0],
                     "direction":"anticlockwise" if sign==1 else "clockwise",
                     "hand":"right" if sign==1 else "left","status":status,"path":path}
            if shape is not None:
                regions.setdefault(shape,[]).append(len(attempts))
            attempts.append(attempt)
        return regions,attempts,Counter(a["status"] for a in attempts)


def validate_obstacles(shape, occupied):
    planes=halfplanes(list(shape)+[shape[0]])
    return [i for i,polygon in occupied.items()
            if exact_area(convex_intersection(list(map(_exact_point,polygon.exterior.coords)),planes))]
