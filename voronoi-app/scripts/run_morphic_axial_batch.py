"""Reproduce the staged axial comparison.

From voronoi-app/:
    PYTHONPATH=src .venv/bin/python scripts/run_morphic_axial_batch.py --pilot
    PYTHONPATH=src .venv/bin/python scripts/run_morphic_axial_batch.py
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voronoi_app.morphic.axial_experiment import (  # noqa: E402
    AxialExperimentConfig,
    run_axial_batch,
    save_axial_batch,
)
from voronoi_app.morphic.axial_viz import (  # noqa: E402
    fig_axial_graph_diagnostics,
    fig_axial_snapshot,
    fig_axial_trajectories,
    summarise_axial_runs,
)
from voronoi_app.morphic.axial_statistics import paired_final_tests  # noqa: E402

MODES = ["random", "adjacent", "enclosing"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--first-seed", type=int, default=40)
    parser.add_argument("--cells", type=int, default=200)
    parser.add_argument("--occupied", type=int, default=60)
    parser.add_argument("--terrain", default="flat")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--sample-spacing", type=float, default=8.0)
    parser.add_argument("--angle-step", type=float, default=15.0)
    parser.add_argument("--local-radius", type=int, default=3)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "outputs" / "morphic_axial_batch"
    )
    parser.add_argument("--pilot", action="store_true", help="run 5 seeds before the full batch")
    args = parser.parse_args()

    seed_count = 5 if args.pilot else args.seeds
    out_dir = Path(str(args.out) + "_pilot") if args.pilot else args.out
    config = AxialExperimentConfig(
        num_cells=args.cells,
        occupied_target=args.occupied,
        terrain=args.terrain,
        analysis_interval=args.interval,
        sample_spacing=args.sample_spacing,
        angle_step_degrees=args.angle_step,
        local_radius=args.local_radius,
    )
    runs = run_axial_batch(
        range(args.first_seed, args.first_seed + seed_count), MODES, config
    )
    save_axial_batch(runs, out_dir)

    summary = summarise_axial_runs(runs)
    summary_json = out_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=1))
    summary_csv = out_dir / "summary.csv"
    with summary_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(
            {key: ("" if value is None else value) for key, value in row.items()}
            for row in summary
        )
    paired = paired_final_tests(runs, mode_a="random", mode_b="adjacent",
                                step=args.occupied)
    paired_json = out_dir / "paired_tests.json"
    paired_json.write_text(json.dumps(paired, indent=1))
    paired_csv = out_dir / "paired_tests.csv"
    with paired_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paired[0]))
        writer.writeheader()
        writer.writerows(paired)

    representative = runs[0]
    latest = representative.snapshots[-1]
    fig_axial_snapshot(
        representative.carrier,
        latest,
        representative.generation.target,
        "length",
    ).savefig(out_dir / "representative_morphology_and_lines.png", dpi=110,
              bbox_inches="tight")
    fig_axial_graph_diagnostics(latest).savefig(
        out_dir / "representative_axial_diagnostics.png", dpi=110,
        bbox_inches="tight",
    )
    fig_axial_trajectories(runs).savefig(
        out_dir / "trajectories.png", dpi=110, bbox_inches="tight"
    )

    print(
        f"{len(runs)} runs ({seed_count} seeds x {len(MODES)} modes) saved to {out_dir}"
    )
    print(f"  snapshot summary: {summary_csv}")
    print(f"  exploratory paired tests: {paired_csv}")
    print(f"  complete geometry, histories and analyses: {out_dir / 'axial_runs.json'}")


if __name__ == "__main__":
    main()
