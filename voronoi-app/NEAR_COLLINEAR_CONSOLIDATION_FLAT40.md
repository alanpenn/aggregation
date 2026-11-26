# Near-collinear axial consolidation on corrected Flat 40

Three independently certified exchanges reduce archived C-H from 34 to 33
lines. Each removes **1435 and 1509** and adds one of **323, 1365, or 1436**.
All three replacements are shorter than either removed interval. The experiment
therefore finds structural consolidation without supporting the specific
prediction that a longer maximal tangent would replace this pair.

## Provenance and controls

The experiment matched SHA-256 digests for 23 archived inputs against the
migration manifest. These include the Flat 40 source journal and immutable
stage files, the frozen candidate geometry and intersection records, the
benchmark C-H inventory, the earlier unrestricted sheaf inventory, and the
Algorithm D comparator. The two archived C-H inventories agreed exactly.
Both archives use the same lineage. The independent validator confirmed
292/292 regions, 100/100 doorway incidences, one connected axial component,
and full 24/24 independent winding rank on the 34-line C-H starting map and
the 33-line Algorithm D control. The complete pool contains 1,534 candidates.
The archived complementary selection contains 628 candidates before repair
and 629 afterwards. The experiment used the archived 34-line IDs directly.

## Pair definition and search

The experiment computes rational segment intersections and forms outward rays
from a point intersection to the actual endpoints on each interval. It
discards zero-length rays. It chooses the pair of available rays with the
greatest included angle and reports departure from straight as 180° minus that
angle. Angles are evaluated numerically from exact cross and dot products.
Collinear overlap is recorded as a rational interval in a separate category.

| Maximum departure | Transverse interior pairs | Endpoint pairs |
|---:|---:|---:|
| 10° | 0 | 0 |
| 15° | 0 | 0 |
| 20° | 5 | 0 |
| 30° | 10 | 0 |

Of the 561 pairs in C-H, 463 had no intersection and 98 had noncollinear
point intersections. There were no collinear overlaps or collinear touches.
Each qualifying pair was tried with every full-pool ID outside the current
selection. The screens were strict region incidence, doorway incidence,
clearance, connectivity, and dynamic winding. Trials reaching the winding
target, or yielding an inconclusive dynamic result, were eligible for a full
independent face and clearance check. Certified maps also had their selected
intersection graph rebuilt from exact intervals and compared with the frozen
graph.

| Removed IDs | Departure | Pass region and doorway incidence | Certified |
|---|---:|---:|---:|
| 293, 991 | 18.134° | 10 | 0 |
| 714, 764 | 18.068° | 19 | 0 |
| 1080, 1195 | 27.810° | 1,500 | 0 |
| 1080, 1257 | 26.887° | 55 | 0 |
| 1195, 1278 | 24.054° | 7 | 0 |
| 1257, 1470 | 27.890° | 14 | 0 |
| 1435, 1509 | 15.295° | 12 | 3 |
| 1470, 1519 | 19.309° | 1,500 | 0 |
| 1509, 1531 | 19.498° | 34 | 0 |
| 1519, 1532 | 20.535° | 40 | 0 |

Of 15,000 initial trials, 11,809 failed region incidence, 101 failed
connectivity, and 3,087 had insufficient dynamic winding rank. No trial
first failed at the doorway or clearance screen. A diagnostic subset of 101
trials used a candidate longer than both removed lines, within 30° of both
arms, with positive projected overlap on both arms. Of those, 87 failed
region incidence and 14 failed winding. Projected overlap measures longitudinal
reach and does not assert that a candidate lies close to both arms.

## Certified exchanges

Lines 1435 and 1509 measured 45.46 and 46.04 model units. Removing them left
regions 255, 256, 257, and 270 uncovered. All three replacements recover
those regions and preserve the same set of contacts with the retained
network. Candidates 1365 and 1436 are documented mutual tangents.
Candidate 323 records ring-boundary, occupied-face, and same-building
tangent support.

| Map | Lines | Total length | Intersection pairs | Transverse pairs |
|---|---:|---:|---:|---:|
| Archived C-H | 34 | 1725.21 | 98 | 88 |
| Replace with 323 | 33 | 1672.26 | 92 | 84 |
| Replace with 1365 | 33 | 1673.64 | 92 | 84 |
| Replace with 1436 | 33 | 1675.14 | 92 | 84 |
| Archived Algorithm D | 33 | 1628.66 | 90 | 81 |

Every 33-line exchange retained 292/292 regions, 100/100 doorway incidences,
one component, exact clearance, and 24/24 winding rank. Each resulting map
had eight eligible pairs. Across the three maps, 36,024 additional proposals
yielded no further consolidation. Thus 33 is the minimum reachable under
this procedure from archived C-H. The search does not establish a global
minimum across all axial selections or equivalence of doorway route costs.

## Reproduction

Use a fresh output path. The supplied manifest uses paths relative to
`AGGREGATION_DATA_ROOT`.

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
PYTHONPATH=src:. .venv/bin/python -m experiments.near_collinear_consolidation \
  --manifest "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json" \
  --output diagnostics/strict-generalisation/near-collinear-consolidation-1/flat-40-replay.json
```

The JSON inventory includes exact junctions and arm endpoints, counts and
incidence survivors per pair, the replacement supports, candidate IDs, and
full winding certificates. The companion PDF highlights the removed and
replacement intervals. Both are under
`diagnostics/strict-generalisation/near-collinear-consolidation-1/`.
