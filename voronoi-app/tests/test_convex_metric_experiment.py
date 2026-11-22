from fractions import Fraction

from shapely.geometry import box

from voronoi_app.angular import LineClearance
from voronoi_app.batch_routing_reference import MasterNetwork
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.convex_metric_experiment import build_master_doors, combine, connector_points, metric_network
from voronoi_app.region_incidence_angular import halfplanes
from voronoi_app.strict_coverage_experiment import omissions


def p(x,y):
    return Fraction(x),Fraction(y)


def line(i,a,b):
    return ExactCandidate(i,a,b,a,b,"test")


def test_wide_region_keeps_every_traversing_line_and_exact_boundary_stops():
    region=box(0,0,24,12)
    lines=[line(0,p(0,3),p(24,3)),line(1,p(0,8),p(24,8))]
    saved={"doorways":[{"point":["12","0"]}],"doorway_regions":[[1]],
           "region_lines":{"1":[0,1]}}
    clearance=IndexedClearance(LineClearance(region,box(30,30,31,31)))
    doors,evidence,rejected=build_master_doors(lines,saved,{1:region},clearance)
    assert not rejected
    assert {i for i,_ in doors[0]["connectors"]}=={0,1}
    assert {(i,q) for i,q in doors[0]["connectors"] if q[0]==12} == {(0,p(12,3)),(1,p(12,8))}
    assert len(evidence[0])==6


def test_regional_projection_can_differ_from_unconstrained_nearest_point():
    ring=[p(0,0),p(5,0),p(5,10),p(0,10),p(0,0)]
    diagonal=line(0,p(-5,0),p(5,10))
    assert connector_points(p(0,0),diagonal,halfplanes(ring)) == [
        (p(0,5),"nearest"),(p(5,10),"region_boundary"),
    ]


def test_joint_swap_detects_coverage_failure_hidden_by_individual_swaps():
    base=frozenset({1,2,3})
    bands=[{1},{2}]
    regions={162:{1,2}}
    doors=[{1,2}]
    assert omissions(combine(base,bands,[{4},None]),regions,doors)==([],[])
    assert omissions(combine(base,bands,[None,{5}]),regions,doors)==([],[])
    assert omissions(combine(base,bands,[{4},{5}]),regions,doors)==([162],[0])


def test_overlapping_bands_remove_shared_lines_once_and_keep_explicit_reintroductions():
    base=frozenset({1,2,3,4})
    assert combine(base,[{1,2},{2,3}],[{2,8},{9}])=={2,4,8,9}


def test_duplicate_stop_noding_preserves_doorway_ownership_and_distances():
    lines=[line(0,p(0,0),p(8,0)),line(1,p(5,-1),p(5,4))]
    doors=[{"point":p(5,1),"connectors":[(0,p(5,0)),(1,p(5,1))]},
           {"point":p(5,-2),"connectors":[(1,p(5,0))]}]
    ordinary=MasterNetwork(lines,doors)
    deduplicated=metric_network(lines,doors)
    assert ordinary.nodes==deduplicated.nodes
    for chosen in ({0},{1},{0,1}):
        assert ordinary.options(chosen)==deduplicated.options(chosen)
        assert ordinary.route(chosen,False)==deduplicated.route(chosen,False)
