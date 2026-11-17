# Connectivity-prioritised Y axial maps

This experiment uses the Converging Valleys/Y seed-42 settlement and the
displayed building numbering of the saved diagnostic. It does not change the
production generator, selector or exact-Y fixtures. The 32-line legacy result
is a replay of the saved candidates, not an inspection of a running app.

## Shared candidate pool and constraints

Both experimental selectors use the same 3,214 distinct rational maximal
intervals: 1,651 exact baseline intervals and 1,563 additional
boundary-endpoint intervals. Candidate intervals and original occupied
polygons were checked with exact rational predicates; the accessible-domain
union, complement and 267 convex regions were constructed by GEOS.
Fresh exact region-coverage calculations matched the prepared coverage data.
The complete exact intersection graph has 412,106 edges. A fixed degree is
computed once for every candidate, counting each other candidate with an exact
intersection, including permissible boundary contacts.

The required topology consists of one connected accessible component and
cycles enclosing each of the three specified occupied-obstacle witnesses.
It does not require the precise same edges or all cycles of the full network.

The connectivity selector traverses candidates in descending full-graph degree,
then descending length, then canonical rational interval order; it takes a
candidate only if it covers a new region. Its 29-line cover already met both
topology requirements, so no repair lines were needed. The comparison greedy
is the existing experimental exact coverage/length greedy on the *same* pool,
including its ring seed and removal steps, not the live selector run on a
different pool.

The subsequent deterministic search considers up to the 400 highest-ranked
available additions and 300 coverage-qualified feasibility checks per map,
with at most eight accepted 2-for-1 or 3-for-2 rounds. It checks exact clearance,
coverage, component connectivity and witness rings; it imposes no angular
constraint. A separate bounded 3-for-2 probe used the first 40 available
additions and 100 checks for each resulting map and found no exchange. These
are bounded searches, not proofs of local or global optimality.

## Fixed-terminal angular evaluation

The same 52 sample locations (the 36 saved Y samples plus 16 distributed
points) and terminal options are used for every map. Independently of the
selected maps, each sample has up to 128 fixed nearest visible perpendicular
connectors, chosen from the union of the 3,214 certified candidates and the
32 stored legacy lines. There are 6,488 such options. Connector visibility is
checked exactly against the original occupied polygons and constructed domain.
A connector is available only if its associated line is selected; no terminal
is reattached during evaluation. Origin and destination angular costs include
the connector directions. No terminal can be used as an intermediate shortcut.

There are 2,652 ordered sample pairs. "Unreachable" below means no route with
these fixed, limited options; it does not prove that the corresponding places
are physically inaccessible. Means and maxima are over reachable pairs and
therefore may involve different pair sets. On the 1,980 ordered pairs reachable
in **all five** main maps, mean depths are 4.3664 for legacy, 4.0411 for
unified greedy, 4.0219 for greedy after exchanges, 3.9653 for connectivity
ordering, and 4.2119 after connectivity exchanges. These numbers use the
existing right-angle-normalised angular model and no fidelity constraint.

## Results

| Map | Lines | Length | Regions | Components / edges | Witness rings | Mean / max depth | Unreachable pairs | Exchanges | Selection time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Legacy live-pool replay | 32 | 1268.45 | 267/267 | 1 / 46 | 2/3 exact; 3/3 GEOS | 4.514 / 10.920 | 300 | — | 428.62 |
| Unified exact greedy | 29 | 1171.88 | 267/267 | 1 / 37 | 3/3 | 4.097 / 8.411 | 102 | 0 | 8.49 |
| Unified greedy + exchanges | 28 | 1168.80 | 267/267 | 1 / 36 | 3/3 | 4.112 / 8.411 | 300 | 1 | 10.39 |
| Connectivity ordering | 29 | 1454.85 | 267/267 | 1 / 72 | 3/3 | 3.902 / 7.983 | 300 | 0 | 0.12 |
| Connectivity + exchanges | 24 | 1207.14 | 267/267 | 1 / 43 | 3/3 | 4.134 / 8.815 | 300 | 5 | 2.60 |
| Connectivity + targeted 1391 continuation | 23 | 1118.27 | 267/267 | 1 / 37 | 3/3 | 4.164 / 8.815 | 300 | 6 | 3.08 |

The final row is a **separate targeted probe**, not the result of the unbiased
ranking: candidate 1391 was examined as an addition and accepted only after
the same topology and clearance checks. The first five rows are the main
comparison. Selection times exclude shared candidate certification, full-graph
construction (26.98 s), and fixed-terminal preparation (209.65 s); the legacy
time is from its earlier replay. The 23-line time includes its targeted probe.

The legacy replay uses 15,189 float candidates and GEOS/tolerance-based
selection, not the unified exact pool. When its stored float endpoints are
interpreted as exact rationals, 26 of its 32 lines fail the exact
occupied/domain clearance test and only two witness rings close. The live
GEOS ring check reports all three. This discrepancy must not be interpreted
as an exact certification of the live map or as proof of the magnitude or
cause of each float discrepancy.

## Investigated candidates

| Buildings | Exact candidate | Full-pool degree | Connectivity-ordered map |
|---|---:|---:|---|
| 1–50 | 1183 | 810 | Not selected |
| 49–54 | 1391 | 109 | Not selected |
| 49–54 | 1392 | 102 | Selected |
| 49–23 | 1303 | 424 | Selected |

In a targeted 2-for-1 probe of the unified greedy map, candidate 1303
(length 45.2595) replaces 25 and 30 (27.6780 and 18.0297); the resulting
28-line map remains feasible and has all 2,652 fixed-terminal pairs reachable.
Its mean angular change over the 2,550 pairs reachable in both maps is
0.0351, with maximum increase 0.9918.

From the 29-line connectivity map, 1183 can replace 766 and 1040
(68.3440 and 20.7759), and 1391 can independently replace the same pair.
Candidate 1183 is not longer than both removed lines. These are alternatives,
not two exchanges that can both be applied to that initial map. For each,
the largest angular increase over the 2,352 common reachable pairs is 3.1482.

From the 24-line connectivity result, 1391 replaces 1389 and 1592
(26.7449 and 86.2744), yielding the targeted 23-line map; it is shorter than
both removed lines. Its mean angular increase on the 2,352 pairs reachable
before and after is 0.0298; the maximum is 0.1902. None of these probes forces
an infeasible candidate into a map.

## Reproduction

First prepare the saved Valley data and replay the legacy selector as described
in [the previous experiment](./VALLEY_EXCHANGE_RESEARCH.md). Then choose a new
output directory:

```sh
SNAPSHOT=/path/to/axial-648f8da1364449a6aa70fd24038eea21.json
DATA=/path/to/prepared-valley-exchange-directory
OUT=/path/to/new-connectivity-directory
.venv/bin/python -m experiments.valley_connectivity --snapshot "$SNAPSHOT" --data-dir "$DATA" --output-dir "$OUT"
.venv/bin/python -m experiments.valley_connectivity_terminals --snapshot "$SNAPSHOT" --data-dir "$DATA" --output-dir "$OUT" --terminal-attachments 128
.venv/bin/python -m experiments.valley_connectivity_probe --snapshot "$SNAPSHOT" --data-dir "$DATA" --output-dir "$OUT"
.venv/bin/python -m experiments.valley_connectivity_probe_angular --data-dir "$DATA" --output-dir "$OUT"
.venv/bin/python -m experiments.valley_connectivity_plot --snapshot "$SNAPSHOT" --data-dir "$DATA" --output-dir "$OUT"
.venv/bin/python -m experiments.valley_connectivity_plot --snapshot "$SNAPSHOT" --data-dir "$DATA" --output-dir "$OUT" --targeted-continuation
VALLEY_EXCHANGE_DATA="$DATA" VALLEY_CONNECTIVITY_DATA="$OUT" .venv/bin/python -m pytest -q tests/test_experimental_connectivity_selection.py tests/test_valley_connectivity.py
```

The output directory holds the exact full-graph degrees and edges, selection and
exchange records, fixed terminals, angular results and numbered comparison
figures. These outputs and the prior Valley data are preserved outside Git in
`$HOME/Developer/aggregation-valley-research-2026-11-17.tar.gz`; see
[the handover](./HANDOVER.md) for its checksum and limitations. Transfer the
archive separately when moving to another machine.
