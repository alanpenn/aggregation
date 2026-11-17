# Y-settlement tangent and exchange experiment

This is an experimental analysis of the saved Converging Valleys, seed-42
diagnostic, not the separate Hill settlement. Its regenerated cell geometry,
100 occupied cells and paired open cells match the snapshot. Displayed building
labels 1, 50, 49, 54 and 23 correspond to occupied cell IDs 251, 370, 317,
363 and 271 respectively. The saved snapshot does not contain a selected map;
the live convex-coverage selector was replayed from its candidates and hole
edges, producing 32 lines. This is a replay, not an inspection of a running
Streamlit session.

The original occupied-polygon coordinates are treated as exact binary64
rationals. Clearance tests include original polygons, the occupied union and
the accessible-domain complement. The union, complement and convex regions
are constructed by GEOS, not independently exact polygon overlays.

## Tangents

Exact IDs below refer to the preserved Y pool, not displayed building labels
or live candidate IDs. The live column identifies candidates by a collinear
original support, not equality of rounded interval endpoints. None of the live
matches was selected in the 32-line replay.

| Displayed buildings | Exact ID | Length | Limiting building labels | Exact intersections with combined pool | Live support ID | Boundary-endpoint pool |
|---|---:|---:|---|---:|---:|---|
| 1–50 | 1183 | 66.8146 | 10, 94 | 810 | 597 | No |
| 49–54 | 1391 | 24.1516 | 12, 61 | 109 | 727 | No |
| 49–54 | 1392 | 18.9813 | 12, shared 54/71 | 102 | Absent | Yes |
| 49–23 | 1303 | 45.2595 | 76, 8 | 424 | 730 | No |

All four exact maximal intervals are clear and in the 1,651-line exact pool.
For each pair the other mutually supporting original convex-vertex pairs are
obstructed by occupied interiors: respectively three, two and three pairs.
This only enumerates direct mutual vertex supports; other lines associated with
the neighbourhood need not touch both named buildings.

The live generator omits 1392 because its shared 54/71 vertex is not an
occluding corner of the accessible-union boundary, even though the original
building vertices support an exact-clear interval. It was not recorded as an
ambiguous live clipping pair. Lines 597, 727 and 730 were available, but not
chosen by the coverage greedy phase: the 112 ring seeds already covered 206 of
267 regions, leaving initial new-region gains of 0, 0 and 8 respectively.
Seven additional candidates completed coverage. The selector subsequently
reconsiders removals, but does not generally add a line solely to replace
several selected lines. Its primary greedy score is newly covered regions;
length is a tie-breaker, not an intrinsic preference for short lines.

The stored floating-point intervals for 727 and 730 fail exact
occupied-interior clearance when their rounded endpoints are interpreted as
rationals, even though their original supports reconstruct clear rational
intervals. Candidate 597's stored interval passed this exact clearance check.
This is a representation discrepancy, not evidence that the rational
intervals are invalid. In the 32-line live replay, 26 stored float intervals
failed the exact domain/occupied clearance test; this does not by itself
characterise the magnitude or cause of each discrepancy.

## Fixed-terminal exchanges

The exact pool and boundary-endpoint pool combine to 3,214 distinct rational
intervals, including 1,563 not in the exact baseline. All were checked for
exact clearance. The 52 fixed samples comprise the preserved 36 Y sample
positions plus 16 distributed candidate midpoints; each sample was attached
once to the full pool and its attachment line pinned. There are 51 distinct
pinned lines and 2,652 ordered pairs. The 32-line live map cannot meet this
pinning requirement, and the previous Hill attachments cannot be reused:
13 of those sample locations are inside buildings in this settlement and 43
of their 54 pinned lines fail exact clearance here. The fixed-terminal result
therefore does **not** establish a 2-for-1 exchange from the live 32-line map.

The full combined network supplies the unpenalised angular reference.
Deflection costs use the existing normalised right-angle convention, with
`epsilon = 0.05` and numerical comparison slack `1e-10`. A penalised path
search supplied only a seed; all feasibility comparisons were unpenalised.
The feasible initial experimental map had 463 lines.

The first exchange removes exact lines 43 and 1389, lengths 17.8366 and
26.7449, and adds candidate 1391, length 24.1516. It is not longer than both
removed lines. It reduces the experimental map from 463 to 462 lines, total
length from 19,142.6085 to 19,122.1786, and exact line-intersection graph
edges from 16,129 to 16,096. Coverage remains 267/267, all three specified
ring witnesses survive, and the selected network remains connected. The
maximum angular-depth increase relative to the full reference is
`3.56e-15` (zero pairs increased by more than `1e-10`).

The next exchange removes 1391 and 45 and adds 1392, again satisfying the
same checks. In the seventh exchange, 1303 is removed together with 1392
and 1391 is added: the maximum increase becomes 0.013681 and 72 ordered
pairs increase. Candidate 1183 remains selected; no exchange introducing it
was evaluated because it was already selected in the experimental seed.

The bounded search accepted 26 two-for-one exchanges in 28 attempts, including
two involving other candidates (506 and 1817). Its final 437-line network has
length 18,432.4412 and 15,245 exact intersection edges; all 267 regions,
one component and three ring witnesses are retained. Across all 2,652 pairs
the mean increase is 0.0004762, the maximum 0.042884 and 158 pairs increase
by more than `1e-10`. Recalculation confirmed exact clearance and region
coverage. The search repeatedly exchanges 1391 and 1392 while removing
other lines; each accepted step strictly reduces the count. It is bounded,
not an exhaustive search, a proof of local optimality, or a global minimum.
Three-for-two exchanges are implemented and covered by deterministic tests,
but were not reached in this particular bounded run.

Starting from that 437-line result, a separate bounded revisit of 49–23
replaces lines 1024 and 1204 (lengths 39.5162 and 37.8107) with line 1303
(45.2595). The resulting 436-line experimental map has total length
18,400.3738 and 15,192 exact intersection edges. All 267 regions, the
connected component and three specified ring witnesses remain; every selected
line is recertified against the occupied polygons and constructed domain.
The maximum angular increase is 0.042884, the mean is 0.0001048, and 88
ordered pairs increase by more than `1e-10`, relative to the full reference.
This exchange was found in the first attempt of the separate revisit, not in
the 32-line live map.

The pair overlays show the 32-line live replay in green and exact candidate
directions in orange; these overlays are not asserted to be feasible exchanges
of that live map. Separate 49–54 and 49–23 before/after figures show the
fixed-terminal exchanges. Results and figures are saved in the separate
experiment data directory; they are not certified fixtures or Git-tracked
artifacts.

## Reproduction

Use the raw Y diagnostic snapshot preserved with the research archive. `DATA`
must name a **new** directory; output files are created exclusively.

```sh
SNAPSHOT=/path/to/axial-648f8da1364449a6aa70fd24038eea21.json
DATA=/path/to/new-valley-exchange-directory
.venv/bin/python -m experiments.valley_exchange_prepare --snapshot "$SNAPSHOT" --output-dir "$DATA"
.venv/bin/python -m experiments.valley_exchange_network --snapshot "$SNAPSHOT" --data-dir "$DATA" --reference tests/fixtures/exact_y/exact-y-24-forced-reference.json
.venv/bin/python -m experiments.valley_exchange_live --snapshot "$SNAPSHOT" --data-dir "$DATA"
.venv/bin/python -m experiments.valley_exchange_reference --data-dir "$DATA"
.venv/bin/python -m experiments.valley_exchange_reference --data-dir "$DATA" --turn-penalty 0.001 --output heuristic.json
.venv/bin/python -m experiments.valley_exchange_solve --snapshot "$SNAPSHOT" --data-dir "$DATA" --epsilon 0.05 --attempts 30
.venv/bin/python -m experiments.valley_exchange_solve --snapshot "$SNAPSHOT" --data-dir "$DATA" --epsilon 0.05 --revisit-pair 49-23 --attempts 10 --removal-limit 5
.venv/bin/python -m experiments.valley_exchange_diagnostics --snapshot "$SNAPSHOT" --data-dir "$DATA"
VALLEY_EXCHANGE_DATA="$DATA" .venv/bin/python -m pytest -q tests/test_valley_exchange.py
```

The focused exchange, exact-Y replay, boundary-enumerator, Hill geometry and
Streamlit import regressions passed in two runs: 52 passed, one slow Y
regeneration skipped. A separate fresh Y enumeration in this experiment
reproduced the preserved 1,651 baseline candidate records and ring candidates
exactly.
