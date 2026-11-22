"""Replay the preserved Hill 42 and Y 42 fixtures without rebuilding settlements."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
from uuid import uuid4

from shapely import wkt

from experiments.circulation_topology import EXPECTED_HASHES
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.batch import run_stage
from voronoi_app.batch_store import BatchStore, atomic_write, digest, encode


GENERATORS = ("fresh-exact", "projected-faces")
SELECTORS = ("exact-greedy", "entrance-guided", "full-pool")
Y_DOORWAY_SHA256 = "39a9a96c7f390e90bcd7e2387ce99cf0bee31ba27d8d0ce6942a96fbb9d6a5b6"


def read(path, expected=None):
    content = path.read_bytes()
    checksum = digest(content)
    if expected and checksum != expected:
        raise ValueError(f"Preserved source differs from its expected hash: {path}")
    data = json.loads(gzip.decompress(content) if path.suffix == ".gz" else content)
    return data, {"file": path.name, "sha256": checksum}


def preserved(args, name):
    hill = name == "Hill 42"
    geometry_path = args.hill_snapshot if hill else args.y_snapshot
    snapshot, geometry_source = read(geometry_path, None if hill else EXPECTED_HASHES["y-snapshot"])
    opened, occupied, _, config, paired = load_axial_snapshot(snapshot)
    polygons = {**opened, **occupied}
    if hill:
        inventory, labels_source = read(args.hill_geometry, EXPECTED_HASHES["hill-data"])
        other = {int(i): wkt.loads(p) for i, p in inventory["polygons"].items()}
        if other.keys() != polygons.keys() or any(not p.equals_exact(other[i], 0) for i, p in polygons.items()):
            raise ValueError("The Hill snapshot differs from the preserved Hill polygon inventory.")
        if paired != set(inventory["dyad_open_cells"]):
            raise ValueError("The Hill snapshot differs from the preserved dyad inventory.")
    else:
        inventory, labels_source = read(args.y_labels, EXPECTED_HASHES["y-settlement"])
        if any(config.get(key) != value for key, value in inventory["configuration"].items()):
            raise ValueError("The Y snapshot differs from the preserved configuration.")
    labels = {int(i): label for i, label in inventory["building_labels"].items()}
    if set(labels) != set(occupied) or config.get("seed") != 42:
        raise ValueError(f"The snapshot does not match {name}.")
    path = args.hill_doors if hill else args.y_doors
    door_records, door_source = read(path, None if hill else Y_DOORWAY_SHA256)
    doors = []
    for door in door_records["entrances" if hill else "doors"]:
        open_id = door["open_cell" if hill else "open_id"]
        label = door["building" if hill else "building_label"]
        building_id = next(i for i, n in labels.items() if n == label) if hill else door["building_id"]
        if labels[building_id] != label or open_id not in paired:
            raise ValueError("A saved doorway conflicts with the settlement inventory.")
        doors.append([open_id, building_id])
    if len(set(map(tuple, doors))) != len(doors):
        raise ValueError("The saved doorway inventory contains a duplicate pair.")
    return {
        "configuration": config,
        "polygons_wkb": {str(i): p.wkb_hex for i, p in polygons.items()},
        "building_labels": labels,
        "dyad_open_cells": sorted(paired),
        "doors": doors,
        "provenance": {
            "case": name, "snapshot": geometry_source, "label_inventory": labels_source,
            "saved_doorway_inventory": door_source,
            "doorway_origin": "Previously reconstructed and saved research pairings. No pairings inferred in this import.",
            "unavailable": ["Original contemporaneous door table", "Original aggregation trace", "Original grid graph"],
            "dyad_open_cells_without_saved_door": sorted(paired - {a for a, _ in doors}),
            "buildings_without_saved_door": sorted(set(labels) - {b for _, b in doors}),
        },
    }


def branch(root, directory, name, record_ids, generator):
    store = BatchStore(root)
    filename = directory / f"{name.replace(' ', '-')}-{generator}.json"
    cases = [{"case": name, "generator": generator, "selector": s,
              "records": dict(record_ids)} for s in SELECTORS]
    atomic_write(filename, encode(cases))
    generated = run_stage(store, "candidates", generator, {}, record_ids["topology"])
    for case in cases:
        case["records"]["candidates"] = generated["id"]
    atomic_write(filename, encode(cases))
    if generated["status"] == "successful":
        for case in cases:
            parent = generated["id"]
            for stage in ("selection", "measures", "validation"):
                record = run_stage(store, stage, case["selector"] if stage == "selection" else None, {}, parent)
                parent = case["records"][stage] = record["id"]
                atomic_write(filename, encode(cases))
                print(name, generator, case["selector"], stage, record["status"], flush=True)
                if record["status"] != "successful":
                    # The saved map can still undergo independent geometric validation.
                    if stage == "measures":
                        fallback = run_stage(store, "validation", None, {}, case["records"]["selection"])
                        case["records"]["validation"] = fallback["id"]
                        atomic_write(filename, encode(cases))
                    break
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("store", "hill-snapshot", "hill-geometry", "hill-doors", "y-snapshot", "y-labels", "y-doors"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    store = BatchStore(args.store)
    directory = store.root / "benchmarks" / uuid4().hex
    directory.mkdir(parents=True)
    print(directory, flush=True)
    tasks = []
    for name, expected in (("Hill 42", 11), ("Y 42", 3)):
        settlement = run_stage(store, "settlement", "preserve-settlement", preserved(args, name))
        topology = run_stage(store, "topology", None, {}, settlement["id"])
        record, result, _ = store.load(topology["id"])
        if record["status"] != "successful":
            raise ValueError(record.get("error", record))
        actual = result["topology"]
        if len(actual["internal_blocks"]) != expected or len(actual["internal_circulation_holes"]) != expected:
            raise ValueError(f"{name} differs from the preserved circulation benchmark.")
        if name == "Hill 42" and actual["excluded_open_cells"] != [335, 383]:
            raise ValueError("Hill 42 has unexpected excluded open-space cells.")
        ids = {"settlement": settlement["id"], "topology": topology["id"]}
        tasks.extend((store.root, directory, name, ids, generator) for generator in GENERATORS)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(branch, *task) for task in tasks]
        cases = [case for f in futures for case in f.result()]
    atomic_write(directory / "cases.json", encode(cases))


if __name__ == "__main__":
    main()
