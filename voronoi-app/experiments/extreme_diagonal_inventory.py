"""Inventory exact frontage contacts and plot local overlapping pairs."""
import csv
import json
from fractions import Fraction

from shapely import from_wkb
from shapely.geometry import LineString
from shapely.strtree import STRtree

from voronoi_app.angular import _exact_point, _intersections
from voronoi_app.batch_routing_reference import point
from voronoi_app.batch_store import BatchStore
from voronoi_app.exact_axial import ExactCandidate, _bounds
from voronoi_app.extreme_diagonal_experiment import span

from .extreme_diagonals import OUT, ROOT


def inventory(case, data):
    lines = [ExactCandidate(i, a, b, a, b, "certified")
             for i, (a,b) in enumerate(tuple(map(point,pair)) for pair in data["intervals"])]
    settlement = data["settlement"]
    polygons = {i:from_wkb(settlement["polygons_wkb"][i]) for i in settlement["building_labels"]}
    fronts = []
    for poly in polygons.values():
        ring = list(map(_exact_point, poly.exterior.coords))
        fronts.extend(zip(ring,ring[1:]))
    index = STRtree([LineString(edge) for edge in fronts])
    for n, corridor in enumerate(data["corridors"],1):
        extreme = set(corridor["extreme_pair"] or ())
        for i in corridor["members"]:
            line = lines[i]
            a, b = line.start, line.end
            touches = any(len(_intersections(a,b,*fronts[int(j)])) >= 2
                          for j in index.query(_bounds(line)))
            (x0,y0),(x1,y1),length = span(corridor["axis"],line)
            run = max(0,min(length,x1)-max(0,x0))
            yield {"case":case,"corridor":n,"candidate":i, "face_hugging":touches,
                   "inclination":"level" if abs(y1-y0)<1e-8 else "positive" if y1>y0 else "negative",
                   "longitudinal_fraction":run/length,"length":line.length,
                   "selected_original":i in corridor["original_members"],"extreme":i in extreme,
                   "start":json.dumps(list(map(str,a))),"end":json.dumps(list(map(str,b)))}


def local_map(case, data):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    c = data["corridors"][0]
    if not c.get("local_pairs"):
        return
    lines = [[tuple(map(float,map(Fraction,p))) for p in line] for line in data["intervals"]]
    s = data["settlement"]
    fig, ax = plt.subplots(figsize=(9,5),layout="constrained")
    for i,label in s["building_labels"].items():
        polygon = from_wkb(s["polygons_wkb"][i])
        ax.fill(*polygon.exterior.xy,color="#353b41")
        p = polygon.representative_point()
        ax.text(p.x,p.y,label,color="white",fontsize=7,ha="center",va="center")
    ax.add_collection(LineCollection([lines[i] for i in c["members"]],colors="#8193a2",alpha=.27,
                                     linewidths=.8))
    for pair, axis, color in zip(c["local_pairs"], c["local_axes"], ("#df5330","#225ca0"),strict=True):
        a,b = axis[0]
        ax.plot([a[0],b[0]],[a[1],b[1]],color=color,linestyle="--",linewidth=.9)
        if pair:
            ax.add_collection(LineCollection([lines[i] for i in pair],colors=color,linewidths=2))
    ax.autoscale()
    ax.set(aspect="equal",title=f"{case.capitalize()} · Two overlapping local pairs")
    ax.axis("off")
    with (OUT/f"{case}-overlapping.png").open("xb") as stream:
        fig.savefig(stream,format="png",dpi=150)
    plt.close(fig)


def main():
    store = BatchStore(ROOT)
    rows = []
    for path in sorted(OUT.glob("*.json")):
        state = json.loads(path.read_text())
        if "record" not in state:
            continue
        _,data,_ = store.load(state["record"])
        rows.extend(inventory(path.stem,data))
        local_map(path.stem,data)
    with (OUT/"sheaf-inventory.csv").open("x",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
