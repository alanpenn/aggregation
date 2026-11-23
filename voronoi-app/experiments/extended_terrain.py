"""Extend the corrected facewise pilot to four documented terrain defaults."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from subprocess import check_output

from experiments.facewise_rerun import ROOT as PREVIOUS, run_case
from experiments.strict_generalisation import case_path
from voronoi_app.batch_store import BatchStore, atomic_write, encode
from voronoi_app.registry import get_registry

ROOT = Path("diagnostics/strict-generalisation/extended-terrain-1")
COMMIT = "def67112a4ec8cf2e1c8f0e4bd1f794edb512e45"
TERRAINS = ("flat", "ridge", "shoulder", "twin_peaks")
PREVIOUS_TERRAINS = ("hill", "converging_valleys")
SEEDS = tuple(range(40, 46))
NEW_CASES = [(terrain, seed) for seed in SEEDS for terrain in TERRAINS]


def verify_previous():
    """Verify the committed export and its local immutable lineage."""
    archived = json.loads((PREVIOUS / "export-record.json").read_bytes())
    store = BatchStore(PREVIOUS)
    for name in ("export-record.json", "statistics.csv", "visual-index.json"):
        path = PREVIOUS / name
        if path.read_bytes() != check_output(["git", "show", f"{COMMIT}:voronoi-app/{path}"]):
            raise ValueError(f"Local {path} differs from the committed benchmark.")
    for terrain in PREVIOUS_TERRAINS:
        for seed in SEEDS:
            path = case_path(PREVIOUS, terrain, seed)
            journal = json.loads(path.read_bytes())
            records = {stage: value["record"] for stage, value in journal["stages"].items()}
            if records != archived["case_records"][path.stem]:
                raise ValueError(f"Record lineage differs for {path.stem}.")
            for record_id in records.values():
                store.load(record_id)
    return {"commit": COMMIT, "root": str(PREVIOUS),
            "export_manifest_sha256": sha256((PREVIOUS / "export-record.json").read_bytes()).hexdigest(),
            "records": archived["case_records"]}


def configurations():
    exemplar = json.loads(case_path(PREVIOUS, "hill", 40).read_bytes())["configuration"]
    registry = get_registry()
    resolved = {name: {key: value for key, value in registry.get_terrain(name).get_config().items()
                       if key != "type"} for name in TERRAINS}
    return {(terrain, seed): exemplar | {"terrain_provider": terrain, "terrain_params": resolved[terrain],
                                         "seed": seed} for terrain, seed in NEW_CASES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--through", choices=("topology", "analysis"), default="analysis")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--case", choices=[f"{terrain}-{seed}" for terrain, seed in NEW_CASES])
    args = parser.parse_args()
    if args.workers < 1 or args.output.resolve() in (PREVIOUS.resolve(), (PREVIOUS.parent / "pilot-1").resolve()):
        parser.error("Choose a positive worker count and a new output directory.")
    previous = verify_previous()
    args.output.mkdir(parents=True, exist_ok=True)
    config = configurations()
    manifest = {"previous": previous, "configurations": {f"{t}-{s}": value for (t, s), value in config.items()}}
    # JSON normalization makes explicit extents identical to resumed journals.
    manifest = json.loads(encode(manifest))
    path = args.output / "benchmark.json"
    if path.exists() and json.loads(path.read_bytes()) != manifest:
        raise ValueError(f"Benchmark provenance changed for {args.output}.")
    atomic_write(path, encode(manifest))
    cases = [(t, s) for t, s in NEW_CASES if args.case is None or args.case == f"{t}-{s}"]
    print(f"Verified 12 archived cases. Running {len(cases)} new cases with {args.workers} workers.", flush=True)
    if args.through == "topology":
        for terrain, seed in cases:
            run_case(args.output, terrain, seed, args.retry_failed, args.through,
                     manifest["configurations"][f"{terrain}-{seed}"])
        return
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as workers:
        jobs = [workers.submit(run_case, args.output, t, s, args.retry_failed, args.through,
                               manifest["configurations"][f"{t}-{s}"]) for t, s in cases]
        for job in jobs:
            job.result()


if __name__ == "__main__":
    main()
