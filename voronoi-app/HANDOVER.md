# Voronoi research handover · 24 November 2026

The GitHub repository is `alanpenn/aggregation`. Use branch
`shortest-path-tangent-backbone` and run Python commands from its
`voronoi-app` subdirectory. The data archive is
`voronoi-research-handover-2026-11-24.tar.gz`. Its internal
`research-handover-manifest.json` records the exact source commit, file
inventory, sizes and SHA-256 checksums. The independent checksum sidecar
verifies the compressed archive. Earlier handover notes remain in Git history.

## Implemented and verified

- Corrected facewise aggregation and numbered building geometry underpin the
  exact candidate, incidence and winding records. See
  [facewise research](FACEWISE_CORRECTED_RESEARCH.md) and
  [strict generalisation](STRICT_AXIAL_GENERALISATION_RESEARCH.md).
- The Streamlit selector enumerates fresh certified candidates, chooses pairs
  of well-connected tangents with different intersection sets at exposed
  convex occupied-block vertices, and repairs strict coverage, doorway
  incidence, connectivity and winding. C-H removes sheaf redundancy first.
  C-S tries shorter intervals first. Both recompute winding during deletion,
  then check final winding and clearance independently. Optional bounded
  exchanges prefer fewer lines, then shorter total length, then more distinct
  transverse crossings. Archived replay uses the frozen acceptance policy.
- Flat 40 replay passed with 1,534 full candidates, 628 complementary lines,
  and 629 after coverage repair with candidate 1212. Both frozen modes reached
  34 lines, 292/292 strict regions, 100/100 doorways, one component and winding
  rank 24/24. All seven archived settlements reproduced both frozen inventories.
- Flat 40 parent recombination found alternative valid 34-line maps within the
  tested unions. The factorial analysis documents 128 minimum configurations
  in its stated search scope. The seven reproducible cross-terrain cases all
  favoured C-S and C-H on line count over strict backward selection.

## Reports and atlases

- [Flat 40 recombination](diagnostics/strict-generalisation/recombined-axial-maps-2/report.md)
  and [numbered atlas](diagnostics/strict-generalisation/recombined-axial-maps-2/flat-40-numbered-atlas.pdf)
- [Flat 40 factorial analysis](diagnostics/strict-generalisation/flat-40-factorial-1/report.md)
  and [all 128 maps](diagnostics/strict-generalisation/flat-40-factorial-1/flat-40-all-128-maps.pdf)
- [Cross-terrain benchmark](diagnostics/strict-generalisation/cross-terrain-constructive-1/report.md),
  [numbered atlas](diagnostics/strict-generalisation/cross-terrain-constructive-1/numbered-cross-terrain-atlas.pdf)
  and [input lineage](diagnostics/strict-generalisation/cross-terrain-constructive-1/lineage.json)

## Open work

1. Recover the 348 missing immutable files for 29 of 36 benchmark settlements
   before extending the matched comparison. Keep the original stage IDs and
   confirm recorded hashes before using recovered inputs. Published maps,
   journals and configuration files are insufficient to reproduce those cases.
2. Continue interactive checks on larger fresh settlements. Live controls,
   session caching, movement gating and legacy displays already passed
   automated tests. The interactive time limit is cooperative and bounded
   search does not prove a global minimum.
3. Implement the historical town-plan import after locating the original
   research image and confirming its provenance and scale. Classify streets
   and passages as accessible and exclude buildings, green areas and enclosed
   precincts. No town-specific source drawing or importer was identified for
   this handover.

## Home Mac

Python 3.12 was used on the work Mac. Python 3.11 or later is required.
Start at the existing clone of `alanpenn/aggregation`. If the status output
shows local changes, preserve them before switching branches. Use a separate
checkout when keeping local work in place.

```sh
cd /path/to/aggregation
git status --short --branch
git remote -v
git fetch origin
git switch shortest-path-tangent-backbone
git pull --ff-only origin shortest-path-tangent-backbone
git rev-parse HEAD origin/shortest-path-tangent-backbone
cd voronoi-app

archive_dir="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives"
bundle=voronoi-research-handover-2026-11-24.tar.gz
(cd "$archive_dir" && shasum -a 256 -c "$bundle.sha256")
archive="$archive_dir/$bundle"
tar -tzf "$archive" | less
tar -xOzf "$archive" research-handover-manifest.json | less

python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest
.venv/bin/python restore_research_archive.py "$archive"
.venv/bin/python restore_research_archive.py "$archive" --apply
MPLBACKEND=Agg PYTHONPATH=src:. .venv/bin/python -m pytest -q tests/test_complementary_axial.py tests/test_complementary_streamlit.py tests/test_exact_streamlit.py tests/test_constructive_axial.py
./run_streamlit.sh
```

For a fresh clone where the branch does not yet exist locally, use
`git switch --track origin/shortest-path-tangent-backbone`. If the archive is
transferred separately, point `archive_dir` at the directory holding both
files. Stop if the sidecar check fails. Check the manifest commit against the
checked-out commit. The restore utility verifies every file before applying
changes, skips byte-identical files and prints conflicting paths. If there
are conflicts, it leaves the original files in place and prints the temporary
directory containing verified incoming copies.

At [localhost:8501](http://localhost:8501), generate a settlement, choose
**Complementary tangents + structural reduction**, then click **Generate
complementary axial map**. The stage selector, candidate inspector and
optional doorway routing are described in the [README](README.md).

To replay all seven exact archives, run:

```sh
VORONOI_ARCHIVE_TESTS=1 MPLBACKEND=Agg PYTHONPATH=src:. .venv/bin/python -m pytest -q tests/test_complementary_axial_archive.py
```

## Shared research data on both Macs

The Python code still comes from GitHub. The current working tree introduces
`AGGREGATION_DATA_ROOT`, which names the directory containing the contents of
`diagnostics/`. With the variable unset, scripts retain their existing local
paths. The shared layout puts the cohort records, atlases and other experiment
folders under `aggregation-data/strict-generalisation/`. Archived work with
repository-relative paths remains readable.

On both Macs, sign in to the same Apple Account and enable **Sync this Mac**
under System Settings → your name → iCloud → Drive. In Finder open iCloud
Drive → ResearchArchives, Control-click **aggregation-data**, and select
**Keep Downloaded**. Use Finder's iCloud Status column to check whether the
folder is waiting to upload or contains files that still need downloading.
[Apple iCloud setup](https://support.apple.com/en-us/118443) ·
[Apple download and sync status guidance](https://support.apple.com/en-gb/guide/mac-help/mchlc994344b/mac)

Once this code is available in the checkout, run from `voronoi-app` on each Mac.

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
PYTHONPATH=src:. .venv/bin/python -m experiments.research_storage verify \
  "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json"
./run_streamlit.sh
```

The verifier reads each file and compares SHA-256. A successful result confirms
that this Mac can read the complete migrated inventory. For a single file, use
`shasum -a 256 "$AGGREGATION_DATA_ROOT/path/to/file"` and compare the digest in
the manifest. In the app, **Advanced research storage** displays the resolved
location. The separate atlas viewer uses the same location and identifies an
unavailable index or map.

The migration source is the local `diagnostics/` tree plus the verified handover
inventory. Each input path is copied relative to `diagnostics/`. This also
places the handover's misplaced experiment files under their intended shared
paths. The migration compares SHA-256, skips identical destinations and
reports conflicts without replacing either copy. Git's source and reports,
the local data tree and the original TARs stay in place. The archive restoration
script also honours the setting when called with `--apply`. Its verification
mode still validates the TAR without restoring files.

Use the isolated launcher for any experiment that writes results while using
shared data. It hashes and copies the inputs into a private local working
directory, runs the existing module there, and publishes changed scientific
files into `aggregation-data/runs/<timestamp>-<random-id>/`. Allow local free
space for the input copy. This keeps the fixed filenames used by historic
scripts out of concurrent shared writes.

```sh
PYTHONPATH=src:. .venv/bin/python -m experiments.research_storage run \
  experiments.cross_terrain_axial inputs

# Use the ID printed by the first command for the next stage.
PYTHONPATH=src:. .venv/bin/python -m experiments.research_storage run \
  --from-run RUN_ID experiments.cross_terrain_axial case --case flat-42
```

The `inputs` phase validates the available immutable lineage directly and can
use the shared copy without a TAR. Each new run gets its own ID, even with the
same module and arguments. Treat `run.json` as the publication inventory, check
its exit code, and verify its file checksums before reading the run on the
other Mac. An iCloud client may show the inventory before it receives all the
data. Check a published run with:

```bash
PYTHONPATH=src:. .venv/bin/python -m experiments.research_storage verify --run \
  "$AGGREGATION_DATA_ROOT/runs/RUN_ID/run.json"
```

Use new run directories for further edits, and keep shared baseline files
immutable. Direct legacy write commands should use local data or the isolated
launcher.

For an experiment with a fixed output folder, use
`run --fresh strict-generalisation/vertex-axial-1 experiments.vertex_axial`
to start a fresh vertex experiment. The option omits that folder from the
private run copy. The shared checkpoint remains available, and the new
results receive a different run ID.
