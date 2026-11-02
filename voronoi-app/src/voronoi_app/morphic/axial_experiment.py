"""Reproducible axial analyses of cellular aggregation trajectories."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .axial import AxialRepresentation, axial_diagnostics, extract_from_cells
from .carrier import Carrier
from .experiment import MorphicConfig, build_carrier
from .metrics import measure_configuration
from .rules import RunResult, make_rule, run_rule


@dataclass(frozen=True)
class AxialExperimentConfig:
    mode: str = "adjacent"
    num_cells: int = 200
    occupied_target: int = 60
    seed: int = 40
    terrain: str = "flat"
    sample_spacing: float = 8.0
    angle_step_degrees: float = 15.0
    local_radius: int = 3
    analysis_interval: int = 10
    target_size: int = 1
    enclosure_strength: float = 1.0

    def experiment_id(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha1(canonical.encode()).hexdigest()[:10]


@dataclass
class AxialSnapshot:
    step: int
    occupied: List[int]
    morphology_metrics: Dict[str, object]
    representation: AxialRepresentation
    axial_metrics: Dict[str, object]


@dataclass
class AxialExperimentRun:
    config: AxialExperimentConfig
    carrier: Carrier
    carrier_id: str
    generation: RunResult
    snapshots: List[AxialSnapshot]


def _carrier_id(carrier: Carrier) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(carrier.extent).encode())
    for cell in carrier.cells:
        digest.update(str(cell).encode())
        digest.update(carrier.polygons[cell].wkb)
    return digest.hexdigest()[:16]


def _rule(config: AxialExperimentConfig):
    if config.mode == "enclosing":
        return make_rule(
            "enclosing",
            strength=config.enclosure_strength,
            target_size=config.target_size,
            after_enclosure="stop",
        )
    return make_rule(config.mode)


def _stages(config: AxialExperimentConfig, generation: RunResult) -> List[int]:
    stages = list(range(config.analysis_interval, len(generation.occupied) + 1,
                        config.analysis_interval))
    if not stages or stages[-1] != len(generation.occupied):
        stages.append(len(generation.occupied))
    return sorted(set(stages))


def run_axial_experiment(
    config: AxialExperimentConfig,
    carrier: Optional[Carrier] = None,
) -> AxialExperimentRun:
    """Run a growth mode and analyse axial structure at valid stages."""
    if config.analysis_interval < 1:
        raise ValueError("analysis_interval must be >= 1")
    carrier = carrier or build_carrier(MorphicConfig(
        num_cells=config.num_cells,
        occupied_target=config.occupied_target,
        seed=config.seed,
        terrain=config.terrain,
    ))
    generation = run_rule(
        _rule(config), carrier, config.occupied_target, seed=config.seed
    )
    snapshots = []
    for step in _stages(config, generation):
        occupied = generation.occupied_at(step)
        representation = extract_from_cells(
            carrier,
            occupied,
            sample_spacing=config.sample_spacing,
            angle_step_degrees=config.angle_step_degrees,
        )
        snapshots.append(AxialSnapshot(
            step=step,
            occupied=occupied,
            morphology_metrics=measure_configuration(
                carrier, occupied, generation.target or None
            ),
            representation=representation,
            axial_metrics=axial_diagnostics(
                representation, local_radius=config.local_radius
            ),
        ))
    return AxialExperimentRun(
        config=config,
        carrier=carrier,
        carrier_id=_carrier_id(carrier),
        generation=generation,
        snapshots=snapshots,
    )


def run_axial_comparison(
    base: AxialExperimentConfig, modes: Iterable[str]
) -> Dict[str, AxialExperimentRun]:
    """Run selected modes on one carrier with matching geometry and seed."""
    carrier = build_carrier(MorphicConfig(
        num_cells=base.num_cells,
        occupied_target=base.occupied_target,
        seed=base.seed,
        terrain=base.terrain,
    ))
    runs = {}
    for mode in modes:
        config = AxialExperimentConfig(**{**asdict(base), "mode": mode})
        runs[mode] = run_axial_experiment(config, carrier)
    return runs


def run_axial_batch(
    seeds: Iterable[int],
    modes: Iterable[str],
    base: AxialExperimentConfig,
) -> List[AxialExperimentRun]:
    runs = []
    modes = list(modes)
    for seed in seeds:
        config = AxialExperimentConfig(**{**asdict(base), "seed": seed})
        runs.extend(run_axial_comparison(config, modes).values())
    return runs


def _snapshot_payload(snapshot: AxialSnapshot) -> Dict[str, object]:
    representation = snapshot.representation
    return {
        "step": snapshot.step,
        "occupied": snapshot.occupied,
        "morphology_metrics": snapshot.morphology_metrics,
        "axial_method": representation.method,
        "axial_settings": representation.settings,
        "candidate_line_count": representation.candidate_count,
        "open_sample_count": representation.sample_count,
        "covered_sample_count": representation.covered_sample_count,
        "lines": [
            {
                "id": line.id,
                "coordinates": [list(point) for point in line.geometry.coords],
                "length": line.length,
                "covered_samples": line.covered_samples,
            }
            for line in representation.lines
        ],
        "axial_edges": [list(edge) for edge in representation.graph.edges()],
        "axial_metrics": snapshot.axial_metrics,
    }


def save_axial_batch(
    runs: Sequence[AxialExperimentRun], out_dir: Path
) -> Dict[str, Path]:
    """Persist configurations, geometry references, transformations and analyses."""
    out_dir.mkdir(parents=True, exist_ok=True)
    carriers_dir = out_dir / "carriers"
    carriers_dir.mkdir(exist_ok=True)
    carriers_written = set()
    payload = []
    for run in runs:
        if run.carrier_id not in carriers_written:
            carrier_payload = {
                "carrier_id": run.carrier_id,
                "extent": run.carrier.extent,
                "metadata": run.carrier.metadata,
                "cells": {
                    str(cell): {
                        "wkb_hex": run.carrier.polygons[cell].wkb_hex,
                        "adjacent": run.carrier.neighbours(cell),
                    }
                    for cell in run.carrier.cells
                },
            }
            (carriers_dir / f"{run.carrier_id}.json").write_text(
                json.dumps(carrier_payload, indent=1)
            )
            carriers_written.add(run.carrier_id)
        payload.append({
            "experiment_id": run.config.experiment_id(),
            "config": asdict(run.config),
            "carrier_id": run.carrier_id,
            "generation": {
                "rule": run.generation.rule,
                "termination": run.generation.termination,
                "target": sorted(run.generation.target),
                "occupied_order": run.generation.occupied,
                "transformations": [
                    transformation.to_dict()
                    for transformation in run.generation.transformations
                ],
            },
            "snapshots": [_snapshot_payload(snapshot) for snapshot in run.snapshots],
            "analysis_failures": [],
        })
    results_path = out_dir / "axial_runs.json"
    results_path.write_text(json.dumps(payload, indent=1))
    return {"results": results_path, "carriers": carriers_dir}
