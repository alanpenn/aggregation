# Extreme diagonal pairs as corridor representatives

An extreme opposed pair preserved the hard constraints in all four straight
synthetic grids. It was valid in three of the six inferred Hill 42 and Y 42
corridors. Two Y pairs needed additional lines to keep all fixed doorway
attachments, and one Hill corridor supplied no qualifying global pair.
Transverse line contacts alone did not distinguish the valid Y pair from the
two invalid ones.

## Geometry and comparison

The synthetic street has a nominal width of four units, a row of buildings
on either side, front and rear doors, rear passages and transverse gaps.
The four straight fixtures use length-to-width ratios of 4, 8, 8 and 12
with 2, 2, 4 and 4 transverse streets, respectively. Four ratio-8,
four-junction variants curve, taper, bend or vary the building frontage.
The curve is a piecewise-linear approximation. The taper also narrows the
outer bands. All vertices lie on a dyadic coordinate grid. Every pair of
building or end-portal vertices supplies a seed to the exact maximal-interval
builder. Duplicate intervals are merged and open cells serve as required
convex regions. The synthetic exterior retains its full certified line
inventory, so it can provide alternative paths around the corridor.

For the preserved settlements, the longest line from each earlier selected
sheaf proposes an axis. The experiment uses the first three distinct axes
in decreasing line length, screening duplicate bands by common membership.
These are reproducible geometric corridor proxies. Width is 11% of axial
length, limited to a half-band of 2.5–5 coordinate units. A member must
overlap at least 28% of an axis, stay within the band along the overlapping
interval, and be inclined no more than 32° from the axis. Each diagonal in
an opposed pair must overlap at least 60% of the axis, cross its approximate
centreline, and have non-negligible lateral displacement. The two strokes
must intersect exactly. Pairs are ranked by total maximal length, then the
shorter member's length and exact interval identity. The frontage inventory
separately flags positive-length exact overlap with a building face.

A retains the original members, B uses the geometric pair, C adds the
smallest feasible number of lines found in the repair shortlist, D ranks
valid pairs by the sum of their two mean costs normalised by their
respective full-pool means, and E restores only the existing backward-map
members of the same band. E is a corridor replacement inside the original
map's exterior. No saved backward representatives exist for the synthetic
fixtures. Length and external-connectivity rules provide two other
two-line controls.

C considers up to ten additional sheaf members ordered by their ability to
restore transverse connections, then all zero-, one-, and two-line
combinations until it finds a feasible size. D considers up to eight
connectivity-ranked lines and includes both extreme diagonals when present.
It scores every structurally feasible shortlisted pair over all doorways.
External connections count distinct exterior lines touched. The transverse
subset has lateral displacement more than 0.65 times longitudinal
displacement in the corridor frame. A repair line may restore a doorway
attachment with no change in transverse contact count.

The saved full-pool routes, master noding and fixed connectors define the
preserved comparisons. Each synthetic case builds its own exact master
network and fixes up to 64 certified visible connectors per doorway. All
rows distinguish hard failures from valid but degraded routes. Costs for
invalid, partly reachable maps summarise reachable pairs, with missing pairs
counted separately. Angular units correspond to 90° of turn.

## Straight and deformed streets

The arrows show the number of corridor representatives. The cost changes
are mean absolute differences from A across every eligible doorway pair
where the variant is valid.

| Fixture | A → B lines | B metric / angular change | D metric / angular change | Winding B |
|---|---:|---:|---:|---:|
| Straight 4×, 2 transverse streets | 10 → 2 | +0.016 / +0.047 | ≈0 / ≈0 | 6/6 |
| Straight 8×, 2 transverse streets | 14 → 2 | +0.019 / +0.068 | ≈0 / ≈0 | 6/6 |
| Straight 8×, 4 transverse streets | 26 → 2 | +0.020 / +0.056 | +0.001 / ≈0 | 10/10 |
| Straight 12×, 4 transverse streets | 22 → 2 | +0.090 / +0.259 | +0.001 / +0.001 | 10/10 |
| Curve | 61 → 2 | +0.088 / +0.054 | +0.088 / +0.054 | 10/10 |
| Taper | 96 → 2 | +0.262 / +0.368 | +0.120 / +0.021 | 10/10 |
| Bend | 78 → unavailable | unavailable | +0.120 / +0.135 | unavailable |
| Irregular frontages | 85 → 2 | +0.136 / +0.118 | +0.139 / +0.107 | 10/10 |

Every straight extreme pair retained the original transverse contact count.
In the longest straight fixture, it still increased angular cost by 0.259
on average, while the bounded route-aware pair was almost indistinguishable
from the full sheaf by either mean. The parallel result in the taper is
stronger for angular cost. Shorter lines or lines with different
inclinations can therefore matter even when the two longest diagonals
touch every original transverse connection.

The curve loses 24 of 138 transverse contacts with the global pair.
Two overlapping local pairs retained 126 contacts and reduced the mean
metric penalty from 0.088 to 0.058. The bend had no global opposed pair
under the extent rule, but two local overlapping pairs preserved all hard
constraints and incurred mean changes of +0.098 metric and +0.123 angular.
The bend also admitted a valid route-aware two-line alternative, so local
pairs are useful as a geometric fallback, with a higher line count and
lower observed penalties than that particular two-line control.

## Preserved settlements

| Corridor | Certified / chosen A | Extreme pair | In A | B result | C extra lines |
|---|---:|---|---:|---|---:|
| Hill 1 | 7 / 1 | unavailable | — | no qualifying pair | — |
| Hill 2 | 18 / 2 | 479, 710 | 0 | valid | 0 |
| Hill 3 | 28 / 3 | 1278, 1281 | 0 | valid | 0 |
| Y 1 | 45 / 8 | 960, 1183 | 2 | valid | 0 |
| Y 2 | 67 / 8 | 437, 479 | 0 | five unattached doors | 2 |
| Y 3 | 78 / 5 | 965, 1130 | 0 | one unattached door | 1 |

Hill 2 improves the original corridor mean costs by 0.008 metric and 0.011
angular at equal count. Hill 3 removes one map line and improves mean
metric cost by 0.027, with about 0.001 extra angular units. Hill 1 starts
with just one in-band representative, so replacing it by a two-line
control increases count. All valid Hill variants preserve coverage of
266 regions, an independent winding rank of 11, and all 4,950 pairs.

Y 1 removes six of 70 lines. Its mean changes are +0.248 metric and
+0.049 angular. The route-aware pair at the same count performs somewhat
better (+0.198 / +0.048) and the local backward substitution performs
worse (+0.848 / +0.067). Y 2 preserves all 19 transverse contacts and
winding rank 3 with the extreme pair but loses fixed connectors at five
doors. Its four-line repair has mean changes of +0.360 metric and +0.010
angular. Y 3 preserves 21 transverse contacts but loses one doorway
attachment. Its three-line repair incurs +0.147 / +0.018. A different
valid two-line combination incurs +0.136 / +0.015. All repaired Y maps
cover all 267 required regions and restore all 4,851 pairs.

The failed Y 2 replacement disconnects 480 pairs. Its lost doorway
attachments are at buildings 43, 56, 63, 72 and 89. Among pairs that
remain reachable, the route between buildings 25 and 52 is affected
most on both measures, rising by 19.738 metric and 1.973 angular units.
Lines 649 and 873 restore reachability. In Y 3 the lost attachment
at building 22 accounts for 98 newly unreachable pairs, restored by
line 1126. The worst reachable metric and angular changes there are
buildings 5–23 (+5.345) and 5–27 (+2.676), respectively. These are
whole-network movements through the tested bands and their adjoining
streets. The route figures show the rerouting alongside the actual
transverse intersections.

## Interpretation

The rule supplies a small candidate shortlist in straight corridors and
sometimes recovers useful diagonals outside the selected map. It is
most useful as a geometrical proposal with independent coverage, winding,
attachment and route tests. Length and connectivity frequently choose
the same pair in straight grids, yet the route-aware controls show
that those choices can incur avoidable angular costs. Curvature and
bends justify testing overlapping local pairs. Taper and irregular
frontages justify retaining alternatives and checking junction movements
explicitly. The tests hold the exterior fixed and do not establish
simultaneous corridor replacements or optimality outside the shortlists.

## Data and figures

- [Comparison CSV](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/comparison.csv)
- [Candidate and frontage-contact inventory](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/sheaf-inventory.csv)
- [Straight 12× street](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/grid-12x-4-1.png)
- [Hill corridor 3](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/Hill-42-3.png) and [Y corridor 2](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/Y-42-2.png)
- [Overlapping curve pairs](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/curve-overlapping.png) and [overlapping bend pairs](diagnostics/preserved-axial-benchmark/extreme-diagonals/pilot-3/bend-overlapping.png)

Each case journal links to its versioned batch record, exact intervals,
doorway identities, constraints and worst affected pairs. Plots show the
complete in-band sheaf and selected lines, the extreme diagonals and repair
lines, their transverse intersections, and shortest paths for the largest
finite metric and angular deterioration. An X marks the two doors of one
newly unreachable pair where applicable. The same prefix identifies each
case and corridor's route JSON and image.

Run a named case with
`python -m experiments.extreme_diagonals CASE`, export its plots and rows
with `python -m experiments.extreme_diagonal_export CASE`, then combine the
case CSVs with `python -m experiments.extreme_diagonal_export --combine`.
Run `python -m experiments.extreme_diagonal_inventory` to create the
frontage inventory and local-pair figures. Set
`EXTREME_DIAGONAL_OUTPUT` to a fresh directory for a replay. The CLI
protects existing case journals and exports. The linked export renders
the same batch records with the shared connector stop shown on
shortest angular paths that change direction directly at that stop.

The final export contains 100 comparison rows, 635 sheaf inventory rows
and 16 verified figures. Recomputing costs from the illustrated path
coordinates reproduced all 24 plotted route differences. Sixteen targeted
tests passed.
