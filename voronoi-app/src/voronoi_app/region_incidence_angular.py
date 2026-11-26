"""Versioned angular routing with free entrance through incident convex regions."""

from fractions import Fraction
from itertools import combinations
from math import pi
from time import monotonic

import networkx as nx
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely import from_wkb
from shapely.strtree import STRtree

from .angular import LineClearance, _cross, _direction, _exact_point, _on_segment, _ring_location
from .batch_methods import _domain
from .batch_routing_reference import MasterNetwork, describe, point
from .batch_store import StageResult
from .exact_axial import _bounds, region_coverage
from .exact_enumeration import exact_pool_from_dict
from .experimental_visibility import IndexedClearance, _outward_bounds


def halfplanes(ring):
    """Build consistently inward-facing exact half-planes for a convex ring."""
    area = sum(_cross(a, b) for a, b in zip(ring, ring[1:]))
    if not area:
        raise ValueError("Degenerate convex region.")
    edges = [(a, _direction(a, b)) for a, b in zip(ring, ring[1:]) if a != b]
    return [(a, d if area > 0 else (-d[0], -d[1])) for a, d in edges]


def positive_interior(start, end, planes):
    """Independently clip to strict convex half-planes using rational parameters."""
    low, high = Fraction(0), Fraction(1)
    along = _direction(start, end)
    for a, d in planes:
        value = _cross(d, _direction(a, start))
        rate = _cross(d, along)
        if not rate:
            if value <= 0:
                return False
        elif rate > 0:
            low = max(low, -value/rate)
        else:
            high = min(high, -value/rate)
        if low >= high:
            return False
    return start != end


def exact_region_lines(lines, rings):
    """Index candidate bounds and test exact positive-length interior traversal."""
    index = STRtree([_bounds(line) for line in lines])
    result = {}
    for key, ring in rings.items():
        lower = tuple(min(p[i] for p in ring) for i in (0, 1))
        upper = tuple(max(p[i] for p in ring) for i in (0, 1))
        planes = halfplanes(ring)
        result[key] = {int(i) for i in index.query(_outward_bounds(lower, upper))
                       if positive_interior(lines[i].start, lines[i].end, planes)}
    return result


def build_incidence(lines, regions, doors):
    ids = sorted(regions)
    rings = {i: list(map(_exact_point, regions[i].exterior.coords)) for i in ids}
    planes = {i: halfplanes(rings[i]) for i in ids}
    for i in ids:
        if len(regions[i].interiors) or any(
            _cross(d, _direction(a, p)) < 0 for a, d in planes[i] for p in rings[i]
        ):
            raise ValueError(f"Region {i} is not exactly convex.")
    index = STRtree([regions[i].envelope for i in ids])
    incident = []
    for door in doors:
        p = point(door["point"])
        found = {ids[int(j)] for j in index.query(_outward_bounds(p, p))
                 if _ring_location(rings[ids[int(j)]], p) >= 0}
        verified = {i for i in ids if all(_cross(d, _direction(a, p)) >= 0 for a, d in planes[i])}
        if found != verified:
            raise ValueError("Independent doorway-region incidence check disagrees.")
        incident.append(sorted(found))

    covered = region_coverage(lines, regions)
    region_lines = {i: set() for i in ids}
    for i, associated in enumerate(covered):
        for j in associated:
            region_lines[j].add(i)
    line_index = STRtree([_bounds(line) for line in lines])
    checked_regions = sorted({i for group in incident for i in group})
    for i in checked_regions:
        verified = {int(j) for j in line_index.query(regions[i].envelope)
                    if positive_interior(lines[int(j)].start, lines[int(j)].end, planes[i])}
        if verified != region_lines[i]:
            raise ValueError(f"Independent line-region incidence check disagrees for region {i}.")
    return incident, region_lines, len(checked_regions)


def angular_depth(network, selected, line_sets, pairs):
    """Run sparse multi-source shortest paths on oriented exact atomic segments."""
    edges = sorted({edge for i in selected for edge in network.edges_by_line[i]})
    incoming = {}
    directions = np.empty((2*len(edges), 2), dtype=float)
    states = {i: [] for i in selected}
    for i, index in enumerate(edges):
        a, b, _, vector, owners = network.edges[index]
        directions[2*i], directions[2*i+1] = vector, -np.asarray(vector)
        incoming.setdefault(b, []).append(2*i)
        incoming.setdefault(a, []).append(2*i+1)
        for owner in owners & selected:
            states[owner].extend((2*i, 2*i+1))
    count = sum(len(group)**2 for group in incoming.values())
    rows, cols = np.empty(count, dtype=np.int32), np.empty(count, dtype=np.int32)
    costs = np.empty(count, dtype=float)
    offset = 0
    for group in incoming.values():
        n = len(group)
        r, c = np.repeat(group, n), np.tile(np.asarray(group) ^ 1, n)
        a, b = directions[r], directions[c]
        block = slice(offset, offset+n*n)
        rows[block], cols[block] = r, c
        costs[block] = 2*np.arctan2(abs(a[:,0]*b[:,1]-a[:,1]*b[:,0]),
                                    a[:,0]*b[:,0]+a[:,1]*b[:,1])/pi
        offset += n*n
    size = len(directions)
    graph = coo_matrix((costs, (rows, cols)), shape=(size, size)).tocsr()
    ports = [np.unique([k for i in group for k in states[i]]).astype(np.int32) for group in line_sets]

    def components_for(group, labels):
        return {labels[i] for i in group}

    labels = {i: n for n, group in enumerate(nx.connected_components(network.graph.subgraph(selected)))
              for i in group}
    components = [components_for(group, labels) for group in line_sets]
    output, status = [], []
    last = None
    for i, j in pairs:
        a, b = line_sets[i], line_sets[j]
        if not a or not b:
            value, reason = None, "attachment_failure"
        elif a & b:
            value, reason = 0., "reachable"
        elif not components[i] & components[j]:
            value, reason = None, "disconnected"
        else:
            if last != i:
                distances = dijkstra(graph, directed=True, indices=ports[i], min_only=True)
                last = i
            value = float(distances[ports[j]].min())
            if not np.isfinite(value):
                raise ValueError("Atomic routing disagrees with independently connected axial lines.")
            reason = "reachable"
        output.append(value)
        status.append(reason)
    return output, status


def analyze(inputs, parameters):
    started = monotonic()
    reference = parameters["reference"]
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    doors = reference["doorways"]
    pairs = list(combinations(range(len(doors)), 2))
    if pairs != list(map(tuple, reference["pairs"])) or any(
        (d["open_cell"], d["building_cell"], d["point"]) !=
        (old["open_cell"], old["building_cell"], old["point"])
        for d, old in zip(doors, inputs["measures"]["entrances"], strict=True)
    ):
        raise ValueError("Saved doorway inventory or order differs.")
    regions = {int(i): from_wkb(wkb) for i, wkb in inputs["candidates"]["regions_wkb"].items()}
    incident, region_lines, checked = build_incidence(lines, regions, doors)
    _, occupied, accessible, obstacle_union = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible, obstacle_union, original_obstacles=occupied.values()))
    if any(not clearance.permits(line.start, line.end) for line in lines):
        raise ValueError("An archived axial interval failed independent exact clearance.")
    network = MasterNetwork(lines, [])
    # Each possible transition joins two atomic edges at one shared rational node.
    # Verify the edge ends against their certified owners independently of noding.
    nodes = list(network.nodes)
    for a, b, _, _, owners in network.edges:
        for owner in owners:
            line = lines[owner]
            if not (_on_segment(nodes[a], line.start, line.end)
                    and _on_segment(nodes[b], line.start, line.end)):
                raise ValueError("Atomic edge leaves a certified owner interval.")
    print(parameters["case"], "certified graph", len(nodes), len(network.edges), flush=True)
    maps = {}
    cache = {}
    full_sets = [set().union(*(region_lines[i] for i in group)) for group in incident]
    for name, entry in (reference["maps"] | parameters.get("additional_maps", {})).items():
        selected = frozenset(entry["line_ids"])
        if selected not in cache:
            attached = [group & selected for group in full_sets]
            costs, status = angular_depth(network, selected, attached, pairs)
            cache[selected] = (attached, costs, status)
        attached, costs, status = cache[selected]
        old_angular, old_metric = (
            (describe(entry["routes"]["angular"]), describe(entry["routes"]["metric"]))
            if "routes" in entry else (entry["angular_statistics"], entry["metric_statistics"])
        )
        maps[name] = {
            "line_ids": sorted(selected), "doorway_lines": [sorted(i) for i in attached],
            "covered_regions": sorted(i for i in regions if region_lines[i] & selected),
            "unattached_doors": [i for i, group in enumerate(attached) if not group],
            "angular": costs, "pair_status": status, "statistics": describe(costs),
            "zero_depth": costs.count(0.),
            "connector_angular_statistics": old_angular,
            "connector_metric_statistics": old_metric,
        }
        print(parameters["case"], name, maps[name]["statistics"], flush=True)
    full = maps["full"]["angular"]
    for name, entry in maps.items():
        for a, b in zip(full, entry["angular"], strict=True):
            if b is not None and (a is None or b < a-(1e-8+1e-9*max(abs(a),abs(b)))):
                raise ValueError(f"Reduced incidence depth below full pool for {name}.")
    return StageResult({"doorways": [{k:v for k,v in d.items() if k != "connectors"} for d in doors],
                        "pairs": pairs, "doorway_regions": incident,
                        "region_lines": {str(i): sorted(group) for i, group in region_lines.items()},
                        "maps": maps, "independently_checked_regions": checked,
                        "exact_nodes": len(nodes), "exact_atomic_edges": len(network.edges),
                        "seconds": monotonic()-started})
