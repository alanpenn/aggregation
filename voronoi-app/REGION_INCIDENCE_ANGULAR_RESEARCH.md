# Doorway angular depth through convex-region incidence

The preserved doorway positions and fresh-exact convex-region geometries
define the incidence calculation. A doorway qualifies for every accessible
region whose closure contains its exact coordinate. A line qualifies for
a region only when it passes through the region's interior over a
positive-length interval. Doorway access uses the union of the incident
regions' traversing lines, restricted to the selected map. The same
line–region table defines the interior-traversal coverage reported here.
Earlier coverage checks could count a boundary touch, so their covered
region totals can differ from these totals.

## Movement and geometric checks

The angular network uses exact axial endpoints and axial–axial
intersections for its nodes. The directed state of an atomic segment
preserves movement direction and the order of intersections along a line.
Each transition uses the existing angular-change convention, with one
unit per 90° turn. All orientations and positions on the accessible
first and last lines are eligible at zero entry and exit cost. A common
accessible line gives zero depth. The calculation has no doorway
connector segments, doorway turning angles, attachment limits or
nearest-line ranking.

An empty axial-line set is an attachment failure. Two nonempty sets in
separate axial components are disconnected. These statuses are recorded
separately for each pair and distinct from finite depth, including
zero. Each origin is evaluated against every subsequent doorway in the
saved order.

Doorway point-in-ring incidence was checked against independent rational
convex half-plane containment. Each line–region membership used for
doorway attachment was checked against independent rational
positive-interior clipping. Every full-pool interval passed exact
clearance again. The endpoints of every atomic edge were verified on
each certified line owning that edge. Turns connect incoming and
outgoing states only at a common verified rational point. The
implementation also checked that no reduced map beats its corresponding
full pool on a reachable pair within a tolerance of
`1e-8 + 1e-9 × max(abs(full), abs(reduced))`.

Metric costs are the archived geometric-connector shortest paths.
The archived connector-based angular summaries are included for comparison.
The CSV gives common-pair angular means where both raw arrays are
available. The sparse and extreme experiments retain the archived
summary distributions, including their reachable counts.

## Benchmark angular depths

The means describe reachable pairs. The connector-based column preserves
the old angular definition and uses that method's own reachable pairs.

| Case | Map | Lines | Incidence mean | Incidence median | Incidence p95 | Old angular mean | Incidence reachable |
|---|---|---:|---:|---:|---:|---:|---:|
| Hill 42 | Full candidate pool | 1,347 | 0.529 | 0.502 | 1.294 | 2.068 | 4,950 / 4,950 |
| Hill 42 | Entrance guided | 130 | 1.412 | 1.227 | 3.453 | 3.465 | 4,851 / 4,950 |
| Hill 42 | Best backward | 44 | 1.645 | 1.429 | 3.891 | 3.985 | 4,851 / 4,950 |
| Y 42 | Full candidate pool | 1,651 | 0.382 | 0.203 | 1.831 | 1.987 | 4,851 / 4,851 |
| Y 42 | Entrance guided | 70 | 0.676 | 0.443 | 2.539 | 3.065 | 4,851 / 4,851 |
| Y 42 | Best backward | 37 | 0.701 | 0.494 | 2.571 | 3.388 | 4,851 / 4,851 |

All 100 eligible Hill doors and 99 eligible Y doors have at least
one exact incident region. The independent clipping check covered 157
Hill regions and 146 Y regions, including all regions used by doorways.
The full pools furnish a traversing line for every doorway. Hill's
entrance-guided and best backward maps each lose 99 pairs due to a
single empty doorway-line set. Their earlier connector-based networks
reach every pair. The full pools have 1,306 zero-depth pairs on Hill
and 1,899 on Y under free entry and exit.

## Effect on the extreme-pair cases

The Y 42 corridor 2 and corridor 3 extreme pairs both reach all
4,851 pairs for incidence angular depth. They still leave 480 and 98
pairs unreachable in the geometric-connector metric analysis. Their
mean incidence angular depths are 0.691 and 0.686, compared with
0.681 and 0.681 after their respective repairs. Angular reachability
therefore depends on a different geometric condition than metric
reachability when using the amended definition.

On Hill, building 40 is the unattached door in the saved entrance-guided,
backward, sparse and extreme-pair comparisons. Its only incident convex
region is 162. The full pool contains 61 lines traversing that region,
while those selected maps contain none. Across all 38 map comparisons,
the only angular reachability failures came from empty doorway sets.
No nonempty doorway sets were disconnected.

## Records and reproduction

| Case | Version 2 batch record | Exact nodes | Exact atomic edges |
|---|---|---:|---:|
| Hill 42 | `08e5b5cc58804498964e0c75a987ee49` | 51,239 | 102,643 |
| Y 42 | `2cbef0756bb245958f6bef67bfd72ef9` | 97,331 | 195,338 |

Version 2 adds the saved extreme-pair and repair variants, the shortest
minimum-count beam result and the matched-count control to the 24
full-pool, entrance-guided, backward and sheaf benchmark comparisons.
All original benchmark pairwise depths reproduced the first incidence
run exactly. The saved analysis includes raw depths, failure categories,
the exact saved doorway coordinates, each doorway's incident regions
and selected line sets. The [comparison CSV](diagnostics/preserved-axial-benchmark/region-incidence-angular/pilot-2/comparison.csv)
includes mean, median, minimum, maximum and 95th percentile.

For a replay into a fresh output directory, run:

```bash
.venv/bin/python -m experiments.region_incidence_angular --output PATH "Hill 42"
.venv/bin/python -m experiments.region_incidence_angular --output PATH "Y 42"
.venv/bin/python -m experiments.region_incidence_angular --output PATH export
```
