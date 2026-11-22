# Full-pool doorway routing reference

This benchmark uses the preserved Hill 42 and Y 42 fresh-exact candidate
pools. It evaluates each entrance-guided map, all five backward deletion
orders, and the sheaf strategies. Each tested axial map is an exact subset
of the corresponding fresh-exact pool. Production generation and selection
remain unchanged.

## Fixed doorway and connector inventory

The settlement records identify the doorway pairings as previously
reconstructed research pairings. This experiment reads their saved exact
midpoints and cell IDs from the batch records. It neither reconstructs
doorways nor invents missing pairings. All 100 Hill doorways and 99 Y
doorways qualify. The Y missing-face pairing remains preserved in the
settlement but contributes no route endpoint.

The earlier measures records fixed up to 64 exactly visible
nearest-point-to-line connectors per doorway. After identifying lines by
their rational endpoints, the fresh-exact and projected-face inventories
are identical for both fixtures. The master inventory has 6,105 connectors
on Hill and 6,167 on Y. The experiment independently rechecked the
clearance of every connector and its exact incidence on the claimed line.

The master network is noded once at every line intersection and connector
stop. Each reduced network retains the master segments owned by its
selected lines and the connectors whose lines it retains. This ensures
that adding a line cannot remove an existing connector or path. Line
changes, metric distance and angular turns are separate shortest-path
objectives. Metric costs include connector lengths. Angular costs include
connector turns and are expressed in units of 90°. The axial analyses
require axial-network travel and use no free-space shortcut between doors.

## Full-pool cost distributions

| Settlement | Measure | Mean | Median | Minimum | Maximum | 95th percentile | Reachable | Unreachable |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Hill 42 · 1,347 lines | Metric | 46.098 | 46.902 | 3.371 | 101.982 | 79.394 | 4,950 | 0 |
| Hill 42 | Angular | 2.068 | 2.080 | 0.054 | 4.479 | 3.383 | 4,950 | 0 |
| Hill 42 | Topological | 1.300 | 1.000 | 0.000 | 4.000 | 3.000 | 4,950 | 0 |
| Y 42 · 1,651 lines | Metric | 57.206 | 56.007 | 3.211 | 144.358 | 108.771 | 4,851 | 0 |
| Y 42 | Angular | 1.987 | 1.815 | 0.006 | 5.344 | 3.697 | 4,851 | 0 |
| Y 42 | Topological | 1.068 | 1.000 | 0.000 | 4.000 | 3.000 | 4,851 | 0 |

## Doorway routing after reduction

Each percentage is the mean of the individual doorway-pair percentages.
The last column uses the continuous-space metric reference. The other
columns compare against the full axial candidate network.

| Case | Map | Lines | Metric excess | Angular excess | Continuous metric detour |
|---|---|---:|---:|---:|---:|
| Hill 42 | A · Entrance guided | 130 | 19.55% | 90.72% | 20.04% |
| Hill 42 | B · Best backward | 44 | 32.82% | 121.41% | 33.37% |
| Hill 42 | C · Sheaf aware | 113 | 25.33% | 155.71% | 25.84% |
| Hill 42 | D · Sheaf and backward | 54 | 49.82% | 197.87% | 50.43% |
| Hill 42 | E · Bounded exchanges | 54 | 49.88% | 197.67% | 50.49% |
| Y 42 | A · Entrance guided | 70 | 13.69% | 93.24% | 14.22% |
| Y 42 | B · Best backward | 37 | 24.78% | 115.48% | 25.38% |
| Y 42 | C · Sheaf aware | 53 | 22.77% | 116.77% | 23.35% |
| Y 42 | D · Sheaf and backward | 38 | 24.88% | 121.82% | 25.49% |
| Y 42 | E · Bounded exchanges | 38 | 24.85% | 121.78% | 25.46% |

The full pools already approach the continuous metric reference, with
mean pairwise detours of 0.398% on Hill and 0.430% on Y. Hill's continuous
graph was computed with the existing exact visibility-graph method on the
same saved geometry and doorways. Its mean, median, minimum, maximum
and 95th percentile are 45.962, 46.728, 3.370, 101.931 and 79.252.
Y reuses the archived visibility-graph costs after verifying the source
geometry and exact doorway coordinates and identities. Its corresponding
statistics are 57.062, 55.851, 3.211, 144.268 and 108.609. Every pair was
reachable on both continuous graphs. All 24 comparisons passed the
continuous metric lower-bound check.

The [comparison CSV](diagnostics/preserved-axial-benchmark/routing-references/e101fc909354439e8695fd77ac791d41/comparison.csv)
includes all 24 rows, total lengths, validation status, and distribution
statistics for absolute and percentage excess. The versioned records below
contain the raw full and selected costs and signed excess arrays in a shared
doorway-pair order. Hill continuous costs are in record
`47962d9abe0b40e0ba4b1be71abfbdee`, with
[raw Hill continuous detours](diagnostics/preserved-axial-benchmark/routing-references/e101fc909354439e8695fd77ac791d41/Hill-42-continuous-detour.json)
saved alongside the export.

## Verification

The tolerance for comparing two finite costs is `1e-8 + 1e-9 × max(abs(a), abs(b))`.
All checks across both fixtures passed. No signed full-pool excess was
negative, even before applying the tolerance. The raw excess remains signed.
Percent excess is null when its baseline is zero or either cost is unavailable.

As an independent check of the new master-noding router, I compared each
A–E route against its previously saved sheaf result. The largest difference
on either fixture was below `2.0e-13` in metric cost and `3.6e-15` in angular
cost. The tests also verify that metric and angular optimisation remain
separate, that a shared connector stop does not duplicate sparse arcs, and
that genuine negative excess is retained and flagged.

## Reuse

- Hill full-pool result: `2cb0f919bf034580ac00420272cdddd6`.
- Y full-pool result: `29567ca2f86f4b2aab28b93d6f873ea8`.
- Y replay using the saved full-pool costs: `17718d31e9204e97bde8c274de485176`.

Each result includes the exact master connectors, doorway order, pair index,
selected intervals and raw costs, linked to the versioned candidate and
settlement records. To evaluate a new validated subset without recomputing
the full-pool shortest paths, use:

```bash
.venv/bin/python -m experiments.full_pool_routing \
  --store diagnostics/preserved-axial-benchmark \
  --reuse-baseline FULL_POOL_RECORD_ID \
  --validated-map MAP_VALIDATION_RECORD_ID
```

Use `--validated-map` more than once for several maps in the same settlement.
The replay checks the saved graph and doorway identity and creates a new
record. Existing records remain available.
