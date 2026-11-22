"""Reproduce the first Y-settlement visibility-backbone experiment."""

import argparse
import gzip
import hashlib
import json
import tarfile
import time
from pathlib import Path

from shapely.ops import unary_union

from voronoi_app.angular import LineClearance
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.experimental_visibility import build_visibility_graph


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_inputs(archive, snapshot, data_dir, selection_dir):
    expected_archive = "9128d543e2527588a3562ca2767f6b81de6daed9ecc412d8e376008c373bf3b7"
    if sha256(archive) != expected_archive:
        raise ValueError("Research archive SHA-256 does not match the recorded handover")
    with tarfile.open(archive, "r:gz") as tar:
        stream = tar.extractfile("MANIFEST.json")
        if stream is None:
            raise ValueError("Research archive has no manifest")
        manifest = {entry["path"]: entry for entry in json.load(stream)["files"]}
    suffixes = {
        "home/Downloads/axial-diagnostic.json": snapshot,
        "valley42-exchange-2026-11-17/prepared.json": data_dir / "prepared.json",
        "valley42-exchange-2026-11-17/settlement.json": data_dir / "settlement.json",
        "valley-connectivity-2026-11-17/selection-results.json": selection_dir / "selection-results.json",
        "valley-connectivity-2026-11-17/targeted-evaluated.json": selection_dir / "targeted-evaluated.json",
    }
    hashes = {}
    for suffix, path in suffixes.items():
        matches = [record for name, record in manifest.items() if name.endswith(suffix)]
        if len(matches) != 1 or not path.is_file():
            raise ValueError(f"Missing or ambiguous preserved input: {suffix}")
        digest = sha256(path)
        if digest != matches[0]["sha256"] or path.stat().st_size != matches[0]["bytes"]:
            raise ValueError(f"Input differs from archive manifest: {path}")
        hashes[suffix] = digest
    return hashes


def exact_point(point):
    return [str(value) for value in point]


def graph_stage(args):
    hashes = verified_inputs(args.archive, args.snapshot, args.data_dir, args.selection_dir)
    snapshot = json.loads(args.snapshot.read_text())
    opened, buildings, _, config, paired = load_axial_snapshot(snapshot)
    settlement = json.loads((args.data_dir / "settlement.json").read_text())
    if set(map(int, settlement["building_labels"])) != set(buildings) or len(paired) != 100:
        raise ValueError("Snapshot building identities do not match the saved Valley settlement")
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    LineClearance(accessible, occupied, original_obstacles=buildings.values())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    print("building exact-predicate visibility graph", flush=True)
    graph = build_visibility_graph(
        accessible, buildings,
        progress=lambda accepted, blocked: print("visible", accepted, "blocked", blocked, flush=True),
    )
    output = {
        "vertices": [{"point": exact_point(v.point), "component": v.component,
                      "buildings": v.buildings} for v in graph.vertices],
        "edges": [{"start": e.start, "end": e.end, "length": e.length,
                   "boundary_following": e.boundary_following,
                   "tangent_supported": e.tangent_supported} for e in graph.edges],
        "ambiguous_vertices": [exact_point(p) for p in graph.ambiguous_vertices],
        "blocked_edges": graph.blocked_edges, "ambiguous_edges": graph.ambiguous_edges,
        "component_count": len(graph.components),
        "input_sha256": hashes, "snapshot_configuration": config,
        "geometry": {"open_cells": len(opened), "occupied_cells": len(buildings),
                     "paired_cells": len(paired), "accessible_area": accessible.area},
        "elapsed_seconds": time.monotonic() - started,
    }
    with gzip.open(args.output_dir / "visibility-graph.json.gz", "xt") as file:
        json.dump(output, file, allow_nan=False)
    print("vertices", len(graph.vertices), "obstacle vertices",
          sum(bool(v.buildings) for v in graph.vertices), "edges", len(graph.edges),
          "blocked", graph.blocked_edges, "ambiguous", len(graph.ambiguous_vertices),
          "seconds", round(output["elapsed_seconds"], 2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--selection-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    graph_stage(args)


if __name__ == "__main__":
    main()
