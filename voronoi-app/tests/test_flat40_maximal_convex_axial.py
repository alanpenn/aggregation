from fractions import Fraction as F
from types import SimpleNamespace

from experiments.flat40_maximal_convex_axial import exact_incidence, variant


def test_incidence_requires_positive_length_in_the_strict_interior():
    region = [(F(0),F(0)),(F(1),F(0)),(F(1),F(1)),(F(0),F(1))]
    segments = [((-1,0),(2,0)),((-1,-1),(0,0)),((-1,F(1,2)),(2,F(1,2))),
                ((F(1,2),F(1,2)),(F(1,2),F(1,2))),((2,2),(3,3))]
    lines = [SimpleNamespace(start=tuple(map(F,a)),end=tuple(map(F,b))) for a,b in segments]
    matrix = exact_incidence(lines,{"square":region})
    assert matrix["by_region"] == {"square":[2]}
    assert matrix["singleton"] == {"square":2}
    assert matrix["by_candidate"] == {0:[],1:[],2:["square"],3:[],4:[]}


def test_cover_variant_preserves_frozen_doorways_and_candidate_identity():
    study = SimpleNamespace(lines=[object(),object()],doors=[frozenset({0})],
                            regions={0:frozenset({0})},graph=object(),winding=object())
    adapted = variant(study,{"region_order":["polygon"],"by_region":{"polygon":[1]}})
    assert adapted.lines is study.lines
    assert adapted.doors is study.doors
    assert adapted.graph is study.graph
    assert adapted.winding is study.winding
    assert adapted.incidence == [frozenset({1}),frozenset({0})]
    assert adapted.by_line == [{1},{0}]
    assert study.regions == {0:frozenset({0})}
