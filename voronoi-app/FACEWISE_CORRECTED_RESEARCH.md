# Facewise dyad growth across Hill and Converging Valleys, seeds 40–42

The versioned **slope_preference_facewise_v1** strategy completed 100 dyads on each of the six matched settlements. The 600 corrected placements passed independent geometry and prefix-connectivity checks. All 600 assigned open cells belong to their settlement’s main face-connected open-space component. The six corrected settlements reuse the original parameters and have byte-identical clipped cell polygons and identical grid sites and edges. Their building arrangements can differ.

## Before and after

Each run has 100 completed dyads, 100 buildings and 100 assigned open cells. Values below are legacy → corrected. Internal occupied block counts equal circulation-hole counts in all twelve records.

| Configuration | Invalid dyads | Assigned-open components | Excluded assigned cells | Excluded unassigned cells | Internal blocks / holes |
|---|---:|---:|---:|---:|---:|
| Hill 40 | 0 → 0 | 1 → 1 | 0 → 0 | 0 → 0 | 16 → 17 |
| Hill 41 | 0 → 0 | 1 → 1 | 0 → 0 | 0 → 0 | 13 → 15 |
| Hill 42 | 0 → 0 | 1 → 1 | 0 → 0 | 2 → 2 | 11 → 16 |
| Y 40 | 7 → 0 | 3 → 1 | 3 → 0 | 54 → 184 | 6 → 6 |
| Y 41 | 6 → 0 | 4 → 1 | 4 → 0 | 115 → 130 | 2 → 6 |
| Y 42 | 1 → 0 | 1 → 1 | 0 → 0 | 0 → 29 | 3 → 5 |

The Y 40 and Y 41 replays reproduce the first invalid dyad at building 78, where the building and its paired open cell share zero boundary length. The first split of the assigned-open component occurs at building 81 in Y 40 and 79 in Y 41. Y 42 has an invalid building–open pair at building 99 even though every assigned open cell is connected. The audit confirmed that all 16 distinct invalid links were SciPy ridge neighbors with zero ridge length inside the canvas. Corrected placement excludes all 16 and requires both faces, catching building–open failures independently of the connectivity test. Unassigned open cells can still be cut off by the building arrangement, as the Y cases show.

The full set of invalid legacy placements is shown below. Edges are identified by their ordered cell IDs in the per-case audit.

| Configuration | Building labels with a missing parent face | Building labels with a missing building–open face |
|---|---|---|
| Y 40 | 81, 94 | 78, 81, 82, 84, 97, 98 |
| Y 41 | 79, 80, 86, 94 | 78, 83, 86 |
| Y 42 | — | 99 |

The corrected generator draws from face-neighbor lists ordered by cell ID before applying the existing randomized preference scores. Removing ridge-only neighbors changes the eligible choices and random draws, and the stable ordering can also change which site receives each draw. This explains why matched seeds can diverge even when the legacy placements happened to be valid. Building numbers identify placement order within each settlement. Across cases, 43–67 building cells are occupied in both variants, and only 2–4 retain the same number. The close-ups align physical cell IDs so labels can be read in context.

## Code and verification

- [Shared face graph](src/voronoi_app/face_adjacency.py) indexes clipped polygons and admits edges only when their boundaries share positive length. [Topology](src/voronoi_app/experimental_circulation_topology.py) uses the same graph for open-space connectivity and retains the separate vertex-or-face rule for occupied blocks.
- [Versioned strategy](src/voronoi_app/aggregation.py) grows each dyad from an already assigned open parent and selects two unused face neighbors. It records the parent cell and both face lengths, with an unavailable parent and length for the seed dyad. It requires a complete clipped polygon inventory.
- The [orchestrator](src/voronoi_app/orchestrator.py) prepares the authoritative clipped geometry before corrected growth. The [batch adapter](src/voronoi_app/batch_methods.py) saves that same geometry and the ordered placements. The registered batch method is `generate-facewise-settlement`, version 1. Legacy generation remains the default for existing configuration replay.
- [Regression tests](tests/test_facewise_growth_audit.py) cover positive face length, vertex-only contact, polygon separation, a real SciPy ridge outside the canvas, missing clipped geometry, a valid extension and a disconnected invalid prefix. The [matched runner](experiments/facewise_matched.py) independently replays each legacy record against its exact sites, polygon bytes, doorway sequence and building labels. It checks both shared lengths, cell uniqueness, the already-assigned parent and face connectivity at every corrected placement.
- Six fresh corrected generations and six topology derivations reproduced the saved output hashes. All 15 PNGs have a short side greater than 2,000 pixels, and the corresponding PDFs retain vector geometry. The record index and per-case audit JSON retain exact legacy and corrected settlement/topology IDs and record hashes. The experiment stopped after deriving topology. The focused regression suite passed all 13 tests. The broad suite was interrupted at its long default axial coverage case after 147 passes and two skips.

## Numbered maps

Both panels use the same coordinate extent and clipped polygons. White building numbers follow each run’s actual placement order. Teal cells are assigned open cells, blue arrows represent parent-to-new-open relationships, and dashed red links mark zero-length shared faces. The separate parent maps show all 99 growth links after initialization. Close-ups compare the seven named legacy locations at matching cell IDs.

| Configuration | Side-by-side map | Corrected parent links | Named locations |
|---|---|---|---|
| Hill 40 | [PNG](diagnostics/facewise-corrected/pilot-1/hill-40-comparison.png) · [PDF](diagnostics/facewise-corrected/pilot-1/hill-40-comparison.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/hill-40-corrected-parents.png) · [PDF](diagnostics/facewise-corrected/pilot-1/hill-40-corrected-parents.pdf) | — |
| Hill 41 | [PNG](diagnostics/facewise-corrected/pilot-1/hill-41-comparison.png) · [PDF](diagnostics/facewise-corrected/pilot-1/hill-41-comparison.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/hill-41-corrected-parents.png) · [PDF](diagnostics/facewise-corrected/pilot-1/hill-41-corrected-parents.pdf) | — |
| Hill 42 | [PNG](diagnostics/facewise-corrected/pilot-1/hill-42-comparison.png) · [PDF](diagnostics/facewise-corrected/pilot-1/hill-42-comparison.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/hill-42-corrected-parents.png) · [PDF](diagnostics/facewise-corrected/pilot-1/hill-42-corrected-parents.pdf) | — |
| Y 40 | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-40-comparison.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-40-comparison.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-40-corrected-parents.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-40-corrected-parents.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-40-named-closeups.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-40-named-closeups.pdf) |
| Y 41 | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-41-comparison.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-41-comparison.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-41-corrected-parents.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-41-corrected-parents.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-41-named-closeups.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-41-named-closeups.pdf) |
| Y 42 | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-42-comparison.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-42-comparison.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-42-corrected-parents.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-42-corrected-parents.pdf) | [PNG](diagnostics/facewise-corrected/pilot-1/converging_valleys-42-named-closeups.png) · [PDF](diagnostics/facewise-corrected/pilot-1/converging_valleys-42-named-closeups.pdf) |

[Comparison CSV and exact record IDs](diagnostics/facewise-corrected/pilot-1/comparison.csv)

Per-case placement audits

[Hill 40](diagnostics/facewise-corrected/pilot-1/hill-40.json) · [Hill 41](diagnostics/facewise-corrected/pilot-1/hill-41.json) · [Hill 42](diagnostics/facewise-corrected/pilot-1/hill-42.json) · [Y 40](diagnostics/facewise-corrected/pilot-1/converging_valleys-40.json) · [Y 41](diagnostics/facewise-corrected/pilot-1/converging_valleys-41.json) · [Y 42](diagnostics/facewise-corrected/pilot-1/converging_valleys-42.json)


To reproduce the matched experiment into a new output directory, run the following from the repository root.

```sh
PYTHONPATH=src:. python -m experiments.facewise_matched \
  --output diagnostics/facewise-corrected/pilot-2
```
