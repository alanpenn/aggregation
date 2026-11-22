# Route-efficient sparse axial maps

The experiment starts from the saved 130-line Hill 42 and 70-line Y 42
entrance-guided maps. Fresh-exact candidate IDs identify lines in all
exports. The sheaf diagnostics use their original projected-face IDs, so
the experiment joins them by their exact rational interval endpoints.

| Fixture | Certified lines | Eligible doors | Master connectors | Exact nodes | Atomic segments |
|---|---:|---:|---:|---:|---:|
| Hill 42 | 1,347 | 100 | 6,105 | 56,530 | 107,934 |
| Y 42 | 1,651 | 99 | 6,167 | 102,767 | 200,774 |

## Experiment design

- The primary runs load the saved full-pool costs and exact doorway
  inventories. They verify the parent connector lists, reconstruct the
  master nodes and directed turn states, and reproduce the entrance-guided
  all-pair costs against the archived values. Separate metric and angular
  shortest paths include the doorway connectors. A unit of angular cost
  is a 90° turn.
- Each single-line deletion gets an all-pair route calculation, along
  with coverage, components, winding rank and attachment diagnostics.
  For deletions that disconnect any terminal, finite-cost summaries
  describe reachable pairs only. Pair counts show the omitted routes.
- The sheaf variants include every single deletion, up to eight canonical
  double deletions per sheaf, every single original representative,
  and up to three nearby, aligned full-pool replacements per sheaf.
  Each structurally valid variant receives an all-pair comparison with
  the rest of the entrance-guided map fixed.
- The four beam budgets constrain the mean **absolute** excess over the
  full-pool metric and angular costs. Each budget uses multipliers of the
  original entrance-guided excess for that fixture. The multipliers,
  in metric and angular order, are balanced (1.35, 1.35), metric-priority
  (1.18, 2.0), angular-priority (2.0, 1.18), and loose (2.2, 2.2).
- Each beam keeps two states per budget for up to 36 rounds. A round
  tests one-line deletions and disjoint blocks of two and four from a
  14-line window. The order favours structurally removable lines with
  low initial route impact. Up to two certified one-for-one sheaf
  alternatives can be combined with a deletion. Feasible proposals
  within budget are ordered by line count, then total length.
- Structural validation precedes route calculation. The router builds
  the exact master noding once, indexes atomic edges by owning line,
  and caches exact and sampled route summaries by selected line set.
  Eight evenly spaced doorway indices provide the fixed preliminary
  sample, using all higher-index destinations for each origin. The
  first round audits all structurally eligible proposals against all
  pairs. Later rounds evaluate the top five sample-ranked proposals
  per budget and use complete costs to admit surviving states.
- The combined Pareto frontier uses line count and both mean absolute
  excesses, with length breaking exact objective ties. Every exported
  beam map has complete evaluation over 4,950 Hill or 4,851 Y pairs.
  The independent audit recomputes clearance, required convex coverage,
  connectivity and circulation for the combined frontier using the
  batch validator.

The fixed sample can miss combinations in later rounds. The deletion
window, budget limits and allowed exchanges also restrict the search.
The results describe the available frontier for this pilot.

## Reading the angular baseline

| Case | Saved map | Mean absolute angular excess | Mean pairwise percentage excess | 95th-percentile absolute excess | Maximum absolute excess |
|---|---|---:|---:|---:|---:|
| Hill 42 | Entrance guided | 1.397 | 90.72% | 3.576 | 6.337 |
| Hill 42 | Best backward | 1.917 | 121.41% | 4.271 | 6.676 |
| Y 42 | Entrance guided | 1.078 | 93.24% | 2.547 | 6.035 |
| Y 42 | Best backward | 1.401 | 115.48% | 2.936 | 6.035 |

Near-zero denominators strongly affect the percentage mean. Four Hill
pairs have baseline angular cost below 0.1, with 2,836% mean excess
in the entrance-guided map. On Y, six such pairs average 10,944% excess.
Among pairs with baseline cost of at least one 90° unit, the percentage
means are 72.11% for Hill and 56.09% for Y. Their mean absolute excesses
are still 1.391 and 1.018, respectively. The angular deterioration thus
persists across the bulk of the cost distribution. The stored diagnostics
stratify every archived map using bands below 0.1, 0.1–0.5, 0.5–1, and
1 or more.

## Reproduce the pilot

The run command takes a fresh output directory. For each fixture, run
`--kind sparse_routes`, `--kind sensitivity` and `--kind matched`.
Run `--kind audit` after the search and matched-count control to certify
the combined frontier, then export the two fixtures together.

```bash
.venv/bin/python -m experiments.route_sparse PATH --case "Hill 42" --kind sparse_routes
.venv/bin/python -m experiments.route_sparse PATH --case "Hill 42" --kind sensitivity
.venv/bin/python -m experiments.route_sparse PATH --case "Hill 42" --kind matched
.venv/bin/python -m experiments.route_sparse PATH --case "Hill 42" --kind audit
.venv/bin/python -m experiments.route_sparse PATH --export
```

Repeat the case-specific commands with `Y 42` before exporting. Stage
journals link to versioned records containing the parameters, canonical
line identities, source hashes, doorway pair sample, complete summaries,
validation results and runtimes.

## Sensitivity to the connector cap

Both fixed inventories were regenerated with the original exactly visible
nearest-point rule. The first 64 connectors, or all available connectors
where fewer exist, matched the archived inventories. The cap-32 and cap-96
networks were noded separately and tested over all pairs. Raising the cap
preserved previously reachable pairs and produced no increases in either
route objective within the routing benchmark tolerance.

| Case | Cap | Certified connectors | Full metric mean | Full angular mean | Unreachable pairs A / B |
|---|---:|---:|---:|---:|---:|
| Hill 42 | 32 | 3,196 | 46.186 | 2.359 | 764 / 1,869 |
| Hill 42 | 64 | 6,105 | 46.098 | 2.068 | 0 / 0 |
| Hill 42 | 96 | 7,898 | 46.079 | 1.950 | 0 / 0 |
| Y 42 | 32 | 3,163 | 57.262 | 2.157 | 2,295 / 3,311 |
| Y 42 | 64 | 6,167 | 57.206 | 1.987 | 0 / 0 |
| Y 42 | 96 | 8,884 | 57.187 | 1.880 | 0 / 0 |

The full networks retain complete reachability at every tested cap.
At cap 32, many doorways lose every retained connector on the reduced
networks. Raising the cap from 64 to 96 changes the full-pool metric
mean by about 0.02 units on either fixture, while the angular mean
falls by 0.118 on Hill and 0.107 on Y. Connector policies therefore
materially affect sparse-map reachability and angular comparison.
All line-selection experiments use the original cap-64 inventory.

## Matched line-count control

A separate control starts from each archived best backward map and
permits one-for-one exchanges with lines from the original entrance-guided
map. The sample ranks possible additions, then valid exchanges. At most
six additions, six valid removals per addition and five complete exchange
evaluations are considered per round. The control allows up to three
rounds. It accepts an exchange only if all doorway pairs remain reachable
and both whole-map mean route costs improve or tie, with at least one
strict improvement.

| Case | Map | Lines | Length | Metric excess mean / p95 / max | Angular excess mean / p95 / max |
|---|---|---:|---:|---:|---:|
| Hill 42 | Best backward | 44 | 1,467.12 | 14.141 / 31.593 / 48.640 | 1.917 / 4.271 / 6.676 |
| Hill 42 | Matched exchange | 44 | 1,468.66 | 13.757 / 32.268 / 45.164 | 1.862 / 3.982 / 6.337 |
| Y 42 | Best backward | 37 | 1,402.73 | 10.480 / 23.883 / 42.931 | 1.401 / 2.936 / 6.035 |
| Y 42 | Matched exchange | 37 | 1,400.95 | 9.826 / 23.868 / 42.931 | 1.371 / 2.937 / 6.035 |

Hill replaced line 278 with 45 and preserved winding rank 11. Y replaced
line 1050 with 960 and preserved winding rank 3. Both maps cover every
required region, form one connected component and reach every doorway
pair. The Hill exchange also improves both means over the other
44-line backward map, whose excesses were 13.881 metric and 1.893
angular. Whole-map mean improvements can coincide with deterioration in
part of the tail, as Hill's metric 95th percentile shows. Control
runtimes were 192 seconds for Hill and 70 seconds for Y.

## Marginal contribution and sheaf substitution

On Hill, 108 of 130 entrance-guided lines were individually removable.
The other 22 split evenly between coverage and circulation as the first
failed condition. Removing line 48 increased the metric mean by 1.942
units and produced a maximum pairwise increase of 12.267. Removing
line 867 increased the angular mean by 0.507, with a maximum pairwise
increase of 3.226. The route importance of these two lines differs even
though either can be deleted in isolation while preserving the topology.

In Hill sheaf 2, replacing 824 with 823 shifts the mean metric and
angular costs by less than 0.0003 units in absolute value. Deleting that
sheaf's lines 824 and 867 together increases the means by 0.499 metric
and 0.666 angular units. The tested single external representative 837
also incurs about 0.667 angular units. Near-equivalent swaps and costly
group collapses occur within the same corridor.

On Y, 43 of the 70 entrance-guided lines were individually removable.
The first failed condition for the other 27 was coverage in 13 cases,
circulation in six, doorway attachment in five and connectivity in
three. Among the removable lines, deleting line 24 incurred the
largest metric penalty, increasing mean cost by 0.703 units. Deleting
line 1261 incurred the largest mean angular penalty of 0.055 turn units,
with a maximum pairwise angular increase of 3.182. The same line
also caused a maximum metric increase of 15.576 units for an affected
pair. Structural redundancy and route redundancy are distinct.

Several Y corridors had both useful substitutes and poor representatives.
Replacing line 1174 with nearby line 1126 in sheaf 3 improved the
whole-map means by 0.243 metric and 0.048 angular units. Replacing that
entire sheaf with line 276 increased them by 0.518 and 0.077. In sheaf 2,
exchanging 1050 for 1044 shifted both means by less than 0.0001 units.
These examples support evaluating whole-network routes before treating
geometrically similar lines as interchangeable.

## Beam results

| Budget | Hill lines | Hill metric / angular excess | Y lines | Y metric / angular excess |
|---|---:|---:|---:|---:|
| Balanced | 61 | 10.035 / 1.730 | 39 | 7.330 / 1.319 |
| Metric-priority | 63 | 10.006 / 1.728 | 42 | 6.402 / 1.231 |
| Angular-priority | 64 | 9.273 / 1.640 | 40 | 6.968 / 1.264 |
| Loose | 61 | 10.035 / 1.730 | 37 | 8.199 / 1.399 |

The table shows one minimum-count beam survivor per budget. Where
multiple same-count maps survive, it shows the one with the lower excess
in the budget's priority objective, using metric for balanced and loose.
Hill's 61-line beam map has length 1,753.83. It reaches all 4,950 pairs
with winding rank 11, and its pairwise excess p95 is 22.005 metric and
3.838 angular. The beam used all 36 rounds under the balanced and loose
budgets. The separate exchange control reached 44 lines by starting
from the saved backward map.

On Y the loose budget reached 37 lines, the balanced budget reached 39,
the angular-priority budget reached 40 and the metric-priority budget
reached 42. The 37-line beam map is shorter than the 37-line backward
map (1,362.51 versus 1,402.73). Its mean metric excess is 8.199 versus
10.480 and its mean angular excess is 1.399 versus 1.401. The 95th-percentile
metric excess falls from 23.883 to 18.646, while the maximum rises from
42.931 to 49.947. The separate matched control offers a lower angular
mean at the same line count and a different metric trade-off. The
earlier lowest-connectivity backward order has the lowest observed
angular excess at exactly 37 lines (1.368), with a higher mean metric
excess (10.334). The 39-line balanced beam lowers both means to
7.330 and 1.319. The
399-pair sample and all-pair ranking retained the same winners from
the 30 valid proposals examined in the first Y round. After that
round complete routing evaluates the shortlist only.

Across 12 newly selected Y Pareto maps within eight lines of the minimum,
33 lines survive in every map. They include 1261, the most costly
individual angular deletion, and 960, the line restored in the
matched-count control. Line 24, the most costly individual metric
deletion, survives in 11 of the 12. Some other frequently retained
lines are structurally indispensable in the starting map. The
survival map depicts frequency within this search and the marginal
table separates structural necessity from measured route effect.

Fully scoring the later Y shortlists changed the top-ranked proposal
in ten budget-round comparisons. The sample was sufficient to recover
the first-round winners in this audit. Later rounds leave the ranking
of proposals outside the shortlist unresolved. Y's search took 442
seconds and the independent audit passed all 22 combined frontier
entries in 43 seconds.

The 400-pair Hill sample also recovered the same first-round winners
as the all-pair audit of all 28 valid proposals. Later all-pair scoring
changed the top sample-ranked proposal in four metric-priority rounds.
The Hill search took 1,241 seconds. Across ten newly selected Hill
frontier maps with at most 69 lines, 38 lines survive every time.
They include lines 48, 867, 45, 46 and 1333, all among the most costly
individual deletions on at least one route objective.

## Interpretation

The two fixtures both admit fixed-count exchanges that improve the
saved backward maps' mean routes. Y also reaches the backward line
count directly from the entrance-guided map, with a larger metric
improvement than the local exchange control. The 61-line Hill beam
map pays for shorter routes with 17 extra lines compared with the
fixed-count control. Geometric similarity identifies promising
exchange candidates, and the whole-map route tests distinguish
interchangeable lines from those that serve different movements.

The priority budgets show no consistent line-count premium for
preserving angular efficiency. The angular-priority minimum is one
line higher than the metric-priority minimum on Hill and two lines
lower on Y under the tested fixture-relative budgets. Even the
efficient compact examples remain materially above the full pools.
For example, the 61-line Hill map and the 37-line Y beam map average
about 22% and 14% above the full-pool metric means, and about 84% and
70% above the angular means. These percentages compare means directly.
Both examples retain the required circulation topology and all
doorway pairs.

## Saved records and exports

| Case | Beam and marginal analysis | Connector sensitivity | Matched-count control |
|---|---|---|---|
| Hill 42 | `4f10973c793e4c5e951bdde27feebc49` | `74f974e1f9bb4760a6d14ce2716b5e29` | `b9a9825eca354bc78d60e468ef77af37` |
| Y 42 | `7f5389e342ad42cd8f61e16c94266136` | `c7d2fb6e1f504495941fee220308db0d` | `35869ae99bd8477880bae3a3d540af80` |

The version 1 beam code expected a line-count field in the archived
map summary. The failed Y attempt and the interrupted Hill attempt
are preserved. Version 2 derives the count from the certified line
IDs. It reuses the original baseline, sensitivity and matched-count
records.

The independent audit passed all 49 Hill frontier entries in 169
seconds (record `03f5f41908174c12a13a81161b4d75d3`) and all 22 Y
entries (record `76ed909524df471195b44a4446dc1550`). The exports
contain 169 map comparisons, 200 marginal deletions and 184 sheaf
alternatives. All comparison maps have complete doorway reachability,
one component and the required coverage and winding rank. Twelve
targeted tests passed.

- [All map comparisons](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/comparison.csv)
- [All 200 individual deletions](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/marginal.csv)
- [Sheaf alternatives](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/sheaf-alternatives.csv)
- [Hill Pareto plots](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/Hill-42-pareto.png) and [numbered survival map](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/Hill-42-survival.png)
- [Y Pareto plots](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/Y-42-pareto.png) and [numbered survival map](diagnostics/preserved-axial-benchmark/route-sparse/pilot-2/Y-42-survival.png)
