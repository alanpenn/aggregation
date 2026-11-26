# Flat 40 candidate 1509 diagnosis

Candidate 1509 is the only selected C-H interval that crosses the strict
interior of convex region 257. Candidate 1435 coincides with an edge of the
region for approximately 6.07 model units. Its positive-length contact with
the boundary supplies zero strict interior incidence. Candidate 1509 crosses
approximately 6.67 model units of the interior. An independent rational
half-plane replay checked all 34 intervals against the archived convex polygon
and reproduced the stored incidence. The exact ring and all contacts are in
the structural output.

## Structural deletion controls

| Selection | Lines | Regions | Doorways | Components | Winding |
|---|---:|---:|---:|---:|---:|
| Archived C-H | 34 | 292/292 | 100/100 | 1 | 24/24 |
| Delete 1509 | 33 | 291/292 | 100/100 | 1 | 24/24 |
| Delete 1435 | 33 | 292/292 | 100/100 | 1 | 23/24 |
| Delete both | 32 | 288/292 | 100/100 | 1 | 23/24 |

Exact clearance passes for every retained interval in all four selections.
Deleting 1509 alone leaves region 257 uncovered. Deleting 1435 alone makes
the winding signatures of occupied blocks `internal-8` and `internal-12`
indistinguishable. A validated face encloses both blocks after that deletion.
Deleting both leaves regions 255, 256, 257 and 270 uncovered and has the same
winding deficit as deleting 1435. The three earlier certified replacements
supply the missing coverage and restore independent winding.

## Configurational effects

The pair meets at a transverse interior junction with a 15.295° departure
from straight. Apart from each other, both lines contact 1257, 1470, 1519,
1531 and 1532. Candidate 1435 also contacts 1369. Removing 1509 leaves all
528 unweighted shortest-path lengths between the 33 surviving axial lines
unchanged. The shared contacts occur at their own exact junction coordinates,
which remain relevant to angle and distance.

On the existing certified route definitions, removing 1509 increases angular
cost for **59** of 4,950 doorway pairs and metric cost for **39**. All pairs
remain reachable and no cost decreases. Mean increases are 0.001415 angular
units and 0.004026 model units. The largest angular increase is 0.16995 for
doorway indices 46 and 69. The largest metric increase is 2.28011 model
units for doorway indices 69 and 75. Doorway indices follow the archived
zero-based order. These route results compare the original and deletion maps.
They do not imply an ordering of geometric preference across replacement
maps.

## Records

The analysis verified 24 archived inputs against the migration SHA-256
manifest, checked the atlas and optimisation lineage, replayed the three
previous exchange certificates, and independently rebuilt the selected line
intersections. The C-H route arrays matched the archived reference to
numerical tolerance. The exact region and winding witnesses, vector PDF and
route arrays are in
`diagnostics/strict-generalisation/flat40-candidate-1509-diagnosis-2/`.
The replay entry point is `experiments.flat40_diagnose_1509`.
