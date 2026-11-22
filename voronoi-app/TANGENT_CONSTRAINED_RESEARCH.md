# Tangent-constrained reduction: Y seed 42

## Inputs and constraints

This independent experiment starts from the saved 66-line completed 0.25%
structural map. It uses the same 3,214 exact rational candidates, 267 convex
regions, 412,106-edge candidate intersection graph and 187 sampled
shortest-path tangent segments as the earlier experiments. The original
archive, snapshot, candidate graph, coverage data and selections are checked
against the archive manifest. The later visibility and structural result
files are checked against previously recorded SHA-256 values; they are not
part of the older archive. All candidate intervals are rechecked for exact
clearance relative to the constructed GEOS accessible-domain overlay, convex
coverage is recomputed, and tangent-to-candidate containment is checked again.
Prior data and results are not overwritten.

Each map must preserve complete convex coverage, connectivity within every
accessible component, all three exact witness rings and candidate clearance.
Original structural lines and the earlier aggregate structural footprint are
**not** pinned. Tangent containment is exact collinear subsegment containment,
not intersection and not proof of route preservation.

## Ten most-used tangents

The table gives every certified maximal candidate containing each segment.
The listed regions are the number of convex-region interiors covered by that
candidate; the complete region IDs and exact endpoints are in the result
records. None of these candidates was in the completed 66-line map.

| Rank | Building labels | Journey-edge uses | Candidate | Length | Full-pool degree | Regions |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 59–59 | 18,402 | 137 | 14.62 | 242 | 17 |
| 2 | 59–59 | 18,402 | 138 | 22.58 | 260 | 17 |
| 3 | 59–59 | 12,812 | 136 | 35.49 | 407 | 32 |
| 4 | 26–2 | 12,500 | 870 | 39.38 | 434 | 29 |
| 5 | 59–85 | 12,486 | 526 | 40.74 | 426 | 36 |
| 6 | 42–42 | 11,415 | 319 | 10.71 | 113 | 8 |
| 7 | 23–23 | 11,351 | 24 | 14.82 | 267 | 10 |
| 8 | 23–42 | 10,471 | 1255 | 20.66 | 327 | 19 |
| 9 | 2–23 | 10,080 | 991 | 39.91 | 490 | 26 |
| 10 | 59–26 | 8,574 | 603 | 73.64 | 801 | 57 |

Same-building entries include permissible boundary-following segments. Every
one of the ten has exactly one containing candidate, and these candidates
are distinct. An exact bitmask set-cover dynamic program independently
confirms that the minimum combined cover is **10 lines**, not merely ten
independently chosen lines. Adding those candidates creates a 76-line map;
the ten are individually essential to the top-ten condition in the final
31-line result.

## Reduction method and outcomes

For the top-ten experiment the ten segments are hard constraints. Four
separate experiments instead impose a minimum represented utilisation weight
of 25%, 50%, 75% or 90% of 245,126 journey-edge uses; they do not
additionally require the top ten. The weighted starts add the candidate with
largest marginal uncovered utilisation, breaking ties by the fixed
full-network connectivity ranking. The required use count is rounded up
exactly, so it cannot fall below the requested percentage.

Reduction greedily attempts single removals, followed by bounded 2-for-1 and
3-for-2 exchanges. Every accepted change rechecks the hard tangent condition,
convex coverage, connectivity, rings and exact clearance. The exchange pool is
the union of the 160 highest-connectivity candidates and all 187 candidates
that support at least one sampled tangent: 320 distinct candidates. At most
60 additions are considered for 2-for-1 and 16 for 3-for-2, prioritised by
missing required tangents and marginal weight; each search examines at most
400 removal sets and 60 full feasibility checks, with at most three accepted
rounds per exchange mode. Both exchange searches hit a bound in every case.
Thus the reported counts are feasible results, **not global minima**.

All rows below cover 267/267 regions, form one line-network component and
preserve 3/3 witness rings. Uses are distinct sampled journey-edge uses,
not whole-journey coverage.

| Map | Lines | Length | Line intersections | Tangents / 187 | Uses represented | Top ten |
|---|---:|---:|---:|---:|---:|---:|
| Unified greedy | 29 | 1,171.88 | 37 | 12 | 6.256% | 0 |
| Connectivity-first coverage | 29 | 1,454.85 | 72 | 5 | 0.632% | 0 |
| Structural completed | 66 | 3,469.03 | 575 | 13 | 3.867% | 0 |
| Structural reduced | 35 | 1,511.18 | 74 | 5 | 0.578% | 0 |
| Top ten added, before reduction | 76 | 3,781.60 | 726 | 23 | 55.470% | 10 |
| Top ten constrained and reduced | 31 | 1,320.36 | 65 | 12 | 51.607% | 10 |
| Weighted 25% | 26 | 1,167.08 | 42 | 7 | 27.585% | 4 |
| Weighted 50% | 30 | 1,305.77 | 56 | 14 | 52.060% | 8 |
| Weighted 75% | 39 | 1,648.84 | 111 | 24 | 75.081% | 10 |
| Weighted 90% | 49 | 2,191.90 | 222 | 37 | 90.004% | 10 |

All four requested weighted thresholds were reached: the final represented
use counts are 67,617, 127,612, 184,043 and 220,624, respectively. The
top-ten result removes 45 of the original 66 lines and retains the ten added
support lines. The 25% and 50% runs each found one 3-for-2 exchange after
single removals; the other runs accepted only single removals within these
bounds. Exact lists of additions, removals, exchanges, constraints and
individual tangent-essential lines are saved for every run.

## Fixed-terminal routing

All maps use the previous experiment's exact same 32 spatial sample points
and 4,003 fixed, exactly visible candidate connectors. The saved four baseline
route records reproduced exactly. There are 992 ordered pairs: 178 directly
visible and 814 occluded. Direct movement is allowed. A missing retained
connector is reported as an **attachment failure**, not as a disconnected
network or physical inaccessibility. The protocol is a bounded sample; it
does not include the separate building-boundary terminals.

The means below are calculated on the same **498 occluded pairs reachable in
every map in this comparison**, not on each map's different reachable set.
Metric detour is network length divided by the continuous-space visibility
reference. Angular depth uses the existing right-angle-normalised model.
Metric and angular optima need not be the same route.

| Map | Mean metric detour | Mean angular depth | Attachment failures / 992 |
|---|---:|---:|---:|
| Unified greedy | 1.2909 | 4.8601 | 142 |
| Connectivity-first coverage | 1.1911 | 4.6916 | 168 |
| Structural completed, 66 | 1.1016 | 4.2471 | 0 |
| Structural reduced, 35 | 1.1831 | 4.6932 | 0 |
| Top ten added, 76 | 1.0598 | 4.1944 | 0 |
| Top ten reduced, 31 | 1.1411 | 4.4533 | 218 |
| Weighted 25%, 26 | 1.1570 | 4.6045 | 230 |
| Weighted 50%, 30 | 1.1344 | 4.5786 | 180 |
| Weighted 75%, 39 | 1.0982 | 4.4179 | 180 |
| Weighted 90%, 49 | 1.0743 | 4.2311 | 128 |

No map produced a network-disconnected pair when both terminals had
connectors. The 31-line top-ten map has 27 of 32 terminals attached, while
both 66- and 35-line structural references have 32. Its 498-pair means improve
on the 35-line map, but its 218 attachment failures prevent claiming that it
preserves that map's route coverage. The 49-line 90% map improves both
common-pair means relative to the 66-line map, but has 128 attachment
failures; it is not a full route-quality replacement. The 76-line augmented
map improves both common-pair means over the 66-line map without losing
attachments, but uses ten extra lines. Means over all reachable pairs and
maxima are also retained in the machine-readable output; those means have
different denominators when attachments fail.

## Conditional tangent ablation

For each of the ten added candidates, the experiment removes just that line
from the 76-line augmented map and recomputes routes using the same fixed
terminals. Restoring each candidate improved metric length for at least 290
ordered sample pairs, with a `1e-9` comparison threshold; none added a
reachable pair because the original 66-line map was retained. Therefore no
one of the ten was observed to add a line without improving **either**
metric or angular performance in this particular conditional test.

Candidates 24, 137, 138, 319 and 526 improved no sampled angular shortest
path in that ablation, although each improved metric paths. These counts
reflect one-at-a-time removal while the other nine additions remain; they
cannot establish the independent value of a tangent in every map. An
improved route may use the maximal line or its terminal attachment rather
than traversing the tangent segment itself.

An independent monotonicity check found no metric or angular regression above
`1e-9`, and no loss of reachable pairs, when comparing the 76-line superset
with the 66-line baseline or any of the ten ablated maps.

The route-change figure maps per-origin mean changes between the 31-line
top-ten result and the 66-line reference over their common reachable occluded
pairs. Five origins have no comparable occluded pairs and are marked with
crosses, rather than treated as zero change.

## Limitations and reproduction

The observed trade-off concerns fixed-connector network routes on a small
sample, not all continuous-space journeys or globally optimal angular paths.
Exact predicates certify geometry relative to the GEOS overlay; metric and
angular costs use floating point. Weighted tangent containment, metric routing
and angular routing are different measurements. Retaining a segment
geometrically does not prove that the selected map preserves the continuous
shortest path that used it.

Set `ARCHIVE`, `SNAPSHOT`, `DATA`, `SELECTIONS`, `VISIBILITY`, and
`STRUCTURAL` to the verified preserved files described in
[the previous report](./CONNECTIVITY_BACKBONE_RESEARCH.md). Set `OUT` to a
nonexistent directory; no existing result is overwritten.

```sh
MPLBACKEND=Agg .venv/bin/python -m experiments.tangent_reduction \
  --archive "$ARCHIVE" --snapshot "$SNAPSHOT" --data-dir "$DATA" \
  --selection-dir "$SELECTIONS" --visibility-dir "$VISIBILITY" \
  --structural-dir "$STRUCTURAL" --output-dir "$OUT"
```

The output contains the ten full support records, intermediate and final
selections, per-exchange details, pairwise and ablation route records, and
numbered map and route-change figures. Two independent executions reproduced
the selected sets, exchanges and sampled route records.

The headless regression suite passed 245 tests, with 3 skipped and one slow
default-Voronoi test deselected. The suite included saved-Y clearance,
constraint and independent-replay checks. Pylance syntax requests timed out.
The final `results.json.gz` SHA-256 is
`cd0cc28201a5cfca9a4e302e2726206680a0c420b0bd057f62b66811bce3d313`.
