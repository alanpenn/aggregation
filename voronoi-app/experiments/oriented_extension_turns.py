"""Directed wall crawler with provenance-checked turns onto face extensions."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import pairwise

from experiments.directed_boundary_cover import Crawler, permits_turn, validate_obstacles
from experiments.face_extension_cover import bounds, hull
from shapely.strtree import STRtree
from experiments.flat40_region257_inspection import exact_area, packed
from voronoi_app.angular import _cross, _direction, _inside_prepared, _intersections
from voronoi_app.region_incidence_angular import halfplanes, positive_interior


ADMISSIBLE={"straight","follow_physical_face","straight_extension_from_wall",
            "turn_towards_originating_face"}


@dataclass(frozen=True)
class Track:
    """A wall, or a ray whose first endpoint is its physical origin."""
    id: int
    face: int
    a: tuple
    b: tuple
    wall: bool
    # Handed state in which motion away from the anchor continues the wall.
    away_sign: int = 0

    def direction(self, p, q):
        return 1 if (p < q) == (self.a < self.b) else -1


class ExtensionCrawler:
    def __init__(self, domain, blocks=()):
        self.walls = Crawler(domain,blocks)
        self.faces = self.walls.faces
        self.tracks = [Track(f.identifier,f.identifier,f.a,f.b,True) for f in self.faces]
        for f in self.faces:
            for sign,(a,b) in ((1,(f.a,f.b)),(-1,(f.b,f.a))):
                if hit:=self.walls.ray_hit(b,_direction(a,b)):
                    self.tracks.append(Track(len(self.tracks),f.identifier,b,hit[0],False,sign))
        splits=[{t.a,t.b} for t in self.tracks]
        tree=STRtree([bounds((t.a,t.b)) for t in self.tracks])
        for a in self.tracks:
            for j in tree.query(bounds((a.a,a.b))):
                if j<=a.id:
                    continue
                b=self.tracks[j]
                contacts=_intersections(a.a,a.b,b.a,b.b)
                splits[a.id].update(contacts)
                splits[b.id].update(contacts)
        self.outgoing=defaultdict(list)
        for t,points in zip(self.tracks,splits):
            for a,b in pairwise(sorted(points)):
                self.outgoing[a].append((t.id,a,b))
                self.outgoing[b].append((t.id,b,a))

    def decision(self, incoming, outgoing, sign, vertices):
        i,p,q=incoming
        j,_,r=outgoing
        current,candidate=self.tracks[i],self.tracks[j]
        before,after=_direction(p,q),_direction(q,r)
        own_departure=(current.wall and current.face==candidate.face and q==candidate.a
                       and candidate.away_sign==sign and _cross(before,after)==0)
        if i!=j and not candidate.wall and candidate.direction(q,r)>0 and not own_departure:
            return "away_from_originating_face"
        if not permits_turn(before,after,sign):
            return "wrong_turn_or_reversal"
        if i==j:
            return "straight"
        if candidate.wall:
            if candidate.direction(q,r)!=sign:
                return "wrong_wall_direction"
            if not current.wall and q not in (current.a,current.b):
                return "no_physical_boundary_stop"
            if (not current.wall and q==current.a and current.direction(p,q)<0
                    and current.face!=candidate.face):
                return "must_reach_originating_face"
            event="follow_physical_face"
        else:
            direction=candidate.direction(q,r)
            if direction>0:
                # A ray may start away from its own physical face, but may
                # never be joined in the away direction from another track.
                if not own_departure:
                    return "away_from_originating_face"
                event="straight_extension_from_wall"
            else:
                if not self.faces[candidate.face].blocks:
                    return "extension_parent_is_not_an_occupied_face"
                if candidate.away_sign!=-sign:
                    return "wrong_building_side_at_origin"
                if not _cross(before,after):
                    return "collinear_track_switch"
                event="turn_towards_originating_face"
        if any(self.faces[candidate.face].signed(v)<0 for v in vertices):
            return "inward_support_conflict"
        return event

    def valid_cycle(self, vertices, supports, occupied):
        poly=hull(vertices[:-1])
        if len(poly)<3 or len(set(vertices[:-1]))!=len(vertices)-1:
            return None
        area=abs(sum(_cross(a,b) for a,b in pairwise(vertices)))/2
        if area<=0 or area!=exact_area(list(poly)):
            return None
        if any(f.signed(v)<0 for f in supports for v in poly):
            return None
        segments=list(pairwise(vertices))
        for i,(a,b) in enumerate(segments):
            for j in range(i+2,len(segments)):
                if i==0 and j==len(segments)-1:
                    continue
                if _intersections(a,b,*segments[j]):
                    return None
        centre=tuple(sum(x)/len(poly) for x in zip(*poly))
        planes=halfplanes(list(poly)+[poly[0]])
        if (not _inside_prepared(centre,self.walls.prepared)
                or any(positive_interior(f.a,f.b,planes) for f in self.faces)
                or validate_obstacles(poly,occupied)):
            return None
        return poly

    def starts(self):
        states=sorted(x for group in self.outgoing.values() for x in group)
        return [(sign,state) for sign in (1,-1) for state in states
                if self.tracks[state[0]].wall and self.tracks[state[0]].direction(*state[1:])==sign]

    def traverse(self, initial, sign, occupied, stack=None):
        i,a,b=initial
        wall=self.tracks[i]
        if stack is None:
            stack=[((initial,),(a,b),frozenset({wall.face}),())]
        while stack:
            route,vertices,support_ids,history=stack.pop()
            current=route[-1]
            q=vertices[-1]
            options=[]
            for candidate in self.outgoing[q]:
                status=self.decision(current,candidate,sign,vertices)
                _,_,r=candidate
                if status in ADMISSIBLE:
                    if any(self.faces[f].signed(r)<0 for f in support_ids):
                        status="active_support_conflict"
                    elif candidate!=initial and r in vertices and r!=a:
                        status="repeated_vertex"
                    elif candidate!=initial and candidate in route:
                        status="repeated_state"
                    elif candidate!=initial and any(
                        _intersections(q,r,u,v) - ({a} if r==a else set())
                        for u,v in pairwise(vertices[:-1])):
                        status="self_crossing"
                options.append((candidate,status))
            closed=[]
            rejections=Counter()
            for candidate,status in options:
                if status not in ADMISSIBLE:
                    rejections[status]+=1
                    continue
                recorded=history+((current,candidate,status,tuple(options)),)
                if candidate==initial:
                    poly=self.valid_cycle(vertices,[self.faces[f] for f in support_ids],occupied)
                    if poly is not None:
                        closed.append((poly,{"sign":sign,"tracks":[j for j,_,_ in route],
                                             "points":packed(vertices),"transitions":recorded}))
                    else:
                        rejections["invalid_cycle"]+=1
                    continue
                j,_,r=candidate
                stack.append((route+(candidate,),vertices+(r,),support_ids|{self.tracks[j].face},recorded))
            yield route,tuple(options),closed,rejections,stack

    def construct(self, occupied=None):
        occupied={} if occupied is None else occupied
        rejects=Counter()
        regions=defaultdict(list)
        self.branch_log=[]
        for sign,initial in self.starts():
            for route,options,closed,rejection,_ in self.traverse(initial,sign,occupied):
                extensions={c[0] for c,_ in options if not self.tracks[c[0]].wall}
                if (len(extensions)>1 or sum(status in ADMISSIBLE for _,status in options)>1
                        or any(status=="turn_towards_originating_face" for _,status in options)):
                    self.branch_log.append((sign,route,options))
                for poly,path in closed:
                    regions[poly].append(path)
                rejects.update(rejection)
        return dict(regions),dict(rejects)
