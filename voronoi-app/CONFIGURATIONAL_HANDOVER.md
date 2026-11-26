# Configurational research handover · 26 November 2026

Use the `shortest-path-tangent-backbone` branch of
[alanpenn/aggregation](https://github.com/alanpenn/aggregation).
Run Python commands from the `voronoi-app` subdirectory. This handover adds
the configurational experiments on top of the existing Flat 40 geometric,
31-line and 29-line axial, and integer lower-bound work. See
[WORK_MAC_HANDOVER.md](WORK_MAC_HANDOVER.md) for the earlier transfer and
[HANDOVER.md](HANDOVER.md) for the storage layout.

## Completed work

- [Flat 40 configurational pilot](diagnostics/strict-generalisation/flat40-configurational-1/report.md)
  reproduces the 31-H, 29-H and 34-H axial geometries and the certified 596
  maximal convex polygons. The historical angular segment graph remains
  available for reproducibility.
- [Six-terrain configurational pilot](diagnostics/configurational-analysis/six-terrain-pilot-1/report.md)
  validates continuous directed segment traversal. Six seed-40 C-H cases
  match in realised building count and aggregation settings. Flat 41 provides
  one further C-H observation.
- The separate strict-backward analysis verified all 348 previously missing
  stage files in the shared archive and evaluated 36 saved maps. Shoulder 42
  realised 89 buildings and is illustrative. The five seeds common to all
  six 100-building terrains underlie the matched terrain-mean comparisons.
- The complete certified maximal convex cover is available for Flat 40.
  Five additional terrain covers require separate checkpointed enumeration.
  No new settlements or axial selections were generated in these pilots.

## Data carried forward

The existing shared `aggregation-data` root remains the source of the
immutable batch inputs. The 26 November Flat 40 research transfer under
`aggregation-data/transfers/flat40-research-2026-11-26/` remains the source
of the exhaustive Flat 40 records and full doorway arrays. The 24 November
handover archive remains available for earlier local diagnostics.

The new `voronoi-configurational-handover-2026-11-26.tar.gz` in
iCloud Drive `ResearchArchives/` contains the local Flat 40 and six-terrain
configurational outputs, including the vector PDFs, per-case graphs and node arrays,
and any local research files found outside the prior archive inventories.
Its sidecar verifies the compressed file. Its embedded
`research-handover-manifest.json` lists the exact Git commit and file hashes.
The repository carries source, tests, specifications and compact summaries.

## Resume on the home Mac

From the existing clone, check the remote and preserve any uncommitted
changes before switching branches. Use a separate clone if needed.

```sh
cd /path/to/aggregation
git status --short --branch
git remote -v
git fetch origin
git switch shortest-path-tangent-backbone
git pull --ff-only origin shortest-path-tangent-backbone
git rev-parse HEAD origin/shortest-path-tangent-backbone
cd voronoi-app

archives="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives"
bundle=voronoi-configurational-handover-2026-11-26.tar.gz
export AGGREGATION_DATA_ROOT="$archives/aggregation-data"
(cd "$archives" && shasum -a 256 -c "$bundle.sha256")
tar -tzf "$archives/$bundle" | less
tar -xOzf "$archives/$bundle" research-handover-manifest.json | less
```

After the checksum passes and the archive commit is identified, use Python
3.12, as tested on the work Mac. The restore helper checks each path and
digest and preserves both versions when a local path conflicts.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest
.venv/bin/python restore_research_archive.py "$archives/$bundle" --apply
MPLBACKEND=Agg PYTHONPATH=src:. .venv/bin/python -m pytest -q \
  tests/test_configurational.py tests/test_configurational_traversal.py \
  tests/test_configurational_statistics.py tests/test_exact_axial.py
```

Open the restored [Flat 40 atlas](diagnostics/strict-generalisation/flat40-configurational-1/atlas.pdf),
[six-terrain atlas](diagnostics/configurational-analysis/six-terrain-pilot-1/atlas.pdf)
and [seed figures](diagnostics/configurational-analysis/six-terrain-pilot-1/strict-backward-seeds/seed-variability.pdf).
The [six-terrain replay guide](diagnostics/configurational-analysis/six-terrain-pilot-1/reproduce.md)
uses an isolated archive of the exact source revision and fresh output
paths. For the app, run `./run_streamlit.sh`. Sync completion on the home
Mac can be checked by verifying the archive there.
