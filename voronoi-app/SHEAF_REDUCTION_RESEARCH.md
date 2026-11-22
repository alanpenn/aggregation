# Sheaf-aware reduction on preserved Y 42 and Hill 42

This experiment branches from the validated projected-face entrance-guided
maps. It uses the existing certified candidate pools, settlement geometry
and doorway connectors. It registers diagnostics and reduction as independent
versioned batch methods and preserves the earlier records. The initial
numbered diagnostics were saved before the reduction began. The completed
Y analysis uses the archived version-2 method, and the Hill comparison
uses the independently checkpointed version-5 method. Their differences
are in reuse of exact validation inputs and scheduling, with unchanged
validation rules. Earlier interrupted attempts were retained.

## Detection and comparison protocol

A proposed sheaf uses selected lines at least 22 canvas units long. Pair
screening requires a direction difference of at most 21°, at least 48%
overlap along the longer line's axis, an average perpendicular separation
of at most three units within the overlap, at least 25% Jaccard similarity
of convex visibility-region sets, and at least 22% Jaccard similarity of
connections outside the pair's provisional spatial neighbourhood.
Deterministic complete-link grouping avoids drifting through a chain of
nearby lines. These are exploratory thresholds for the preserved 100-unit
canvases. Internal and external intersections below count pairs of lines.
The archived diagnostics contain each member's length, degree, unique
covered regions and unique outside connections, pairwise similarity values,
and the exact witness rings they support.

Every reduction uses full visibility coverage, one connected exact line
graph, exact clearance, full independent winding rank, and an attachment
for every valid saved doorway. In a connected line graph, a certified
attachment for every doorway gives complete pair reachability. Necessary
coverage, connectivity, and attachment checks precede the exact topology
validator on surviving proposals. The same checks apply to all deletion
orders and exchanges.

The five backward orders rescan after each accepted deletion and stop at
a single-deletion local minimum. Sheaves of up to five live lines use
complete subset enumeration. The larger sheaf is tested with up to 36
ranked removals of one to three lines per visit. There are at most two
passes over the sheaves, with each proposed subset evaluated in the current
whole map. The full-pool exchange phase tests up to six alternatives per
sheaf, removing up to three original members per proposal, under a
72-trial budget distributed over the detected sheaves. The objective is
fewer lines, then shorter total length, with canonical ordering breaking
ties. These are bounded results and do not provide a global minimum proof.

For route evaluation, the origins, destinations, and exact connectors
were fixed by the benchmark measures record. Doorway topological depth
counts changes of axial line. Metric paths include the lengths of the
two doorway connectors and traverse the noded axial lines. Angular paths
include connector turns and use units of 90°. Both route measures use
the same connector choices wherever their lines survive. They require
axial-network travel, with no free-space bypass between terminals. The
reported pairs are the 4,950 on Hill and 4,851 on Y from the valid saved
doorways.

## Initial bundles

| Settlement | Sheaf | Original pool IDs | Regions (shared) | Internal edges | External edges | Winding witness blocks |
|---|---|---|---:|---:|---:|---|
| Hill 42 | S1 | 360, 358, 472, 1179, 1259, 373 | 38 (38) | 15 | 137 | internal-0, internal-1, internal-10, internal-2 |
| Hill 42 | S2 | 557, 480, 878 | 43 (28) | 3 | 76 | internal-0, internal-1 |
| Hill 42 | S3 | 5, 594 | 35 (17) | 0 | 19 | internal-0, internal-7 |
| Hill 42 | S4 | 109, 671 | 39 (38) | 1 | 38 | internal-0, internal-3, internal-4, internal-6, internal-7 |
| Hill 42 | S5 | 910, 933 | 27 (21) | 1 | 37 | internal-1, internal-2 |
| Hill 42 | S6 | 353, 736 | 30 (30) | 1 | 24 | internal-0, internal-2, internal-8 |
| Hill 42 | S7 | 277, 742 | 28 (28) | 1 | 28 | internal-0, internal-2, internal-8 |
| Hill 42 | S8 | 477, 484 | 23 (23) | 1 | 49 | internal-0, internal-2 |
| Y 42 | S1 | 140, 130, 813, 670, 844 | 58 (58) | 7 | 90 | internal-0 |
| Y 42 | S2 | 917, 490, 1045, 926 | 58 (51) | 5 | 106 | None |
| Y 42 | S3 | 534, 1567, 1565 | 38 (34) | 2 | 72 | internal-0 |
| Y 42 | S4 | 589, 1270 | 57 (57) | 1 | 50 | internal-0 |
| Y 42 | S5 | 507, 506 | 57 (37) | 1 | 55 | internal-0 |
| Y 42 | S6 | 1515, 1092 | 47 (45) | 1 | 48 | internal-0 |
| Y 42 | S7 | 1391, 1292 | 33 (22) | 1 | 19 | internal-0 |

Y has three qualifying groups of at least three lines. Hill has two,
with six smaller pairs. This is the grouping returned by the stated
thresholds, rather than a count of distinct physical corridors.

## Backward order comparison

| Settlement | Order | Lines | Total length | Mean doorway line changes | Mean metric cost | Mean angular cost | Search seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| Hill 42 | shortest | 44 | 1472.26 | 2.422 | 59.979 | 3.961 | 680.9 |
| Hill 42 | longest | 69 | 1438.18 | 5.010 | 63.717 | 5.957 | 439.4 |
| Hill 42 | lowest-connectivity | 44 | 1467.12 | 2.424 | 60.239 | 3.985 | 618.7 |
| Hill 42 | marginal-external | 45 | 1486.15 | 2.432 | 59.795 | 3.964 | 567.8 |
| Hill 42 | geometry | 63 | 1565.97 | 4.304 | 65.005 | 5.904 | 667.4 |
| Y 42 | shortest | 37 | 1456.88 | 1.646 | 67.651 | 3.390 | 63.1 |
| Y 42 | longest | 41 | 1239.29 | 3.625 | 74.388 | 5.173 | 57.7 |
| Y 42 | lowest-connectivity | 37 | 1431.50 | 1.617 | 67.540 | 3.356 | 82.5 |
| Y 42 | marginal-external | 37 | 1402.73 | 1.736 | 67.687 | 3.388 | 59.4 |
| Y 42 | geometry | 40 | 1294.59 | 2.182 | 70.697 | 3.999 | 88.8 |

All ten outcomes preserve full winding rank, coverage, connectivity,
and entrance reachability. The archived order records include exact
retained interval identities and the order of accepted deletions.

## Strategy comparison

A is the original map. B is the best backward order. C searches only within
sheaves. D follows C with the best backward order from B. E starts at D
and tests full-pool replacements. Route evaluations are timed separately
in the CSV. B shows the search time of its winning order, rather than
the cost of running all five. Hill orders ran in parallel.

| Settlement | Strategy | Lines | Length | Winding rank | Mean axial depth | Mean doorway changes | Mean metric cost | Mean angular cost | Search seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hill 42 | A | 130 | 3076.28 | 11 | 3.813 | 2.138 | 54.609 | 3.465 | 0.0 |
| Hill 42 | B | 44 | 1467.12 | 11 | 4.020 | 2.424 | 60.239 | 3.985 | 618.7 |
| Hill 42 | C | 113 | 2278.40 | 11 | 5.715 | 3.668 | 56.953 | 4.758 | 124.1 |
| Hill 42 | D | 54 | 1452.66 | 11 | 5.743 | 4.076 | 68.280 | 5.472 | 335.9 |
| Hill 42 | E | 54 | 1451.36 | 11 | 5.743 | 4.076 | 68.310 | 5.469 | 339.0 |
| Y 42 | A | 70 | 2527.25 | 3 | 3.051 | 1.500 | 62.678 | 3.065 | 0.0 |
| Y 42 | B | 37 | 1402.73 | 3 | 3.566 | 1.736 | 67.687 | 3.388 | 59.4 |
| Y 42 | C | 53 | 1514.14 | 3 | 3.866 | 2.000 | 66.423 | 3.460 | 46.4 |
| Y 42 | D | 38 | 1272.41 | 3 | 3.923 | 2.004 | 66.917 | 3.518 | 67.2 |
| Y 42 | E | 38 | 1272.00 | 3 | 3.923 | 2.004 | 66.892 | 3.516 | 68.0 |

All A–E outcomes retain the original coverage, one connected graph, and
complete reachability among valid doorways. The original exact validator
independently confirmed clearance and full winding rank for every distinct
A–E result. Candidate enumeration reversal reproduced both complete
canonical diagnostics. Targeted tests passed 14 checks.

## Findings

- **Hill 42.** Sheaf-only search removed 17 of 21 detected sheaf lines. In the best backward result, 12 of 86 deletions came from sheaves. The five orders gave 5 distinct selections. The E substitutions by original pool ID were [([736], [737])]. B compared with A increased mean metric cost by 10.3% and mean angular cost by 15.0%.
- **Y 42.** Sheaf-only search removed 17 of 20 detected sheaf lines. In the best backward result, 14 of 33 deletions came from sheaves. The five orders gave 5 distinct selections. The E substitutions by original pool ID were [([1391], [1301])]. B compared with A increased mean metric cost by 8.0% and mean angular cost by 10.5%.

Geometric sheaves contain substantial removable redundancy on both fixtures.
Redundancy also extends outside the detected groups, particularly on Hill.
Different starting deletions and sheaf-first decisions lead to different
local minima. Here the best global backward order uses fewer lines than
either sheaf-first sequence. Each bounded exchange saves some length
without reducing count. Shorter total line length can come at a routing
cost. The number of lines is an insufficient proxy for preserving metric
and angular route quality. Both fixtures show these effects, with a much
wider spread of backward outcomes on Hill. No generalisation beyond the
two preserved cases is established.

[CSV with strategy and per-pair change summaries](diagnostics/preserved-axial-benchmark/sheaf-experiments/hill-y-comparison/comparison.csv)
 · [Checkpoint and batch record IDs](diagnostics/preserved-axial-benchmark/sheaf-experiments/hill-y-comparison/cases.json)
