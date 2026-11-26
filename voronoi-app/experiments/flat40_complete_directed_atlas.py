"""Validate and visualise a recorded checkpoint of the systematic Flat 40 crawl."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
import json
from itertools import pairwise
from pathlib import Path
import sys

from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm
import pymupdf

from experiments.face_extension_cover import bounds, hull
from experiments.flat40_complete_directed_convex import HANDS, setup
from experiments.flat40_crawler_atlas import draw, read, stats, uncovered_components, validate
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_exchange_atlas import Atlas, combine, foot, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, lines, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed, ring
from experiments.oriented_extension_turns import ADMISSIBLE
from voronoi_app.angular import _cross, _direction, _intersections
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.region_incidence_angular import halfplanes


def collect(replay):
    regions, paths, branching = {}, set(), {}
    rejected = Counter()
    example = None
    for _, side in HANDS:
        for source in sorted((replay.out / side).glob("*/*.json.gz")):
            with gzip.open(source, "rb") as stream:
                records = json.load(stream)["records"]
            for row in records:
                rejected.update(row["rejections"])
                admitted = [i for i, action in row["outgoing"] if action in ADMISSIBLE]
                if len(admitted) > 1:
                    branching[side, tuple(row["path"])] = row["outgoing"]
                if example is None and any(action == "turn_towards_originating_face"
                                           for _, action in row["outgoing"]):
                    example = row
                for closed in row["closed"]:
                    key = side, tuple(row["path"])
                    if key in paths:
                        continue
                    paths.add(key)
                    region = regions.setdefault(closed["id"], {"vertices": closed["vertices"], "paths": []})
                    region["paths"].append(closed | {"hand": side, "ordered_directed_edges": row["path"]})
    return regions, rejected, branching, example


def check_paths(replay, regions):
    """Check actual ordered directed edges, including the transition across closure."""
    for region in regions.values():
        for record in region["paths"]:
            ids = record["ordered_directed_edges"]
            states = [replay.states[i] for i in ids]
            hand = 1 if record["hand"] == "right" else -1
            assert record["points"] == packed((states[0][1], *(s[2] for s in states)))
            for (incoming, outgoing), (i, j, action, options) in zip(
                    pairwise(states + states[:1]), record["transitions"], strict=True):
                a, p, q = incoming
                b, origin, r = outgoing
                before = replay.crawler.tracks[a]
                after = replay.crawler.tracks[b]
                assert q == origin and (replay.ids[incoming], replay.ids[outgoing]) == (i, j)
                assert [j, action] in options and action in ADMISSIBLE
                assert hand * _cross(_direction(p, q), _direction(q, r)) >= 0
                phase, destination = replay.crawler.phase(incoming)
                if phase == "committed":
                    if q == before.a:
                        assert after.wall and after.face == destination and after.direction(q, r) == hand
                    else:
                        assert a == b and before.direction(q, r) < 0
                if action == "turn_towards_originating_face":
                    assert not after.wall and after.direction(q, r) < 0 and after.away_sign == -hand
                    for index in replay.crawler.walls.tree.query(bounds((q, after.a))):
                        face = replay.crawler.faces[index]
                        if face.identifier != after.face:
                            assert not (_intersections(q, after.a, face.a, face.b) - {q, after.a})
        region["validation"]["ordered_closure_handedness_and_commitment"] = True


def branch_examples(regions, branching, replay):
    completed = {}
    for key, region in regions.items():
        for record in region["paths"]:
            edges = record["ordered_directed_edges"]
            for at, outgoing in enumerate(edges[1:], 1):
                prefix = record["hand"], tuple(edges[:at])
                if prefix in branching:
                    completed.setdefault(prefix, {}).setdefault(outgoing, {})[key] = record
    examples = []
    for prefix, options in completed.items():
        if len(options) < 2 or len({k for rows in options.values() for k in rows}) < 2:
            continue
        best = {}
        for outgoing, rows in options.items():
            choices = sorted(rows, key=lambda k: (regions[k]["maximality"]["status"] != "proved_global", k))
            best[outgoing] = [{"region": k, "path": rows[k]} for k in choices]
        hand, incoming = prefix
        examples.append({"hand": hand, "prefix": incoming,
                         "junction": packed((replay.states[incoming[-1]][2],))[0],
                         "options": branching[prefix], "completed_alternatives": best})
    examples.sort(key=lambda r: -len(r["completed_alternatives"]))
    return examples


def title_page(atlas, title, subtitle, n=1):
    fig, axes = page(title, subtitle, n)
    for ax in axes:
        atlas.base(ax)
    return fig, axes


def normal(ax, f, scale=.75, colour="#22865e"):
    a,b = xy(f.a), xy(f.b)
    x,y = ((a[i]+b[i])/2 for i in range(2))
    dx,dy = b[0]-a[0],b[1]-a[1]
    factor = scale / (dx*dx+dy*dy)**.5
    ax.annotate("", (x-dy*factor,y+dx*factor), (x,y),
                arrowprops={"arrowstyle": "-|>", "color": colour, "lw": .75}, zorder=8)


def supplemental(out, atlas, replay, regions, maximal, overlay, examples, local):
    chapters = []
    def save(filename, title, fig):
        path = out / filename
        plot_pdf(path, [fig])
        chapters.append((title, path))

    fig, (ax,) = title_page(atlas, "Physical faces and accessible-side normals",
                            "Green building-face normals · Purple inward external-frame normals")
    for face in replay.crawler.faces:
        external = face.identifier in replay.crawler.external
        normal(ax, face, colour="#7b37a3" if external else "#22865e")
    save("oriented-physical-faces.pdf", "Building and external boundary normals", fig)

    fig, axes = title_page(atlas, "Certified maximal convex cover", "Equal-opacity polygons and exact interior counts", 2)
    draw_polygons(axes[0], list(maximal.values()), facecolors="#367cac", edgecolors="none", alpha=.11, zorder=3)
    cells = overlay["faces"]
    top = max(row["multiplicity"] for row in cells)
    collection = PolyCollection([[xy(p) for p in row["vertices"]] for row in cells],
                                cmap="Blues", edgecolors="none", zorder=2,
                                norm=BoundaryNorm([n-.5 for n in range(top+2)], 256))
    collection.set_array([r["multiplicity"] for r in cells])
    axes[1].add_collection(collection)
    ticks = sorted(set(range(0,top+1,max(1,(top+1)//10))) | {top})
    bar = fig.colorbar(collection, ax=axes[1], ticks=ticks, label="Overlapping interiors")
    bar.solids.set_rasterized(False)
    foot(fig, f"{len(maximal)} certified polygons · {overlay['covered_percent']:.5f}% accessible area")
    save("maximal-cover.pdf", "Certified-only overlap and multiplicity", fig)

    committed = next((p for r in regions.values() for p in r["paths"]
                      if p["turns_at_extensions"]), None)
    if committed:
        ordered = committed["ordered_directed_edges"]
        transition = next(i for i, t in enumerate(committed["transitions"])
                          if t[2] == "turn_towards_originating_face")
        i = transition + 1
        track_id, start, _ = replay.states[ordered[i]]
        destination = replay.crawler.tracks[track_id].face
        j = next(j for j in range(i + 1, len(ordered))
                 if replay.crawler.tracks[replay.states[ordered[j]][0]].wall)
        face = replay.crawler.faces[destination]
        fig, (ax,) = title_page(atlas, "Committed approach to a physical face",
                               f"{committed['hand'].capitalize()} hand · destination face {destination}")
        steps = [replay.states[edge] for edge in ordered[transition:j + 1]]
        extent = [xy(p) for _, a, b in steps for p in (a,b)]
        ax.set(xlim=(min(x for x,y in extent)-1,max(x for x,y in extent)+1),
               ylim=(min(y for x,y in extent)-1,max(y for x,y in extent)+1))
        for k, (_, a, b) in enumerate(steps):
            color = "#365b79" if k == 0 else "#9c6629" if k < len(steps)-1 else "#297960"
            lines(ax,[(a,b)],colors=color,linewidths=2.2,zorder=7)
            if k == 0 or k == len(steps)-1:
                ax.annotate("", xy(b), xy(a),
                            arrowprops={"arrowstyle":"->","color":color,"lw":1.6},zorder=9)
        x,y = xy(start)
        ax.scatter(x,y,s=34,c="#923450",zorder=10)
        normal(ax,face)
        foot(fig, "Blue incoming edge · Burgundy adoption junction · Ochre committed leg · Green arrival on destination face")
        save("committed-approach.pdf", "Committed approach to the exact destination face", fig)

    for number, branch in enumerate(examples[:3], 1):
        choices = branch["completed_alternatives"]
        pair = next(((a[0], b_item) for a, b in pairwise(choices.values()) for b_item in b
                     if a[0]["region"] != b_item["region"]), None)
        if pair is None:
            continue
        colors = ("#256caa", "#cb6a33")
        fig, axes = title_page(atlas, f"Branch junction {number} | {branch['hand'].capitalize()} hand",
                               "Two actual completed walks from a shared prefix", 3)
        shapes = [regions[s["region"]] for s in pair]
        vertices = [points(shape) for shape in shapes]
        intersection = exact_area(convex_intersection(vertices[0], halfplanes(vertices[1]+vertices[1][:1])))
        exact_difference = [str(exact_area(p)-intersection) for p in vertices]
        branch["illustrated_pair"] = {"regions": [r["region"] for r in pair],
                                      "exclusive_areas": exact_difference, "intersection_area": str(intersection)}
        x,y = xy(branch["junction"])
        extent = [xy(p) for polygon in vertices for p in polygon]
        for ax in axes:
            ax.set(xlim=(min(p[0] for p in extent)-1,max(p[0] for p in extent)+1),
                   ylim=(min(p[1] for p in extent)-1,max(p[1] for p in extent)+1))
            ax.scatter(x,y,c="#9d2245",s=27,zorder=10)
        for idx, (row, shape, colour) in enumerate(zip(pair, shapes, colors)):
            draw_polygons(axes[idx], [shape], facecolors=colour, alpha=.15, zorder=3)
            draw_polygons(axes[2], [shape], facecolors=colour, alpha=.30, zorder=3)
            for edge in row["path"]["ordered_directed_edges"]:
                t,a,b = replay.states[edge]
                track = replay.crawler.tracks[t]
                lines(axes[idx], [(a,b)], colors=colour, linewidths=1.2,
                      linestyles="solid" if track.wall else "dashed", zorder=7)
            next_edge = row["path"]["ordered_directed_edges"][len(branch["prefix"])]
            track = replay.crawler.tracks[replay.states[next_edge][0]]
            face = replay.crawler.faces[track.face]
            normal(axes[idx], face, 1)
            lines(axes[idx], [(face.a,face.b)], colors="#22865e", linewidths=2, zorder=9)
            status = shape["maximality"]["status"].replace("_", " ")
            axes[idx].set_title(f"Face {face.identifier} · {status}", fontsize=9)
        axes[2].set_title("Both completed convex regions", fontsize=9)
        foot(fig, "Area exclusive to each illustrated alternative: " +
             " and ".join(f"{float(Fraction(a)):.5f}" for a in exact_difference) + " square units")
        save(f"branch-{number:02d}.pdf", f"Completed branch alternatives {number}", fig)

    fig, axes = title_page(atlas, "Archived region 257 | Certified maximal cover",
                           "Gold archived region · Blue 1435 · Red 1509", 3)
    x,y,X,Y = atlas.regions[257].bounds
    local_maximal = [maximal[k] for k in local if k in maximal]
    for ax in axes:
        ax.set(xlim=(x-3,X+3),ylim=(y-3,Y+3))
        draw_polygons(ax,[{"vertices":list(atlas.regions[257].exterior.coords)}],
                      facecolors="none", edgecolors="#cf992a", linewidths=1.6,zorder=6)
    draw_polygons(axes[0],local_maximal,facecolors="#367cac",edgecolors="#2a7097",alpha=.19,zorder=4)
    for i,side in enumerate(("right","left"),1):
        choice = next(((r,p) for r in local_maximal for p in r["paths"] if p["hand"]==side),None)
        axes[i].set_title(f"{side.capitalize()} hand" if choice else f"{side.capitalize()} hand · pending",fontsize=9)
        if choice:
            r,p = choice
            draw_polygons(axes[i],[r],facecolors="#367cac",alpha=.16,zorder=4)
            for edge in p["ordered_directed_edges"]:
                t,a,b = replay.states[edge]
                track = replay.crawler.tracks[t]
                lines(axes[i],[(a,b)],colors="#785495", linewidths=1.35,
                      linestyles="solid" if track.wall else "dashed",zorder=7)
            for face_id in r["physical_support_faces"]:
                normal(axes[i],replay.crawler.faces[face_id])
    for ax in axes:
        atlas.line(ax,1435,"#1f5b99",width=1.2,z=9)
        atlas.line(ax,1509,"#bb3940",width=1.2,z=9)
    save("region-257.pdf", "Region 257 certified convex polygons and axial incidence", fig)
    with pymupdf.open(out/"region-257.pdf") as pdf:
        pdf[0].get_pixmap(dpi=300,alpha=False).save(out/"region-257-300dpi.png")
    return chapters


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    a = parser.parse_args()
    study, ch, domain, replay, _ = setup(a.manifest, a.output)
    root = a.output
    progress = read(root / "progress.json")
    regions, rejected, branching, example = collect(replay)
    atlas = Atlas(study, ch)
    old = ring(atlas.regions[257])
    local = validate(regions, replay, domain, old, study)
    check_paths(replay, regions)
    print(f"Validated {len(regions)} distinct regions", flush=True)
    maximal = {k:r for k,r in regions.items() if r["maximality"]["status"] == "proved_global"}
    exhaustive = all(not row["pending_faces"] for row in progress.values())
    overlays = {}
    for name, group in (("all", regions), ("maximal", maximal)):
        if name == "maximal" and len(group) == len(regions):
            overlay = overlays["all"]
        else:
            overlay = exact_coverage(domain, [points(r) for r in group.values()])
            overlay["statistics"] = stats(overlay)
            overlay["uncovered_components"] = uncovered_components(overlay)
            for component in overlay["uncovered_components"]:
                component["diagnosis"] = "unclassified" if exhaustive else "search still pending"
        atomic_write(root / f"coverage-{name}.json", encode(overlay))
        overlays[name] = overlay
    branches = branch_examples(regions, branching, replay)
    atlas_inputs = list(read(a.previous)["components"][0]["regions"].values())
    local_records = {
        k: {"archived_region_overlap_area": str(exact_area(convex_intersection(
                old, halfplanes(points(regions[k]) + points(regions[k])[:1])))),
            "positive_interior_axial_candidates": regions[k]["strict_local_incidence"],
            "supporting_faces": regions[k]["physical_support_faces"],
            "maximality": regions[k]["maximality"]["status"]}
        for k in local
    }
    clips = [hull(convex_intersection(old, halfplanes(points(maximal[k]) + points(maximal[k])[:1])))
             for k in local if k in maximal]
    local_union = exact_coverage(atlas.regions[257], clips)
    atomic_write(root / "region-257-incidence.json", encode(local_records))
    atomic_write(root / "region-257-coverage.json", encode(local_union))
    result = {"progress": progress, "rejected": dict(rejected), "exhaustive": exhaustive,
              "regions": regions, "local_257": local, "branching_prefixes": len(branching),
              "distinct_completed_branch_examples": len(branches)}
    atomic_write(root / "regions.json", encode(result))
    previous_atlas = root / "flat40_directed_face_convex_atlas.pdf"
    draw(root, atlas, replay, regions, overlays["all"], local, example, atlas_inputs)
    with pymupdf.open(previous_atlas) as pdf:
        sources = [(title,root/f"{n:02d}.pdf") for _,title,n in pdf.get_toc()]
    sources.extend(supplemental(root, atlas, replay, regions, maximal, overlays["maximal"], branches, local))
    atomic_write(root / "branch-alternatives.json", encode(branches))
    consolidated = root / "flat40-complete-directed-convex-atlas.pdf"
    combine(consolidated, sources)
    with pymupdf.open(consolidated) as pdf:
        if len(pdf) != len(sources) or any(p.get_images() for p in pdf):
            raise ValueError("Atlas failed vector verification.")
    print(dict(regions=len(regions), maximal=len(maximal), branches=len(branches), local=len(local),
               covered=overlays["maximal"]["covered_percent"], pages=len(sources)), flush=True)


if __name__ == "__main__":
    main()
