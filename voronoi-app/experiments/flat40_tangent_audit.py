"""Read-only Flat 40 tangent and exchange experiment."""
from collections import Counter
from functools import cache
from itertools import combinations, product
from pathlib import Path
from hashlib import sha256
import json

import networkx as nx
from shapely.geometry import LineString

from voronoi_app.research_data import data_path
from voronoi_app.angular import LineClearance, _crosses_polygon_interior_exact, _direction, _cross
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_routing_reference import MasterNetwork, describe
from voronoi_app.batch_store import BatchStore, atomic_write, encode
from voronoi_app.convex_metric_experiment import build_master_doors
from voronoi_app.exact_enumeration import exact_pool_from_dict, _vertices, _supports
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.region_incidence_angular import angular_depth, build_incidence
from voronoi_app.strict_coverage_experiment import incidence_sets, omissions
from voronoi_app.strict_generalisation import Geometry, RegionalNetwork
from shapely import from_wkb

SOURCE = data_path('strict-generalisation/extended-terrain-1')
OUTPUT = data_path('strict-generalisation/flat40-tangent-audit-1')
PAIRS = ((15, 25), (6, 5), (41, 43))
RADIUS = 2.0


def endpoint(point):
    return list(map(str, point))


def interval(line):
    return tuple(sorted((line.start, line.end)))


def load():
    journal = json.loads((SOURCE / "cases/flat-40.json").read_bytes())
    store = BatchStore(SOURCE)
    inputs, lineage = {}, {}
    for stage, entry in journal["stages"].items():
        manifest, payload, checksum = store.load(entry["record"])
        inputs[stage] = payload
        lineage[stage] = {"id": entry["record"], "record_sha256": checksum,
                          "output_sha256": manifest["output_sha256"], "source": manifest["method"]["source"]}
    store._inputs("validation", journal["stages"]["selection"]["record"])
    polygons, buildings, _ = _settlement(inputs)
    labels = {int(i): n for i, n in inputs["settlement"]["building_labels"].items()}
    assert set(labels.values()) == set(range(1, 101)) and labels.keys() == buildings
    nodes = inputs["settlement"]["grid"]["nodes"]
    assert set(polygons) == set(range(len(nodes))) and all(p.is_valid and p.area > 0 for p in polygons.values())
    manifest = json.loads((SOURCE / "records" / lineage["settlement"]["id"] / "record.json").read_bytes())
    for source in manifest["runtime"]["sources"]:
        blob = SOURCE / "source" / f"{source['sha256']}.py"
        assert sha256(blob.read_bytes()).hexdigest() == source["sha256"]
    return inputs, lineage, polygons, labels


def discover(lines, occupied, labels, polygons, clearance, indexed):
    vertex_map, _ = _vertices(occupied)
    by_label = {n: i for i, n in labels.items()}
    by_interval = {interval(line): line.line_id for line in lines}
    shapes = [LineString([line.start, line.end]) for line in lines]
    by_seed = {tuple(sorted((support.start, support.end))): interval(line)
               for line in lines for support in line.provenance}
    groups = {}
    for a, b in PAIRS:
        key = f"{a}-{b}"
        left, right = by_label[a], by_label[b]
        targets = [polygons[left], polygons[right]]

        def near(shape):
            return all(shape.distance(polygon) <= RADIUS for polygon in targets)

        local = sorted((i for i, shape in enumerate(shapes) if near(shape)),
                       key=lambda i: (-lines[i].length, i))
        direct = []
        unseen = {}
        # Search both named polygons and their neighbouring frontages. The
        # proximity window defines the local experiment, not a clearance test.
        from shapely.geometry import Point
        corners = [[(point, v) for point, vertices in vertex_map.items() for v in vertices
                    if polygon.distance(Point(point)) <= 5] for polygon in targets]
        checked = set()
        for (p, u), (q, v) in product(*corners):
            if p == q or not (_supports(u, q) and _supports(v, p)):
                continue
            seed = tuple(sorted((p, q)))
            named = (u.reference.building_id, v.reference.building_id) == (left, right)
            if (seed, named) in checked:
                continue
            checked.add((seed, named))
            if not indexed.permits(p, q):
                if named:
                    obstruction = [labels.get(cell, cell) for cell, poly in occupied.items()
                                   if _crosses_polygon_interior_exact(p, q, poly)]
                    direct.append({"seed": list(map(endpoint, seed)), "status": "rejected",
                                   "blocking_buildings_or_effective_cells": obstruction,
                                   "reason": "occupied interior" if obstruction else "effective occupied union or frame"})
                continue
            maximal = by_seed.get(seed)
            if maximal is None:
                maximal = tuple(sorted(clearance.maximal_interval(p, q)))
            shape = LineString(maximal)
            if not near(shape):
                continue
            i = by_interval.get(maximal)
            entry = {"seed": list(map(endpoint, seed)), "interval": list(map(endpoint, maximal)),
                     "length": shape.length, "candidate_id": i, "status": "certified",
                     "supports": [[u.reference.building_id, u.reference.vertex_index],
                                  [v.reference.building_id, v.reference.vertex_index]]}
            if named:
                direct.append(entry)
            if i is None:
                entry["generation_reason"] = ("support endpoint is nonconvex" if not (u.convex and v.convex)
                                              else "no matching generated support under the archived rules")
                unseen[maximal] = entry
        groups[key] = {"local_ids": local, "named_mutual_supports": direct,
                       "independently_certified_absent": list(unseen.values()),
                       "tested_supports": len(checked)}
        print(key, "pool lines", len(local), "named supports", len(direct), "absent", len(unseen), flush=True)
    return groups


def main():
    OUTPUT.mkdir(exist_ok=True)
    inputs, lineage, polygons, labels = load()
    opened, occupied, accessible, obstacles = _domain(inputs)
    clearance = LineClearance(accessible, obstacles, original_obstacles=occupied.values())
    indexed = IndexedClearance(clearance)
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    group = discover(lines, occupied, labels, polygons, clearance, indexed)
    data = inputs["analysis"]
    archived_maps = data["maps"]
    guided = frozenset(archived_maps["strict_entrance_guided"]["line_ids"])
    base = frozenset(archived_maps["strict_backward"]["line_ids"])
    baseline = archived_maps["strict_backward"]["routing"]
    screen = inputs["physical_screen"]
    winners = {method: frozenset(data["corridors"][winner - 1][name]["line_ids"]) if winner else frozenset()
               for method, name in (("geometric_extreme", "extreme"), ("route_ranked", "best_ranked"))
               for winner in (screen["winners"][method],)}
    axial = MasterNetwork(lines, [])
    graph = axial.graph
    engine = Geometry(inputs, lines, graph, indexed)
    region_polygons = {int(i): from_wkb(wkb) for i, wkb in inputs["candidates"]["regions_wkb"].items()}
    region_sets, doors = incidence_sets(data["incidence"])
    pairs = [tuple(pair) for pair in data["pairs"]]
    route_doors, _, _ = build_master_doors(lines, data["incidence"], region_polygons, indexed)
    metric = RegionalNetwork(axial, route_doors)
    required = data["holes"]

    @cache
    def validate(chosen):
        missing, unattached = omissions(chosen, region_sets, doors)
        components = nx.number_connected_components(graph.subgraph(chosen))
        if missing or unattached or components != 1:
            return {"valid": False, "missing_regions": missing, "unattached_doors": unattached,
                    "components": components}
        topology = engine.geometry(chosen)
        rank = topology["independent_circulation_rank"]
        rejected = topology["lines_crossing_effective_occupied_space"]
        return {"valid": topology["circulation_constraints_satisfied"] and not rejected,
                "rank": rank, "required_rank": required, "clearance_rejections": rejected,
                "components": components, "missing_regions": [], "unattached_doors": []}

    @cache
    def routes(chosen):
        checks = validate(chosen)
        if not checks["valid"]:
            return checks
        angular, statuses = angular_depth(axial, chosen, [link & chosen for link in doors], pairs)
        distance = metric.route(chosen, False)
        return checks | {"valid": all(s == "reachable" for s in statuses) and None not in distance,
                         "angular": describe(angular), "metric": describe(distance), "line_count": len(chosen),
                         "length": sum(lines[i].length for i in chosen)}

    local_ids = set().union(*(item["local_ids"] for item in group.values()))
    before_delete, attempts = {}, {i: [] for i in local_ids}
    chosen = guided
    trace = iter(data["deletion_trace"])
    next_deleted = next(trace, None)
    order = sorted(guided, key=lambda i: (lines[i].length, lines[i].start, lines[i].end))
    pass_number = 0
    while True:
        previous = chosen
        pass_number += 1
        for i in order:
            if i not in chosen:
                continue
            accepted = i == next_deleted
            if i in local_ids:
                outcome = validate(chosen - {i})
                assert accepted == outcome["valid"], (i, pass_number)
                attempts[i].append({"pass": pass_number, "starting_count": len(chosen),
                                    "accepted": accepted, **outcome})
                if accepted:
                    before_delete[i] = outcome
            if accepted:
                chosen -= {i}
                next_deleted = next(trace, None)
        if chosen == previous:
            break
    assert chosen == base and next_deleted is None
    base_check = routes(base)
    for name in ("angular", "metric"):
        assert abs(base_check[name]["mean"] - baseline[name]["cost"]["mean"]) < 1e-9

    inventory, additions = {}, {}
    for i in sorted(local_ids):
        line = lines[i]
        supports = [{"source": source.source, "seed": [endpoint(source.start), endpoint(source.end)],
                     "vertices": [[ref.building_id, labels.get(ref.building_id), ref.vertex_index]
                                  for ref in source.start_vertices + source.end_vertices]}
                    for source in line.provenance]
        original_neighbors = set(graph[i]) & base
        direction = _direction(line.start, line.end)
        transverse = []
        for j in original_neighbors:
            other = _direction(lines[j].start, lines[j].end)
            if abs(float(_cross(direction, other))) >= .5 * line.length * lines[j].length:
                transverse.append(j)
        maximal = tuple(sorted(clearance.maximal_interval(line.seed_start, line.seed_end)))
        inventory[i] = {"interval": list(map(endpoint, interval(line))), "length": line.length,
                        "supports": supports, "clear": indexed.permits(line.start, line.end),
                        "maximal": maximal == interval(line),
                        "convex_regions": [region for region, members in region_sets.items() if i in members],
                        "doorway_building_labels": [labels[data["doorways"][j]["building_cell"]]
                                                    for j, link in enumerate(doors) if i in link],
                        "pool_intersections": sorted(graph[i]), "selected_intersections": sorted(original_neighbors),
                        "transverse_selected": sorted(transverse), "in_guided": i in guided,
                        "deletion_attempts": attempts[i], "removed": i in before_delete, "deletion_certificate": before_delete.get(i),
                        "deletion_index": data["deletion_trace"].index(i) if i in before_delete else None,
                        "in_backward": i in base, **{method: i in ids for method, ids in winners.items()}}
        if i not in base:
            additions[i] = routes(base | {i})
            inventory[i]["addition"] = additions[i]
    print("Baseline and", len(inventory), "local candidates checked", flush=True)

    exchanges, summaries = {}, {}
    for key, item in group.items():
        local = [i for i in item["local_ids"] if i not in base]
        named = [entry["candidate_id"] for entry in item["named_mutual_supports"]
                 if entry.get("candidate_id") is not None and entry["candidate_id"] not in base]
        targets = list(dict.fromkeys(local[:3] + named))
        item["targets"] = targets
        counts = Counter()
        trials = []

        def attempt(add, remove):
            selected = (base | set(add)) - set(remove)
            result = validate(frozenset(selected))
            counts[(len(add), len(remove), "structural" if result["valid"] else "rejected")] += 1
            if result["valid"]:
                trials.append((tuple(sorted(add)), tuple(sorted(remove)), frozenset(selected)))

        for i in local:
            for j in sorted(base):
                attempt([i], [j])
        # Rank nearby removals by represented regions and direct network
        # contacts. Pair additions are chosen from the entire pool.
        for i in targets:
            touches = set(graph[i]) & base
            covered = set(inventory[i]["convex_regions"])
            ordered = sorted(base, key=lambda j: (-sum(j in region_sets[r] for r in covered),
                                                    j not in touches, lines[j].length, j))[:8]
            item.setdefault("bounded_removals", {})[i] = ordered
            for removed in combinations(ordered, 2):
                attempt([i], removed)
            others = sorted(set(graph[i]) - base - {i}, key=lambda j: (-len(set(graph[j]) & base),
                                                                       -lines[j].length, j))[:8]
            item.setdefault("second_additions", {})[i] = others
            for j in others:
                for removed in combinations(ordered[:6], 3):
                    attempt([i, j], removed)
        exchanges[key] = []
        for add, remove, selected in sorted(set(trials), key=lambda x: (len(x[2]), x[0], x[1])):
            result = routes(selected)
            exchanges[key].append({"add": add, "remove": remove, **result})
        summaries[key] = [{"added": a, "removed": r, "status": status, "trials": value}
                          for (a, r, status), value in sorted(counts.items())]
        print(key, "exchange trials", dict(counts), flush=True)
    combos = []
    preferred = [next(i for i in item["local_ids"] if i not in base) for item in group.values()]
    for count in (2, 3):
        for add in combinations(preferred, count):
            supersets = base | set(add)
            combos.append({"add": add, "remove": [], **routes(supersets)})
            removable = [i for i in base if validate(supersets - {i})["valid"]]
            for removed in combinations(removable, count):
                chosen = supersets - set(removed)
                if validate(chosen)["valid"]:
                    combos.append({"add": add, "remove": removed, **routes(chosen)})
    atomic_write(OUTPUT / "audit.json", encode({"source": lineage, "actual_cells": len(polygons), "window": RADIUS, "baseline": base_check,
                  "baseline_ids": sorted(base), "global_longest": max(lines, key=lambda line: line.length).line_id,
                  "global_longest_length": max(line.length for line in lines), "groups": group, "inventory": inventory,
                  "exchanges": exchanges, "exchange_trials": summaries, "combinations": combos}))


if __name__ == "__main__":
    main()
