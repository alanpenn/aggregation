# Voronoi axial-map handover

## Git state

On 2026-11-16 the branch was `morphic-grammar-local`, tracking
`origin/morphic-grammar-local` at `https://github.com/alanpenn/aggregation.git`.
Before the handover commit, a fetch confirmed it was two commits ahead and
zero behind:

* `b445e76` Secure and display certified axial research maps
* `3c7dc55` Integrate exact axial candidate inspection

The main research handover commit is
`49cc7ec4cebbe2b5b70ea8208b954085ce531575`. It and both earlier commits were
pushed to `origin/morphic-grammar-local`. The earlier commits include
`tests/fixtures/exact_y/` and `tests/fixtures/angular_y_geometry.json`.
This document has a subsequent documentation commit; use `git rev-parse HEAD`
after cloning to see the final branch commit.

Files included in the main handover commit:

* Modified: `README.md`, `src/voronoi_app/convex_coverage.py`,
  `tests/test_axial_generator.py`, `tests/test_render_doors.py`.
* New research reports: `ANGULAR_FIDELITY_RESEARCH.md`,
  `BOUNDARY_ENDPOINT_RESEARCH.md`, and this `HANDOVER.md`.
* New experimental modules: `src/voronoi_app/experimental_angular_selection.py`,
  `src/voronoi_app/experimental_boundary_candidates.py`.
* New tests: `tests/test_experimental_angular_selection.py`,
  `tests/test_experimental_boundary_candidates.py`.
* New experiment scripts: `experiments/angular_hill_{prepare,reference,solve,combine,validate,plots}.py`.

No changes outside `voronoi-app/` were found in the worktree.

## Data that Git will not transfer

The following paths are **not included** by committing the worktree:

1. `diagnostics/` is Git-ignored. Preserve the whole directory separately if
   the full research history matters: it contains exact-Y map plots, reports,
   candidate records, certifications, angular investigations and saved axial
   snapshots. It contains about 118 non-log files totalling 124 MB. Some
   snapshots duplicate the tracked exact-Y fixtures, but do not assume all
   diagnostics are duplicates.
2. The earlier session's files are outside the repository at
   `$HOME/.copilot/session-state/3191f707-b920-4e07-817a-e0bca07f81eb/files/`.
   Preserve this directory separately for a complete handover, including its
   research scripts and results; it contains about 189 non-log, non-cache files
   totalling 43.8 MB. In particular:
   * **Required Hill replay inputs:** `hill42-corridor-pool.json`,
     `hill42-fresh-exact-baseline.json`, `boundary-hill42.json`.
   * **Exact provenance and results:** `angular-hill-prepared.json`,
     `angular-hill-reference.json`, `angular-hill-*-results.json`,
     `angular-hill-validation.json`, `boundary-exact-y.json`,
     `boundary-{cartesian,voronoi}-{11,42}.json` and `boundary-angular-*.json`.
   * **Plots and map data:** `angular-hill-*.png`,
     `hill42-axial-map-numbered.png`, `hill42-axial-map-data.json`,
     `hill42-components*.png` and `hill42-corridor-2-15.png`.
   * `hill42_axial_overlay.py` is identical to the shared overlay snapshot but
     hard-codes this Mac's session path; adapt its path before reuse.

The session also contains disposable logs, caches, scratch scripts and
intermediate measurements; retaining the whole directory separately is safest
until its contents have been reviewed. Do not copy `.venv/`, `node_modules/`,
bytecode, caches or logs into Git. Review data before sharing: diagnostics
contain settlement geometry and experiment configuration.

On 2026-11-16, a separate local archive was created at
`$HOME/Developer/aggregation-research-transfer-2026-11-16.tar.gz`
(75,605,176 bytes; SHA-256
`873d6e45d5750f56d12ee7f008f5ce08d128b2a7fab0158970642fed26fd6496`).
Its `MANIFEST.json` records sizes and SHA-256 hashes for 307 files. The archive
was extracted into a fresh verification directory and every file was checked
against the manifest. It contains the diagnostics under
`repository/voronoi-app/diagnostics/` and the session data under
`home/.copilot/session-state/3191f707-b920-4e07-817a-e0bca07f81eb/files/`.
Volatile `.log` files and Python bytecode/cache were excluded and are listed
in the manifest. **The archive is local and must be transferred separately**;
it is not in Git.

For integrity checks, SHA-256 of key external files:

```text
8600caead6af8243a95e0203fe76f755bc03440042c28bd8e72246a94fd2812c  hill42-corridor-pool.json
6a1f3515742c7c3ca62d66479d6db5cb5789f041bb42ec13ac1517d6ec19aaaa  hill42-fresh-exact-baseline.json
347e92513b9fc875438ba2f9aaafd378c0f127c201c301d44edba20ace267945  boundary-hill42.json
e9a917dae22be1cd78d1468c9190e6af10feb6ca69eee8cc5e342ad4a97b7dea  boundary-exact-y.json
579a87b56926482b26ea9b61df49d22674ccc529b4d262c94cc46b4c357f71fd  angular-hill-prepared.json
93beb90ce3f83a89741f65c5440c72479757a08a3041dcb6d4441eec4457f26e  angular-hill-final-results.json
```

No relevant current file checked exceeds 50 MiB; the largest diagnostic is
9,001,982 bytes. GitHub warns above 50 MiB and blocks files above 100 MiB, so
Git LFS is not required for these individual files. It is not installed here.
The directories contain many generated files, however: a separate archive or
selective reviewed Git additions are preferable to blindly adding everything.
This size check excludes dependency directories and Git history.

## Setup on the second Mac

After separately transferring the archive to the second Mac, clone the branch
and set up the app with Python 3.12:

```sh
git clone --branch morphic-grammar-local https://github.com/alanpenn/aggregation.git
cd aggregation/voronoi-app
python3.12 -m venv .venv
.venv/bin/python -m pip install -e . pytest
./run_streamlit.sh
```

For the archived research, replace `ARCHIVE` below with its transferred path.
Extract into a new directory and copy the three replay inputs to a separate
working directory, because the experiment scripts overwrite named results:

```sh
ARCHIVE="$HOME/Downloads/aggregation-research-transfer-2026-11-16.tar.gz"
shasum -a 256 "$ARCHIVE"
TRANSFER="$(mktemp -d "${TMPDIR:-/tmp}/voronoi-transfer.XXXXXX")"
tar -xzf "$ARCHIVE" -C "$TRANSFER"
SOURCE="$TRANSFER/home/.copilot/session-state/3191f707-b920-4e07-817a-e0bca07f81eb/files"
DATA="$(mktemp -d "${TMPDIR:-/tmp}/voronoi-hill-work.XXXXXX")"
cp "$SOURCE/hill42-corridor-pool.json" "$SOURCE/hill42-fresh-exact-baseline.json" \
  "$SOURCE/boundary-hill42.json" "$DATA/"
```

Compare the `shasum` result to the archive hash above. Use `DATA` with the
commands in `ANGULAR_FIDELITY_RESEARCH.md`; the extracted diagnostics are under
`$TRANSFER/repository/voronoi-app/diagnostics/`.

The app requires Python 3.11+, NumPy, SciPy, Matplotlib, NetworkX,
Shapely >= 2.1 and Streamlit 1.67.0. `pytest` is not declared as a project
dependency. Apart from Streamlit and the Shapely minimum, dependencies are not
locked; exact replay across package versions is not guaranteed. The tested
environment was Python 3.12.13, NumPy 2.5.2, SciPy 1.18.0, Matplotlib 3.11.1,
NetworkX 3.6.1, Shapely 2.1.2, Streamlit 1.67.0 and pytest 9.1.1. A clean
installation on the second Mac has not been tested.

The tracked root `.agents/skills/developing-with-streamlit` symlink points
inside `.venv/lib/python3.12/`; it works here but may be broken until the
Python 3.12 environment and Streamlit are installed. This affects the optional
agent skill, not the application. The old absolute `cd` example in
`PHASES_9_11_SUMMARY.md` is machine-specific. The Hill experiment scripts take
`--data-dir` rather than hard-coding the old Mac's path. The app binds to
`0.0.0.0:8501` by default.

The repository root also contains a separate Vite project. Its tracked lockfile
requires Node `^20.19.0 || >=22.12.0`; this Mac's default Node is 5.5.0, so its
build was not verified. The Vite project is not required to run Streamlit.

## Results, validation and next steps

The experimental boundary rule adds 1,238 distinct intervals to the Hill
seed-42 exact baseline. The combined pool contains 2,610 rational intervals.
The fixed-attachment angular experiment found feasible 365-line subsets for
ε=0 and 0.02 and 362-line subsets for ε=0.05–0.50. Both cover 268/268 convex
regions, preserve 11/11 ring witnesses and all three connected components.
These are not proven minima; ε=0 uses a `1e-10` numerical comparison slack.
The 21.0679-unit corridor candidate is in the pool but not in those selected
subsets. See `BOUNDARY_ENDPOINT_RESEARCH.md` and
`ANGULAR_FIDELITY_RESEARCH.md` for the geometry, limitations and diagnostics.

On this Mac the following targeted command passed **138 tests**, with two
opt-in regeneration tests skipped and one slow default-Voronoi test deselected:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_experimental_angular_selection.py tests/test_experimental_boundary_candidates.py \
  tests/test_angular.py tests/test_exact_axial.py tests/test_exact_replay.py \
  tests/test_axial_generator.py tests/test_render_doors.py \
  -k 'not default_voronoi_experiment_coverage_and_rings'
```

The live full Hill regeneration requires `HILL42_FULL_REGENERATION=1`; the
fresh exact-Y enumeration requires `EXACT_Y_REGENERATE=1`. Neither was rerun
for this handover. The Hill research report documents the complete replay
commands using a user-chosen `DATA` directory containing the three saved
inputs. **Use a fresh working copy:** those scripts write and may overwrite
their named result files in `DATA`. Exact geometry is authoritative, but the
accessible-domain overlay and convex decomposition are GEOS-constructed;
the candidate pool and angular sample do not prove axial-map completeness or
global optimality.
