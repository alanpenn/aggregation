"""
Experiment configuration, execution and batch comparison.

A run is identified deterministically by a hash of its full configuration,
so re-running the same configuration yields the same identifier and results.
"""

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..registry import get_registry
from .carrier import Carrier, build_voronoi_carrier
from .metrics import measure_configuration
from .rules import GenerativeRule, RunResult, make_rule, run_rule

MODE_LABELS = {
    "random": "Mode 0 - Random occupation",
    "adjacent": "Mode 1 - Adjacent aggregation (3-syntax)",
    "enclosing": "Mode 2 - Enclosing aggregation (4-syntax approx.)",
    "enclosing_continue": "Mode 2b - Enclosing, then adjacent growth to budget",
}


@dataclass(frozen=True)
class MorphicConfig:
    mode: str = "adjacent"
    num_cells: int = 200
    occupied_target: int = 60
    seed: int = 40
    terrain: str = "flat"
    canvas_size: float = 100.0
    enclosure_strength: float = 1.0
    target_size: int = 1

    def experiment_id(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha1(canonical.encode()).hexdigest()[:10]


@dataclass
class ExperimentRun:
    config: MorphicConfig
    carrier: Carrier
    result: RunResult
    metrics: Dict[str, Any]

    @property
    def experiment_id(self) -> str:
        return self.config.experiment_id()

    def flat_record(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            **asdict(self.config),
            "n_cells_actual": len(self.carrier.cells),
            "termination": self.result.termination,
            "steps": len(self.result.transformations),
            **self.metrics,
        }


def rule_for(config: MorphicConfig) -> GenerativeRule:
    if config.mode == "enclosing":
        return make_rule("enclosing", strength=config.enclosure_strength,
                         target_size=config.target_size, after_enclosure="stop")
    if config.mode == "enclosing_continue":
        return make_rule("enclosing", strength=config.enclosure_strength,
                         target_size=config.target_size, after_enclosure="continue")
    return make_rule(config.mode)


def build_carrier(config: MorphicConfig) -> Carrier:
    terrain = get_registry().get_terrain(config.terrain)
    return build_voronoi_carrier(
        num_cells=config.num_cells,
        seed=config.seed,
        terrain=terrain,
        canvas_size=config.canvas_size,
    )


def run_experiment(config: MorphicConfig, carrier: Optional[Carrier] = None) -> ExperimentRun:
    """Run one configuration. Pass ``carrier`` to reuse geometry across modes."""
    carrier = carrier or build_carrier(config)
    result = run_rule(rule_for(config), carrier, config.occupied_target, config.seed)
    target = result.target or None
    metrics = measure_configuration(carrier, result.occupied, target)
    return ExperimentRun(config=config, carrier=carrier, result=result, metrics=metrics)


def run_comparison(base: MorphicConfig, modes: Iterable[str]) -> Dict[str, ExperimentRun]:
    """Run several modes on the identical carrier and seed."""
    carrier = build_carrier(base)
    return {
        mode: run_experiment(MorphicConfig(**{**asdict(base), "mode": mode}), carrier)
        for mode in modes
    }


def run_batch(
    seeds: Iterable[int],
    modes: Iterable[str],
    base: MorphicConfig = MorphicConfig(),
) -> List[ExperimentRun]:
    """For each seed, build one carrier and run every mode on it."""
    runs: List[ExperimentRun] = []
    modes = list(modes)
    for seed in seeds:
        seeded = MorphicConfig(**{**asdict(base), "seed": seed})
        runs.extend(run_comparison(seeded, modes).values())
    return runs


def save_batch(runs: List[ExperimentRun], out_dir: Path) -> Dict[str, Path]:
    """Write per-run metrics (CSV), full configs + step logs (JSON)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    records = [run.flat_record() for run in runs]
    csv_path = out_dir / "results.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        for record in records:
            writer.writerow({k: ("" if v is None else v) for k, v in record.items()})

    json_path = out_dir / "runs.json"
    payload = [
        {
            "experiment_id": run.experiment_id,
            "config": asdict(run.config),
            "rule": run.result.rule,
            "termination": run.result.termination,
            "target": sorted(run.result.target),
            "occupied_order": run.result.occupied,
            "metrics": run.metrics,
            "transformations": [t.to_dict() for t in run.result.transformations],
        }
        for run in runs
    ]
    json_path.write_text(json.dumps(payload, indent=1))
    return {"csv": csv_path, "json": json_path}
