"""Batch adapters around the existing settlement and axial research methods."""

from math import hypot

import networkx as nx
import numpy as np
from shapely import from_wkb
from shapely.ops import unary_union

from .angular import LineClearance
from .angular_optimisation import _obstacles
from .batch_store import StageResult
from .convex_coverage import convex_regions
from .core import ExperimentPipeline, UrbanFormComposition
from .exact_axial import _bounds, candidate_graph, greedy_selection, region_coverage
from .exact_enumeration import (
    exact_pool_from_dict, exact_pool_to_dict, generate_fresh_exact_candidate_pool,
)
from .experimental_circulation_topology import analyse_circulation_topology
from .experimental_entrance_reduction import (
    _ring_witnesses, entrance_depth, entrance_seed, fixed_terminal_attachments,
    improve_entrance_depth, shared_faces, summary, union_mask, visibility_masks,
)
from .experimental_projected_faces import generate_projected_face_all_lines
from .experimental_visibility import IndexedClearance
from .orchestrator import ExperimentOrchestrator
from .registry import get_registry


def generate_settlement(inputs, parameters):
    configuration = ExperimentPipeline().to_dict() | parameters
    pipeline = ExperimentPipeline.from_dict(dict(configuration))
    pipeline.urban_form = UrbanFormComposition.from_dict(configuration["urban_form"])
    if pipeline.seed is None:
        raise ValueError("A saved settlement requires an explicit seed.")
    registry = get_registry()
    terrain = registry.get_terrain(pipeline.terrain_provider, pipeline.terrain_params)
    generator = registry.get_grid(pipeline.grid_generator, pipeline.grid_params)
    strategy = registry.get_aggregation(pipeline.aggregation_strategy, pipeline.aggregation_params)
    extent = (0, 0, pipeline.canvas_size, pipeline.canvas_size)
    grid = generator.generate(terrain=terrain, extent=extent, seed=pipeline.seed)
    grid.metadata["extent"] = extent
    orchestrator = ExperimentOrchestrator(pipeline)
    orchestrator._prepare_aggregation_geometry(grid, strategy)
    aggregation = strategy.aggregate(terrain=terrain, grid=grid, form=pipeline.urban_form, seed=pipeline.seed)
    polygons = orchestrator._space_polygons(grid)
    if set(polygons) != set(range(len(grid.nodes))):
        raise ValueError("The generated grid has missing cell geometry.")
    return StageResult({
        "configuration": configuration,
        "resolved_components": {"terrain": terrain.get_config(), "grid": generator.get_config(),
                                "aggregation": strategy.get_config()},
        "polygons_wkb": {str(i): p.wkb_hex for i, p in polygons.items()},
        "grid": {"extent": extent, "nodes": [list(map(float, p)) for p in grid.nodes],
                 "edges": [list(map(int, edge)) for edge in grid.edges]},
        "building_labels": {str(i): int(label) for i, label in aggregation.building_labels.items()},
        "dyad_open_cells": sorted(map(int, aggregation.open_spaces)),
        "doors": [list(map(int, door)) for door in aggregation.doors],
        **aggregation.diagnostics,
    })


def generate_facewise_settlement(inputs, parameters):
    strategy = "slope_preference_facewise_v1"
    if parameters.get("aggregation_strategy", strategy) != strategy:
        raise ValueError(f"This settlement method requires {strategy}.")
    return generate_settlement(inputs, parameters | {"aggregation_strategy": strategy})


def _settlement(inputs):
    data = inputs["settlement"]
    return ({int(i): from_wkb(p) for i, p in data["polygons_wkb"].items()},
            set(map(int, data["building_labels"])), set(data.get("dyad_open_cells", ())))


def preserve_settlement(inputs, parameters):
    """Import a settlement geometry and door inventory without regeneration."""
    polygons, buildings, dyads = _settlement({"settlement": parameters})
    required = buildings | dyads
    labels = parameters["building_labels"]
    doors = parameters["doors"]
    if (not polygons or not required <= polygons.keys() or buildings & dyads
            or any(p.geom_type != "Polygon" or p.is_empty or not p.is_valid for p in polygons.values())
            or len(set(labels.values())) != len(labels)
            or any(open_id not in dyads or building_id not in buildings
                   for open_id, building_id in doors)
            or not isinstance(parameters["configuration"], dict)):
        raise ValueError("Preserved settlement geometry, labels or door inventory is inconsistent.")
    return StageResult(parameters)


def derive_topology(inputs, parameters):
    polygons, buildings, dyads = _settlement(inputs)
    topology = analyse_circulation_topology(polygons, buildings, dyads, [],
                                           main_open_seed=parameters.get("main_open_seed"))
    opened = {i: polygons[i] for i in topology["main_open_cells"]}
    occupied = {i: polygons[i] for i in topology["effective_occupied_cells"]}
    occupied_union = unary_union(list(occupied.values()))
    accessible = unary_union(list(opened.values())).difference(occupied_union)
    return StageResult({
        "topology": topology,
        "accessible_wkb": accessible.wkb_hex,
        "occupied_wkb": occupied_union.wkb_hex,
        "blocks_wkb": {block["id"]: unary_union([polygons[i] for i in block["cells"]]).wkb_hex
                       for block in topology["occupied_blocks"]},
    })


def _domain(inputs):
    topology = inputs["topology"]
    polygons, _, _ = _settlement(inputs)
    return ({i: polygons[i] for i in topology["topology"]["main_open_cells"]},
            {i: polygons[i] for i in topology["topology"]["effective_occupied_cells"]},
            from_wkb(topology["accessible_wkb"]), from_wkb(topology["occupied_wkb"]))


def _certify_pool(pool, audit, regions, obstacles, inputs):
    _, occupied, accessible, occupied_union = _domain(inputs)
    clearance = LineClearance(accessible, occupied_union, original_obstacles=occupied.values())
    rejected = [line.line_id for line in pool.candidates
                if not clearance.permits_exact(line.start, line.end)]
    duplicates = len(pool.candidates) - len({tuple(sorted((line.start, line.end)))
                                             for line in pool.candidates})
    graph = candidate_graph(pool.candidates)
    interior = region_coverage(pool.candidates, regions)
    visible = visibility_masks(pool.candidates, interior, regions,
                               [_bounds(line) for line in pool.candidates])
    interior_regions = set().union(*interior)
    visible_regions = union_mask(visible, range(len(visible)))
    return StageResult({
        "pool": exact_pool_to_dict(pool),
        "audit": audit,
        "regions_wkb": {str(i): polygon.wkb_hex for i, polygon in regions.items()},
        "obstacle_witnesses": obstacles,
        "geometric_certification": {"clearance_rejections": rejected, "duplicate_intervals": duplicates},
        "pool_summary": {
            "candidates": len(pool.candidates),
            "exact_clearance_passes": len(pool.candidates) - len(rejected),
            "intersecting_candidate_pairs": graph.number_of_edges(),
            "components": nx.number_connected_components(graph),
            "regions": len(regions),
            "interior_regions_covered": len(interior_regions),
            "visibility_regions_covered": visible_regions.bit_count(),
            "uncovered_visibility_regions": sorted(i for i in regions if not visible_regions & (1 << i)),
        },
    }, valid=not rejected and not duplicates)


def fresh_exact_pool(inputs, parameters):
    opened, occupied, _, _ = _domain(inputs)
    problem, audit = generate_fresh_exact_candidate_pool(opened, occupied)
    return _certify_pool(problem.pool, {
        "counts": audit.counts,
        "domain_rejections": [{
            "source": item.source, "start": list(map(str, item.start)), "end": list(map(str, item.end)),
            "start_vertices": [[v.building_id, v.vertex_index] for v in item.start_vertices],
            "end_vertices": [[v.building_id, v.vertex_index] for v in item.end_vertices],
        } for item in audit.domain_rejections],
    }, problem.regions, problem.obstacles, inputs)


def projected_face_pool(inputs, parameters):
    opened, occupied, accessible, occupied_union = _domain(inputs)
    pool, audit = generate_projected_face_all_lines(opened, occupied)
    min_x, min_y, max_x, max_y = accessible.bounds
    tolerance = max(hypot(max_x - min_x, max_y - min_y) * 1e-9, 1e-12)
    obstacles, _ = _obstacles(accessible, occupied_union, tolerance)
    return _certify_pool(pool, audit, convex_regions(accessible),
                         [(point.x, point.y) for point in obstacles], inputs)


def _selection(inputs, selected):
    pool = inputs["candidates"]["pool"]
    return StageResult({"line_ids": sorted(selected),
                        "lines": [pool["candidates"][i] for i in sorted(selected)]})


def exact_greedy(inputs, parameters):
    data = inputs["candidates"]
    pool = exact_pool_from_dict(data["pool"])
    regions = {int(i): from_wkb(p) for i, p in data["regions_wkb"].items()}
    accessible = from_wkb(inputs["topology"]["accessible_wkb"])
    selected, _, _ = greedy_selection(pool, regions, accessible, data["obstacle_witnesses"])
    return _selection(inputs, selected)


def retain_pool(inputs, parameters):
    return _selection(inputs, range(len(inputs["candidates"]["pool"]["candidates"])))


def _map(inputs):
    pool = exact_pool_from_dict(inputs["candidates"]["pool"])
    selected = inputs["selection"]["line_ids"]
    records = inputs["candidates"]["pool"]["candidates"]
    if (selected != sorted(set(selected)) or any(i < 0 or i >= len(records) for i in selected)
            or inputs["selection"]["lines"] != [records[i] for i in selected]):
        raise ValueError("Saved axial map does not match its certified candidate pool.")
    return pool, set(selected)


def _fixed_entrances(inputs, lines, limit):
    polygons, _, _ = _settlement(inputs)
    opened, occupied, accessible, occupied_union = _domain(inputs)
    clearance = LineClearance(accessible, occupied_union, original_obstacles=occupied.values())
    entries, doors, points = [], [], []
    for open_id, building_id in inputs["settlement"]["doors"]:
        faces = shared_faces(polygons[open_id], polygons[building_id]) if open_id in opened else []
        point = tuple((a + b) / 2 for a, b in zip(*faces[0])) if len(faces) == 1 else None
        if point is not None and clearance.permits_exact(point, point):
            doors.append({"open_cell": open_id, "building_cell": building_id, "point": list(map(str, point))})
            points.append(point)
        else:
            entries.append({"open_cell": open_id, "building_cell": building_id,
                            "status": "outside-main-space" if open_id not in opened else
                                      "ambiguous-face" if len(faces) > 1 else
                                      "missing-face" if not faces else "blocked"})
    from types import SimpleNamespace
    indexed = IndexedClearance(clearance)
    fixed = fixed_terminal_attachments(
        points, lines, SimpleNamespace(permits_exact=indexed.permits), limit,
    ) if points else []
    links = [{a.line_id for a in options} for options in fixed]
    for door, options in zip(doors, fixed, strict=True):
        door["connectors"] = [{"line": a.line_id, "point": list(map(str, a.point))} for a in options]
    return doors, entries, links


def entrance_guided(inputs, parameters):
    data = inputs["candidates"]
    pool = exact_pool_from_dict(data["pool"])
    lines = pool.candidates
    polygons, buildings, dyads = _settlement(inputs)
    topology = analyse_circulation_topology(
        polygons, buildings, dyads, lines, include_witness_faces=True,
    )
    if not topology["circulation_constraints_satisfied"]:
        raise ValueError("Saved candidates cannot supply all required circulation witnesses.")
    regions = {int(i): from_wkb(p) for i, p in data["regions_wkb"].items()}
    covers = visibility_masks(lines, pool.covers, regions, [_bounds(line) for line in lines])
    target = sum(1 << i for i in regions)
    if union_mask(covers, range(len(lines))) != target:
        raise ValueError("Saved candidates cannot supply full visibility coverage.")
    witnesses = _ring_witnesses(lines, topology, polygons)
    doors, excluded, links = _fixed_entrances(inputs, lines, parameters["connector_limit"])
    if not links:
        raise ValueError("No valid building entrances are available for selection.")
    graph = candidate_graph(lines)
    compact, door_masks = entrance_seed(graph, links, witnesses, covers, target)
    selected, trail = improve_entrance_depth(
        graph, lines, links, door_masks, compact, len(compact) + parameters["extra_lines"],
    ) if len(links) >= 2 else (compact, [])
    return StageResult({
        **_selection(inputs, selected).output,
        "compact_line_ids": sorted(compact),
        "initial_ring_line_ids": sorted(witnesses),
        "shortcut_growth": trail,
        "entrances": doors,
        "excluded_entrances": excluded,
    })


def axial_and_entrance_depth(inputs, parameters):
    pool, selected = _map(inputs)
    lines = pool.candidates
    graph = candidate_graph(lines)
    subgraph = graph.subgraph(selected)
    per_line = {}
    for i, distances in nx.all_pairs_shortest_path_length(subgraph):
        per_line[str(i)] = {
            "mean_depth": sum(distances.values()) / max(1, len(distances) - 1),
            "unreachable": len(selected) - len(distances),
        }
    limit = parameters.get("connector_limit", 64)
    doors, entries, links = _fixed_entrances(inputs, lines, limit)
    values = entrance_depth(graph, selected, links) if links else np.array([])
    return StageResult({
        "connector_limit": limit,
        "axial_by_line": per_line,
        "axial_mean_depth": sum(x["mean_depth"] for x in per_line.values()) / len(per_line) if per_line else None,
        "entrances": doors,
        "excluded_entrances": entries,
        "entrance_pair_depths": [float(v) if v != float("inf") else None for v in values],
        "entrance_depth": summary(values, sum(bool(o & selected) for o in links)),
    })


def validate_axial_map(inputs, parameters):
    pool, selected = _map(inputs)
    polygons, buildings, dyads = _settlement(inputs)
    lines = [pool.candidates[i] for i in sorted(selected)]
    topology = analyse_circulation_topology(polygons, buildings, dyads, lines)
    regions = {int(i): from_wkb(p) for i, p in inputs["candidates"]["regions_wkb"].items()}
    covers = visibility_masks(lines, region_coverage(lines, regions), regions,
                              [_bounds(line) for line in lines])
    covered = union_mask(covers, range(len(lines)))
    missing = [i for i in sorted(regions) if not covered & (1 << i)]
    measures = inputs.get("measures")
    entrance = measures["entrance_depth"] if measures else None
    connectivity = nx.number_connected_components(candidate_graph(lines))
    failures = []
    if missing:
        failures.append("visibility coverage")
    if connectivity != 1:
        failures.append("axial connectivity")
    if not topology["circulation_constraints_satisfied"]:
        failures.append("independent circulation")
    if topology["lines_crossing_effective_occupied_space"]:
        failures.append("geometric clearance")
    if entrance and (entrance["unreachable"]
                     or entrance["attached_entrances"] != len(measures["entrances"])):
        failures.append("valid entrance reachability")
    return StageResult({
        "failed_checks": failures,
        "uncovered_regions": missing,
        "topology": topology,
        "summary": {
            "lines": len(lines), "total_axial_length": sum(line.length for line in lines),
            "components": connectivity, "covered_regions": len(regions) - len(missing),
            "regions": len(regions), "winding_rank": topology["independent_circulation_rank"],
            "required_rank": topology["required_circulation_rank"],
            "axial_mean_depth": measures["axial_mean_depth"] if measures else None,
            "entrance_depth": entrance,
            "excluded_entrances": len(measures["excluded_entrances"]) if measures else None,
        },
    }, valid=not failures)
