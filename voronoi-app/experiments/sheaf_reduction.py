"""Run sheaf diagnostics and reductions as new records on the preserved benchmark."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from itertools import combinations
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
from matplotlib.colors import TwoSlopeNorm
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from shapely import from_wkb

from voronoi_app.angular import _intersections
from voronoi_app.batch import run_stage
from voronoi_app.batch_store import BatchStore, atomic_write, encode
from voronoi_app.sheaf_experiment import DEFAULTS, ORDERS


COLORS = ("#007c80", "#a63372", "#3554a4", "#ab5d19", "#81731a", "#62663c")


def figure(settlement, data, strategies, destination):
    positions = [[tuple(map(Fraction, point)) for point in line]
                 for line in data["canonical_intervals"]]
    polygons = {int(i): from_wkb(item) for i, item in settlement["polygons_wkb"].items()}
    labels = {int(i): n for i, n in settlement["building_labels"].items()}
    fig = Figure(figsize=(17, 7) if strategies else (11, 8), layout="constrained")
    FigureCanvasAgg(fig)
    axes = fig.subplots(1, 3 if strategies else 1, squeeze=False)[0]
    groups = data["sheaves"]

    def segment(i):
        return [tuple(map(float, point)) for point in positions[i]]

    def rings(ax, witnesses):
        ax.add_collection(LineCollection(
            [[tuple(float(Fraction(value)) for value in point) for point in ring["ring"]]
             for ring in witnesses],
            colors="#eeae52", linewidths=1.1, linestyles=":", alpha=.85, zorder=3,
        ))

    for ax in axes:
        for cell, poly in polygons.items():
            ax.fill(*poly.exterior.xy, facecolor="#303640" if cell in labels else "#f2f0e9",
                    edgecolor="#d8d3c8", linewidth=.27)
            if cell in labels:
                p = poly.representative_point()
                ax.text(p.x, p.y, str(labels[cell]), color="white", fontsize=6,
                        va="center", ha="center", zorder=6)
        ax.set_aspect("equal")
        ax.set_axis_off()

    original = set(data["selected"])
    ax = axes[0]
    sheaf_lines = {i for item in groups for i in item["lines"]}
    ax.add_collection(LineCollection([segment(i) for i in original-sheaf_lines],
                                     colors="#75818c", linewidths=.55, alpha=.72))
    rings(ax, data["witnesses"])
    for number, group in enumerate(groups, 1):
        color = COLORS[(number-1) % len(COLORS)]
        ax.add_collection(LineCollection([segment(i) for i in group["lines"]],
                                         colors=color, linewidths=1.35, zorder=4))
        edges = [("internal_edges", "o", 13), ("external_edges", "x", 7)]
        for key, marker, size in edges:
            points = {tuple(map(float, p)) for i, j in group[key]
                      for p in _intersections(*positions[i], *positions[j])}
            if points:
                ax.scatter(*zip(*sorted(points)), marker=marker, s=size, c=color, alpha=.65, zorder=5)
        a, b = segment(group["lines"][0])
        ax.text((a[0]+b[0])/2, (a[1]+b[1])/2, f"S{number}", color=color, fontsize=8,
                bbox={"facecolor":"white","edgecolor":color,"pad":1}, zorder=8)
    ax.set_title(f"Original map · {len(original)} lines\nCircle: internal crossing · ×: external crossing",
                 loc="left")
    if strategies:
        for ax, name in zip(axes[1:], ("B", "E")):
            result = strategies["strategies"][name]
            kept = set(result["ids"])
            ax.add_collection(LineCollection([segment(i) for i in kept&original],
                                             colors="#28728c", linewidths=.9, zorder=4))
            ax.add_collection(LineCollection([segment(i) for i in original-kept],
                                             colors="#bf5a51", linestyles="--", linewidths=.85, zorder=4))
            ax.add_collection(LineCollection([segment(i) for i in kept-original],
                                             colors="#008f70", linewidths=1.6, zorder=5))
            if name == "E":
                rings(ax, strategies["final_witnesses"])
                tested = {
                    candidate for item in result["trace"]
                    for candidate in [next((p["add"] for p in item["proposals"]
                                            if p["add"] not in kept), None)]
                    if candidate is not None
                }
                ax.add_collection(LineCollection(
                    [segment(i) for i in sorted(tested)], colors="#7048a8",
                    linewidths=1.2, linestyles=":", zorder=5,
                ))
            ax.set_title(
                f"{name} · {len(kept)} lines · mean doorway depth {result['entrance_depth']['mean']:.2f}\n"
                f"{len(kept-original)} added (green) · {len(original-kept)} removed (red)"
                + ("\nPurple dotted: other tested representatives" if name == "E" else ""),
                loc="left",
            )
    fig.suptitle("Axial corridor sheaves · circulation witnesses in dotted gold", fontsize=14)
    if destination.exists():
        raise ValueError(f"Refusing to overwrite {destination}")
    fig.savefig(destination, dpi=190)


def route_change_figure(settlement, reduction, case_name, destination):
    """Show all fixed doorway-pair changes, ordered by building label."""
    labels=[settlement['building_labels'][str(i)] for i in reduction['entrance_order']]
    pairs=list(combinations(range(len(labels)),2))
    before=reduction['strategies']['A']
    after=reduction['strategies']['E']
    fig=Figure(figsize=(14,5.4),layout='constrained')
    FigureCanvasAgg(fig)
    axes=fig.subplots(1,3)
    ordered=np.argsort(labels)
    for ax,(key,title) in zip(axes,[
        ('entrance_pair_depths','Axial line changes'),
        ('metric_pair_lengths','Metric route length'),
        ('angular_pair_depths','Angular route depth'),
    ]):
        matrix=np.full((len(labels),len(labels)),np.nan)
        for (a,b),x,y in zip(pairs,before[key],after[key],strict=True):
            if x is not None and y is not None:
                matrix[a,b]=matrix[b,a]=y-x
        matrix=matrix[np.ix_(ordered,ordered)]
        bound=max(float(np.nanpercentile(np.abs(matrix),98)),.01)
        image=ax.imshow(matrix,cmap='RdBu_r',norm=TwoSlopeNorm(vmin=-bound,vcenter=0,vmax=bound))
        ax.set_title(title,loc='left')
        ticks=list(range(0,len(labels),20))
        ax.set_xticks(ticks,[labels[ordered[i]] for i in ticks])
        ax.set_yticks(ticks,[labels[ordered[i]] for i in ticks])
        ax.set_xlabel('Building at destination')
        if ax is axes[0]:
            ax.set_ylabel('Building at origin')
        fig.colorbar(image,ax=ax,shrink=.7,extend='both')
    fig.suptitle(f"{case_name} · route changes after reduction\nE minus original A · red is higher cost",fontsize=13)

    with destination.open("xb") as image:
        fig.savefig(image, format="png", dpi=190)


def run_order(store_path, parent, parameters, order):
    store = BatchStore(store_path)
    record = run_stage(store, "validation", "voronoi_app.sheaf_experiment:backward_order",
                       {**parameters, "order": order}, parent, "1")
    print(parameters["case"], order, record["status"], record["id"], flush=True)
    return order, record


def run_case(store_path, directory, case, settings, parallel_orders=False):
    store = BatchStore(store_path)
    records = case["records"]
    validation, status, checksum = store.load(records["validation"])
    if validation["status"] != "successful" or validation["parent"]["id"] != records["measures"]:
        raise ValueError("A validated entrance-guided map is required.")
    case_name = case["case"]
    slug = case_name.replace(" ", "-")
    state = {"case": case_name, "input_records": records}
    journal = directory / f"{slug}.json"
    atomic_write(journal, encode(state))
    params={"case":case_name,"settings":settings,
            "validation_record":records["validation"],"validation_sha256":checksum}
    for method in ("diagnostics", "reduction"):
        if method == "reduction":
            params={**params,"diagnostics_record":state["diagnostics"],
                    "diagnostics_sha256":store.load(state["diagnostics"])[2]}
            if parallel_orders:
                state["orders"] = {}
                results = {}
                with ProcessPoolExecutor(max_workers=len(ORDERS)) as workers:
                    futures = [workers.submit(run_order, store.root, records["measures"], params, order)
                               for order in ORDERS]
                    from concurrent.futures import as_completed
                    for future in as_completed(futures):
                        order, saved = future.result()
                        state["orders"][order] = saved["id"]
                        atomic_write(journal, encode(state))
                        if saved["status"] != "successful":
                            raise ValueError(f"Backward order {order} failed: {saved.get('error')}")
                        _, output, checksum = store.load(saved["id"])
                        results[order] = output | {"record": saved["id"], "record_sha256": checksum}
                params["saved_orders"] = results
        record = run_stage(store, "validation", f"voronoi_app.sheaf_experiment:{method}",
                           params, records["measures"], "5")
        state[method] = record["id"]
        state[f"{method}_status"] = record["status"]
        atomic_write(journal, encode(state))
        if record["status"] != "successful":
            print(case_name, method, record.get("error"), flush=True)
            break
        _, payload, _ = store.load(record["id"])
        settlement = store.load(records["settlement"])[1]
        if method == "diagnostics":
            diagnostic = payload
            figure(settlement, diagnostic, None, directory / f"{slug}-diagnostics.png")
            print(case_name, "detected sheaves", [len(g["lines"]) for g in diagnostic["sheaves"]], flush=True)
        else:
            figure(settlement, diagnostic, payload, directory / f"{slug}-reduction.png")
            route_change_figure(settlement, payload, case_name, directory / f"{slug}-route-changes.png")
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store",type=Path,required=True)
    parser.add_argument("--cases",type=Path,required=True)
    parser.add_argument("--settings",type=Path)
    parser.add_argument("--case", choices=("Hill 42", "Y 42"))
    parser.add_argument("--parallel-orders", action="store_true")
    args=parser.parse_args()
    settings=DEFAULTS|(json.loads(args.settings.read_text()) if args.settings else {})
    cases=[case for case in json.loads(args.cases.read_text())
           if case["selector"]=="entrance-guided" and case["generator"]=="projected-faces"]
    if {c["case"] for c in cases}!={"Hill 42","Y 42"} or len(cases)!=2:
        raise ValueError("Expected Hill and Y projected-face entrance-guided cases.")
    if args.case:
        cases = [case for case in cases if case["case"] == args.case]
    directory=args.store/"sheaf-experiments"/uuid4().hex
    directory.mkdir(parents=True)
    print(directory,flush=True)
    with ProcessPoolExecutor(max_workers=len(cases)) as executor:
        workers=[executor.submit(run_case,args.store,directory,case,settings,args.parallel_orders)
                 for case in cases]
        results=[worker.result() for worker in workers]
    atomic_write(directory/"cases.json",encode(results))
    return int(any(result.get("reduction_status")!="successful" for result in results))


if __name__=="__main__":
    raise SystemExit(main())
