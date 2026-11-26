"""Record resumed-search provenance, exact coverage progression and the vector atlas."""
import argparse
from collections import Counter
from fractions import Fraction
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

import pymupdf
from matplotlib import pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm

from experiments.flat40_exhaustive_resume import triangle_discovery
from experiments.flat40_face_extension import lines, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area
from voronoi_app.region_incidence_angular import halfplanes
from experiments.flat40_complete_directed_convex import setup
from experiments.flat40_exchange_atlas import Atlas, page, plot_pdf, xy
from voronoi_app.batch_store import atomic_write, encode


def read(path):
    return json.loads(path.read_bytes())


def journal_inventory(out):
    network = read(out/"geometry.json")
    result = {}
    for hand, starts in network["starts"].items():
        origins = []
        for ordinal, edge in enumerate(starts):
            directory = out/hand/f"{ordinal:05d}"
            journals = sorted(directory.glob("*.json.gz"))
            with gzip.open(journals[-1], "rb") as stream:
                last = json.load(stream)["after"]
            track = network["directed_edges"][edge]["track"]
            origins.append({"ordinal": ordinal, "start_edge": edge, "face": network["tracks"][track]["face"],
                            "journal": str(journals[-1].relative_to(out)), "complete": last["complete"],
                            "prefixes": last["prefixes"], "closures": last["closures"],
                            "pending": len(last["stack"] or [])})
        result[hand] = origins
    return result


def verify_checkpoint(original, older, out):
    verified = 0
    for row in (out/"original-checkpoint-sha256.txt").read_text().splitlines():
        digest, path = row.split(None,1)
        if sha256((original/path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Archived checkpoint changed: {path}")
        if path not in {"regions.json","coverage-maximal.json","progress.json"}:
            if sha256((out/path).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Copied checkpoint changed: {path}")
        verified += 1

    registry = read(original/"regions.json")["regions"]
    restored = {}
    for directory in ("right","left"):
        for path in sorted((original/directory).glob("*/*.json.gz")):
            with gzip.open(path,"rb") as stream:
                for row in json.load(stream)["records"]:
                    for region in row["closed"]:
                        vertices = region["vertices"]
                        ident = sha256(encode(vertices)).hexdigest()
                        if ident != region["id"]:
                            raise ValueError("Archived canonical region identifier does not reconstruct.")
                        restored[ident] = vertices
    if restored != {k:v["vertices"] for k,v in registry.items()}:
        raise ValueError("Archived geometry registry differs from its journals.")

    source = read(original/"geometry.json")
    earlier = read(older/"geometry.json")
    same_edges = [(r["track"],r["segment"]) for r in source["directed_edges"]] == [
        (r["track"],r["interval"]) for r in earlier["directed_edges"]]
    return {"baseline_files_verified": verified, "baseline_registry_reconstructed": len(restored),
            "older_edge_intervals_and_ids_match": same_edges,
            "older_journals_imported": False, "baseline_network_sha256": sha256(
                (original/"geometry.json").read_bytes()).hexdigest()}


def coverage_record(path, registry, progress):
    coverage = read(path)
    return {"prefixes": sum(p["prefixes"] for p in progress.values()), "progress": progress,
            "globally_maximal": sum(r["maximality"]["status"] == "proved_global" for r in registry.values()),
            "coverage": coverage["statistics"], "area_by_count": coverage["area_by_count"],
            "uncovered_components": len(coverage["uncovered_components"])}


def local_multiplicity(out, study, ch):
    atlas = Atlas(study,ch)
    local = read(out/"region-257-coverage.json")
    x,y,X,Y = atlas.regions[257].bounds
    fig,(ax,) = page("Archived region 257 | exact overlap multiplicity",
                     "Clipped to the original region · Blue 1435 · Red 1509")
    atlas.base(ax,(x-2,X+2,y-2,Y+2))
    maximum = max(cell["multiplicity"] for cell in local["faces"])
    patches = PolyCollection([[xy(p) for p in cell["vertices"]] for cell in local["faces"]],
                             edgecolors="none", cmap="Blues", zorder=5,
                             norm=BoundaryNorm([i-.5 for i in range(maximum+2)],256))
    patches.set_array([cell["multiplicity"] for cell in local["faces"]])
    ax.add_collection(patches)
    legend = fig.colorbar(patches,ax=ax,ticks=range(maximum+1),label="Certified polygon interiors")
    legend.solids.set_rasterized(False)
    atlas.line(ax,1435,"#215eab",z=8)
    atlas.line(ax,1509,"#ae3044",z=8)
    plot_pdf(out/"region-257-exact-multiplicity.pdf",[fig])


def triangle_route_map(out, study, ch, replay, discovery, fixture):
    hit = discovery["first_discovery"]
    if hit is None:
        return
    atlas = Atlas(study,ch)
    fig,(ax,) = page("Three-face triangle | ordinary search circuit",
                     f'{hit["hand"].capitalize()} hand · origin {hit["origin"]} · start edge {hit["start_edge"]}')
    vertices = [xy(p) for p in fixture["vertices"]]
    x,y = zip(*vertices)
    atlas.base(ax,(min(x)-3,max(x)+3,min(y)-3,max(y)+3))
    ax.fill(*zip(*vertices),color="#b5dfcd",alpha=.65,zorder=4)
    for k, edge_id in enumerate(hit["path"]):
        track_id, p, q = replay.states[edge_id]
        physical = replay.crawler.tracks[track_id].wall
        color = "#345480" if physical else "#227c68"
        lines(ax,[(p,q)],colors=color,linewidths=2,
              linestyles="solid" if physical else "dashed",zorder=7)
        if k % 4 == 0:
            a,b = xy(p),xy(q)
            pivot = tuple((u+v)/2 for u,v in zip(a,b))
            ax.annotate("",pivot,a,arrowprops={"arrowstyle":"-|>","color":color,"lw":1.2},zorder=8)
    ax.scatter(*xy(hit["start_coordinates"]),s=35,color="#a64142",zorder=10)
    plot_pdf(out/"triangle-ordinary-path.pdf",[fig])


def final_atlas(out, triangle, milestones):
    prior = out/"flat40-complete-directed-convex-atlas.pdf"
    with pymupdf.open(prior) as pdf:
        entries = pdf.get_toc()
    # Keep the base atlas's bookmarks while adding the new milestone and triangle pages.
    fig, ax = plt.subplots(figsize=(15.5, 8.5))
    ax.plot([r["prefixes"] for r in milestones],
            [r["coverage"]["covered_pct"] for r in milestones],
            "o-", color="#226c8b", lw=2)
    for r in milestones:
        ax.annotate(f'{r["coverage"]["covered_pct"]:.5f}% · {r["globally_maximal"]} regions',
                    (r["prefixes"],r["coverage"]["covered_pct"]), xytext=(8,8),
                    textcoords="offset points")
    ax.set(title="Certified exact coverage at saved milestones",
           xlabel="Cumulative explored prefixes", ylabel="Accessible area covered (%)")
    ax.set_ylim(0, 103)
    ax.margins(x=.15)
    ax.grid(axis="y", alpha=.25)
    progression = out/"coverage-progression.pdf"
    plot_pdf(progression,[fig])
    result = out/"flat40-exhaustive-convex-atlas.pdf"
    with pymupdf.open() as merged:
        with pymupdf.open(prior) as pdf:
            merged.insert_pdf(pdf)
        sources = [("Exact coverage progression",progression),
                   ("Region 257 · exact local multiplicity",out/"region-257-exact-multiplicity.pdf"),
                   ("Buildings 30, 32 and 33 · exact triangle",triangle/"04.pdf"),
                   ("Discovery in ordinary enumeration",out/"triangle-discovery.pdf")]
        if (out/"triangle-ordinary-path.pdf").exists():
            sources.append(("First ordinary triangle path",out/"triangle-ordinary-path.pdf"))
        for label, path in sources:
            entries.append([1,label,len(merged)+1])
            with pymupdf.open(path) as pdf:
                merged.insert_pdf(pdf)
        merged.set_toc(entries)
        merged.save(result, garbage=3, deflate=True)
    with pymupdf.open(result) as pdf:
        if any(p.get_images() for p in pdf):
            raise ValueError("The atlas must remain vector.")


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("original","older","output","triangle"):
        parser.add_argument("--"+key,type=Path,required=True)
    parser.add_argument("--manifest",type=Path)
    args = parser.parse_args()
    manifest = args.manifest or Path(os.environ["AGGREGATION_DATA_ROOT"])/"migration-sha256-2026-11-24.json"
    out = args.output
    status = verify_checkpoint(args.original,args.older,out)
    status["origins"] = journal_inventory(out)
    repo = Path(__file__).resolve().parents[1]
    paths = ("experiments/face_extension_cover.py", "experiments/flat40_complete_directed_atlas.py",
             "experiments/flat40_exhaustive_resume.py", "experiments/flat40_exhaustive_parallel.py",
             "experiments/flat40_exhaustive_outputs.py", "src/voronoi_app/angular.py",
             "src/voronoi_app/region_incidence_angular.py")
    status["additional_source_sha256"] = {p:sha256((repo/p).read_bytes()).hexdigest() for p in paths}
    network = read(out/"geometry.json")
    status["origin_classes"] = {}
    for hand, origins in status["origins"].items():
        starts = [row["start_edge"] for row in origins]
        if len(set(starts)) != len(starts) or {row["face"] for row in origins} != set(range(len(network["faces"]))):
            raise ValueError("Duplicate directed origins or missing physical faces.")
        status["origin_classes"][hand] = dict(Counter(
            "physical_endpoint" if network["directed_edges"][row["start_edge"]]["segment"][0]
            in network["faces"][row["face"]]["endpoints"] else "extension_landing" for row in origins
        ))
    journal_hashes = []
    for folder in ("right","left"):
        for path in sorted((out/folder).glob("*/*.json.gz")):
            journal_hashes.append(f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out)}")
    atomic_write(out/"journal-sha256.txt",("\n".join(journal_hashes)+"\n").encode())
    status["journal_batches"] = len(journal_hashes)
    atomic_write(out/"checkpoint-audit.json",encode(status))
    progress = read(out/"progress.json")
    old = read(args.original/"regions.json")["regions"]
    new = read(out/"regions.json")["regions"]
    milestones = [coverage_record(args.original/"coverage-maximal.json",old,read(args.original/"progress.json"))]
    milestones.extend(read(p) for p in sorted(out.glob("milestone-*.json")))
    current = coverage_record(out/"coverage-maximal.json",new,progress)
    if milestones[-1]["prefixes"] != current["prefixes"]:
        milestones.append(current)
    covers = [Fraction(r["coverage"]["covered_area"]) for r in milestones]
    if not set(old) <= set(new) or covers != sorted(covers):
        raise ValueError("The resumed certified cover lost baseline regions or area.")
    atomic_write(out/"coverage-progression.json",encode(milestones))
    triangle = triangle_discovery(out,args.triangle/"triangle-diagnosis.json")
    triangle["paths"].sort(key=lambda p: (int(Path(p["batch"]).name.split(".")[0]),
                           (out/p["batch"]).stat().st_mtime_ns, p["journal_row"], p["batch"]))
    for hit in triangle["paths"]:
        edge = network["directed_edges"][hit["start_edge"]]
        hit["start_face"] = network["tracks"][edge["track"]]["face"]
        hit["start_coordinates"] = edge["segment"][0]
    triangle["first_discovery"] = next(iter(triangle["paths"]),None)
    if bool(triangle["paths"]) != (triangle["polygon_id"] in new):
        raise ValueError("Triangle closure and registry disagree.")
    if triangle["paths"]:
        vertices = points(new[triangle["polygon_id"]])
        plane = halfplanes(vertices+vertices[:1])
        inside = Counter()
        for cell in read(out/"coverage-maximal.json")["faces"]:
            area = exact_area(convex_intersection(points(cell),plane))
            if area:
                inside[cell["multiplicity"]] += area
        if sum(inside.values()) != exact_area(vertices):
            raise ValueError("Triangle overlay does not reconstruct its exact area.")
        triangle["certified_overlap_area_by_multiplicity"] = {n:str(a) for n,a in inside.items()}
        triangle["exclusive_area_in_current_cover"] = str(inside[1])
    atomic_write(out/"triangle-discovery.json",encode(triangle))
    # Render a concise discovery record alongside the original geometric diagram.
    fig = plt.figure(figsize=(15.5,8.5))
    fig.text(.06,.88,"Three-face triangle in ordinary enumeration",fontsize=24,weight="bold")
    if hit := triangle["first_discovery"]:
        content = (f'First journal  {hit["batch"]}\n'
                   f'{hit["hand"].capitalize()} hand · origin {hit["origin"]} · start edge {hit["start_edge"]}\n'
                   f'Prefix {hit["prefix_number_within_origin"]} within the origin · journal row {hit["journal_row"]}\n\n'
                   f'Canonical polygon ID\n{triangle["polygon_id"]}\n\n'
                   f'{len(triangle["paths"])} accepted generating paths in saved ordinary search journals\n'
                   f'{len(triangle["expected_origins_observed"])} of 6 generating-face endpoint starts observed\n'
                   f'{float(Fraction(triangle["exclusive_area_in_current_cover"])):.6f} square units covered by this polygon alone')
    else:
        content = "The saved ordinary search journals have yet to record this closure."
    fig.text(.06,.77,content,fontsize=14,va="top",linespacing=1.65)
    plot_pdf(out/"triangle-discovery.pdf",[fig])
    path_counts = dict(Counter(len(r["paths"]) for r in new.values()))
    result = {"maximality": dict(Counter(r["maximality"]["status"] for r in new.values())),
              "generating_path_frequency": path_counts,
              "paths": sum(len(r["paths"]) for r in new.values()),
              "region_257": dict(Counter(str(tuple(r["positive_interior_axial_candidates"])) for r in
                                        read(out/"region-257-incidence.json").values()
                                        if r["maximality"] == "proved_global")),
              "triangle": triangle}
    atomic_write(out/"summary.json",encode(result))
    study,ch,_,replay,_ = setup(manifest,out)
    local_multiplicity(out,study,ch)
    triangle_route_map(out,study,ch,replay,triangle,read(args.triangle/"triangle-diagnosis.json"))
    final_atlas(out,args.triangle,milestones)
    print({k:v for k,v in result.items() if k!="triangle"},flush=True)
    print("Triangle",triangle["first_discovery"],"path count",len(triangle["paths"]),flush=True)


if __name__ == "__main__":
    main()
