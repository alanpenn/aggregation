"""Deterministic street grids and controlled corridor deformations."""

from fractions import Fraction
from functools import cache
from itertools import combinations
from types import SimpleNamespace

import networkx as nx
from shapely import to_wkb
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .angular import LineClearance
from .batch_routing_reference import MasterNetwork
from .batch_store import StageResult
from .exact_axial import _bounds, build_candidates
from .experimental_circulation_topology import analyse_circulation_topology, evaluate_circulation_lines
from .experimental_entrance_reduction import fixed_terminal_attachments, union_mask, visibility_masks
from .experimental_visibility import IndexedClearance
from .extreme_diagonal_experiment import analyze_corridor, ends
from .route_sparse_experiment import MEASURES


FIXTURES = {
    "grid-4x-2": (16, 2, "straight"),
    "grid-8x-2": (32, 2, "straight"),
    "grid-8x-4": (32, 4, "straight"),
    "grid-12x-4": (48, 4, "straight"),
    "curve": (32, 4, "curve"),
    "taper": (32, 4, "taper"),
    "bend": (32, 4, "bend"),
    "irregular": (32, 4, "irregular"),
}


def layout(name):
    length, streets, shape = FIXTURES[name]
    cut = [0, 2]
    for i in range(1, streets+1):
        centre = round(i*length/(streets+1))
        cut.extend((centre-1, centre+1))
    cut.extend((length-2, length))
    cut = sorted(set(cut))
    bands = (-8, -6, -2, 2, 6, 8)

    def vertex(x, j):
        r = Fraction(x, length)
        y = Fraction(bands[j])
        if shape == "curve":
            y += 32*r*(1-r)
        elif shape == "bend":
            y += 24*max(0, r-Fraction(1, 2))
        elif shape == "taper":
            y *= 1-r/2
        elif shape == "irregular" and j in (2, 3):
            y += Fraction(((cut.index(x)*7+j) % 5)-2, 4)
        return Fraction(x), y

    polygons, occupied, doors, vertices = {}, set(), [], set()
    for i, (a, b) in enumerate(zip(cut, cut[1:])):
        for j in range(5):
            v = (vertex(a,j), vertex(b,j), vertex(b,j+1), vertex(a,j+1))
            cell = len(polygons)
            polygons[cell] = Polygon(v)
            if i % 2 and j in (1, 3):
                occupied.add(cell)
                e, f = v[2:] if j == 1 else v[:2]
                doors.append({"building_cell": cell, "open_cell": i*5+2,
                              "point": tuple((s+t)/2 for s, t in zip(e, f, strict=True))})
                # Secondary doors open into the rear passage.
                e, f = v[:2] if j == 1 else v[2:]
                doors.append({"building_cell": cell, "open_cell": i*5+(0 if j == 1 else 4),
                              "point": tuple((s+t)/2 for s, t in zip(e, f, strict=True))})
                vertices.update(v)
    # End portals define the extreme unobstructed tangents.
    vertices.update(vertex(x,j) for x in (0, length) for j in range(6))
    centreline = [(x, float((vertex(x,2)[1]+vertex(x,3)[1])/2)) for x in cut]
    return polygons, occupied, doors, sorted(vertices), centreline


def synthetic(_inputs, parameters):
    name = parameters["fixture"]
    polygons, buildings, doors, vertices, centreline = layout(name)
    occupied = unary_union([polygons[i] for i in sorted(buildings)])
    regions = {i: p for i,p in polygons.items() if i not in buildings}
    accessible = unary_union(list(regions.values()))
    clearance = LineClearance(accessible, occupied, original_obstacles=[polygons[i] for i in buildings])
    seeds = [("visible-vertex-pair", a, b) for a,b in combinations(vertices, 2)]
    pool = build_candidates(clearance, regions, [], seeds)
    lines = pool.candidates
    fixed = fixed_terminal_attachments(
        [d["point"] for d in doors], lines, SimpleNamespace(permits_exact=IndexedClearance(clearance).permits), 64,
    )
    doors = [{**d, "connectors": [(a.line_id, a.point) for a in group]}
             for d, group in zip(doors, fixed, strict=True)]
    network = MasterNetwork(lines, doors)
    full = frozenset(range(len(lines)))
    target = sum(1 << i for i in regions)
    coverage = visibility_masks(lines, pool.covers, regions, [_bounds(line) for line in lines])
    blocks = analyse_circulation_topology(polygons, buildings, [], [])["occupied_blocks"]

    @cache
    def topology(selected):
        return evaluate_circulation_lines(polygons, [lines[i] for i in sorted(selected)], blocks, clearance)

    def checks(selected, diagnostic=True):
        covered = union_mask(coverage, selected)
        components = nx.number_connected_components(network.graph.subgraph(selected))
        unattached = sum(not options for options in network.options(selected))
        cheap = (covered == target and components == 1 and unattached == 0)
        if not cheap and not diagnostic:
            return {"status": "invalid"}
        rings = topology(selected)
        rejected = rings["lines_crossing_effective_occupied_space"]
        return {"status": "valid" if cheap and rings["circulation_constraints_satisfied"] and not rejected else "invalid",
                "coverage_regions": covered.bit_count(), "required_regions": len(regions), "components": components,
                "rank": rings["independent_circulation_rank"], "required_rank": rings["required_circulation_rank"],
                "unattached_doors": unattached, "clearance_rejected": rejected}

    @cache
    def routes(selected):
        return {k: network.route(selected, k == "angular") for k in MEASURES}

    length, streets, shape = FIXTURES[name]
    local_axes = []
    if shape in ("curve", "bend"):
        split = len(centreline)//2
        local_axes = [((centreline[0], centreline[split+1]), 3.5),
                      ((centreline[split-1], centreline[-1]), 3.5)]
    band = 2.15 if shape == "straight" else 3.0
    corridor = analyze_corridor(network, full, None, routes(full), routes, checks,
                                (centreline[0], centreline[-1]), band, parameters,
                                local_axes=local_axes)
    return StageResult({
        "corridors": [corridor], "ratio": length/4, "transverse_streets": streets, "shape": shape,
        "doorways": [{**d, "point": list(map(str, d["point"])),
                      "connectors": [[i,list(map(str,p))] for i,p in d["connectors"]]} for d in doors],
        "intervals": [[list(map(str,p)) for p in ends(line)] for line in lines],
        "settlement": {"building_labels": {str(i): str(i) for i in buildings},
                       "polygons_wkb": {str(i):to_wkb(p,hex=True) for i,p in polygons.items()}},
        "seed_trials": len(seeds), "rejected_seeds": len(pool.rejected),
    })
