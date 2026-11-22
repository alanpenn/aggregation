"""Regenerate and evaluate the matched facewise axial cohort."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from fcntl import LOCK_EX, LOCK_NB, flock
from hashlib import sha256
import json
from pathlib import Path
from subprocess import check_output
from time import monotonic

from shapely import from_wkb

from experiments.audit_facewise_growth import prefix_audit
from experiments.strict_generalisation import CASES, ROOT as LEGACY, case_path, rss_mib
from voronoi_app.batch import run_stage
from voronoi_app.batch_methods import generate_facewise_settlement
from voronoi_app.batch_store import BatchStore, StageResult, atomic_write, encode

ROOT = Path("diagnostics/strict-generalisation/facewise-1")
REGRESSIONS = [("converging_valleys", seed) for seed in (40, 41)]


def certify(data):
    polygons = {int(cell): from_wkb(value) for cell, value in data["polygons_wkb"].items()}
    placements = data["placements"]
    errors = []
    if len(placements) != len(data["doors"]):
        errors.append("Growth record and door inventory differ in size.")
    parents = [row.get("parent_open_cell") for row in placements]
    rows = []
    if not errors:
        try:
            rows = prefix_audit(data["doors"], data["building_labels"], parents, polygons)
        except (KeyError, ValueError) as error:
            errors.append(f"Cannot audit recorded cell IDs and parents: {error}")
    assigned = set()
    for index, (row, placement) in enumerate(zip(rows, placements, strict=True), 1):
        opened, building = row["open_cell"], row["building_cell"]
        parent = row["parent_open_cell"]
        checks = {
            "unused cells": opened != building and not assigned.intersection((opened, building)),
            "recorded IDs and label": (placement["open_cell"], placement["building_cell"], placement["label"])
            == (opened, building, row["building"]) and row["building"] == index,
            "positive building face": row["pair_face_length"] > 0
            and placement["building_face_length"] == row["pair_face_length"],
            "positive earlier parent face": (parent is None if index == 1 else parent in row["earlier_face_neighbors"])
            and placement["parent_face_length"] == row["parent_face_length"],
            "connected open prefix": row["components"] == 1,
        }
        row["checks"] = checks
        errors.extend(f"Placement {index}: {check}" for check, passed in checks.items() if not passed)
        assigned.update((opened, building))
    if not rows or rows[-1]["components"] != 1:
        errors.append("Expected exactly one assigned-open component.")
    if {row["open_cell"] for row in rows} != set(data["dyad_open_cells"]):
        errors.append("Assigned open inventory disagrees with placements.")
    if {row["building_cell"] for row in rows} != set(map(int, data["building_labels"])):
        errors.append("Building inventory disagrees with placements.")
    maximum = data.get("configuration", {}).get("aggregation_params", {}).get("max_dyads")
    stop = None
    if maximum is not None:
        if len(data["doors"]) >= maximum:
            stop = "dyad limit reached"
        elif not data["doors"]:
            stop = "no initial building–open face"
        elif len(assigned) == len(polygons):
            stop = "all cells assigned"
        else:
            stop = "stagnation limit reached"
    return {"valid": not errors, "errors": errors, "placements": rows, "termination": stop,
            "assigned_open_components": rows[-1]["components"] if rows else 0,
            "completed_dyads": len(data["doors"])}


def generate_certified(inputs, parameters):
    data = generate_facewise_settlement(inputs, parameters).output
    certificate = certify(data)
    return StageResult(data | {"aggregation_certificate": certificate,
                               "rng": {"seed": parameters["seed"], "aggregation": "Python random and NumPy legacy seeded streams",
                                       "grid": "NumPy legacy seeded stream"}}, valid=certificate["valid"])


def run_case(root, terrain, seed, retry_failed=False, through="analysis"):
    claims = root / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    with (claims / f"{terrain}-{seed}.lock").open("a") as lock:
        try:
            flock(lock, LOCK_EX | LOCK_NB)
        except BlockingIOError:
            print(f"{terrain}-{seed} already has a worker", flush=True)
            return
        run_claimed_case(root, terrain, seed, retry_failed, through)


def run_claimed_case(root, terrain, seed, retry_failed, through):
    path = case_path(root, terrain, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        journal = json.loads(path.read_text())
    else:
        original = case_path(LEGACY, terrain, seed).read_bytes()
        legacy = json.loads(original)
        config = legacy["configuration"] | {"aggregation_strategy": "slope_preference_facewise_v1"}
        journal = {"case": path.stem, "terrain": terrain, "seed": seed, "configuration": config,
                   "legacy_journal_sha256": sha256(original).hexdigest(),
                   "git_head": check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "stages": {}}
    store = BatchStore(root)
    parent = None
    references = root / "route-references"
    references.mkdir(exist_ok=True)
    steps = (
        ("settlement", "settlement", "experiments.facewise_rerun:generate_certified", "1", journal["configuration"]),
        ("topology", "topology", "main-open-topology", None, {}),
        ("candidates", "candidates", "fresh-exact", None, {}),
        ("selection", "selection", "full-pool", None, {}),
        ("analysis", "validation", "voronoi_app.strict_generalisation:analyze", "3",
         {"require_metric_reachability": True, "reference_path": str(references / (path.stem + ".json"))}),
    )
    for key, stage, method, version, params in steps:
        entry = journal["stages"].get(key)
        if entry and retry_failed and entry["status"] == "failed":
            journal.setdefault("earlier_attempts", {}).setdefault(key, []).append(entry)
            entry = None
        if entry is None:
            if key == "analysis":
                params["candidate_record"] = journal["stages"]["candidates"]["record"]
            started = monotonic()
            record = run_stage(store, stage, method, params, parent, version)
            entry = {"record": record["id"], "status": record["status"], "error": record.get("error"),
                     "seconds": monotonic() - started, "peak_rss_mib": rss_mib()}
            journal["stages"][key] = entry
            atomic_write(path, encode(journal))
            print(path.stem, key, entry["status"], round(entry["seconds"], 1), flush=True)
        if entry["status"] != "successful":
            break
        parent = entry["record"]
        if key == through:
            break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--through", choices=("topology", "analysis"), default="analysis")
    parser.add_argument("--remaining", action="store_true")
    parser.add_argument("--case", choices=[f"{t}-{s}" for t, s in CASES])
    args = parser.parse_args()
    if args.output.resolve() == LEGACY.resolve():
        parser.error("Use a separate output directory for the corrected cohort.")
    if args.case and args.remaining:
        parser.error("Choose either one case or the remaining cohort.")
    if args.workers < 1:
        parser.error("Worker count must be positive.")
    remaining = [case for case in CASES if case not in REGRESSIONS]
    groups = [REGRESSIONS, remaining]
    if args.case:
        groups = [[case for case in CASES if f"{case[0]}-{case[1]}" == args.case]]
    elif args.remaining:
        groups = [remaining]
    for group in groups:
        with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
            futures = [pool.submit(run_case, args.output, *case, args.retry_failed, args.through) for case in group]
            for future in futures:
                future.result()


if __name__ == "__main__":
    main()
