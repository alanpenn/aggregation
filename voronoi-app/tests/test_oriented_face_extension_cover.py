from fractions import Fraction as F

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from experiments.face_extension_cover import examine_component
from experiments.flat40_oriented_face_audit import audit, semantic_faces, side
from experiments.oriented_face_extension_cover import checked_cover, classify_support
from voronoi_app.angular import _exact_point


@pytest.mark.parametrize("blocks",[
    [box(2,2,3,5),box(5,2,6,5)],
    [box(2,2,4,4),box(4,4,6,6)],
    [Polygon([(2,2),(5,2),(5,3),(3,3),(3,5),(2,5)])],
    [box(2,2,4,4)],
],ids=["opposing-faces","vertex-contact","concave-block","enclosed-island"])
def test_oriented_cover_preserves_exact_open_space(blocks):
    frame=box(0,0,8,8)
    domain=frame.difference(unary_union(blocks))
    named=[(str(i),poly) for i,poly in enumerate(blocks)]
    # The independent obstacle clipping receives the original fixture cells.
    occupied={i:p for i,p in enumerate(blocks)}
    raw=examine_component(domain,named,occupied)
    result=audit(raw,named,frame)
    corrected=checked_cover(raw,result,domain,occupied)
    assert set(corrected["regions"])==set(raw["regions"])
    assert corrected["exact_uncovered_area"]=="0"
    assert not corrected["rejected"]
    assert all(F(row["min_signed"])>=0 for region in corrected["regions"].values()
               for row in region["physical_supports"])


def test_reversed_ring_order_keeps_the_occupied_face_normal():
    a=box(0,0,2,2)
    b=Polygon(list(a.exterior.coords)[::-1])
    target={"face":[["0","0"],["2","0"]]}
    def make(p):
        r=list(p.exterior.coords)
        index=next(i for i,(s,t) in enumerate(zip(r,r[1:])) if {s,t}=={(0.,0.),(2.,0.)})
        return semantic_faces([("block",p)],{f"block:{index}:0":target})[f"block:{index}:0"]
    face=make(a)
    assert face["outward_normal"]==make(b)["outward_normal"]
    open_triangle=list(map(_exact_point,[(0,0),(2,0),(1,-1)]))
    behind=list(map(_exact_point,[(0,0),(2,0),(1,1)]))
    assert side(face,open_triangle)[0]==0
    assert classify_support(face,open_triangle,physical=True)=="valid_physical_support"
    assert classify_support(face,behind,physical=True)=="invalid_physical_support"
    assert classify_support(face,behind,physical=False)=="backward_extension_context"
