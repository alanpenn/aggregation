from fractions import Fraction as F

from shapely.geometry import box

from experiments.directed_boundary_reference import LOW, UP
from experiments.oriented_extension_reference import JUNCTION, TARGET, at_junction, check_references
from voronoi_app.angular import _cross, _direction


def test_reference_crawls_and_mirror_open_space_turn():
    _,room,_,room_cover,crawler,regions,rejections,cover,exemplars=check_references()
    assert set(room)=={LOW,UP}
    assert room_cover["covered_area"]=="20"
    assert cover["covered_area"]=="49"
    assert cover["uncovered_area"]=="0"
    assert len(regions)==7
    assert {p["sign"] for p in regions[TARGET]}=={-1,1}
    assert rejections["wrong_building_side_at_origin"]>0

    for sign,path in exemplars.items():
        incoming,chosen,_,options=at_junction(path)[0]
        assert incoming[2]==chosen[1]==JUNCTION
        a,b=_direction(*incoming[1:]),_direction(*chosen[1:])
        assert sign*_cross(a,b)>0
        assert all(x*y==0 for x,y in zip(a,b))  # orthogonal, all displacement is on different axes
        assert not crawler.tracks[chosen[0]].wall
        assert any(status=="straight" for _,status in options)
        assert any(t[0]==chosen[0] and status=="away_from_originating_face"
                   for t,status in options)


def test_independent_occupied_island_check_rejects_target_cycle():
    _,_,_,_,crawler,_,_,_,exemplars=check_references()
    path=exemplars[1]
    vertices=[tuple(map(F,v)) for v in path["points"]]
    assert crawler.valid_cycle(vertices,[],{"extra island":box(2,2,3,3)}) is None
