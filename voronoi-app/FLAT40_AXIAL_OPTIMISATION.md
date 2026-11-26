# Corrected Flat 40 axial optimisation

## Complete intersecting-pair control

The 34-line archived C-H map contains 561 unordered pairs. Of these, 463 are
disjoint and 98 have a noncollinear intersection. For each intersecting pair
the experiment evaluated all 1,500 candidates outside the current selection.
The strict region and doorway screens compare the incidences lost on removal
with those supplied by the replacement. The remaining trials use exact
clearance, the frozen intersection graph, and dynamic winding. All possible
successes and inconclusive dynamic results go to independent exact validation.
The graph of every accepted selection is rebuilt from the rational intervals.

| Departure from straight | Intersecting pairs | Pairs with a certified replacement | Certified replacements |
|---|---:|---:|---:|
| 0°–10° | 0 | 0 | 0 |
| >10°–15° | 0 | 0 | 0 |
| >15°–20° | 5 | 1 | 3 |
| >20°–30° | 5 | 0 | 0 |
| >30°–45° | 16 | 0 | 0 |
| >45°–60° | 20 | 0 | 0 |
| >60°–90° | 52 | 2 | 20 |

| Removed pair | Departure | Replacements |
|---|---:|---|
| 1435 and 1509 | 15.295° | 323, 1365, 1436 |
| 1470 and 1509 | 74.252° | 377, 1387, 1443, 1444, 1445, 1460, 1466, 1469, 1475 |
| 957 and 1519 | 88.461° | 364, 367, 1389, 1391, 1425, 1427, 1481, 1501, 1502, 1503, 1504 |

Across **147,000 trials**, 113,710 failed strict region incidence, 1,139
failed connectivity, 32,128 failed winding, and 23 certified. All certified
selections retained 292/292 regions, 100/100 doorway incidences, one component,
exact clearance and 24/24 independent winding rank. One of 10 near-collinear
pairs was replaceable (10.0%), compared with two of 88 other pairs (2.3%).
A two-sided Fisher calculation is 0.279. This is descriptive because pairs
share lines and belong to the same map. The two near-right-angle successes
show that similarity of continuation direction is unnecessary for structural
substitutability. This search measures one exchange from archived C-H.

The 24 archive files were checked against the migration SHA-256 manifest.
The previous experiment was checked against its recorded input hashes and
experiment script hash. Its three exchange certificates were independently
replayed and matched, and the prior result file's digest is recorded with the
new run. The previous result file has no independent published digest in the
migration manifest.

## Boundary effects

All five intervals in the three original exchanges have an endpoint exactly
on the east boundary of the 100 × 100 settlement frame. Holding the interior
endpoint fixed and intersecting the line with a square rotated by 22.62°
clockwise about the settlement centre changes the ordering. The three
replacement lines have boundary-only lengths of 40.74, 41.18 and 41.85 model
units. Removed line 1509 measures 38.87 under that same construction. In the
archived frame, all three replacements were shorter than 1509. The rotated
lengths for these replacements extrapolate past their archived endpoints.
They are geometric sensitivity measurements, with no clearance claim for
extrapolated intervals. Clipped length was excluded from the trial screens
and is not an efficiency measure.

A second test only trims originally certified intervals. It never extends
them. It retains the original region, doorway and winding requirements, so
this is a fixed-geometry stress test and not a regenerated settlement.
Exact intersections, coverage and independent winding were recalculated.

| Window | C-H and original three exchanges, coverage / rank | Algorithm D, coverage / rank |
|---|---:|---:|
| Archived | 292 / 24 | 292 / 24 |
| Inset by 5 units on each side | 288 / 20 | 290 / 21 |
| Rotate 22.62° counterclockwise | 289 / 19 | 290 / 19 |
| Rotate 22.62° clockwise | 289 / 22 | 290 / 22 |

All cases retained one connected component and all 100 doorway-region
incidences. Each altered window broke full structural certification for
both the original map and its exchanges. At the level of these totals, the
three exchanges introduce no additional loss relative to C-H. The tests
demonstrate sensitivity of absolute certification to clipping. Substitutability
under a regenerated candidate pool and recomputed requirements for a new
boundary remains an open question.

## Doorway movement

The archived routing definitions were applied to all 4,950 unordered pairs
of the same 100 doorways on C-H, the three original exchanges, and Algorithm
D. Angular routes use the existing angular depth convention. Metric routes
use the certified regional connectors. All pairs were reachable in every
map. Replayed C-H and D angular costs matched the archives exactly. The
largest absolute metric replay difference was below 1.5 × 10⁻¹³ model units.

| Map | Mean angular cost | Angular 95th percentile | Mean metric cost | Metric 95th percentile |
|---|---:|---:|---:|---:|
| C-H | 0.881667 | 1.98081 | 48.78003 | 88.59845 |
| C-H + 323 | 0.882161 | 2.03429 | 48.81104 | 88.59845 |
| C-H + 1365 | 0.882796 | 2.03429 | 48.79873 | 88.59845 |
| C-H + 1436 | 0.883173 | 2.03429 | 48.79492 | 88.59845 |
| D | 0.869102 | 2.03957 | 48.69090 | 88.57342 |

Candidate 323 gave the smallest mean angular increase among the original
exchanges (+0.000494), and the largest single-route increases (+0.813 angular
and +7.460 metric). Candidate 1436 gave the smallest mean metric increase
(+0.01489) and the smallest worst-route increases (+0.258 angular and +2.955
metric) of the three. Algorithm D had the lowest mean costs and a higher
angular 95th percentile than archived C-H. The 20 newly found
near-right-angle alternatives received structural certificates. The movement
comparison covers the three exchange maps specified as inputs.

## Reproduce

The isolated run reads the archives without modifying them and requires a
fresh output directory. It writes the pair audit and certificates, boundary
calculations, and the complete angular and metric route arrays.

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_axial_optimisation \
  --manifest "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json" \
  --previous diagnostics/strict-generalisation/near-collinear-consolidation-1/flat-40.json \
  --output diagnostics/strict-generalisation/flat40-axial-optimisation-replay
```

The complete run is under `diagnostics/strict-generalisation/flat40-axial-optimisation-2/`.
Eight focused tests passed.
