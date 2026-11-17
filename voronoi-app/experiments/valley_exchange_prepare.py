"""Prepare exact candidates for the saved Converging Valleys diagnostic."""

import argparse
import json
import time
from pathlib import Path

from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.core import ExperimentPipeline
from voronoi_app.exact_enumeration import (
    _support_dict, exact_pool_to_dict, generate_fresh_exact_candidate_pool,
)
from voronoi_app.experimental_boundary_candidates import enumerate_boundary_endpoint_candidates
from voronoi_app.orchestrator import ExperimentOrchestrator
from voronoi_app.registry import get_registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text())
    opened, occupied, live, config, paired = load_axial_snapshot(data)
    pipeline = ExperimentPipeline.from_dict(config)
    registry = get_registry()
    terrain = registry.get_terrain(pipeline.terrain_provider, pipeline.terrain_params)
    extent = (0, 0, pipeline.canvas_size, pipeline.canvas_size)
    grid = registry.get_grid(pipeline.grid_generator, pipeline.grid_params).generate(
        terrain=terrain, extent=extent, seed=pipeline.seed,
    )
    grid.metadata["extent"] = extent
    aggregation = registry.get_aggregation(
        pipeline.aggregation_strategy, pipeline.aggregation_params,
    ).aggregate(terrain=terrain, grid=grid, form=pipeline.urban_form, seed=pipeline.seed)
    if aggregation.buildings != set(occupied) or aggregation.open_spaces != paired:
        raise ValueError("Regenerated aggregation differs from the saved diagnostic")
    polygons = ExperimentOrchestrator(pipeline)._space_polygons(grid)
    if any(not polygons[cell].equals_exact(polygon, 0)
           for cell, polygon in {**opened, **occupied}.items()):
        raise ValueError("Regenerated cell geometry differs from the saved diagnostic")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    with (args.output_dir / "settlement.json").open("x") as output:
        json.dump({
            "snapshot": str(args.snapshot),
            "configuration": config,
            "building_labels": {int(k): int(v) for k, v in aggregation.building_labels.items()},
            "live_candidate_count": len(live.candidate_lines),
        }, output)
    started = time.monotonic()
    print("generating exact pool", flush=True)
    problem, audit = generate_fresh_exact_candidate_pool(opened, occupied)
    baseline = exact_pool_to_dict(problem.pool)
    baseline["audit_counts"] = audit.counts
    baseline["domain_rejections"] = [_support_dict(support) for support in audit.domain_rejections]
    with (args.output_dir / "baseline.json").open("x") as output:
        json.dump(baseline, output)
    print("exact pool", len(problem.pool.candidates), "seconds",
          round(time.monotonic() - started, 2), flush=True)
    started = time.monotonic()
    print("generating boundary-endpoint pool", flush=True)
    boundary = enumerate_boundary_endpoint_candidates(opened, occupied)
    records = [{
        "start": [str(v) for v in candidate.start],
        "end": [str(v) for v in candidate.end],
        "supports": [_support_dict(support) for support in candidate.supports],
        "contacts": [{
            "point": [str(v) for v in contact.point],
            "buildings": [[int(ref.building_id), int(ref.vertex_index)] for ref in contact.buildings],
            "accessible_boundary": contact.accessible_boundary,
        } for contact in candidate.contacts],
    } for candidate in boundary.candidates]
    with (args.output_dir / "boundary.json").open("x") as output:
        json.dump({"counts": boundary.counts, "candidates": records}, output)
    print("boundary pool", len(records), "seconds", round(time.monotonic() - started, 2),
          flush=True)


if __name__ == "__main__":
    main()
