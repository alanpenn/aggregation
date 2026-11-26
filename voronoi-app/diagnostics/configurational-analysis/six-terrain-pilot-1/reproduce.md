# Reproduce the six-terrain pilot

Run from the `voronoi-app` directory with the local Python environment and
project requirements installed. Python 3.12 was used for the pilot. Set
`AGGREGATION_DATA_ROOT` to the shared root containing
`migration-sha256-2026-11-24.json` and `strict-generalisation/`. The same
root contains the Flat 40 transfer. Preserve the original
`diagnostics/strict-generalisation/flat40-configurational-1/` outputs as the
historical reference.

```sh
python="$PWD/.venv/bin/python"
source_revision=8cb6d461f707691dedea77f5e3a387c6c441fc06
snapshot=$(mktemp -d)
git -C .. archive "$source_revision" voronoi-app | tar -xf - -C "$snapshot"
records="$snapshot/voronoi-app"
bundle="$AGGREGATION_DATA_ROOT/transfers/flat40-research-2026-11-26/flat40-research-2026-11-26.tar.gz"
(cd "$records" && PYTHONPATH=src:. "$python" -m experiments.verify_flat40_transfer --archive)
tar -xzf "$bundle" -C "$records" \
  diagnostics/strict-generalisation/flat40-exhaustive-convex-1/coverage-maximal.json \
  diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/movement.json
MPLBACKEND=Agg PYTHONPATH=src:. "$python" -m experiments.six_terrain_configurational \
  --records "$records" --evidence "$records" --source-revision "$source_revision" \
  --legacy diagnostics/strict-generalisation/flat40-configurational-1 \
  --output diagnostics/configurational-analysis/six-terrain-pilot-replay
MPLBACKEND=Agg PYTHONPATH=src:. "$python" -m pytest -q \
  tests/test_configurational.py tests/test_configurational_traversal.py \
  tests/test_configurational_statistics.py tests/test_complementary_axial.py \
  tests/test_constructive_axial.py tests/test_exact_axial.py
```

The output directory must be new. It receives the completed per-case
checkpoints as the runner proceeds. The runner loads exact existing maps,
verifies the source and reproduces the old Flat 40 statistics before
publishing terrain comparisons. It does not regenerate settlements,
enumerate new convex polygons or optimise axial selections.

Run the separate recovered seed cohort with the same shared archive:

```sh
MPLBACKEND=Agg PYTHONPATH=src:. "$python" -m experiments.configurational_seed_audit \
  --primary diagnostics/configurational-analysis/six-terrain-pilot-replay \
  --output diagnostics/configurational-analysis/six-terrain-pilot-replay/strict-backward-seeds
```

This supplementary run uses the saved strict-backward inventories for every
case. Keep its summaries separate from the seven saved C-H inventories.
