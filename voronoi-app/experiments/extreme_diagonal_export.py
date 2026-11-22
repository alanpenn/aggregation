"""Export maps and tabular diagnostics from completed extreme-diagonal cases."""
from collections import Counter
import csv
import json
import sys

from voronoi_app.batch_routing_reference import MasterNetwork, point
from voronoi_app.batch_store import BatchStore
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.route_sparse_experiment import doors_from_reference

from .extreme_diagonals import OUT, ROOT
from voronoi_app.extreme_diagonal_synthetic import FIXTURES


def export_case(case):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from shapely import from_wkb
    from voronoi_app.angular import _intersections

    state = json.loads((OUT / f"{case}.json").read_text())
    if state["status"] != "successful":
        raise ValueError(f"Unsuccessful experiment {case}: {state['error']}")
    _, data, _ = BatchStore(ROOT).load(state["record"])
    intervals = [tuple(map(point, pair)) for pair in data["intervals"]]
    lines = [ExactCandidate(i, a, b, a, b, "saved-certified-interval")
             for i, (a,b) in enumerate(intervals)]
    network = MasterNetwork(lines, doors_from_reference(data))
    polygons = data["settlement"]["polygons_wkb"]
    labels = data["settlement"]["building_labels"]
    rows = []
    for n, corridor in enumerate(data["corridors"], 1):
        variants = corridor["variants"]
        figure, axes = plt.subplots(1, 3, figsize=(15, 5), layout="constrained")
        exterior = set(corridor["exterior"])
        original = exterior | set(corridor["original_members"])
        pair = set(corridor["extreme_pair"] or ())
        repair = set(variants["C"].get("representatives", []))
        transverse = set(corridor["transverse"])
        for ax in axes:
            for key, label in labels.items():
                polygon = from_wkb(polygons[key])
                x,y = polygon.exterior.xy
                ax.fill(x,y,color="#353b41",zorder=0)
                centre = polygon.representative_point()
                ax.text(centre.x,centre.y,str(label),color="white",ha="center",va="center",
                        fontsize=4.7,zorder=6)
            ax.set(aspect="equal")
            ax.axis("off")

        def draw(ax, ids, colour, alpha, weight, zorder=1):
            if ids:
                ax.add_collection(LineCollection([intervals[i] for i in sorted(ids)], colors=colour,
                                                 alpha=alpha, linewidths=weight, zorder=zorder))

        draw(axes[0], set(corridor["members"]), "#84a3be", .48, .7)
        draw(axes[0], set(corridor["original_members"]), "#16537c", .75, 1.1, 3)
        draw(axes[0], pair, "#d64825", .95, 2, 5)
        axes[0].set_title("Certified sheaf and opposed pair")
        draw(axes[1], exterior, "#70787d", .14, .65)
        draw(axes[1], transverse, "#347485", .5, .9)
        draw(axes[1], pair, "#d64825", .95, 2, 5)
        draw(axes[1], repair-pair, "#6940a6", .96, 2, 5)
        for i in pair | repair:
            for j in network.graph[i]:
                if j in transverse:
                    for x,y in _intersections(*intervals[i], *intervals[j]):
                        axes[1].scatter(float(x),float(y),s=10,color="#142937",zorder=7)
        axes[1].set_title("Transverse contacts and repair lines")

        draw(axes[2], original, "#70787d", .18, .8)
        traces = {}
        selected = exterior | pair
        b = variants["B"]
        for measure, colour in (("metric", "#bd4829"), ("angular", "#6940a6")):
            impacted = b.get("affected_pairs", {}).get(measure, [])
            if not impacted:
                continue
            key = tuple(impacted[0]["doors"])
            trace_sets = [network.route(selection, measure=="angular", trace_pairs=[key])[key]
                          for selection in (original, selected)]
            traces[measure] = {"doors": list(key), "increase": impacted[0]["increase"],
                               "original": trace_sets[0], "extreme_pair": trace_sets[1]}
            for path, style in zip(trace_sets, ("--","-"), strict=True):
                if path:
                    x,y = zip(*path, strict=True)
                    axes[2].plot(list(map(float,x)),list(map(float,y)),linestyle=style,
                                 linewidth=1.5,color=colour,zorder=8,alpha=.85)
        lost = b.get("affected_pairs", {}).get("unreachable", [])
        if lost:
            i,j = lost[0]
            coords = [network.doors[k]["point"] for k in (i,j)]
            axes[2].scatter(*zip(*(tuple(map(float,p)) for p in coords)),marker="x",s=30,zorder=9,color="black")
        axes[2].set_title("Worst metric and angular routes\nDashed original, solid extreme pair")
        for ax in axes:
            ax.autoscale()
        figure.suptitle(f"{case} · Corridor {n} · Pair {b['status']} · Repair {variants['C']['status']}")
        with (OUT / f"{case}-{n}.png").open("xb") as stream:
            figure.savefig(stream,format="png",dpi=150)
        plt.close(figure)

        for variant, entry in variants.items():
            hard = entry.get("constraints", {})
            rows.append({
                "case": case, "corridor": n, "variant": variant, "status": entry["status"],
                "certified_sheaf": len(corridor["members"]),
                "selected_original_sheaf": len(corridor["original_members"]),
                "opposed_pairs": corridor["opposed_pairs"],
                "pair_members_already_selected": corridor["selected_pair_members"],
                "representatives": " ".join(map(str,entry.get("representatives",[]))),
                "line_count": entry.get("line_count"), "length": entry.get("length"),
                "external_connections": len(entry["external_connections"]) if hard else None,
                "transverse_connections": len(entry["transverse_connections"]) if hard else None,
                "coverage": hard.get("coverage_regions"), "required_coverage": hard.get("required_regions"),
                "components": hard.get("components"), "winding": hard.get("rank"),
                "required_winding": hard.get("required_rank"), "unattached_doors": hard.get("unattached_doors"),
                "clearance_rejections": len(hard["clearance_rejected"]) if hard else None,
                **{f"{measure}_{column}": entry.get(group,{}).get(measure,{}).get(stat,{}).get(key)
                   for measure in ("metric", "angular")
                   for column, group, stat, key in (
                        ("mean","route","cost","mean"), ("excess","route","absolute","mean"),
                        ("delta","deterioration","absolute","mean"),
                        ("delta_p95","deterioration","absolute","p95"),
                        ("delta_max","deterioration","absolute","max"),
                        ("unreachable","route","cost","unreachable"))},
            })
        with (OUT / f"{case}-{n}-worst-routes.json").open("x") as stream:
            json.dump({"routes": traces, "newly_unreachable": lost, "doorways": [
                {**{k:d[k] for k in ("building_cell", "open_cell")}, "point": d["point"]}
                for d in data["doorways"]]},stream,default=str)
    with (OUT / f"{case}.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: "null" if v is None else v for k,v in row.items()} for row in rows)


def combine():
    files = [(OUT / f"{case}.csv").read_text().splitlines(keepends=True)
             for case in ("Hill-42", "Y-42", *FIXTURES)]
    with (OUT / "comparison.csv").open("x") as stream:
        for index, lines in enumerate(files):
            stream.writelines(lines if index == 0 else lines[1:])


if __name__ == "__main__":
    if sys.argv[1] == "--combine":
        combine()
    else:
        export_case(sys.argv[1])
