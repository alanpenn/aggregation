from fractions import Fraction as F

from shapely.geometry import Polygon, box

from experiments.face_extension_cover import arrangement, crawl, edge, examine_component


def p(x,y):
    return F(x),F(y)


def test_exact_noding_and_handed_state_closure():
    raw = {edge(p(0,0),p(4,0)):{"long"}, edge(p(2,0),p(4,0)):{"coincident"},
           edge(p(3,-1),p(3,1)):{"crossing"}}
    graph = arrangement(raw)
    assert set(graph[p(3,0)]) == {p(2,0),p(4,0),p(3,-1),p(3,1)}
    assert graph[p(2,0)][p(3,0)]["sources"] == {"coincident","long"}
    walks, states, _ = crawl(graph)
    assert all(closed for _,_,closed in walks.values())
    assert all(len(s)==2*graph.number_of_edges() for s in states.values())


def test_exact_cover_respects_a_building_island_and_records_all_face_states():
    block = box(2,2,4,4)
    domain = Polygon(box(0,0,6,6).exterior.coords,[block.exterior.coords])
    result = examine_component(domain,[("island",block)],{1:block})
    assert result["partition_certified"]
    assert result["domain_area"] == "32"
    assert "0" not in result["area_by_multiplicity"]
    assert max(map(int,result["area_by_multiplicity"])) >= 2
    assert result["regions"] and not result["rejected"]
    for starts in result["face_starts"].values():
        assert {(r["hand"],r["direction"]) for r in starts} == {
            ("left",0),("left",1),("right",0),("right",1)}
