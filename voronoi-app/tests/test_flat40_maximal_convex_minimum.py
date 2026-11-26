from fractions import Fraction as F
from types import SimpleNamespace

from experiments.flat40_maximal_convex_minimum import Search, lower_bound, valid_exchanges
from experiments.flat40_maximal_convex_minimum_report import ray_hits


def test_exhaustive_pair_screen_admits_distant_substitute():
    study = SimpleNamespace(lines=list(range(5)),regions={"a":{0,4},"b":{1,4},"c":{2,3}},
                            doors=[{0,3,4}])
    study.incidence = [*study.regions.values(),*study.doors]
    study.by_line = [{i for i,g in enumerate(study.incidence) if j in g} for j in range(5)]
    search = Search(study,{"region_order":["a","b","c"]})
    search.assess = lambda ids: "accepted"
    original = frozenset({0,1,2})
    rows = search.one(original,2)
    assert list(valid_exchanges(original,rows)) == [(frozenset({2,4}),(0,1),[4])]
    assert all(sum(r["counts"].values())==2 for r in rows)
    witness = lower_bound(search)
    assert witness["bound"] == 2
    assert witness["maximum_weight_covered_by_a_line"] <= witness["denominator"]


def test_forward_ray_exact_contacts():
    p,d = (F(0),F(0)),(F(1),F(0))
    assert ray_hits(p,d,(F(2),F(-1)),(F(2),F(1)))
    assert ray_hits(p,d,(F(2),F(0)),(F(2),F(1)))
    assert ray_hits(p,d,(F(1),F(0)),(F(2),F(0)))
    assert not ray_hits(p,d,(F(-2),F(-1)),(F(-2),F(1)))
    assert not ray_hits(p,d,(F(0),F(-1)),(F(0),F(1)))
