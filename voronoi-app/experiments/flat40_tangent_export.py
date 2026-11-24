"""Export the Flat 40 tangent investigation and exact-interval diagnostics."""
from hashlib import sha256
import json

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely import from_wkb
from shapely.geometry import LineString

from experiments.flat40_tangent_audit import OUTPUT, load
from experiments.plot_facewise_matched import draw_map
from voronoi_app.exact_axial import candidate_graph
from voronoi_app.experimental_entrance_reduction import union_mask
from voronoi_app.strict_coverage_experiment import incidence_sets
import networkx as nx
from voronoi_app.angular import _intersections
from voronoi_app.exact_enumeration import exact_pool_from_dict


def guided_history(inputs, lines, targets):
    """Rebuild the coverage, pruning and shortcut eligibility from saved inputs."""
    analysis = inputs["analysis"]
    if analysis["circulation_proof"] != "exact ring-seed subset":
        raise ValueError("This replay expects the archived ring support subset.")
    graph = candidate_graph(lines)
    regions, links = incidence_sets(analysis["incidence"])
    masks = [0] * len(lines)
    doors = [0] * len(lines)
    for region, group in regions.items():
        for i in group:
            masks[i] |= 1 << region
    for door, group in enumerate(links):
        for i in group:
            doors[i] |= 1 << door
    target = sum(1 << region for region in regions)
    all_doors = (1 << len(links)) - 1
    witnesses = set(inputs["candidates"]["pool"]["ring_candidates"])
    selected = set(witnesses)
    records = {i: {"ring_seed": i in witnesses, "coverage_eligible_rounds": 0, "coverage_selected": False,
                   "coverage_pruned": False, "shortcut_shortlisted_rounds": 0,
                   "shortcut_eligibility": []} for i in targets}
    while True:
        uncovered = target & ~union_mask(masks, selected)
        missing = all_doors & ~union_mask(doors, selected)
        if not uncovered and not missing and nx.is_connected(graph.subgraph(selected)):
            break
        available = ({i for j in selected for i in graph[j]} - selected if selected else set(graph))
        winner = max(available, key=lambda i: ((masks[i] & uncovered).bit_count() + (doors[i] & missing).bit_count(),
                                              len(selected.intersection(graph[i])), len(graph[i]), -i))
        for i in targets & available:
            records[i]["coverage_eligible_rounds"] += 1
        if winner in records:
            records[winner]["coverage_selected"] = True
        selected.add(winner)
    for i in sorted(selected - witnesses):
        trial = selected - {i}
        if (union_mask(doors, trial) == all_doors and union_mask(masks, trial) == target
                and nx.is_connected(graph.subgraph(trial))):
            selected = trial
            if i in records:
                records[i]["coverage_pruned"] = True
    growth = analysis["entrance_growth"]
    for step in [*growth, *([None] if len(growth) < 8 else [])]:
        available = {i for j in selected for i in graph[j]} - selected
        ranking = sorted(available, key=lambda i: (-len(selected.intersection(graph[i])), -doors[i].bit_count(),
                                                   -lines[i].length, i))
        alternatives = sorted(available, key=lambda i: (-doors[i].bit_count(), -len(selected.intersection(graph[i])), i))
        shortlist = set(ranking[:16]) | set(alternatives[:8])
        for i in targets:
            records[i]["shortcut_eligibility"].append({
                "primary_rank": ranking.index(i) + 1 if i in available else None,
                "doorway_rank": alternatives.index(i) + 1 if i in available else None,
                "chosen": bool(step and step["line"] == i),
            })
        for i in targets & shortlist:
            records[i]["shortcut_shortlisted_rounds"] += 1
        if step:
            assert step["line"] in shortlist
            selected.add(step["line"])
    assert sorted(selected) == analysis["maps"]["strict_entrance_guided"]["line_ids"]
    for i, row in records.items():
        row["in_guided"] = i in selected
    return records


def candidate_table(group, inventory):
    for i in group["targets"]:
        row = inventory[str(i)]
        add = row["addition"]
        history = "Removed at deletion " + str(row["deletion_index"] + 1) if row["removed"] else (
            "Retained" if row["in_backward"] else "Omitted by entrance-guided selection")
        yield (f"| {i} | {row['length']:.2f} | {len(row['selected_intersections'])} | "
               f"{len(row['transverse_selected'])} | {len(row['convex_regions'])} | "
               f"{len(row['doorway_building_labels'])} | {history} | {add.get('rank', '—')} | "
               f"{add['angular']['mean']:.4f} | {add['metric']['mean']:.4f} |")


def ranked(rows):
    return sorted((row for row in rows if row["valid"]),
                  key=lambda row: (row["angular"]["mean"], row["metric"]["mean"], row["length"],
                                   row["add"], row["remove"]))


def describe_exchange(row):
    additions = ", ".join(map(str, row["add"]))
    removed = ", ".join(map(str, row["remove"])) or "none"
    return (f"{row['line_count']} lines and total length {row['length']:.2f}, with rank {row['rank']}/{row['required_rank']}. "
            f"Add {additions}, remove {removed}. Angular mean {row['angular']['mean']:.4f}, "
            f"max {row['angular']['max']:.4f}. Metric mean {row['metric']['mean']:.4f}, "
            f"max {row['metric']['max']:.4f}.")


def write_report(data, best, history):
    base = data["baseline"]
    sections = ["# Flat seed 40 axial tangent investigation", "",
                "The corrected settlement and its saved candidate and selection records are identified by output and "
                f"source hashes in [audit.json](audit.json). The grid was configured for 500 points and produced {data['actual_cells']} clipped cells with "
                "the original 100 building labels.", "",
                "The local inventory uses intervals within two canvas units of both named polygons. Independent supporting "
                "vertex tests include frontages within five units of either polygon. These operational windows define a "
                "bounded local search. The figures show which lines the window includes.", "",
                f"The strict backward baseline has {base['line_count']} lines, total length {base['length']:.2f}, and "
                f"full winding rank {base['rank']}/{base['required_rank']}. Across {base['metric']['reachable']:,} reachable "
                f"doorway pairs, angular mean and maximum are {base['angular']['mean']:.4f} and {base['angular']['max']:.4f} "
                f"quarter turns, and metric mean and maximum are {base['metric']['mean']:.4f} and {base['metric']['max']:.4f} "
                "canvas units in the finite certified routing graph.", "",
                f"The globally longest certified interval is candidate {data['global_longest']} "
                f"at {data['global_longest_length']:.2f} units.", ""]
    for key, group in data["groups"].items():
        inventory = data["inventory"]
        longest = group["local_ids"][0]
        direct = group["named_mutual_supports"]
        exact = sorted({r["candidate_id"] for r in direct if r.get("candidate_id") is not None})
        rejected = sum(r["status"] == "rejected" for r in direct)
        absent = group["independently_certified_absent"]
        sections += [f"## Buildings {key.replace('-', ' and ')}", "",
                     f"The longest local certified interval is **{longest}** at {inventory[str(longest)]['length']:.2f} units. "
                     f"The pool contains {len(group['local_ids'])} local intervals. Exact mutual supports between the two named "
                     f"buildings produce candidate IDs {', '.join(map(str,exact)) or 'none'}. "
                     f"The independent search rejected {rejected} named support seeds and certified {len(absent)} absent local intervals.",
                     "", "| Candidate | Length | Baseline intersections | Transverse | Regions | Doorways | Selection history | Rank after addition | Angular mean after addition | Metric mean after addition |",
                     "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|",
                     *candidate_table(group, inventory), ""]
        for entry in direct:
            if entry["status"] == "rejected":
                blockers = ", ".join(map(str, entry["blocking_buildings_or_effective_cells"]))
                sections.append(f"- A named mutual support failed exact clearance through {entry['reason']}"
                                + (f" at {blockers}." if blockers else "."))
        swaps = ranked(data["exchanges"][key])
        for candidate in group["targets"]:
            row = inventory[str(candidate)]
            add = row["addition"]
            related = [trial for trial in swaps if candidate in trial["add"]]
            best_count = min((trial["line_count"] for trial in related), default=None)
            outcome = f"The smallest accepted exchange containing it used {best_count} lines." if best_count is not None else (
                "The tested exchanges containing it yielded no accepted map.")
            trace = history[candidate]
            if trace["coverage_pruned"]:
                pathway = " It entered greedy coverage and was removed in the guided coverage pruning pass."
            elif not trace["in_guided"] and not trace["shortcut_shortlisted_rounds"]:
                pathway = (" It did not win a greedy coverage round or reach the shortcut shortlist.")
            elif not trace["in_guided"]:
                pathway = " It reached the shortcut shortlist without being chosen."
            else:
                pathway = ""
            corridor_maps = [name for name, key in (("geometric extreme", "geometric_extreme"),
                                                       ("route-ranked", "route_ranked")) if row[key]]
            membership = " Final corridor map membership " + (", ".join(corridor_maps) or "none") + "."
            sections.append(
                f"- Candidate {candidate} changed angular mean by {add['angular']['mean']-base['angular']['mean']:+.4f} "
                f"and maximum by {add['angular']['max']-base['angular']['max']:+.4f}. "
                f"Metric mean changed by {add['metric']['mean']-base['metric']['mean']:+.4f} "
                f"and maximum by {add['metric']['max']-base['metric']['max']:+.4f}. {outcome}{pathway}{membership}")
        equal = [r for r in swaps if r["line_count"] == base["line_count"]]
        smaller = [r for r in swaps if r["line_count"] < base["line_count"]]
        if equal:
            sections.append("Best equal-count exchange by angular mean, with metric mean as the tiebreaker. " +
                            describe_exchange(equal[0]))
        else:
            sections.append("No equal-count exchange in the tested set passed all checks.")
        if smaller:
            sections.append("Best lower-count exchange under the same ordering. " + describe_exchange(smaller[0]))
        else:
            sections.append("The bounded lower-count search yielded no accepted exchange.")
        sections += ["", f"[Numbered comparison PDF]({key}-comparison.pdf) · [High-resolution PNG]({key}-comparison.png)", ""]
    sections += ["## Full-map comparisons", ""]
    for title, row in best.items():
        if row:
            sections.append(f"**{title}.** " + describe_exchange(row))
    equal = best["Best equal-count exchange"]
    lower = best["Best lower-count exchange"]
    sections += ["", "## Selection implications", "",
                 "The archived guided map started with 387 ring-supported lines. That set already met the initial "
                 "coverage, doorway and connectivity targets. Four shortlisted shortcuts grew it to 391 lines. "
                 "The three longest local candidates remained outside the shortcut shortlist and thus outside "
                 "the backward deletion order. The guided-history record includes their exact shortlist ranks."]
    if equal:
        sections.append(
            f"The best equal-count exchange changes angular mean by {equal['angular']['mean']-base['angular']['mean']:+.4f} "
            f"and metric mean by {equal['metric']['mean']-base['metric']['mean']:+.4f}. "
            "The equal line count isolates the movement trade-off from a change in map size.")
    accepted = ranked([row for trials in data["exchanges"].values() for row in trials] + data["combinations"])
    efficient = [row for row in accepted if row["line_count"] <= base["line_count"]
                 and row["angular"]["mean"] < base["angular"]["mean"] - 1e-9
                 and row["metric"]["mean"] < base["metric"]["mean"] - 1e-9]
    sections.append(f"{len(efficient)} accepted trial entries reduce both means at equal or lower line count.")
    if lower:
        sections.append(f"The bounded search also found a certified map with {base['line_count']-lower['line_count']} fewer lines. "
                        "Shortest-first deletion alone could not make its new lines available.")
    sections.append("The leading local tangents were present in the certified pool. Their selection histories identify "
                    "where each was lost. Shortest-first ordering tests shorter lines earlier, while the guided coverage rule uses junction counts as tiebreakers. "
                    "One shortcut shortlist uses length as a later tiebreaker before entrance-depth ranking. These three local cases "
                    "cannot establish a systematic disadvantage across settlements.")
    sections += ["", "The JSON records exact endpoints, supporting vertices or faces, pool intersections, traversed regions, "
                 "doorway labels, circulation certificates at archived deletions, and both movement distributions for every "
                 "routed proposal. Transverse intersections use an acute crossing angle of at least 30°. All lines added "
                 "individually attach to the existing connected component when they intersect it. Multiple crossings can "
                 "provide alternate routes inside that same component. In the simple line-intersection graph, "
                 "an added line with d contacts increases cycle rank by d − 1. Geometric circulation winding is checked separately.", "",
                 "One-for-one exchanges test all local nonbaseline candidates against every retained line. Lower-count "
                 "exchanges use the three longest local omissions and any named-pair omissions as primary additions. "
                 "They test one addition against pairs from eight ranked removals and two additions against triples from "
                 "six ranked removals. Second additions are drawn from the full certified pool among intersecting lines. "
                 "The combinations pass also tests joint additions of the local leaders. These trials establish local "
                 "exchange opportunities within the stated search budget.", "",
                 "The guided ranking works from necessary coverage and entrance access. The backward pass deletes shortest-first "
                    "from the guided set and checks exact clearance, region coverage, doorway incidence, connectivity and winding. "
                 "An absent line never enters its deletion order. The trials distinguish that search restriction from geometric "
                 "certification and measure route costs that the deletion rule treats as outside its structural objective.", "",
                 "[Vector atlas](numbered-axial-audit.pdf) · [Exact audit and trial results](audit.json) · [Guided selection replay](guided-history.json)", ""]
    (OUTPUT / "report.md").write_text("\n".join(sections))


def export():
    data = json.loads((OUTPUT / "audit.json").read_bytes())
    inputs, _, polygons, labels = load()
    settlement = inputs["settlement"]
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    regions = {int(i): from_wkb(wkb) for i, wkb in inputs["candidates"]["regions_wkb"].items()}
    base = set(data["baseline_ids"])
    all_trials = [r for rows in data["exchanges"].values() for r in rows] + data["combinations"]
    for i, row in data["inventory"].items():
        if row.get("addition"):
            all_trials.append({"add": [int(i)], "remove": [], **row["addition"]})
    best = {
        "Best equal-count exchange": next(iter(ranked(r for r in all_trials if r["line_count"] == len(base))), None),
        "Best lower-count exchange": next(iter(ranked(r for r in all_trials if r["line_count"] < len(base))), None),
        "Best angular route alternative": next(iter(ranked(all_trials)), None),
        "Best metric route alternative": min((r for r in all_trials if r["valid"]),
                                             key=lambda r: (r["metric"]["mean"], r["angular"]["mean"]), default=None),
    }

    def draw_lines(ax, ids, color, width, zorder, alpha=1):
        segments = [[lines[i].start, lines[i].end] for i in sorted(ids)]
        collection = LineCollection(segments, colors=color, linewidths=width, zorder=zorder, alpha=alpha)
        ax.add_collection(collection)
        assert [segment.tolist() for segment in collection.get_segments()] == [
            [[float(value) for value in point] for point in segment] for segment in segments]

    def save(fig, stem, atlas):
        for suffix in ("png", "pdf"):
            fig.savefig(OUTPUT / f"{stem}.{suffix}", dpi=310, bbox_inches="tight", facecolor="white")
        atlas.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    with PdfPages(OUTPUT / "numbered-axial-audit.pdf") as atlas:
        for key, group in data["groups"].items():
            a, b = map(int, key.split("-"))
            target = group["local_ids"][0]
            interesting = [polygons[cell].bounds for cell,n in labels.items() if n in (a, b)]
            interesting.append(LineString([lines[target].start, lines[target].end]).bounds)
            x0, y0, x1, y1 = (func(bound[k] for bound in interesting) for k,func in enumerate((min,min,max,max)))
            extent = (max(0, x0 - 5), max(0, y0 - 5), min(100, x1 + 5), min(100, y1 + 5))
            swaps = ranked(data["exchanges"][key])
            best_local = next((r for r in swaps if target in r["add"]), swaps[0] if swaps else None)
            orange = set(best_local["remove"]) if best_local else set()
            fig, axes = plt.subplots(2, 2, figsize=(13, 13), layout="constrained")
            loc, pool, before, after = axes.flat
            fig.suptitle(f"Flat seed 40 · buildings {a} and {b} · longest local candidate {target}", fontsize=15)
            draw_map(loc, polygons, settlement, label_size=5)
            loc.add_patch(Rectangle(extent[:2], extent[2]-extent[0], extent[3]-extent[1],
                                    fill=False, edgecolor="#842ea2", linewidth=1.6, zorder=9))
            loc.set_title("Whole settlement and close-up extent")
            for ax in (pool, before, after):
                draw_map(ax, polygons, settlement, extent=extent, label_size=7)
                for cell, n in labels.items():
                    if n in (a,b):
                        ax.plot(*polygons[cell].exterior.xy, color="#842ea2", linewidth=1.6, zorder=7)
            for r in data["inventory"][str(target)]["convex_regions"]:
                pool.plot(*regions[r].exterior.xy, color="#67937a", linewidth=.7, alpha=.6, zorder=4)
            draw_lines(pool, group["local_ids"], "#7a8792", .85, 5, .65)
            named = {row["candidate_id"] for row in group["named_mutual_supports"]
                     if row.get("candidate_id") is not None}
            draw_lines(pool, named - {target}, "#b77ccc", 1.15, 7, .85)
            draw_lines(pool, [target], "#842ea2", 2, 8)
            pool.set_title("Local candidate inventory and traversed convex regions")
            draw_lines(before, base, "#155b94", 1.1, 4)
            draw_lines(before, orange, "#dc7018", 2, 6)
            draw_lines(before, [target], "#842ea2", 1.9, 7)
            row = data["inventory"][str(target)]
            for i in row["selected_intersections"]:
                for point in _intersections(lines[target].start, lines[target].end, lines[i].start, lines[i].end):
                    before.scatter(*map(float, point), c="#a72e8b" if i in row["transverse_selected"] else "#29333c",
                                   s=24, edgecolors="white", linewidths=.4, zorder=9)
            before.set_title("Strict backward baseline with proposed line and crossings")
            if best_local:
                draw_lines(after, base-orange, "#155b94", 1.1, 4)
                draw_lines(after, best_local["add"], "#842ea2", 1.8, 7)
                after.set_title(f"Certified exchange · {best_local['line_count']} lines · rank {best_local['rank']}/{best_local['required_rank']}")
            else:
                draw_lines(after, base, "#155b94", 1.1, 4)
                after.set_title("Baseline · no accepted local exchange")
            fig.legend(handles=[Line2D([],[],color=color,label=label) for color,label in
                                (("#155b94","Retained baseline"),("#842ea2","Proposed or added"),
                                 ("#dc7018","Removable in displayed exchange"),("#67937a","Traversed convex region"),
                                 ("#a72e8b","Transverse crossing"))], loc="outside lower center", ncols=5)
            save(fig, f"{key}-comparison", atlas)

        variants = [("Strict backward baseline", {"add": [], "remove": [], **data["baseline"]}),
                    *((title,row) for title,row in best.items() if row)]
        for index, (title,row) in enumerate(variants):
            fig, ax = plt.subplots(figsize=(9, 10), layout="constrained")
            draw_map(ax, polygons, settlement, label_size=6.5)
            draw_lines(ax, base - set(row["remove"]), "#155b94", 1, 4)
            draw_lines(ax, row["add"], "#842ea2", 1.8, 6)
            fig.suptitle(f"Flat seed 40 · {title}")
            ax.set_title(f"{row['line_count']} lines · length {row['length']:.1f} · complete strict coverage · "
                         f"rank {row['rank']}/{row['required_rank']}\nAngular mean {row['angular']['mean']:.3f} · "
                         f"metric mean {row['metric']['mean']:.2f}")
            save(fig, f"full-map-{index}", atlas)
    history = guided_history(inputs, lines, set(map(int, data["inventory"])))
    (OUTPUT / "guided-history.json").write_text(json.dumps(history, indent=2))
    write_report(data, best, history)
    files = sorted(p for p in OUTPUT.iterdir() if p.suffix in (".png", ".pdf", ".md", ".json"))
    (OUTPUT / "export-checksums.json").write_text(json.dumps({
        p.name: sha256(p.read_bytes()).hexdigest() for p in files if p.name != "export-checksums.json"}, indent=2))


if __name__ == "__main__":
    export()
