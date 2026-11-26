"""Experimental commitment to the physical source of an adopted extension."""
from functools import cache

from experiments.face_extension_cover import bounds
from experiments.oriented_extension_turns import ExtensionCrawler
from voronoi_app.angular import _inside_prepared, _intersections


class CommittedCrawler(ExtensionCrawler):
    """Each directed track encodes a traversal phase and, when committed, its destination."""

    def phase(self, state):
        i,a,b=state
        track=self.tracks[i]
        if track.wall:
            return "physical",None
        if track.direction(a,b)>0:
            return "uncommitted",None
        return "committed",track.face

    @cache
    def approach_failure(self, track_id, point):
        track=self.tracks[track_id]
        anchor=track.a
        if not self.faces[track.face].blocks:
            return "blocked_approach_destination_is_not_occupied"
        for j in self.walls.tree.query(bounds((point,anchor))):
            f=self.faces[j]
            if _intersections(point,anchor,f.a,f.b)-{point,anchor}:
                return "blocked_approach_intervening_physical_boundary"
        midpoint=tuple((x+y)/2 for x,y in zip(point,anchor))
        if not _inside_prepared(midpoint,self.walls.prepared):
            return "blocked_approach_outside_accessible_interior"
        return None

    def decision(self,incoming,outgoing,sign,vertices):
        i,p,q=incoming
        j,_,r=outgoing
        current,target=self.tracks[i],self.tracks[j]
        phase,destination=self.phase(incoming)
        if phase=="committed":
            if current.away_sign!=-sign:
                return "blocked_approach_wrong_handed_arrival"
            if q!=current.a:
                if i==j and target.direction(q,r)<0:
                    return super().decision(incoming,outgoing,sign,vertices)
                prior=super().decision(incoming,outgoing,sign,vertices)
                if prior=="turn_towards_originating_face":
                    return "turn_prohibited_during_commitment"
                return prior if prior not in {"straight","follow_physical_face"} else "must_continue_committed_line"
            if not target.wall or target.face!=destination:
                return "arrival_requires_destination_face"
            if target.direction(q,r)!=sign:
                return "blocked_approach_wrong_handed_arrival"
            return super().decision(incoming,outgoing,sign,vertices)
        result=super().decision(incoming,outgoing,sign,vertices)
        if result=="turn_towards_originating_face":
            return self.approach_failure(j,q) or result
        return result
