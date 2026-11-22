"""Numbered maps for the matched facewise growth experiment."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle


def draw_map(ax, polygons, data, *, extent=None, highlight=None, label_size=6):
    buildings = {int(i): label for i, label in data["building_labels"].items()}
    assigned = set(data["dyad_open_cells"])
    canvas = data["grid"]["extent"]
    left, bottom, right, top = extent or canvas
    visible = {i: p for i, p in polygons.items() if
               p.bounds[0] <= right and p.bounds[2] >= left and
               p.bounds[1] <= top and p.bounds[3] >= bottom}
    colors = ["#4a505a" if i in buildings else "#b9dedb" if i in assigned else "#f5f4ef"
              for i in visible]
    ax.add_collection(PolyCollection([p.exterior.coords for p in visible.values()],
                                     facecolors=colors, edgecolors="#96a2a8", linewidths=.35))
    ax.add_patch(Rectangle(canvas[:2], canvas[2] - canvas[0], canvas[3] - canvas[1],
                           fill=False, edgecolor="#404951", linewidth=.8))
    if highlight is not None:
        p = polygons[highlight]
        ax.plot(*p.exterior.xy, color="#a51548", linewidth=1.6, zorder=5)
    for cell, p in visible.items():
        if cell not in buildings:
            continue
        point = p.centroid
        if left <= point.x <= right and bottom <= point.y <= top:
            ax.text(point.x, point.y, buildings[cell], color="white", fontsize=label_size,
                    ha="center", va="center", zorder=8, clip_on=True)
    ax.set(xlim=(left, right), ylim=(bottom, top), aspect="equal")
    ax.set_axis_off()


def draw_links(ax, polygons, rows, *, parents=False, failures=False, ax_zoom=False):
    for row in rows:
        open_cell = row["open_cell"]
        for other, length, is_parent in (
            (row["building_cell"], row["pair_face_length"], False),
            (row["parent_open_cell"], row["parent_face_length"], True),
        ):
            if other is None or (parents and not is_parent) or (failures and length != 0):
                continue
            start, end = polygons[other].centroid, polygons[open_cell].centroid
            color = "#b31646" if length == 0 else "#215c96" if is_parent else "#317d72"
            if is_parent and not failures:
                ax.annotate("", xy=(end.x, end.y), xytext=(start.x, start.y),
                            arrowprops={"arrowstyle": "->", "color": color,
                                        "lw": .7 if not ax_zoom else 1.25, "shrinkA": 0, "shrinkB": 0},
                            zorder=6)
            else:
                ax.plot([start.x, end.x], [start.y, end.y], color=color,
                        linewidth=1.35 if failures or ax_zoom else .48,
                        linestyle="--" if length == 0 else "-", zorder=7 if length == 0 else 3)


def save(fig, root, name, atlas=None):
    for ext in ("png", "pdf"):
        fig.savefig(root / f"{name}.{ext}", dpi=300, bbox_inches="tight", facecolor="white")
    if atlas is not None:
        atlas.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def plot_case(root, case, polygons, old, new, legacy, revised, summary, *, atlas=None):
    title = case.replace("converging_valleys", "Converging Valleys (Y)").replace("hill", "Hill")
    title = title.replace("-", " · seed ")
    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    for ax, variant, data, rows in zip(axes, ("legacy", "corrected"), (old, new), (legacy, revised)):
        draw_map(ax, polygons, data)
        draw_links(ax, polygons, rows, failures=False)
        draw_links(ax, polygons, rows, failures=True)
        counts = summary[variant]
        ax.set_title(f"{variant.capitalize()}  |  {counts['dyads']} dyads  |  "
                     f"{counts['assigned_components']} assigned-open components\n"
                     f"{summary[f'{variant}_settlement']}", fontsize=11)
    fig.suptitle(title, fontsize=16, y=.99)
    fig.legend(handles=[Patch(color="#4a505a", label="Numbered buildings"),
                        Patch(color="#b9dedb", label="Assigned open cells"),
                        Patch(color="#f5f4ef", label="Unassigned open cells"),
                        Line2D([], [], color="#317d72", label="Building–open dyad"),
                        Line2D([], [], color="#215c96", label="Parent → new open"),
                        Line2D([], [], color="#b31646", linestyle="--", label="Missing shared face")],
               loc="lower center", ncols=6, frameon=False)
    fig.tight_layout(rect=(0, .04, 1, .97))
    save(fig, root, f"{case}-comparison", atlas)

    fig, ax = plt.subplots(figsize=(9, 9))
    draw_map(ax, polygons, new, label_size=7)
    draw_links(ax, polygons, revised, parents=True)
    ax.set_title(f"{title}\nCorrected parent → new open for every growth step\n"
                 f"{summary['corrected_settlement']}", fontsize=12)
    save(fig, root, f"{case}-corrected-parents", atlas)

    if not case.startswith("converging_valleys") or not summary["legacy"]["invalid_dyads"]:
        return
    named = {row["building"] for row in legacy if 0 in (row["parent_face_length"], row["pair_face_length"])}
    rows = [row for row in legacy if row["building"] in named]
    fig, axes = plt.subplots(len(rows), 2, figsize=(12, 3.2 * len(rows)), squeeze=False)
    xmin, ymin, xmax, ymax = old["grid"]["extent"]
    def zoom(row):
        cells = [i for i in (row["building_cell"], row["open_cell"], row["parent_open_cell"]) if i is not None]
        bounds = [polygons[i].bounds for i in cells]
        return (max(xmin, min(b[0] for b in bounds) - 3), max(ymin, min(b[1] for b in bounds) - 3),
                min(xmax, max(b[2] for b in bounds) + 3), min(ymax, max(b[3] for b in bounds) + 3))

    def show(panel, data, placement, label):
        draw_map(panel, polygons, data, extent=zoom(placement), highlight=placement["building_cell"], label_size=8)
        draw_links(panel, polygons, [placement], ax_zoom=True)
        parent = placement["parent_face_length"]
        parent_text = "—" if parent is None else f"{parent:.3f}"
        panel.set_title(f"{label} step {placement['building']} · building cell {placement['building_cell']}\n"
                        f"Parent face {parent_text} · dyad face {placement['pair_face_length']:.3f}", fontsize=10)

    by_step = {row["building"]: row for row in revised}
    for row, (left, right) in zip(rows, axes, strict=True):
        show(left, old, row, "Legacy")
        replacement = by_step.get(row["building"])
        if atlas is not None and replacement:
            show(right, new, replacement, "Corrected")
        else:
            cell = row["building_cell"]
            draw_map(right, polygons, new, extent=zoom(row), highlight=cell, label_size=8)
            right.set_title(f"Corrected at same site · cell {cell}\n"
                            f"Building label {new['building_labels'].get(str(cell), 'none')}", fontsize=10)
    fig.suptitle(f"{title} · comparison by placement step" if atlas is not None else
                 f"{title} · named legacy building locations", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, .98))
    save(fig, root, f"{case}-named-closeups", atlas)
