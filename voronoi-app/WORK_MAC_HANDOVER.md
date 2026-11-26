# Work Mac handover

The repository is [alanpenn/aggregation](https://github.com/alanpenn/aggregation). Use branch `shortest-path-tangent-backbone`. The verified research commit is `c5c4b29d80a3757f730178c4181d8aa5a1213743`. The handover is a follow-up commit on the same branch. Use `git rev-parse HEAD origin/shortest-path-tangent-backbone` after fetching to check both commit IDs.

Flat 40 has 596 certified maximal convex polygons with exact full accessible-space coverage and 1,534 frozen certified axial candidates. The reference C-H and C-S selections each have 31 lines. The bounded reduction found two feasible 29-line maps and proved a lower bound of 19. The minimum remains open. The certified maps preserve all 100 doorway requirements and independent winding rank 24/24. Movement was evaluated over 4,950 doorway pairs per map.

## Checkout and Python

For a fresh clone:

```sh
mkdir -p "$HOME/Developer"
git clone --branch shortest-path-tangent-backbone https://github.com/alanpenn/aggregation.git "$HOME/Developer/first-project"
cd "$HOME/Developer/first-project/voronoi-app"
```

For an existing clone, check `git status --short --branch` first and preserve local edits. Fetch `origin`, check out `shortest-path-tangent-backbone`, and fast-forward with `git merge --ff-only origin/shortest-path-tangent-backbone`. The branch checkout must point at the repository containing this document.

Python **3.12** is recommended. The transfer was verified with Python 3.12.13. From `voronoi-app`:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pytest
export PYTHONPATH=src:.
export MPLBACKEND=Agg
```

## Verify the Git checkpoint

```sh
.venv/bin/python -m experiments.verify_flat40_transfer
.venv/bin/python -m pytest -q tests/test_{committed_extension_turns,directed_boundary_cover,external_committed_crawler,face_extension_cover,flat40_axial_optimisation,flat40_convex_enlargement,flat40_exhaustive_resume,flat40_maximal_convex_axial,flat40_maximal_convex_minimum,flat40_oriented_crawler,flat40_three_face_triangle,imported_town,near_collinear_consolidation,oriented_extension_turns,oriented_face_extension_cover,research_storage,region_incidence_angular,complementary_axial,complementary_streamlit}.py
```

The verifier checks canonical hashes for the 596 rational polygons in [the compact registry](research/flat40/maximal-regions.json), their saved maximality evidence, the exact zero-gap record, the selected inventories, and the 19-line certificate summary. It reads the saved results without running the crawler. The 31-line records are `B-C-H.json` and `B-C-S.json` in the maximal-cover selection directory. The two 29-line inventories and their certificates are in `combined-results.json` in the further-reduction directory.

Open the committed atlases directly:

```sh
base=diagnostics/strict-generalisation
open "$base/flat40-exhaustive-convex-1/flat40-exhaustive-convex-atlas.pdf"
open "$base/flat40-maximal-convex-axial-selection-1/flat40-maximal-convex-axial-selection-atlas.pdf"
open "$base/flat40-maximal-convex-minimum-1/flat40-maximal-convex-minimum-atlas.pdf"
```

See the [exhaustive cover](FLAT40_EXHAUSTIVE_CONVEX.md), [axial selection](FLAT40_MAXIMAL_CONVEX_AXIAL_SELECTION.md), and [further reduction](FLAT40_MAXIMAL_CONVEX_MINIMUM.md) reports.

## Verify the shared data

Enable iCloud Drive for the same Apple Account on the work Mac. In Finder, use **Keep Downloaded** on `ResearchArchives/aggregation-data`. Wait for local downloads and use the checksum checks to confirm what is available on that Mac.

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
.venv/bin/python -m experiments.research_storage verify "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json"
.venv/bin/python -m experiments.verify_flat40_transfer --archive
```

The migration inventory covers the earlier shared benchmark records, including the exact frozen Flat 40 inputs. The new transfer bundle is under `transfers/flat40-research-2026-11-26/`. It is 476,523,200 bytes and contains 11,512 files across 22 experiment directories. The verifier checks the manifest, compressed archive and every member against SHA-256. The [committed transfer pointer](research/flat40/transfer.json) records both expected hashes. The source Mac verified that its iCloud Drive copy is byte-identical. The work Mac’s download and verification are still to be performed.

GitHub contains the research code, tests, reports, compact certified polygons, saved inventories, incidence matrices, structural and lower-bound evidence, and the main vector atlases. The iCloud bundle contains the complete Flat 40 diagnostic trees, including exhaustive journals and generating paths, full overlays, full route arrays, per-proposal traces, and prior Flat 40 pilots. Existing shared source datasets remain under their original paths. Cache files and raw material from the historical town pilot are outside this transfer.

If the full diagnostic tree is needed, extract into a new directory so that files in the checkout and iCloud remain intact:

```sh
bundle="$AGGREGATION_DATA_ROOT/transfers/flat40-research-2026-11-26/flat40-research-2026-11-26.tar.gz"
mkdir -p "$HOME/Developer"
extracted=$(mktemp -d "$HOME/Developer/flat40-restored.XXXXXX")
tar -xzf "$bundle" -C "$extracted"
echo "$extracted/diagnostics/strict-generalisation"
```

For experiments that accept `--source` and `--reference`, point those arguments at the extracted exact experiment directories and give new runs a fresh output path. The shared root still supplies the frozen archival inputs. See [shared storage and isolated runs](HANDOVER.md) for general archive workflows.

## Next research task

Start with Flat 40. Build the axial-line graph, angular axial-segment graph, and maximal-convex graph with edges for strictly positive overlap area. Record connectivity, mean depth, integration, choice or betweenness, and Pearson intelligibility between connectivity and integration. Freeze graph weighting and measure normalisations before comparing aggregation rules, terrains, parameters and seeds. The [configurational inputs section](FLAT40_MAXIMAL_CONVEX_MINIMUM.md#inputs-for-the-configurational-programme) identifies the reusable datasets and functions.

## Streamlit defaults

Run `./run_streamlit.sh` from `voronoi-app`. The live synthetic settlement
workflow defaults to the directed maximal overlapping convex cover, C-H
sheaf-priority reduction, and bounded exchanges. Generate the settlement,
then **Construct or resume maximal cover**, then **Generate complementary
axial map** when the cover is certified. Partial batches are saved locally
under `diagnostics/live-maximal-cover/`. Keep using the same settlement
parameters to continue the same checkpoint. Choose the legacy convex option
or C-S when needed for comparisons.

With the shared Flat 40 inputs verified, **Show saved Flat 40 maximal-cover
reference** opens the archived 31-line C-H result after rechecking exact
incidence and its structural certificate. This is available independently of
live enumeration. See the [README](README.md#default-convex-and-axial-workflow-in-streamlit)
for the live controls and certification states.
