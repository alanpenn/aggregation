# Hill angular-fidelity selection experiment

This is a separate bounded experiment, not a change to the production
generator, selector or certified fixtures. It compresses the **given** candidate
network; it does not prove that the pool contains every possible sightline.

## Model and certification

For each exact candidate interval `i`, choose `x[i]` in `{0, 1}` and minimise
`sum(x[i])`, subject to:

* Each of the 268 convex regions is entered by at least one selected line;
  boundary-only contact is not coverage.
* Selected lines form one exact intersection-connected network in each of the
  three accessible components, with no cross-component connection.
* Each of the 11 occupied-hole witness points required by the existing
  algorithm lies in a bounded face of the selected exact linework. These are
  specified witnesses, not every cycle in the full network.
* Every fixed attachment line is selected. For each tested ordered pair in the
  same component, its directional angular depth must not exceed the full
  reference depth plus `epsilon`; pairs unreachable in the reference must
  remain unreachable. Turns, including connector headings when present, cost
  deflection divided by a right angle.

This is a formulation, not an optimality certificate. The 54 distinct fixed
attachment lines give a valid lower bound of 54 lines. The best feasible results
below give upper bounds of 365 or 362. No integer-programming bound or global
minimum was established.

The pool combines 1,372 baseline exact intervals and 2,104 boundary-endpoint
intervals; 866 overlap, yielding **2,610 distinct intervals** (1,238 new).
Unoriented rational endpoints define identity. The prepared records retain the
complete original baseline records plus all boundary supports and vertex
contacts, including duplicate-interval provenance. All 2,610 were checked
against the original occupied polygons, the occupied union and accessible
complement using exact rational predicates. The coordinates being certified are
the rational representations of the source binary64 values; the accessible
union/difference and convex regions are GEOS-constructed, not an independently
exact polygon overlay. Float display coordinates are not clearance certificates.

The full pool contains 2,585, 15 and 10 lines in the three components. Its
exact noding has approximately 176,069 nodes and 707,546 directed segment
states before adding terminal points. An outward-rounded spatial-index filter
is followed by exact rational intersections. Sparse directional routing uses
the same turn convention as `AngularNetwork`; it was differentially tested
against that implementation, including collinear overlaps and unreachable
pairs. No float-based `AngularNetwork` clearance check was used as certification.

## Fixed terminals and search

The 56 reproducible samples comprise the previous 36 Hill selected-line
midpoints, 16 additional main-component candidate midpoints distributed across
nonempty bins of a 4-by-4 spatial grid, and two points in each isolated
component. All 56 are distinct and lie on the full candidate network, so their
fixed connectors have zero length. Their exact positions, attachment points,
candidate IDs and component IDs are saved in the prepared data. The 36 original
positions are retained even where their original live line is not in the exact
pool: their fixed attachment is an exact candidate containing that point.
Attachments are never recomputed during selection; their lines are pinned.
There are `52*51 + 2*1 + 2*1 = 2,656` within-component ordered pairs.
All are reachable in the full reference network.

The initial feasible network is built from shortest-path witness lines, a
sufficient ring seed and coverage/connectivity repair. Ring-seed lines are
not mandatory: trial removals are accepted only after checking coverage,
component connectivity, the 11 witnesses and every angular pair. Two deterministic
removal orders were tried, with four removal attempts each for the two searches
that supplied the best results. The path-witness search also explored turn
penalties of `0.00001`, `0.001` and `0.01` solely as heuristics to find smaller
seeds; all reported angular depths were subsequently recomputed **without**
the penalty. Shortest-path witness counts were 881 for the unpenalised reference
and 379, 363 and 361 for the respective heuristic searches.

All angular comparisons use binary64 angles. An explicit `1e-10` absolute
numerical slack is applied to the bound, including at `epsilon=0`; this is not
a proof of equality over exact real-valued angles. Geometry and line identity
remain rational.

## Empirical results

The best validated subset from all searches was reused wherever its measured
maximum error met the requested tolerance. Thus this table is an empirical
complexity–fidelity curve, **not** a proven Pareto frontier. The chosen-source
times are the combined time of both removal orders in the search that produced
the chosen subset, not independent runtimes for every row.

| ε | Lines | Total length | Convex coverage | Components | Witnesses | Mean increase | Max increase | Increased pairs | Chosen-source search |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 365 | 14,698.0684 | 268/268 | 3/3 | 11/11 | 1.83e-16 | 2.66e-15 | 0 | 53.1 s |
| 0.02 | 365 | 14,698.0684 | 268/268 | 3/3 | 11/11 | 1.83e-16 | 2.66e-15 | 0 | 53.1 s |
| 0.05 | 362 | 14,122.1256 | 268/268 | 3/3 | 11/11 | 0.000364 | 0.033761 | 30 | 51.6 s |
| 0.10 | 362 | 14,122.1256 | 268/268 | 3/3 | 11/11 | 0.000364 | 0.033761 | 30 | 51.6 s |
| 0.20 | 362 | 14,122.1256 | 268/268 | 3/3 | 11/11 | 0.000364 | 0.033761 | 30 | 51.6 s |
| 0.50 | 362 | 14,122.1256 | 268/268 | 3/3 | 11/11 | 0.000364 | 0.033761 | 30 | 51.6 s |

An increased pair means an increase greater than `1e-10`. All rows are
**feasible bounded-search results**, not locally optimal or globally optimal.
The 365-line result has 362, 2 and 1 lines in the respective components; the
362-line result has 359, 2 and 1. The largest increase for the latter occurs,
among other ties, for ordered pairs `(17, 25)`, `(25, 31)` and `(31, 25)`,
using zero-based saved sample IDs. Sample 25 is approximately
`(52.528699, 85.633173)`. Full-reference routing took 28.7 s; each penalised
reference search took approximately 29–30 s. Preparation took approximately
29.4 s after the saved inputs existed. The full unpenalised six-tolerance
search took about 665 s for its removal-order trials; these timings are
single-run measurements, not benchmarks.

## Corridor interpretation

The 21.0679-unit building 9/19–2 corridor line is in the combined exact pool
(baseline ID 555); the 19.1286-unit exact interval corresponding to the
previous live candidate 588 is baseline ID 592. Neither appears in either
reported subset. Both can be absent while the fixed samples, all regions,
components and required ring witnesses meet the reported constraints. The
unpenalised full-network shortest-path witnesses also omit each one, so
removing either from that full reference preserves all tested angular depths
within the numerical comparison: these samples show no individual full-network
angular contribution for either line. This does not contradict the earlier
improvement from adding candidate 588 to a much smaller 41-line reference,
and does not establish that either corridor line is insignificant for other
origins, destinations or representations.

## Validation and replay

For both selected subsets, a separate replay rechecked exact clearance against
the original occupied polygons and constructed domain, recomputed all 268
region intersections, verified the three connected components and all 11 ring
witnesses, and recalculated all 2,656 fixed-pair depths. Eight predetermined
ordered pairs, including the worst affected pairs and one in each isolated
component, were independently checked with the existing NetworkX
`AngularNetwork`. The focused and related
regressions passed: 130 passed, 1 skipped, 1 deselected. The skipped Hill full
live regeneration is opt-in; the deselected default Voronoi full run was not
repeated here.

The saved data directory contains the original Hill geometry and historical
selection (`hill42-corridor-pool.json`), exact baseline
(`hill42-fresh-exact-baseline.json`) and boundary audit (`boundary-hill42.json`).
These inputs and the prepared candidate/attachment records, detailed per-pair
results and four figures are supplied as experiment artifacts, not fixtures.
With that directory at `DATA`, reproduce the main steps from the app root:

```sh
.venv/bin/python experiments/angular_hill_prepare.py --data-dir "$DATA"
.venv/bin/python experiments/angular_hill_reference.py --data-dir "$DATA"
.venv/bin/python experiments/angular_hill_reference.py --data-dir "$DATA" --witness-turn-penalty 0.001 --output angular-hill-heuristic-medium.json
.venv/bin/python experiments/angular_hill_reference.py --data-dir "$DATA" --witness-turn-penalty 0.01 --output angular-hill-heuristic-coarse.json
.venv/bin/python experiments/angular_hill_solve.py --data-dir "$DATA" --heuristic --heuristic-input angular-hill-heuristic-medium.json --attempts 4 --epsilon 0.02 --output angular-hill-medium-results.json
.venv/bin/python experiments/angular_hill_solve.py --data-dir "$DATA" --heuristic --heuristic-input angular-hill-heuristic-coarse.json --attempts 4 --epsilon 0.5 --output angular-hill-coarse-results.json
.venv/bin/python experiments/angular_hill_combine.py --data-dir "$DATA" --inputs angular-hill-medium-results.json angular-hill-coarse-results.json
.venv/bin/python experiments/angular_hill_validate.py --data-dir "$DATA"
.venv/bin/python experiments/angular_hill_plots.py --data-dir "$DATA"
```

The combined inputs above suffice to reproduce the reported best subsets;
additional saved runs document the alternative seeds and original sweep.
Next experiments should use more independent terminal sets, larger removal or
exchange budgets, and rigorous optimisation bounds. Neither convex coverage,
fixed-sample angular fidelity, candidate completeness nor minimality follows
from the others.
