"""Reproduce the controlled comparison of the morphic grammar modes.

Usage (from voronoi-app/):
    PYTHONPATH=src .venv/bin/python scripts/run_morphic_batch.py --smoke
    PYTHONPATH=src .venv/bin/python scripts/run_morphic_batch.py
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

from voronoi_app.morphic.experiment import MorphicConfig, run_batch, save_batch  # noqa: E402
from voronoi_app.morphic.report import fig_comparison, fig_distributions, summarise  # noqa: E402

MODES = ["random", "adjacent", "enclosing", "enclosing_continue"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=30, help="number of seeds")
    parser.add_argument("--first-seed", type=int, default=40)
    parser.add_argument("--cells", type=int, default=200)
    parser.add_argument("--occupied", type=int, default=60)
    parser.add_argument("--terrain", default="flat")
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "morphic_grammar")
    parser.add_argument("--smoke", action="store_true", help="3 seeds, written to <out>_smoke")
    args = parser.parse_args()

    seeds = 3 if args.smoke else args.seeds
    out_dir = Path(str(args.out) + "_smoke") if args.smoke else args.out
    base = MorphicConfig(
        num_cells=args.cells, occupied_target=args.occupied, terrain=args.terrain,
        enclosure_strength=args.strength,
    )
    runs = run_batch(range(args.first_seed, args.first_seed + seeds), MODES, base)
    paths = save_batch(runs, out_dir)

    summary = summarise(runs)
    with (out_dir / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows({k: ("" if v is None else v) for k, v in row.items()} for row in summary)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))

    first = args.first_seed
    representative = {r.config.mode: r for r in runs if r.config.seed == first}
    fig_comparison(representative).savefig(
        out_dir / f"morphologies_seed{first}.png", dpi=110, bbox_inches="tight")
    fig_distributions(runs).savefig(out_dir / "distributions.png", dpi=110, bbox_inches="tight")

    print(f"{len(runs)} runs ({seeds} seeds x {len(MODES)} modes) -> {out_dir}")
    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
