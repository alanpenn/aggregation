# Strict convex coverage and doorway-incidence repair

For this batch experiment, a convex region is covered when a selected
certified line traverses its interior over positive length. A doorway
has access when at least one such selected line traverses any of the
doorway's exact incident regions. The reusable line–region and
doorway–region tables come from the independently checked incidence
records. The coverage audit also evaluates the legacy rule, which
admits an exact touch or overlap with a region boundary.

The audit scans the preserved Hill 42 and Y 42 archive for explicit
selected sets, including benchmark selections, saved sheaf and
backward results, route-sparse maps and recorded marginal trials,
and extreme-diagonal replacements. Different records can refer to the
same geometry. Source records and candidate IDs are retained. Exact
interval identities link maps to the canonical fresh-exact pool.
The archive contains no selected intervals outside the two master
pools in this audit.

## Coverage audit

| Case | Saved map occurrences | Distinct selections | Occurrences with missing interior coverage | Occurrences with unattached doors |
|---|---:|---:|---:|---:|
| Hill 42 | 439 | 335 | 434 | 433 |
| Y 42 | 299 | 201 | 291 | 6 |

These inventories include deliberately invalid exploratory variants as
well as accepted maps. The per-map CSV distinguishes the source records,
old and new counts, uncovered regions, boundary-only regions and door
labels. Repair candidates are listed by certified line ID for every
omission. The versioned output retains their exact interval inventory
through the original candidate stage.

| Case and map | Legacy coverage | Strict coverage | Boundary-only regions | Unattached doors |
|---|---:|---:|---|---|
| Hill 42 entrance guided, 130 lines | 266/266 | 260/266 | 76, 161, 162, 213, 244, 265 | Building 40 |
| Hill 42 backward, 44 lines | 266/266 | 260/266 | 76, 161, 162, 213, 244, 265 | Building 40 |
| Y 42 entrance guided, 70 lines | 267/267 | 261/267 | 82, 92, 193, 200, 235, 258 | None |
| Y 42 backward, 37 lines | 267/267 | 259/267 | 82, 92, 193, 200, 235, 258, 264, 266 | None |

Hill building 40 has only region 162 in its saved incidence set. All 61
certified lines that traverse region 162 are legitimate eligibility
candidates for the doorway. They still need to be tested in the full
selected network. Hill regions 76 and 265 and Y region 82 each have
only one certified traversing line in their respective full pools.
Those lines are mandatory under strict coverage.

## Repair and reduction procedure

The addition rules first maximise the number of currently missing
regions repaired. They break ties by maximal length or by the number of
connections to the current exterior, respectively. The route-aware rule
also constructs alternatives by forcing each shortlisted candidate,
using the top three candidates per missing region or unattached doorway
under each geometric ranking. It compares complete all-pair angular
costs for the valid options. The first Hill searches found no valid
unbridged repair in that shortlist. The bridged experiment joins
isolated repair components by a shortest chain of certified axial
intersections before validation. It preserves the original failed
attempts as separate records.

The substitution window consists of the six shortest original lines.
The experiment tries removing one or two of them after the route-aware
addition, with the candidate additions held in the map. It retains the
lowest-count valid substitution with the best angular mean at that
count. Backward reduction starts from that repair when available
and tests three deletion orders. Each removal must preserve exact
clearance, strict coverage, a connected axial network, full independent
circulation rank and every doorway's incidence set. The retained
selections also undergo an uncached topology validation. The fewest
observed lines are bounded-search results.

Angular routing uses the independently verified directed exact atomic
network, free axial-line entry and exit, and no geometric doorway
connectors. Every retained map is checked on all 4,950 Hill or 4,851
Y pairs and against its full-pool baseline. Its metric results separately
use the fixed certified geometric connectors. Changes in metric cost
are matched on pairs reachable in both maps and losses of reachability
are counted explicitly. A second backward control starts from the
route-aware addition and also requires all geometric connector
attachments to survive. This control separates low angular-reachable
line counts from maps that serve every pair on both measures.

Angular monotonicity allows numerical error of
`1e-8 + 1e-9 × max(abs(full), abs(subset))`. The saved incidence
memberships and segment intersection positions use exact rational
geometry.

## Repair choices and observed route performance

All of the following means use matched pairs where appropriate. Incidence
angular depth is in 90° turn units. Metric changes are in settlement
coordinate units. A negative metric change means that routes were
shorter on pairs reachable in both maps.

| Start and method | Lines | Angular mean | Median | P95 | Maximum | Mean excess over full pool | Mean metric change | Newly unreachable metric pairs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hill 130, longest-first additions | 136 | 1.332 | 1.170 | 3.291 | 4.335 | 0.803 | −0.266 | 0 |
| Hill 130, connectivity-first additions | 136 | 0.903 | 0.878 | 2.280 | 3.143 | 0.374 | −3.646 | 0 |
| Hill 130, route-aware additions | 136 | 0.903 | 0.878 | 2.280 | 3.143 | 0.374 | −3.646 | 0 |
| Hill 130, bounded substitution | 134 | 0.903 | 0.878 | 2.280 | 3.143 | 0.374 | −3.627 | 0 |
| Hill 130, lowest-connectivity strict backward | 40 | 1.028 | 0.957 | 2.420 | 3.193 | 0.499 | +1.606 | 99 |
| Hill 44, longest-first additions | 50 | 1.540 | 1.403 | 3.556 | 5.056 | 1.011 | −0.476 | 0 |
| Hill 44, connectivity-first additions | 50 | 1.161 | 1.177 | 2.684 | 3.337 | 0.632 | −4.900 | 0 |
| Hill 44, route-aware additions | 50 | 1.161 | 1.177 | 2.684 | 3.337 | 0.632 | −4.900 | 0 |
| Hill 44, bounded substitution | 48 | 1.161 | 1.177 | 2.684 | 3.337 | 0.632 | −4.809 | 0 |
| Hill 44, strict backward | 40 | 1.176 | 1.177 | 2.684 | 3.337 | 0.647 | −2.965 | 0 |
| Y 37, longest-first additions | 42 | 0.660 | 0.491 | 2.481 | 4.361 | 0.278 | −0.095 | 0 |
| Y 37, connectivity-first additions | 42 | 0.663 | 0.494 | 2.489 | 4.361 | 0.281 | −0.447 | 0 |
| Y 37, route-aware additions | 42 | 0.658 | 0.457 | 2.481 | 4.361 | 0.276 | −0.556 | 0 |
| Y 37, shortest-first strict backward | 29 | 0.709 | 0.532 | 2.601 | 4.361 | 0.327 | +4.094 | 2,295 |
| Y 37, strict backward with geometric reachability | 40 | 0.658 | 0.457 | 2.481 | 4.361 | 0.276 | −0.553 | 0 |

From the 44-line Hill start, the longest-first repair selects line 744
for region 162. The connectivity and route-aware choices use line 983
instead. The route-aware repair also adds lines 594, 1236, 1303, 1342
and 1346. Line 983 covers both 161 and 162. Lines 1236, 1303, 1342
and 1346 supply regions 213, 244, 265 and 76, respectively. All three
strict deletion orders from the Hill 44-based substitution finish
at the same 40-line set.

From the 130-line Hill start, the route-aware and connectivity-first
repairs select line 1000 for region 162. The route-aware repair also
adds lines 594, 1236, 1302, 1342 and 1346. The lowest-connectivity
deletion order retains all six additions. Its 40-line map has lower
mean angular depth than the 40-line map from the 44-line start, and
loses 99 geometric metric pairs. Both reach all 4,950 angular pairs
with winding rank 11. The longest-first deletion order stops at 59
lines from the 130-line start.

The route-aware Y repairs use 657 for region 82, 761 for 92,
1337 for 193 and 200, 1574 for 235 and 1644 for 258, 264 and 266.
The 29-line Y map retains complete incidence-angular access and
winding rank 3. The 40-line metric control retains all geometric
doorway routes as well. The finite-pair metric deterioration of the
29-line map describes only the surviving routes.

The audit also finds older exact-greedy maps with full strict coverage.
Hill's 42-line exact-greedy map had archived winding rank 5 of 11.
Y's 29-line exact-greedy map had rank 3 of 3 and an archived geometric
reachability failure. These examples illustrate why a coverage count
must be accompanied by circulation and separately labelled access checks.

## Batch validation implications

The archived 44-line Hill and 37-line Y maps remain historical results
under the legacy rule. Both fail the revised strict coverage check.
The Hill repair reaches 40 lines with both kinds of reachability.
Across the 4,851 pairs already reachable under the old Hill incidence
map, its mean angular depth falls by 0.474. It also restores all 99
pairs involving building 40. Y reaches 29 lines for incidence-angular
analysis and 40 with complete geometric metric reachability. These
counts apply to the tested seeds and deletion orders.

For future batch comparisons, use exact positive interior traversal,
nonempty doorway-incidence sets, exact clearance, one connected axial
network and full independent winding rank as mandatory gates. Verify
all-pair angular reachability and compare subsets with the full pool
on the same doorway pairs. Report geometric metric reachability
separately and require it explicitly when the experiment calls for
a map that serves both kinds of movement. Preserve old coverage
results as legacy fields so the policy behind each result remains
clear.

## Exports and replay

- [All archived coverage comparisons](diagnostics/preserved-axial-benchmark/strict-coverage/pilot-2/audit.csv)
- [Eligible repair lines for each missing region and doorway](diagnostics/preserved-axial-benchmark/strict-coverage/pilot-2/repair-candidates.csv)
- [Repair and backward-reduction route distributions](diagnostics/preserved-axial-benchmark/strict-coverage/pilot-2/repairs.csv)

Every case journal links to its batch record, including the exact
selection IDs and raw angular and metric arrays. A fresh replay starts
with the audit and the A or B repair stage. The metric-aware B control
reads the corresponding repair record in the same directory.
A supplemental pass-based restart of the slow 130-line experiment
was interrupted after the primary three-order run completed. The
reported results use the completed primary run.

```bash
.venv/bin/python -m experiments.strict_coverage --output PATH Hill-42 audit
.venv/bin/python -m experiments.strict_coverage --output PATH Hill-42 A
.venv/bin/python -m experiments.strict_coverage --output PATH Hill-42 B
.venv/bin/python -m experiments.strict_coverage --output PATH Hill-42 Bmetric
.venv/bin/python -m experiments.strict_coverage --output PATH Y-42 audit
.venv/bin/python -m experiments.strict_coverage --output PATH Y-42 B
.venv/bin/python -m experiments.strict_coverage --output PATH Y-42 Bmetric
.venv/bin/python -m experiments.strict_coverage --output PATH export
```
