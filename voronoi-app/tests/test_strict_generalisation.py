from fractions import Fraction

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from voronoi_app.batch_routing_reference import MasterNetwork
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.strict_generalisation import RegionalNetwork, corridor_bands, screen_physical_bands


def line(i,a,b):
    p,q = tuple(map(Fraction,a)),tuple(map(Fraction,b))
    return ExactCandidate(i,p,q,p,q,"test")


def test_regional_noding_matches_master_at_shared_atomic_and_overlap_edges():
    lines = [line(0,(0,0),(8,0)),line(1,(2,0),(6,0)),line(2,(4,-2),(4,4))]
    doors = [{"point":(Fraction(3),Fraction(1)),"connectors":[(1,(Fraction(3),Fraction(0)))]},
             {"point":(Fraction(4),Fraction(2)),"connectors":[(2,(Fraction(4),Fraction(1))) ]}]
    ordinary=MasterNetwork(lines,doors)
    fast=RegionalNetwork(MasterNetwork(lines,[]),doors)
    for chosen in ({0,1,2},{1,2},{0,2},{0,1}):
        assert fast.options(chosen)==ordinary.options(chosen)
        assert fast.route(chosen,False)==pytest.approx(ordinary.route(chosen,False),nan_ok=True)


def test_bank_based_discovery_qualifies_enclosed_long_band_without_fixed_count():
    lines=[line(0,(0,0),(25,0)),line(1,(0,-2),(25,2)),line(2,(0,2),(25,-2))]
    walls=unary_union([box(0,-5,25,-3),box(0,3,25,5)])
    discovered=corridor_bands(lines,walls)
    assert len(discovered)==1
    assert discovered[0]["profile"]["two_banks"]==9
    assert discovered[0]["pairs"]==[(1,2)]
    assert corridor_bands(lines,box(0,3,25,5))==[]


def test_physical_screen_rejects_a_crossing_between_banked_sections():
    walls=[box(0,-5,25,-3),box(0,3,25,5),box(11,-.3,11.2,.3)]
    result=screen_physical_bands(
        {"settlement":{"polygons_wkb":{str(i):p.wkb_hex for i,p in enumerate(walls)},
                       "building_labels":{str(i):i+1 for i in range(len(walls))},"dyad_open_cells":[]},
         "topology":{"occupied_wkb":unary_union(walls).wkb_hex}},
        {"axes":[[(0,0),(25,0)]],"options":{"route_ranked":[[3,.2,10,[1,2]]]}}
    ).output
    assert result["bands"][0]["building_banked_sections"]==9
    assert result["bands"][0]["crosses_occupied_interior"]
    assert result["winners"]["route_ranked"] is None
