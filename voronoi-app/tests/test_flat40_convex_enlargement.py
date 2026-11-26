from fractions import Fraction as F

from shapely.geometry import Polygon, box

from experiments.face_extension_cover import hull
from experiments.flat40_convex_enlargement import Checker, edge_attempts
from experiments.flat40_enlarged_cover import blocked_facets, exact_overlap
from experiments.flat40_region257_inspection import packed


def points(vertices):
    return [(F(x),F(y)) for x,y in vertices]


def test_free_coordinate_enlargement_and_enclosed_island_rejection():
    island=box(4,4,6,6)
    frame=box(0,0,10,10)
    domain=frame.difference(island)
    checker=Checker(domain,{1:island})
    original=hull(points([(1,1),(3,1),(3,3),(1,3)]))
    a,b=points([(3,1),(3,3)])
    valid=edge_attempts(original,a,b,checker,exhaustive=True)
    assert valid and F(valid["added_area"])>0
    assert checker.witness(original,hull(points([(1,1),(8,1),(8,8),(1,8)])),independent=True) is None
    assert checker.witness(original,hull(points([(-1,1),(3,1),(3,3),(-1,3)])),independent=True) is None


def test_integer_overlap_from_exact_boundary_jumps():
    left=hull(points([(0,0),(3,0),(3,2),(0,2)]))
    right=hull(points([(1,0),(4,0),(4,2),(1,2)]))
    atoms,bands=exact_overlap(box(0,0,4,2),[],{"left":{"vertices":packed(left)},
                                                        "right":{"vertices":packed(right)}})
    assert bands[0]==0 and bands[1]==bands[2]==4
    assert all(a["multiplicity"] in (1,2) for a in atoms)
    _,display=exact_overlap(box(0,0,4,2),[],{"left":{"vertices":packed(left)},
                                            "right":{"vertices":packed(right)}},
                            compressed=True)
    assert display=={"exact_domain_area":"8","areas_approx":{"0":0.,"1":4.,"2":4.}}


def test_only_real_domain_contacts_prove_blocked_facets():
    checker=Checker(box(0,0,4,4),{})
    frame=hull(points([(0,0),(4,0),(4,4),(0,4)]))
    truncated=hull(points([(0,0),(3,0),(3,4),(0,4)]))
    assert len(blocked_facets(checker,frame))==4
    assert blocked_facets(checker,truncated) is None
