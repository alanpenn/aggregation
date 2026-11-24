"""Flat 40 vertex diagnosis and geometric E backbone trials from published exports."""
import argparse
from collections import defaultdict
import csv
from fractions import Fraction
from io import StringIO
from itertools import combinations
import json
from math import dist
from pathlib import Path
from statistics import mean, median, quantiles

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection
from shapely.geometry import LineString, MultiPoint, Point, box

from experiments.vertex_directional_pruning import experiment, families
from voronoi_app.angular import _on_segment
from voronoi_app.batch_store import BatchStore, atomic_write, encode

ROOT = Path("diagnostics/strict-generalisation")
TARGETS = {(15, 25): (957, 865), (6, 5): (1244, 1189, 1190, 1208),
           (41, 43): (1355, 1354)}
WEIGHTS = {"E-raw": {"raw": 1}, "E-family": {"family": .6, "length": .2, "mean_length": .2},
           "E-connectivity": {"family": .30, "length": .15, "reach": .10,
                              "regions": .20, "transverse": .25}}


def read(path):
    return json.loads(path.read_bytes())


def rational(values):
    return tuple(map(Fraction, values))


def crossing_span(sites):
    by_family = defaultdict(list)
    for point, groups in sites.items():
        xy = tuple(map(float, rational(point)))
        for group in groups:
            by_family[group].append(xy)
    hulls = [MultiPoint(points).convex_hull for points in by_family.values()]
    extremes = [list((hull.exterior if hull.geom_type == "Polygon" else hull).coords)
                for hull in hulls]
    return max((dist(a, b) for left, right in combinations(extremes, 2)
                for a in left for b in right), default=0)


def build_index(archive):
    saved = experiment(archive)
    old = read(archive / "vertex-axial-1/vertices.json")
    lines = saved["candidates"]
    measures = read(archive / "constructive-axial-3/flat-40/geometry.json")["candidates"]
    endpoints = [(rational(row["start"]), rational(row["end"])) for row in lines]
    lengths = [Fraction(row["squared_length"]) for row in lines]
    angles = [row["orientation_degrees"] for row in lines]
    thresholds = [median(row["length"] for row in lines),
                  quantiles([row["length"] for row in lines], n=4, method="inclusive")[2]]
    vertices = []
    for v in old["vertices"]:
        ids = v["supported"]
        coord = rational(v["point"])
        xy = tuple(map(float, coord))
        contacts = {}
        for i, (a, b) in enumerate(endpoints):
            if all(min(u, w) <= p <= max(u, w) for u, w, p in zip(a, b, coord)) and _on_segment(coord, a, b):
                members = v["support_members"].get(str(i), [])
                contacts[i] = {"support_members": members, "directional_support": bool(members),
                               "at_maximal_endpoint": coord in (a, b),
                               "incidental_collinearity": not members and coord not in (a, b)}
        groups = families(ids, angles, lengths, 10)
        extended = {i for i in ids if lines[i]["length"] > thresholds[0]}
        long_groups = [g for g in groups if extended.intersection(g["candidate_ids"])]
        group_by_line = {i: j for j, g in enumerate(groups) for i in g["candidate_ids"]}
        junction_sites = defaultdict(set)
        for i in ids:
            for p in measures[i]["transverse"].values():
                if coord != rational(p):
                    junction_sites[tuple(p)].add(group_by_line[i])
        junction_span = crossing_span(junction_sites)
        crossing_support_families = set().union(*junction_sites.values())
        crossing = {int(j) for i in ids for j in measures[i]["transverse"]}
        transverse = families(crossing, angles, lengths, 10)
        regions = sorted({r for i in ids for r in lines[i]["regions"]})
        reach = max((dist(xy, p) for i in ids for p in endpoints[i]), default=0)
        long_counts = [sum(lines[i]["length"] > threshold for i in ids) for threshold in thresholds]
        concentration = sum(sorted((len(extended.intersection(g["candidate_ids"]))
                                    for g in long_groups), reverse=True)[:2]) / max(1, len(extended))
        vertices.append({k: v[k] for k in ("id", "point", "members")} |
                        {"contacts": contacts, "supporting_ids": ids, "families": groups,
                         "raw": len(ids), "family": len(groups),
                         "length": max((lines[i]["length"] for i in ids), default=0),
                         "mean_length": mean([lines[i]["length"] for i in ids] or [0]),
                         "long_counts": long_counts, "region_ids": regions, "regions": len(regions),
                         "reach": reach, "transverse": len(transverse),
                         "intersection_dispersion": mean([measures[i]["family_span"] for i in ids] or [0]),
                         "junction_points": sorted(junction_sites), "junction_span": junction_span,
                         "redundancy": 1 - len(groups) / max(1, len(ids)) if ids else 0,
                         "corridor_score": concentration * long_counts[0] * reach,
                         "junction_score": len(crossing_support_families) * junction_span})
    links = defaultdict(list)
    for i, supports in enumerate(old["candidate_supports"]):
        for a, b in combinations(sorted(supports), 2):
            links[a, b].append(i)
    return saved, measures, vertices, old["candidate_supports"], thresholds, links


def backbone(variant, vertices, support, lines, measures):
    weights = WEIGHTS[variant]
    maxima = {key: max(v[key] for v in vertices) or 1 for key in weights}
    scores = [sum(w * v[key] / maxima[key] for key, w in weights.items()) for v in vertices]
    vertex_order = sorted(range(len(vertices)), key=lambda i: (-scores[i], i))
    high = set(vertex_order[:max(1, len(vertices) // 10)])
    representatives = {f["representative"] for v in high for f in vertices[v]["families"]}
    length_max = max(row["length"] for row in lines)
    region_max = max(len(row["regions"]) for row in lines)
    transverse_max = max(len(row["families"]) for row in measures)
    rows = []
    for i, line in enumerate(lines):
        vs = support[i]
        strength = max((scores[v] for v in vs), default=0)
        distinct = len(measures[i]["families"])
        high_count = len(high.intersection(vs))
        local_families = {v: next(j for j, f in enumerate(vertices[v]["families"])
                                  if i in f["candidate_ids"]) for v in vs}
        base = (.45 * strength + .15 * line["length"] / length_max
                + .15 * distinct / transverse_max + .10 * len(line["regions"]) / region_max
                + .15 * (i in representatives))
        rows.append({"id": i, "vertex_strength": strength, "high_vertices": high_count,
                     "supporting_vertices": vs, "supporting_family_indices": local_families,
                     "length": line["length"], "region_count": len(line["regions"]),
                     "transverse_families": distinct, "redundant_neighbors": measures[i]["redundant"],
                     "high_vertex_family_representative": i in representatives, "base_score": base})
    ranking = sorted(range(len(lines)), key=lambda i: (-rows[i]["base_score"], i))
    chosen, covered, trace = set(), set(), []
    for _ in range(12):
        eligible = [i for i in ranking if i not in chosen and not chosen.intersection(measures[i]["redundant"])]
        def marginal(i):
            new = len(set(lines[i]["regions"]) - covered)
            connected = sum(bool(chosen.intersection(f)) for f in measures[i]["families"])
            score = rows[i]["base_score"] + .15 * new / region_max + .10 * connected / max(1, len(chosen))
            return score, new, connected
        terms = {i: marginal(i) for i in eligible}
        winner = min(eligible, key=lambda i: (-terms[i][0], i))
        score, new, connected = terms[winner]
        trace.append(rows[winner] | {"score": score, "new_regions": new, "backbone_transverse_families": connected})
        covered.update(lines[winner]["regions"])
        chosen.add(winner)
    return {"vertex_scores": scores, "vertex_ranking": vertex_order, "line_ranking": ranking,
            "line_measures": rows, "backbone": sorted(chosen), "trace": trace}


def compare(vertices, lines, measures, trials, d_ids, backward_ids):
    d_set = set(d_ids)
    d_geometry = [LineString([rational(lines[i][key]) for key in ("start", "end")]) for i in d_ids]
    sites = MultiPoint(list({tuple(map(float, rational(p))) for i in d_ids
                             for j, p in measures[i]["transverse"].items() if int(j) in d_set}))
    points = [Point(rational(v["point"])) for v in vertices]
    corridor_distances = [min(p.distance(line) for line in d_geometry) for p in points]
    junction_distances = [p.distance(sites) for p in points]
    result = {}
    for name, trial in trials.items():
        top = set(trial["vertex_ranking"][:len(vertices)//10])
        ids = trial["backbone"]
        targets = [i for group in TARGETS.values() for i in group]
        result[name] = {
            "top_decile_vertex_count": len(top),
            "median_distance_to_d_line": [median(d for i, d in enumerate(corridor_distances)
                                                  if (i in top) == group) for group in (True, False)],
            "median_distance_to_d_transverse_crossing": [
                median(d for i, d in enumerate(junction_distances) if (i in top) == group)
                for group in (True, False)],
            "backbone_region_count": len({r for i in ids for r in lines[i]["regions"]}),
            "backbone_intersection_count": sum(j in ids for i in ids
                                               for j in measures[i]["intersections"] if j > i),
            "targets": {i: {"line_rank": trial["line_ranking"].index(i) + 1,
                            "in_backbone": i in ids, "in_d": i in d_set,
                            "in_backward": i in backward_ids, "supports": [
                                {"vertex": v, "vertex_rank": trial["vertex_ranking"].index(v) + 1,
                                 "vertex_score": trial["vertex_scores"][v],
                                 "point": vertices[v]["point"],
                                 "labels": sorted({vertices[v]["members"][member]["label"]
                                                   for member in vertices[v]["contacts"][i]["support_members"]})}
                                for v in trial["line_measures"][i]["supporting_vertices"]]}
                        for i in targets},
        }
    return result


def write_vertex_table(output, vertices, trials):
    stream = StringIO(newline="")
    measures = ("id", "raw", "family", "length", "mean_length", "regions", "reach", "transverse",
                "intersection_dispersion", "junction_span", "redundancy", "corridor_score", "junction_score")
    headings = [*measures, "x_exact", "y_exact", "building_labels", "above_median", "above_upper_quartile"]
    for name in trials:
        headings.extend((f"{name}_rank", f"{name}_score"))
    writer = csv.DictWriter(stream, fieldnames=headings)
    writer.writeheader()
    ranks = {name: {v: rank for rank, v in enumerate(row["vertex_ranking"], start=1)}
             for name, row in trials.items()}
    for vertex in vertices:
        i = vertex["id"]
        x, y = vertex["point"]
        median_count, quartile_count = vertex["long_counts"]
        row = {key: vertex[key] for key in measures} | {
            "x_exact": x, "y_exact": y, "above_median": median_count,
            "above_upper_quartile": quartile_count,
            "building_labels": ",".join(map(str, sorted({m["label"] for m in vertex["members"]}))),
        }
        for name, trial in trials.items():
            row[f"{name}_rank"] = ranks[name][i]
            row[f"{name}_score"] = trial["vertex_scores"][i]
        writer.writerow(row)
    atomic_write(output / "vertex-statistics.csv", stream.getvalue().encode())


def plots(output, vertices, lines, controls, trials):
    cells = defaultdict(dict)
    for v in vertices:
        for m in v["members"]:
            cells[m["label"]][m["vertex_index"]] = tuple(map(float, rational(v["point"])))
    polygons = {label: [p for _, p in sorted(ring.items())] for label, ring in cells.items()}
    points = [tuple(map(float, rational(v["point"]))) for v in vertices]
    intervals = [[tuple(map(float, rational(row[e]))) for e in ("start", "end")] for row in lines]
    selected = trials["E-connectivity"]
    principal = list(dict.fromkeys(r["id"] for r in selected["trace"]))
    output.mkdir(parents=True, exist_ok=True)
    with PdfPages(output / "flat-40-atlas.pdf") as atlas:
        def draw(name, title, values=None, ids=(), labels=None, focus=()):
            fig, ax = plt.subplots(figsize=(11, 10))
            ax.add_collection(PolyCollection(list(polygons.values()), facecolor="#e0e5e6",
                                             edgecolor="#758792", linewidth=.55))
            for label, ring in polygons.items():
                x, y = map(mean, zip(*ring))
                ax.text(x, y, str(label), ha="center", va="center", fontsize=6, clip_on=True)
            if ids:
                ax.add_collection(LineCollection([intervals[i] for i in ids], colors="#256f99",
                                                 linewidths=1.15, alpha=.74))
            if values is not None:
                scatter = ax.scatter(*zip(*points), c=values, s=[6 + 2.5*v["raw"] for v in vertices],
                                     cmap="plasma", edgecolors="#30343b", linewidths=.2, zorder=3)
                fig.colorbar(scatter, ax=ax, shrink=.65)
            if focus:
                relevant = {v["id"] for v in vertices if set(focus).intersection(v["supporting_ids"])}
                ranks = {v: i+1 for i, v in enumerate(selected["vertex_ranking"])}
                for v in sorted(relevant):
                    ax.scatter(*points[v], s=35, color="#9d2533", zorder=5)
                    ax.annotate(f'v{v} · rank {ranks[v]}\n{selected["vertex_scores"][v]:.3f}', points[v],
                                xytext=(5, 5 + 12*(v % 3)), textcoords="offset points", fontsize=7, clip_on=True)
            if labels:
                local = [p for label in labels for p in polygons[label]]
                x, y = zip(*local)
                left, bottom, right, top = min(x)-10, min(y)-10, max(x)+10, max(y)+10
                ax.set(xlim=(left, right), ylim=(bottom, top))
                for j, i in enumerate(ids):
                    visible = LineString(intervals[i]).intersection(box(left, bottom, right, top))
                    if visible.length:
                        location = visible.interpolate((j+1)/(len(ids)+1), normalized=True)
                        ax.annotate(str(i), (location.x, location.y), xytext=(3, 3),
                                    textcoords="offset points", color="#184e72", fontsize=8,
                                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85})
            else:
                ax.set(xlim=(-1, 101), ylim=(-1, 101))
            ax.set_aspect("equal")
            ax.set_title(title)
            ax.set_axis_off()
            fig.savefig(output / f"{name}.pdf", bbox_inches="tight")
            fig.savefig(output / f"{name}.png", bbox_inches="tight", dpi=400)
            atlas.savefig(fig, bbox_inches="tight")
            plt.close(fig)

        for name, title, values in (
            ("families", "Tangent direction families", [v["family"] for v in vertices]),
            ("extended", "Tangents above the pool median length", [v["long_counts"][0] for v in vertices]),
            ("corridor", "Corridor score", [v["corridor_score"] for v in vertices]),
            ("junction", "Junction score from separated transverse crossings", [v["junction_score"] for v in vertices]),
        ):
            draw(name, title, values)
        draw("significant-tangents", "Initial E-connectivity backbone", selected["vertex_scores"], principal)
        for name in ("E-raw", "E-family"):
            draw(name.lower(), f"Initial {name} backbone", trials[name]["vertex_scores"], trials[name]["backbone"])
        draw("algorithm-d", "Archived 33-line Algorithm D", ids=controls)
        for labels, targets in TARGETS.items():
            draw(f"buildings-{labels[0]}-{labels[1]}", f"Buildings {labels[0]} and {labels[1]}",
                 ids=targets, labels=labels, focus=targets)


def complete_flat40(batch_root, output, saved, measures, trials):
    """Run the shared D completion and evaluation on restored immutable inputs."""
    from experiments.constructive_axial import Selection, construct, evaluate
    from voronoi_app.angular import LineClearance
    from voronoi_app.batch_methods import _domain
    from voronoi_app.exact_axial import candidate_graph
    from voronoi_app.exact_enumeration import exact_pool_from_dict
    from voronoi_app.experimental_visibility import IndexedClearance

    store = BatchStore(batch_root)
    inputs = {}
    for stage, reference in saved["input_records"].items():
        record, inputs[stage], checksum = store.load(reference["id"])
        if checksum != reference["sha256"] or record["output_sha256"] != reference["output"]:
            raise ValueError(f"Restored {stage} record differs from the archived Flat 40 input.")
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    _, occupied, accessible, obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible, obstacles, original_obstacles=occupied.values()))
    graph = candidate_graph(lines)

    class VertexSelection(Selection):
        def backbone(self, method, ranking, trace):
            for row in trials[method]["trace"]:
                trace.append(row | {"stage": "backbone", "add": [row["id"]]})
            return set(trials[method]["backbone"])

    selector = VertexSelection(inputs, lines, graph, measures, clearance)
    outcomes = {}
    for name, trial in trials.items():
        outcomes[name] = construct(selector, name, trial["line_ranking"])
        atomic_write(output / f"{name}-completion.json", encode(outcomes[name]))
    reference = read(batch_root / "route-references/flat-40.json")
    valid = {name: outcome for name, outcome in outcomes.items() if outcome.get("maps")}
    if valid:
        atomic_write(output / "movement.json", encode(evaluate(inputs, lines, clearance, reference, valid)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "vertex-significance-diagnosis-1")
    parser.add_argument("--batch-root", type=Path, help="Restored Flat 40 extended-terrain batch directory")
    args = parser.parse_args()
    saved, measures, vertices, supports, thresholds, links = build_index(args.archive)
    lines = saved["candidates"]
    d = read(args.archive / "constructive-axial-3/flat-40/D.json")
    movement = read(args.archive / "constructive-axial-3/flat-40/movement.json")
    trials = {key: backbone(key, vertices, supports, lines, measures) for key in WEIGHTS}
    comparison = compare(vertices, lines, measures, trials, d["maps"]["exchanged"], movement["baseline"]["ids"])
    plots(args.output, vertices, lines, d["maps"]["exchanged"], trials)
    write_vertex_table(args.output, vertices, trials)
    atomic_write(args.output / "diagnosis.json", encode({
        "input_records": saved["input_records"], "input_hashes": saved["input_hashes"],
        "length_thresholds": thresholds, "vertices": vertices, "candidates": lines,
        "vertex_links": [{"vertices": pair, "candidate_ids": ids} for pair, ids in sorted(links.items())],
        "weights": WEIGHTS, "trials": trials, "comparison": comparison, "archived_d": d["maps"],
        "targets": [i for group in TARGETS.values() for i in group],
    }))
    if args.batch_root is not None:
        complete_flat40(args.batch_root, args.output, saved, measures, trials)


if __name__ == "__main__":
    main()
