# Convex-region metric attachment and joint corridor selection

This experiment replaces the capped fixed connector inventory in a
separate metric analysis. It reuses the independently verified doorway
and line incidence tables from Hill 42 and Y 42. The angular analysis
continues to use the same directed exact axial graph, free first- and
last-line access and the archived full-pool incidence baseline.

## Metric attachment and certification

For every doorway, region and eligible line, the experiment clips the
exact line interval to the closed incident convex region. A line must
have positive-length interior traversal. The doorway may be on the
boundary. It retains the exact perpendicular projection clamped to
the feasible interval and both interval endpoints. A clamped projection
is the shortest straight connector to that line *within that region*.
Other valid points may give a shorter complete route. When a doorway
has several incident regions, the inventory contains their union, with
identical line–point stops deduplicated.

Every connector is checked for exact doorway incidence, independent
positive-interior traversal, endpoint membership on both the line
and region closure, and accessible-space clearance. The certified
geometry, its region, type and length are recorded. A common master
metric graph for each settlement is noded at exact line intersections
and all certified stops. Each selected map inherits those stops only
on its retained lines. Routes include straight connector lengths and
distance along the retained axial graph.

There is no limit on the number of incident eligible lines. The finite
choice of projection and interval endpoints does limit the attachment
locations considered. Axial junctions are included as network nodes,
while an arbitrary doorway-to-junction connector is not part of this
pilot rule. Reported distances are shortest paths on the specified
finite master graph. They are not proofs of continuous or unrestricted
doorway-to-doorway metric optimality.

## Simultaneous selections

The study starts independently from the archived strict 40-line Hill
angular and metric-complete maps, the 29-line Y angular map and the
40-line Y metric-complete map. For each archived band it offers the
existing selection, the geometric extreme pair, the individually
best incidence-angular pair and the previously metric-complete
route-ranked pair, when they exist. These are a finite shortlist
in each band. A joint trial removes the union of the replaced sheaves
and adds the union of the requested representatives. This avoids
order dependence where bands overlap.

The Cartesian product of those options is evaluated globally after
deduplication. The hard gates are exact clearance, strict interior
coverage, a single connected component, full winding rank and
complete incidence-angular reachability. Revised metric reachability
and costs are reported separately. The joint economy selection
minimises count, then the sum of each mean route cost divided by its
own full-pool mean. The joint routes selection puts that combined
route score first. Both reported joint winners require full metric
reachability. The CSV identifies worst changes against each original
map and shows gained and lost exterior transverse contacts by band.

## Hill 42

The new master contains 29,131 distinct doorway–line–stop
attachments, with 38,391 region-specific certification entries
including duplicates between incident regions. Every proposed stop
passed independent clearance. All six previously recorded failure
occurrences are repaired, each with 99 now-reachable pairs involving
the formerly unattached door.

| Saved selection | Lines | Metric mean | Median | P95 | Maximum | Metric excess | Unreachable |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full pool | 1,347 | 45.982 | 46.762 | 79.291 | 101.931 | 0.000 | 0 |
| Entrance guided | 130 | 53.112 | 54.064 | 90.507 | 119.568 | 7.053 | 99 |
| Legacy backward | 44 | 57.317 | 57.589 | 99.736 | 129.388 | 11.259 | 99 |
| Strict angular reference | 40 | 52.909 | 53.639 | 90.955 | 120.470 | 6.927 | 0 |
| Strict metric reference | 40 | 53.604 | 53.967 | 94.325 | 127.041 | 7.622 | 0 |

Both legacy Hill maps leave building 40 without an eligible line in
its incident region 162. The old protocol could reach lines outside
that region. Those 99 missing pairs are due to the new eligibility
scope and the maps' strict coverage omission. They are distinct from
the old metric cap and nearest-point failures. The table's legacy
map means describe reachable pairs.

All nine joint combinations per Hill reference were valid. Replacing
both bands by the geometric pairs increased each reference from 40
to 42 lines. From the original angular reference, mean angular depth
changed from 1.0284 to 1.0414 and mean metric cost from 52.9092 to
52.9226. The 40-line original remained the economy winner for both Hill
references. The best route score from the angular reference replaces
only band 2, reaching 41 lines and an angular mean of 1.0238.
The geometric replacements add transverse contact 382 in band 3
and increase the angular cost between buildings 2 and 97 by 1.250.

## Y 42

The new Y master has 53,770 distinct doorway–line–stop attachments and
71,648 region-specific certification entries. No proposed stop failed
the independent clearance check. All 322 archived Y failure occurrences
are repaired. Each now has all 98 possible routes involving its formerly
unattached door. Together with Hill this reproduces and repairs all
328 archived occurrences, including the nine involving Y building 100.

| Saved selection | Lines | Metric mean | Median | P95 | Maximum | Metric excess | Unreachable |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full pool | 1,651 | 57.079 | 55.871 | 108.634 | 144.285 | 0.000 | 0 |
| Entrance guided | 70 | 59.680 | 57.996 | 113.401 | 150.537 | 2.601 | 0 |
| Legacy backward | 37 | 63.303 | 61.590 | 121.223 | 159.416 | 6.224 | 0 |
| Strict angular reference | 29 | 66.325 | 64.398 | 127.682 | 168.845 | 9.246 | 0 |
| Strict metric reference | 40 | 63.047 | 61.496 | 120.588 | 159.416 | 5.968 | 0 |
| Earlier route-ranked alternative | 39 | 61.371 | 59.849 | 116.868 | 154.178 | 4.292 | 0 |

The saved 29-line map now reaches all 4,851 metric pairs. The old
fixed-connector evaluation left 2,295 pairs unreachable. The 29-line map
remains the economy winner from that start, whereas the route-first
combined score selects a 32-line map.

| Y simultaneous selection | Lines | Length | Angular mean / median / p95 / max | Metric mean / median / p95 / max | Angular / metric mean excess |
|---|---:|---:|---:|---:|---:|
| 29-line start | 29 | 1,109.34 | 0.709 / 0.532 / 2.601 / 4.361 | 66.325 / 64.398 / 127.683 / 168.845 | 0.327 / 9.246 |
| All extreme pairs from 29 | 32 | 1,307.77 | 0.696 / 0.508 / 2.580 / 4.321 | 63.627 / 61.977 / 121.625 / 161.254 | 0.314 / 6.548 |
| All angular-ranked pairs from 29 | 32 | 1,297.51 | 0.664 / 0.440 / 2.515 / 4.275 | 62.624 / 61.030 / 119.542 / 158.203 | 0.282 / 5.545 |
| 40-line start | 40 | 1,496.42 | 0.658 / 0.457 / 2.481 / 4.361 | 63.047 / 61.496 / 120.588 / 159.416 | 0.276 / 5.968 |
| All extreme pairs from 40 | 38 | 1,467.32 | 0.671 / 0.457 / 2.481 / 4.321 | 63.065 / 61.541 / 120.957 / 159.995 | 0.289 / 5.986 |
| All angular-ranked pairs from 40 | 38 | 1,457.07 | 0.638 / 0.440 / 2.481 / 4.275 | 62.302 / 60.711 / 119.231 / 158.203 | 0.256 / 5.223 |
| Best combined score from 40 | 38 | 1,445.57 | 0.645 / 0.481 / 2.481 / 4.193 | 60.694 / 59.201 / 115.009 / 150.557 | 0.263 / 3.615 |

The 38-line combined winner uses pairs 1183/1238, 437/752 and 1126/1193.
It improves both means relative to the 40-line original and the saved
39-line alternative. It has slightly higher angular mean than the
all-angular-ranked 38-line map, alongside lower metric mean and
maximum. Compared with the 40-line reference, the worst angular
increase was 0.126 for buildings 6–32. The worst metric increase
was 7.329 for buildings 35–39. All Y joint combinations retain
the same exterior transverse contact identities in these bands.
All retained Y joint maps cover all 267 regions and keep winding
rank 3. The Hill joint maps cover all 266 regions and keep rank 11.

## Interpretation and saved results

The regional attachment policy repairs the observed connector
failures without adding lines to the selected maps. It also exposes
the strict coverage omission of the two legacy Hill selections.
The 29-line Y reference now serves both measures under the finite
regional policy, though its routes remain longer on average than
the 38- or 39-line alternatives.

The extreme-diagonal rule can remove two lines from the 40-line Y
start. Route ranking finds a better 38-line solution under the
combined objective. On Hill and on the 29-line Y reference, the
count-first solution retains the original selection. The geometric
pair remains a low-cost proposal rather than a replacement rule
that guarantees better routes or smaller maps. All 93 distinct
joint proposals across the four starts passed the hard gates within
this shortlist. The experiment leaves other possible corridor
pairs and global line-set optimisation open.

The completed runs took 203 seconds on Hill and 519 seconds on Y.
A supplemental Y run with deduplicated noding was interrupted after
the primary run completed. The primary runs and archived baselines
are preserved. The export checks matched, all-pair monotonicity
against both full-pool references, strict topology on the joint
variants and the exact archived angular-reference arrays.
Nineteen targeted tests passed.

- [116 map comparisons](diagnostics/preserved-axial-benchmark/convex-metric/pilot-1/comparison.csv)
- [328 attachment-failure replays](diagnostics/preserved-axial-benchmark/convex-metric/pilot-1/failure-replay.csv)

| Case | Versioned batch record |
|---|---|
| Hill 42 | `c1a6c6dd4d774ac6994b4f7f781fdd97` |
| Y 42 | `ad0b38a970ac4de5a33647715aef1626` |

The batch records retain exact connector geometry, route arrays,
joint candidates and source checksums. For a replay, run
`python -m experiments.convex_metric --output PATH Hill-42` and then
the same command with `Y-42`. Run
`python -m experiments.convex_metric --output PATH export`
to collect the CSVs.
