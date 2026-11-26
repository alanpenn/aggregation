"""Face-committed traversal with explicit inward-oriented external walls."""
from functools import cache

from experiments.committed_extension_turns import CommittedCrawler
from experiments.directed_boundary_cover import permits_turn
from experiments.face_extension_cover import bounds
from voronoi_app.angular import _cross, _direction, _inside_prepared, _intersections


class ExternalCommittedCrawler(CommittedCrawler):
    def __init__(self, domain, blocks=(), *, external_boundary=None):
        super().__init__(domain,blocks)
        self.external={f.identifier for f in self.faces if f.ring==0 and not f.blocks
                       and (external_boundary is None or external_boundary(f))}
        # Start at each physical face's actual endpoint and at physical
        # landings of extensions. Pure extension intersections are not origins.
        landings={t.b for t in self.tracks if not t.wall}
        self._starts=[(sign,state) for sign,state in super().starts()
            if state[1] in (self.faces[self.tracks[state[0]].face].a,
                            self.faces[self.tracks[state[0]].face].b)
            or state[1] in landings]

    def starts(self):
        return self._starts

    @cache
    def approach_failure(self, track_id, point):
        track=self.tracks[track_id]
        if track.face not in self.external:
            return super().approach_failure(track_id,point)
        a=track.a
        for j in self.walls.tree.query(bounds((point,a))):
            f=self.faces[j]
            if _intersections(point,a,f.a,f.b)-{point,a}:
                return "blocked_approach_intervening_physical_boundary"
        midpoint=tuple((x+y)/2 for x,y in zip(point,a))
        return None if _inside_prepared(midpoint,self.walls.prepared) else (
            "blocked_approach_outside_accessible_interior")

    def decision(self,incoming,outgoing,sign,vertices):
        result=super().decision(incoming,outgoing,sign,vertices)
        if result!="extension_parent_is_not_an_occupied_face":
            return result
        i,p,q=incoming
        j,_,r=outgoing
        candidate=self.tracks[j]
        if candidate.face not in self.external or self.phase(incoming)[0]=="committed":
            return result
        before,after=_direction(p,q),_direction(q,r)
        if (not permits_turn(before,after,sign) or not _cross(before,after)
                or candidate.direction(q,r)>=0 or candidate.away_sign!=-sign):
            return "external_extension_direction_or_turn_conflict"
        if any(self.faces[candidate.face].signed(v)<0 for v in vertices):
            return "inward_support_conflict"
        return self.approach_failure(j,q) or "turn_towards_originating_face"
