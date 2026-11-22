# Connectivity-first structural backbone: Y seed 42

## Question and inputs

This experiment tests whether growing a linear structure before convex
coverage preserves sampled obstacle-supported shortest-path tangents better
than coverage-first selection. It does not change the production axial
generator, previous selectors, or certified fixtures.

All maps use the same preserved Converging Valleys/Y seed-42 snapshot, 267
GEOS-constructed convex regions, 3,214 rational certified intervals, and the
saved graph of 412,106 exact intersections. The candidate graph, snapshot,
coverage data, settlement and saved selections are verified against the
manifest of the research archive whose SHA-256 is
`9128d543e2527588a3562ca2767f6b81de6daed9ecc412d8e376008c373bf3b7`.
The later independent visibility experiment is not in that older archive:
its graph, path records and backbone records are instead verified against
their previously recorded SHA-256 values. Candidate clearance and convex
coverage are checked again, and the 187 saved tangent-containment lists are
recomputed exactly against this pool.

The 187 segments were used in 42,436 ordered sampled journeys, with 245,126
journey-edge uses. The results here measure exact geometric containment, not
functional preservation of those journeys or angular routes.

## Rules

The full graph's candidate degrees are fixed once. The ranking is descending
degree, then descending exact squared interval length, then canonical rational
interval identity. It is not recalculated as the selected set changes.

For each accessible component, seed the highest-ranked candidate. Traverse
the ranking once; a candidate must intersect the already-selected network
in its component and make at least one of these measurable contributions:

1. Its closed neighborhood in the **full candidate graph** contains at least
   `T` candidates not yet in the selected network's neighborhood union.
2. Its endpoints expand an exact coordinate bounding-box extremum.
3. Its undirected direction occupies a previously absent one of 12 equal
   15-degree direction classes.
4. If it is a saved ring candidate and intersects at least two selected
   lines, exact face traversal shows it newly completes a required witness ring.

The one-pass connected-growth rule keeps each selected component connected;
it never first creates disconnected islands that would need a later bridge.
The rank gives long, highly connected lines early consideration, but no
convex-region coverage is consulted during growth. The direction class uses
floating-point `atan2` solely as a heuristic; clearance, intersections and
bounds use rational predicates. We tested `T = 33, 17, 9`, approximately
1%, 0.5% and 0.25% of the full pool, respectively. Growth stops after one
ranked pass, not after a prescribed line count.

After growth, the completion stage adds the candidate covering the largest
number of still-uncovered convex regions, using the fixed full-network
ranking for ties. Existing exact ring/connectivity repair is applied if
necessary. The reduction stage repeatedly tries single removals, followed by
bounded 2-for-1 and 3-for-2 searches. Each proposed result must cover all
regions, remain connected in each accessible component, preserve all three
exact witness rings and pass exact clearance. In addition, it must retain the
original backbone's entire closed-neighborhood union, coordinate extrema and
12-class direction set. Thus coverage alone cannot justify removal of a line.
This footprint is an aggregate proxy: it does **not** guarantee preservation
of each original corridor or tangent. Tangent containment is evaluated,
not constrained.

Each exchange mode examines at most 400 removal sets per search, with at most
30 full feasibility checks; candidate additions are limited to the first 30
ranked candidates for 2-for-1 and the first 10 for 3-for-2. When regions are
missing, considered additions must individually cover at least one missing
region. Each exchange mode has at most five accepted rounds. Both exchange
searches hit the removal-set bound in all three runs, so failure to find an
exchange is not evidence that none exists. The five-panel numbered map uses
the top 20 candidates only for illustration, not as a growth rule.

## Selection and tangent results

All rows have one connected line-network component and all three witness
rings; the backbone-only rows are not required to cover every convex region.
No ring or connection repair lines were needed after coverage completion.
Each listed 1-for-0 reduction is a single-line removal; no 2-for-1 or
3-for-2 exchange was accepted within the stated bounds.

| Map | Lines | Length | Regions | Line intersections | Tangents / 187 | Journey-edge uses | Top 10 tangents |
|---|---:|---:|---:|---:|---:|---:|---:|
| Unified greedy | 29 | 1,171.9 | 267 | 37 | 12 | 6.26% | 0 |
| Coverage-first connectivity | 29 | 1,454.8 | 267 | 72 | 5 | 0.63% | 0 |
| 1%, backbone | 41 | 2,367.7 | 242 | 300 | 10 | 3.78% | 0 |
| 1%, completed | 52 | 2,748.8 | 267 | 369 | 12 | 3.78% | 0 |
| 1%, reduced | 31 | 1,462.2 | 267 | 63 | 5 | 1.72% | 0 |
| 0.5%, backbone | 48 | 2,728.2 | 248 | 378 | 11 | 3.86% | 0 |
| 0.5%, completed | 57 | 3,050.7 | 267 | 428 | 13 | 3.87% | 0 |
| 0.5%, reduced | 31 | 1,460.1 | 267 | 63 | 5 | 1.72% | 0 |
| 0.25%, backbone | 59 | 3,216.4 | 254 | 523 | 11 | 3.86% | 0 |
| 0.25%, completed | 66 | 3,469.0 | 267 | 575 | 13 | 3.87% | 0 |
| 0.25%, reduced | 35 | 1,511.2 | 267 | 74 | 5 | 0.58% | 0 |

The 1%, 0.5%, and 0.25% initial backbones reached 3,034, 3,077, and 3,130
full-pool candidate neighborhoods, respectively. Completion added 11, 9,
and 7 coverage lines; reduction then removed 21, 26, and 31 lines,
respectively. The saved per-stage records identify every line and removal.
Both original maps contain 29 lines; final structural maps contain 31 or 35.
There is no matched-budget result, so differences cannot be attributed to
selection order independently of line count.

The 0.5% reduced map omits all ten most-used segments. For example, two
boundary-following segments at building 59's north-west corner, around
`(8.2, 86.6)` to `(12.8, 86.7)`, each occur in 18,402 sampled journeys. The
26-to-2 tangent near `(36.1, 65.5)` to `(44.9, 54.2)` occurs in 12,500.
Other heavily used omissions include segments around buildings 23 and 42 in
the southern branch. The diagnostic map shows their spatial distribution.

## Fixed-terminal segment-network comparison

The first 16-terminal/32-connector pilot had no occluded pair reachable in
every map. The expanded evaluation takes 32 deterministic, evenly indexed
points from the 204 saved spatial terminals. These yield 992 ordered pairs,
including 178 directly visible and 814 occluded pairs. It does not sample the
separately saved building-boundary terminals, and is not the full set of
42,436 visibility journeys.

Before any map is evaluated, up to 128 nearest exactly visible perpendicular
or endpoint connectors are fixed per terminal from the *full* 3,214-line
pool (4,003 connectors in total). A connector is available only when its
associated candidate survives in a particular map. Terminal connectors may
only be used at the beginning or end of a route; crossing connectors do not
create shortcuts. Directly visible pairs use their straight path regardless
of attachment availability. Other pairs require both terminals to have an
available connector and a connected route on the exactly noded selected
linework. A missing connector is reported separately from a network
disconnection. Metric edge lengths and angular costs are floating point; the
angular cost is the existing right-angle-normalised model.

The following means use the **same 502 occluded pairs** reachable in every
listed map. Metric detour is selected-network path length divided by the
saved continuous-visibility shortest-path length. Means do not imply that
metric and angular optima are the same routes. The final column counts
attachment-failure pairs out of all 992; no map had a network-disconnected
pair among attached terminals.

| Map | Mean metric detour | Mean angular depth | Attachment failures |
|---|---:|---:|---:|
| Unified greedy | 1.2227 | 4.6960 | 142 |
| Coverage-first connectivity | 1.1744 | 4.6534 | 168 |
| 1%, backbone | 1.2224 | 4.5607 | 106 |
| 1%, completed | 1.2054 | 4.4858 | 0 |
| 1%, reduced | 1.2681 | 4.7497 | 0 |
| 0.5%, backbone | 1.1888 | 4.2284 | 106 |
| 0.5%, completed | 1.1829 | 4.2284 | 0 |
| 0.5%, reduced | 1.2701 | 4.7452 | 0 |
| 0.25%, backbone | 1.1026 | 4.1460 | 46 |
| 0.25%, completed | 1.1003 | 4.1460 | 0 |
| 0.25%, reduced | 1.1922 | 4.6709 | 0 |

For the 0.5% reduced map, all 32 terminals have at least one surviving fixed
connector; its 992 pairs include 178 direct and 814 routed. Across its
reachable pairs, the mean and maximum detour are 1.2000 and 3.1711, and mean
and maximum angular depths are 3.9554 and 7.8801. These all-reachable means
include direct pairs and have different denominators for maps with attachment
failures; use the common-pair table for comparison.

The 0.5% reduced segment network has 187 nodes and 218 segments after
including connector stops; its 61 distinct line-intersection locations have
degree distribution `{2: 1, 4: 59, 6: 1}`. The two 29-line baselines have
37 and 68 distinct intersection locations, respectively. Full per-map node,
segment, intersection-degree, terminal and pair records are in the output.

## Interpretation and limitations

These tested structural-first rules did **not** improve tangent representation
over the unified greedy map. The 0.5% completed map represents more distinct
segments than greedy (13 versus 12), but a smaller weighted share (3.87%
versus 6.26%) while using 57 rather than 29 lines. After reduction it retains
only 5 segments and 1.72% of uses. The expanded fixed-terminal protocol did
attach all sampled terminals to the reduced structural map, but the
common-pair route results and the larger line count preclude a general
superiority claim.

Graph-neighborhood reach, bounding extrema and quantized directions are
proxies for corridor structure, not proofs of corridor continuity. A tiny
extremum expansion can admit a near-duplicate line, and a single ranked pass
does not reconsider a previously disconnected candidate after the selected
network grows. Preservation of this aggregate footprint can still discard a
specific important tangent, as the results demonstrate. Thresholds, endpoint
sampling, limited terminal connectors and bounded exchange searches all affect
the outcome. The domain is a GEOS overlay, so exact certification is relative
to that constructed geometry. Equal or nearly equal floating metric routes
remain subject to the visibility experiment's documented tolerance. No
global minimality, full sightline enumeration, metric-route completeness or
minimum-angular-route completeness is claimed.

## Reproduction

Set `ARCHIVE`, `SNAPSHOT`, `DATA`, `SELECTIONS`, and `VISIBILITY` to the
preserved files described in [the visibility report](./SHORTEST_PATH_VISIBILITY_RESULTS.md).
Set `OUT` to a nonexistent directory; the runner refuses to overwrite it.

```sh
MPLBACKEND=Agg .venv/bin/python -m experiments.connectivity_backbone \
  --archive "$ARCHIVE" --snapshot "$SNAPSHOT" --data-dir "$DATA" \
  --selection-dir "$SELECTIONS" --visibility-dir "$VISIBILITY" --output-dir "$OUT"
```

The output contains the three intermediate-stage records, full exact
candidate endpoints and selected-intersection provenance, fixed connector
points, per-pair results, a summary and two diagnostic figures. The
independently repeated pilot and expanded runs preserve the same selections
and are compared by the optional saved-input regression.

The headless regression suite passed 238 tests, with 3 skipped and the slow
default-Voronoi regeneration test deselected. It included the saved-graph
clearance audit and three comparisons of the independently repeated selection
stages. After adding a separate disconnected-network regression, all 10
focused structural tests passed. Pylance syntax requests timed out in this
environment.

The expanded run's `results.json.gz` SHA-256 is
`42a27781612440f6f20088b770f08e415d6ea2f4caf249befe751fbdb3743be5`.
