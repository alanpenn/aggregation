from fractions import Fraction as F

from shapely.geometry import Polygon

from experiments.directed_boundary_cover import Crawler
from experiments.flat40_region257_inspection import convex_intersection, exact_area
from voronoi_app.region_incidence_angular import halfplanes

L_ROOM=Polygon([(0,0),(6,0),(6,2),(2,2),(2,6),(0,6)])
LOW=((0,0),(6,0),(6,2),(0,2))
UP=((0,0),(2,0),(2,6),(0,6))


def test_l_room_closes_two_rectangles_using_only_directed_walls():
    from experiments.flat40_enlarged_cover import blocked_facets
    from experiments.flat40_convex_enlargement import Checker
    crawler=Crawler(L_ROOM)
    regions,attempts,_=crawler.construct()
    assert set(regions)=={LOW,UP}
    for shape, ids in regions.items():
        assert exact_area(list(shape))==12
        assert len(blocked_facets(Checker(L_ROOM,{}),list(shape)))==4
        assert {attempts[i]["direction"] for i in ids}=={
            "anticlockwise" if shape==LOW else "clockwise"}
        for i in ids:
            extensions=[event for event in attempts[i]["path"] if event["type"]=="straight_extension"]
            assert len(extensions)==1
            assert extensions[0]["interval"]==(
                [["2","2"],["0","2"]] if shape==LOW else [["2","2"],["2","0"]])
    assert exact_area(convex_intersection(list(LOW),halfplanes(list(UP)+[UP[0]])))==F(4)
    assert 12+12-4==20


def test_rational_overlay_can_verify_zero_coverage_around_an_island():
    from shapely.geometry import box
    from experiments.flat40_directed_boundary import exact_coverage
    from experiments.directed_boundary_cover import validate_obstacles

    island=box(2,2,4,4)
    domain=box(0,0,6,6).difference(island)
    shape=tuple((F(x),F(y)) for x,y in ((0,0),(6,0),(6,2),(0,2)))
    result=exact_coverage(domain,[shape])
    assert result["domain_area"]=="32"
    assert result["covered_area"]=="12"
    assert result["uncovered_area"]=="20"
    assert not validate_obstacles(shape,{1:island})
    around=tuple((F(x),F(y)) for x,y in ((0,0),(6,0),(6,6),(0,6)))
    assert validate_obstacles(around,{1:island})==[1]


def test_extension_records_do_not_flip_physical_normals():
    records=Crawler(L_ROOM).face_records()
    for record in records:
        assert record["directed_states"]==["anticlockwise","clockwise"]
        for extension in record["supporting_line_extensions"]:
            assert extension["termination"]=="physical_boundary"
    assert [x["interval"] for x in records[2]["supporting_line_extensions"]]==[
        [["2","2"],["0","2"]]]
