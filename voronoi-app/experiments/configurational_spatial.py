"""Exact sampled overlay of distinct element representations on accessible space."""

from collections import Counter
from fractions import Fraction as F
from math import fsum

from voronoi_app.angular import _cross, _direction, _ring_location
from voronoi_app.configurational import pearson, rational_points
from voronoi_app.region_incidence_angular import halfplanes


def distance_squared(point, a, b):
    delta = _direction(a, b)
    offset = _direction(a, point)
    t = sum(x*y for x, y in zip(delta, offset)) / sum(d*d for d in delta)
    t = min(F(1), max(F(0), t))
    return sum((x - t*d)**2 for x, d in zip(offset, delta))


def accessible_grid(domain, step=2):
    parts = domain.geoms if domain.geom_type == "MultiPolygon" else (domain,)
    rings = [(rational_points(part.exterior.coords), [rational_points(hole.coords) for hole in part.interiors])
             for part in parts]
    bounds = domain.bounds
    grid = ((F(x), F(y)) for x in range(int(bounds[0]) + 1, int(bounds[2]), step)
            for y in range(int(bounds[1]) + 1, int(bounds[3]), step))
    return [p for p in grid if any(_ring_location(outer, p) == 1
                                  and all(_ring_location(hole, p) == -1 for hole in holes)
                                  for outer, holes in rings)]


def spatial_overlay(domain, axial, segment, convex, *, step=4, radius=3):
    polygon_graph, _ = convex
    prepared = {}
    for identifier, node in polygon_graph.nodes(data=True):
        points = node["points"]
        x, y = zip(*points)
        prepared[identifier] = (min(x), max(x), min(y), max(y), halfplanes(points + points[:1]))

    def nearby(graph, point):
        distances = [(distance_squared(point, *row["points"]), i) for i, row in graph.nodes(data=True)]
        shortest = min(distance for distance, _ in distances)
        return [i for distance, i in distances if distance == shortest <= radius**2]

    fields = {}
    for point in accessible_grid(domain, step):
        x, y = point
        covers = [i for i, (x0,x1,y0,y1,planes) in prepared.items()
                  if x0 <= x <= x1 and y0 <= y <= y1
                  and all(_cross(d, _direction(a, point)) >= 0 for a, d in planes)]
        identifiers = {"axial": nearby(axial[0], point), "segment": nearby(segment[0], point), "convex": covers}
        values = {}
        for (kind, nodes), (_, rows) in zip(identifiers.items(), (axial, segment, convex)):
            values[kind] = {metric: fsum(rows[node][metric] for node in nodes)/len(nodes) if nodes else None
                            for metric in ("integration", "choice")}
        fields[point] = {"point": point, "ids": identifiers, "scores": values}
    common = [row for row in fields.values() if all(row["ids"].values())]
    correlations = {}
    for metric in ("integration", "choice"):
        for a, b in (("axial", "segment"), ("axial", "convex"), ("segment", "convex")):
            x, y = ([row["scores"][key][metric] for row in common] for key in (a,b))
            correlations[f"{metric}:{a}:{b}"] = pearson(x, y)
    return {"samples": list(fields.values()), "all_three_count": len(common), "pearson": correlations,
            "convex_cover_multiplicity": dict(sorted(Counter(
                len(row["ids"]["convex"]) for row in fields.values()).items()))}
