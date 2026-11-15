"""Experimental convex coverage regions derived from accessible boundaries."""

from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree


def convex_regions(accessible):
    """Cover a polygonal domain with overlapping, boundary-anchor-maximal hulls.

    Constrained triangles are only seeds. Each is expanded with every domain
    boundary vertex while its hull remains inside the same component.
    """
    if accessible.is_empty or not accessible.is_valid:
        raise ValueError("Convex coverage requires a nonempty valid accessible domain")
    domain = accessible.simplify(0, preserve_topology=True)
    if not domain.equals(accessible):
        raise ValueError("Cannot remove redundant boundary vertices without changing the domain")
    parts = [domain] if isinstance(domain, Polygon) else list(domain.geoms)
    if not parts or any(not isinstance(part, Polygon) for part in parts):
        raise ValueError("Convex coverage requires a polygonal accessible domain")
    regions = {}
    for part in sorted(parts, key=lambda item: (item.bounds, item.normalize().wkb_hex)):
        anchors = sorted({
            tuple(point) for ring in [part.exterior, *part.interiors]
            for point in list(ring.coords)[:-1]
        })
        triangles = list(constrained_delaunay_triangles(part).geoms)
        if not triangles or not unary_union(triangles).equals(part):
            raise ValueError("Constrained triangulation does not cover the accessible component")
        for triangle in sorted(triangles, key=lambda item: (item.bounds, item.normalize().wkb_hex)):
            hull = triangle
            for point in anchors:
                expanded = MultiPoint([*list(hull.exterior.coords)[:-1], point]).convex_hull
                if part.covers(expanded):
                    hull = expanded
            if not part.covers(hull):
                raise ValueError("A convex coverage region leaves the accessible domain")
            regions[hull.normalize().wkb_hex] = hull
    ordered = sorted(regions.values(), key=lambda item: (item.bounds, item.normalize().wkb_hex))
    if not unary_union(ordered).equals(accessible):
        raise ValueError("Convex regions do not cover the accessible domain")
    return {index: region for index, region in enumerate(ordered)}


def line_region_coverage(lines: list[LineString], regions: dict[int, Polygon]) -> list[set[int]]:
    """Find regions entered by each line, excluding boundary-only contact."""
    identifiers = list(regions)
    polygons = [regions[index] for index in identifiers]
    tree = STRtree(polygons)
    return [
        {identifiers[int(index)] for index in tree.query(line)
         if line.relate_pattern(polygons[int(index)], "T********")}
        for line in lines
    ]
