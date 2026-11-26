# Reproduce the Flat 40 configurational pilot

Run from the `voronoi-app` directory with Python 3.11 or later and the
project requirements installed. Point `AGGREGATION_DATA_ROOT` at the
shared `aggregation-data` directory. The following commands read the
recorded source revision and verify the transfer in a temporary directory.
They do not change the current branch or archived inputs.

```sh
project="$PWD"
python="$project/.venv/bin/python"
source_revision=8cb6d461f707691dedea77f5e3a387c6c441fc06
snapshot=$(mktemp -d)
git -C .. archive "$source_revision" voronoi-app | tar -xf - -C "$snapshot"
records="$snapshot/voronoi-app"
bundle="$AGGREGATION_DATA_ROOT/transfers/flat40-research-2026-11-26/flat40-research-2026-11-26.tar.gz"
(cd "$records" && PYTHONPATH=src:. "$python" -m experiments.verify_flat40_transfer --archive)
tar -xzf "$bundle" -C "$records" \
  diagnostics/strict-generalisation/flat40-exhaustive-convex-1/coverage-maximal.json \
  diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/movement.json
MPLBACKEND=Agg PYTHONPATH=src:. "$python" -m experiments.flat40_configurational \
  --records "$records" --evidence "$records" --source-revision "$source_revision" \
  --output diagnostics/strict-generalisation/flat40-configurational-replay
PYTHONPATH=src:. "$python" -m pytest -q tests/test_configurational.py tests/test_complementary_axial.py
```

The output directory must be new. The runner validates individual input hashes
against the transfer manifest and frozen provenance record. It does not invoke
the region crawler, selector or doorway-routing search.
