"""Run one reproducible stage or the small axial-robustness pilot."""

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from statistics import median
from uuid import uuid4

from .batch_store import BatchStore, STAGES, atomic_write, encode


@dataclass(frozen=True)
class Method:
    stage: str
    function: str
    version: str = "1"


METHODS = {
    "generate-settlement": Method("settlement", "generate_settlement"),
    "generate-facewise-settlement": Method("settlement", "generate_facewise_settlement"),
    "preserve-settlement": Method("settlement", "preserve_settlement"),
    "main-open-topology": Method("topology", "derive_topology"),
    "fresh-exact": Method("candidates", "fresh_exact_pool", "2"),
    "projected-faces": Method("candidates", "projected_face_pool", "2"),
    "exact-greedy": Method("selection", "exact_greedy"),
    "entrance-guided": Method("selection", "entrance_guided"),
    "full-pool": Method("selection", "retain_pool"),
    "axial-entrance-depth": Method("measures", "axial_and_entrance_depth"),
    "axial-robustness": Method("validation", "validate_axial_map"),
}
DEFAULT_METHODS = dict(zip(STAGES, (
    "generate-settlement", "main-open-topology", "fresh-exact",
    "exact-greedy", "axial-entrance-depth", "axial-robustness",
), strict=True))
EXIT_CODES = {"successful": 0, "failed": 1, "invalid": 2, "incomplete": 3}


def run_stage(store, stage, method, parameters, parent=None, version=None):
    if not isinstance(parameters, dict):
        raise ValueError("Stage parameters must be a JSON object.")
    method = method or DEFAULT_METHODS[stage]
    if method in METHODS:
        spec = METHODS[method]
        if stage != spec.stage or (version is not None and version != spec.version):
            raise ValueError(f"{method} is registered for {spec.stage}, version {spec.version}.")
        if stage == "measures" or method == "entrance-guided":
            defaults = {"connector_limit": 64}
            if method == "entrance-guided":
                defaults["extra_lines"] = 17
            if set(parameters) - defaults.keys():
                raise ValueError(f"{method} accepts only {', '.join(defaults)}.")
            parameters = defaults | parameters
            if (any(type(value) is not int for value in parameters.values())
                    or parameters["connector_limit"] <= 0 or parameters.get("extra_lines", 0) < 0):
                raise ValueError("connector_limit must be positive and extra_lines non-negative.")
        elif stage != "settlement" and parameters:
            raise ValueError(f"{method} takes no explicit parameters.")
        return store.run(stage, f"voronoi_app.batch_methods:{spec.function}", spec.version,
                         parameters, parent)
    if version is None:
        raise ValueError("A custom module:function method requires --version.")
    return store.run(stage, method, version, parameters, parent)


def pilot(store):
    """Pair small settlement configurations to exercise both candidate adapters."""
    root = store.root / "pilots" / uuid4().hex
    root.mkdir(parents=True)
    report_path = root / "pilot.json"
    cases = []
    for terrain, grid, params in (
        ("flat", "voronoi", {"num_points": 36, "jitter_ratio": 1.0}),
        ("hill", "cartesian", {"resolution": 5}),
    ):
        for seed in (11, 42):
            configuration = {
                "terrain_provider": terrain, "grid_generator": grid, "grid_params": params,
                "aggregation_params": {"max_dyads": 5, "stagnation_limit": 100},
                "seed": seed,
            }
            for generator in ("fresh-exact", "projected-faces"):
                for selector in ("exact-greedy", "entrance-guided", "full-pool"):
                    cases.append({
                        "configuration": configuration, "generator": generator,
                        "selector": selector, "records": {}, "status": "incomplete",
                    })
    report = {"scope": "Axial robustness smoke pilot across configurations", "cases": cases}

    def save():
        report["status_counts"] = dict(Counter(case["status"] for case in cases))
        stats = [case["summary"]["lines"] for case in cases if case["status"] == "successful"]
        report["successful_line_counts"] = (
            {"n": len(stats), "min": min(stats), "median": median(stats), "max": max(stats)}
            if stats else {"n": 0}
        )
        atomic_write(report_path, encode(report))

    save()
    shared = {}
    for case in cases:
        parent = None
        configuration = case["configuration"]
        key = encode(configuration)
        for stage in STAGES:
            reuse = (key, stage, case["generator"] if stage == "candidates" else None)
            if reuse in shared:
                record = shared[reuse]
            else:
                method = {"candidates": case["generator"], "selection": case["selector"]}.get(stage)
                record = run_stage(store, stage, method, configuration if stage == "settlement" else {}, parent)
                if stage in ("settlement", "topology", "candidates"):
                    shared[reuse] = record
            parent = case["records"][stage] = record["id"]
            if record["status"] != "successful" or stage == "validation":
                case["status"] = record["status"]
                _, output, _ = store.load(parent)
                if output and "summary" in output:
                    case["summary"] = output["summary"]
                    case["failed_checks"] = output["failed_checks"]
                if "error" in record:
                    case["error"] = record["error"]["message"]
                save()
                break
            save()
    return report_path, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an independently saved stage")
    run.add_argument("stage", choices=STAGES)
    run.add_argument("--parent")
    run.add_argument("--method", help="Built-in adapter name or trusted module:function")
    run.add_argument("--version")
    run.add_argument("--params", type=Path, help="JSON parameter object")
    inspect = commands.add_parser("inspect", help="Verify and print a stage record")
    inspect.add_argument("record_id")
    export = commands.add_parser("export-source", help="Restore archived method source in a new directory")
    export.add_argument("record_id")
    export.add_argument("destination", type=Path)
    comparison = commands.add_parser("export-comparison", help="Export saved case summaries as CSV or JSON")
    comparison.add_argument("cases", type=Path)
    comparison.add_argument("destination", type=Path)
    commands.add_parser("pilot", help="Run the small robustness pilot")
    args = parser.parse_args()
    try:
        store = BatchStore(args.store)
        if args.command == "run":
            parameters = json.loads(args.params.read_text()) if args.params else {}
            record = run_stage(store, args.stage, args.method, parameters, args.parent, args.version)
            print(json.dumps({"id": record["id"], "status": record["status"],
                              "error": record.get("error", {}).get("message")}))
            return EXIT_CODES[record["status"]]
        if args.command == "inspect":
            record, _, record_hash = store.load(args.record_id)
            print(json.dumps({"record_sha256": record_hash, **record}, indent=2))
            return 0
        if args.command == "export-source":
            store.export_source(args.record_id, args.destination)
            print(args.destination)
            return 0
        if args.command == "export-comparison":
            from .batch_export import export_rows
            cases = json.loads(args.cases.read_text())
            count = export_rows(store, cases["cases"] if isinstance(cases, dict) else cases, args.destination)
            print(f"Exported {count} rows to {args.destination}")
            return 0
        path, report = pilot(store)
        print(json.dumps({"report": str(path), "status_counts": report["status_counts"]}))
        return 0
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
