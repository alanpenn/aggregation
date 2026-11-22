"""Geometry, terminal depths and selection for entrance-guided axial maps."""

from fractions import Fraction

import networkx as nx
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.ops import unary_union
from shapely.strtree import STRtree

from .angular import LineClearance, SampleAttachment, _exact_point, _intersections, _on_segment
from .axial_generator import _parts
from .convex_coverage import convex_regions
from .exact_axial import ExactSupport, _bounds, build_candidates, candidate_graph, region_coverage
from .experimental_circulation_topology import (
    _ring_covers_cells, analyse_circulation_topology, bounded_face_rings,
)
from .experimental_projected_faces import generate_projected_face_all_lines
from .experimental_visibility import IndexedClearance, _outward_bounds


def shared_faces(left, right):
    """Return exact positive-length overlaps of polygon boundary edges."""
    a = tuple(map(_exact_point, left.exterior.coords))
    b = tuple(map(_exact_point, right.exterior.coords))
    overlaps = set()
    for p, q in zip(a, a[1:]):
        for r, s in zip(b, b[1:]):
            points = sorted(_intersections(p, q, r, s))
            if len(points) >= 2 and points[0] != points[-1]:
                overlaps.add((points[0], points[-1]))
    return sorted(overlaps)


def fixed_terminal_attachments(samples, lines, clearance, limit, *, progress=None):
    """Fix up to ``limit`` nearest visible perpendicular attachments per sample."""
    if limit <= 0:
        raise ValueError("Attachment limit must be positive")
    result = []
    for number, sample in enumerate(samples):
        ranked = []
        for line in lines:
            vector = tuple(line.end[k] - line.start[k] for k in range(2))
            distance = sum(value * value for value in vector)
            t = sum((sample[k] - line.start[k]) * vector[k] for k in range(2)) / distance
            t = min(Fraction(1), max(Fraction(0), t))
            point = tuple(line.start[k] + t * vector[k] for k in range(2))
            squared = sum((point[k] - sample[k]) ** 2 for k in range(2))
            ranked.append((squared, line.line_id, point))
        chosen = []
        for _, line_id, point in sorted(ranked):
            if clearance.permits_exact(sample, point):
                chosen.append(SampleAttachment(sample, point, line_id))
                if len(chosen) == limit:
                    break
        if not chosen:
            raise ValueError(f"No fixed visible attachments for sample {number}")
        result.append(chosen)
        if progress:
            progress(number + 1, len(samples))
    return result


def visibility_masks(lines, interior, regions, line_bounds):
    ids = sorted(regions)
    search = STRtree([regions[i].envelope for i in ids])
    rings = {i: list(map(_exact_point, regions[i].exterior.coords)) for i in ids}
    masks = []
    for line, known, bounds in zip(lines, interior, line_bounds):
        seen = set(known)
        for raw in search.query(bounds):
            i = ids[int(raw)]
            if i not in seen and any(_intersections(line.start, line.end, a, b)
                                     for a, b in zip(rings[i], rings[i][1:])):
                seen.add(i)
        masks.append(sum(1 << i for i in seen))
    return masks


def union_mask(masks, chosen):
    result = 0
    for i in chosen:
        result |= masks[i]
    return result


def entrance_depth(graph, selected, links):
    """Compute minimum line changes with doorway connectors only at route ends."""
    count = len(links)
    retained = {i: index for index, i in enumerate(sorted(selected))}
    core = len(retained)
    rows, cols, costs = [], [], []

    def edge(i, j, cost):
        rows.append(i)
        cols.append(j)
        costs.append(cost)

    for i, offset in retained.items():
        for j in graph[i]:
            if j in retained:
                edge(offset, retained[j], 1)
    for i, options in enumerate(links):
        for candidate in selected & options:
            edge(core + i, retained[candidate], 0)
            edge(retained[candidate], core + count + i, 0)
    matrix = coo_matrix((costs, (rows, cols)), shape=(core + 2 * count,) * 2).tocsr()
    distances = dijkstra(matrix, indices=np.arange(core, core + count))
    return distances[:, core + count:][np.triu_indices(count, k=1)]


def summary(values, count_attached):
    finite = values[np.isfinite(values)]
    return {"pairs": len(values), "attached_entrances": count_attached,
            "unreachable": len(values) - len(finite),
            "mean": float(finite.mean()) if len(finite) else None,
            "p95": float(np.percentile(finite, 95)) if len(finite) else None,
            "max": int(finite.max()) if len(finite) else None,
            "zero_change_pairs": int(np.count_nonzero(finite == 0))}


def entrance_seed(graph, fixed, witnesses, covers, target):
    selected = set(witnesses)
    all_doors = (1 << len(fixed)) - 1
    doors = [0] * len(graph)
    for i, links in enumerate(fixed):
        for line in links:
            doors[line] |= 1 << i
    while True:
        uncovered = target & ~union_mask(covers, selected)
        missing = all_doors & ~union_mask(doors, selected)
        subgraph = graph.subgraph(selected)
        if not uncovered and not missing and nx.is_connected(subgraph):
            break
        available = ({i for j in selected for i in graph[j]} - selected
                     if selected else set(graph))
        if not available:
            raise ValueError("Unable to connect coverage and entrance attachments")
        selected.add(max(available, key=lambda i: (
            (covers[i] & uncovered).bit_count() + (doors[i] & missing).bit_count(),
            len(selected.intersection(graph[i])), len(graph[i]), -i)))
    for i in sorted(selected - witnesses):
        trial = selected - {i}
        if (union_mask(doors, trial) == all_doors and union_mask(covers, trial) == target
                and nx.is_connected(graph.subgraph(trial))):
            selected = trial
    return selected, doors


def improve_entrance_depth(graph, lines, links, door_masks, compact, budget, *, progress=None):
    selected = set(compact)
    trail = []
    while len(selected) < budget:
        current = entrance_depth(graph, selected, links)
        available = {i for j in selected for i in graph[j]} - selected
        if not available:
            break
        ranked = sorted(available, key=lambda i: (
            -len(selected.intersection(graph[i])), -door_masks[i].bit_count(), -lines[i].length, i))
        alternatives = sorted(available, key=lambda i: (
            -door_masks[i].bit_count(), -len(selected.intersection(graph[i])), i))
        shortlist = sorted(set(ranked[:16]) | set(alternatives[:8]))
        best = min(((i, entrance_depth(graph, selected | {i}, links)) for i in shortlist),
                   key=lambda trial: (trial[1].mean(), trial[1].max(), trial[0]))
        if best[1].mean() >= current.mean():
            break
        selected.add(best[0])
        trail.append({"line": best[0], "mean": float(best[1].mean())})
        if progress:
            progress(len(trail), budget - len(compact))
    return selected, trail


def _ring_witnesses(lines, topology, polygons, *, progress=None):
    tree = STRtree([_bounds(line) for line in lines])
    blocks = {block["id"]: block["cells"] for block in topology["occupied_blocks"]}
    retained = set()
    cycles = topology["circulation_cycles"]
    for number, cycle in enumerate(cycles, 1):
        face = topology["witness_faces"][cycle["face_index"]]
        cells = [cell for block in cycle["enclosed_blocks"] for cell in blocks[block]]
        supports = set()
        for a, b in zip(face, face[1:]):
            matches = {
                int(i) for i in tree.query(_outward_bounds(a, b))
                if _on_segment(a, lines[int(i)].start, lines[int(i)].end)
                and _on_segment(b, lines[int(i)].start, lines[int(i)].end)
            }
            if not matches:
                raise ValueError("A circulation face has an edge without candidate support.")
            if not supports & matches:
                supports.add(min(matches))
        for i in sorted(supports, key=lambda i: (-lines[i].length, i)):
            trial = supports - {i}
            if any(_ring_covers_cells(ring, cells, polygons)
                   for ring in bounded_face_rings([lines[j] for j in sorted(trial)])):
                supports = trial
        retained.update(supports)
        if progress:
            progress(number, len(cycles))
    return retained


def generate_entrance_axial_map(polygons, buildings, dyads, doors, extra_lines, *,
                               progress=None, work_progress=None):
    """Build an exact, entrance-guided map for the main open component."""
    from dataclasses import replace
    from types import SimpleNamespace
    from shapely.geometry import Polygon

    def update(message, done=None, total=None):
        if progress and (done is None or done == 0):
            progress(message)
        if work_progress:
            work_progress(message, done, total)

    update("Classifying open space and occupied blocks")
    domain = analyse_circulation_topology(polygons, buildings, dyads, [])
    opened = {i: polygons[i] for i in domain["main_open_cells"]}
    occupied = {i: polygons[i] for i in domain["effective_occupied_cells"]}
    occupied_union = unary_union(list(occupied.values()))
    accessible = unary_union(list(opened.values())).difference(occupied_union)
    clearance = LineClearance(accessible, occupied_union, original_obstacles=occupied.values())
    indexed = IndexedClearance(clearance)
    entrances = []
    skipped = []
    for open_id, building_id in doors:
        faces = shared_faces(opened[open_id], occupied[building_id]) if open_id in opened else []
        if len(faces) == 1:
            point = tuple((a + b) / 2 for a, b in zip(*faces[0]))
            if indexed.permits(point, point):
                entrances.append(point)
                continue
        skipped.append(building_id)
    if not entrances:
        raise ValueError("No building entrances touch the main open space.")

    update("Generating exact projected-face candidates")
    pool, _ = generate_projected_face_all_lines(
        opened, occupied, progress=work_progress,
    )
    update("Checking coverage and circulation")
    lines = list(pool.candidates)
    regions = convex_regions(accessible)
    covers = visibility_masks(lines, pool.covers, regions, [_bounds(line) for line in lines])
    target = sum(1 << i for i in regions)
    visible = union_mask(covers, range(len(lines)))
    missing = {i: polygon for i, polygon in regions.items() if not (visible & (1 << i))}
    topology = analyse_circulation_topology(
        polygons, buildings, dyads, lines, include_witness_faces=True,
    )
    if missing or not topology["circulation_constraints_satisfied"]:
        update("Completing uncovered regions and circulation supports")
        ring_seeds = []
        if not topology["circulation_constraints_satisfied"]:
            for part in _parts(accessible):
                if isinstance(part, Polygon):
                    for ring in part.interiors:
                        points = list(map(_exact_point, ring.coords))
                        ring_seeds.extend(ExactSupport("ring-boundary", a, b)
                                          for a, b in zip(points, points[1:])
                                          if indexed.permits(a, b))
        supplemental = build_candidates(clearance, missing, [], ring_seeds)
        existing = {tuple(sorted((line.start, line.end))) for line in lines}
        for line in supplemental.candidates:
            key = tuple(sorted((line.start, line.end)))
            if key not in existing:
                lines.append(replace(line, line_id=len(lines)))
                existing.add(key)
        covers = visibility_masks(lines, region_coverage(lines, regions), regions,
                                  [_bounds(line) for line in lines])
        topology = analyse_circulation_topology(
            polygons, buildings, dyads, lines, include_witness_faces=True,
        )
    if not topology["circulation_constraints_satisfied"]:
        raise ValueError(
            f"The candidate pool supports winding rank "
            f"{topology['independent_circulation_rank']}/{topology['required_circulation_rank']}."
        )
    if topology["lines_crossing_effective_occupied_space"]:
        raise ValueError("The candidate pool failed exact clearance.")

    update("Reducing the circulation witnesses")
    witnesses = _ring_witnesses(
        lines, topology, polygons,
        progress=lambda done, total: update("Reducing the circulation witnesses", done, total),
    )
    update("Checking doorway connections", 0, len(entrances))
    fixed = fixed_terminal_attachments(
        entrances, lines, SimpleNamespace(permits_exact=indexed.permits), 64,
        progress=lambda done, total: update("Checking doorway connections", done, total),
    )
    links = [{link.line_id for link in options} for options in fixed]
    update("Selecting axial lines and shortcuts")
    graph = candidate_graph(lines)
    compact, door_masks = entrance_seed(graph, links, witnesses, covers, target)
    selected = compact
    if len(links) >= 2:
        selected, _ = improve_entrance_depth(
            graph, lines, links, door_masks, compact, len(compact) + extra_lines,
            progress=lambda done, total: update("Selecting axial lines and shortcuts", done, total),
        )
    update("Certifying the map and calculating axial mean depth")
    selected_lines = [lines[i] for i in sorted(selected)]
    check = analyse_circulation_topology(polygons, buildings, dyads, selected_lines)
    if (not check["circulation_constraints_satisfied"]
            or check["lines_crossing_effective_occupied_space"]):
        raise ValueError("The reduced map failed exact circulation or clearance verification.")
    axial_depths = {
        i: sum(lengths.values()) / max(1, len(selected) - 1)
        for i, lengths in nx.all_pairs_shortest_path_length(graph.subgraph(selected))
    }
    return {
        "lines": selected_lines,
        "candidate_count": len(lines),
        "compact_count": len(compact),
        "entrances": entrances,
        "skipped_doors": skipped,
        "excluded_cells": domain["excluded_open_cells"],
        "entrance_depth": summary(entrance_depth(graph, selected, links), len(links)),
        "axial_depths": axial_depths,
        "axial_mean_depth": sum(axial_depths.values()) / len(axial_depths),
        "rings": check["independent_circulation_rank"],
        "required_rings": check["required_circulation_rank"],
        "regions": len(regions),
    }
