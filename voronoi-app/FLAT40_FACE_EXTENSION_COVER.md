# Flat 40 face-extension convex cover

The experimental face-extension cover contained **2,201 regions** and
covered the full corrected Flat 40 accessible domain. With the archived
1,534 axial intervals, complementary-tangent sheaf-priority reduction
produced a certified **133-line** map. The result is substantially denser
than archived 34-line C-H and does not remove the coverage role of 1509.
The production convex generator and selector were left intact.

## Geometry and tested maximality

The run reads the exact Flat 40 settlement, effective occupied blocks,
accessible domain, full candidate pool and selected controls from the
verified archive. Archived floating coordinates enter the predicates as
their exact binary rationals. The experiment adds no quantisation.

Each original exposed segment is identified by exact overlap between an
occupied-block face and the accessible boundary. The two rays are tested
independently. An extension starts only when its first interval is in
accessible interior and stops at its first forward domain-boundary event.
Extensions never stop because another extension happened to be processed
first. Collinear segments and exact crossings are noded together and retain
all source IDs. The outer frame and other domain edges carry their own
provenance.

The graph stores exact counterclockwise angular order at each node. Given
a directed incoming edge, the clockwise predecessor of its reverse is
the right-handed successor, and the counterclockwise successor is the
left-handed successor. The run explores both directions for each
physical face with both rules and records the full directed walk and
closure. It also enumerates interior arrangement faces from noded edges.
These internal walks are needed to seed growth in the arrangement. For
this particular successor rule, reversing direction and handedness pairs
oppositely oriented walks of the same face. The appendix shows a physical
face with seven resulting regions on its accessible side. The two
complementary states recover the same seven, and the other two states
face away from the accessible side.

Each convex accessible walk face seeds growth in two deterministic
neighbour orders. A shared-edge union is accepted only if its rational
area equals the area of its convex hull. When no single adjacent atom
can be added, the resulting polygon is a local maximum for that growth
rule. Exact duplicate geometry is consolidated. Strictly contained
generated atom sets are removed only within the same component and
among valid convex unions. Convexity, accessible containment by
arrangement membership, and occupied-interior area are checked. This
construction does not certify maximality under simultaneous multi-atom
merges, arbitrary boundary paths, or all possible convex subsets.
No generic decomposition or gap-filling polygon was used.

## Arrangement and overlap

Flat 40 yielded 413 exposed source segments, 568 extensions, 2,767
accessible atoms and 2,201 retained convex polygons. There were 3,428
physical-face directed starts. The arrangement partition passed exact
area equality and the per-edge incidence check. Its union is the
archived accessible domain, with zero uncovered components.

| Multiplicity | Accessible area in square model units |
|---|---:|
| 0 | 0 |
| 1 | 84.65684 |
| 2 | 619.92095 |
| 3 | 2251.54167 |
| 4 or more | 4975.95170 |
| Total | 7932.07115 |

The overlap count ranges from **1 to 11**. The area-weighted mean is
**3.98633**, and the area-weighted median is **4**. Each atom retains its
rational boundary and integer multiplicity. Counts use polygon
interiors, with shared boundaries excluded from area totals.

There are no exactly equal old and new regions. Using rational
intersection-over-union ≥ 0.8 as a descriptive close-equivalence
threshold, 290 of the 292 archived regions and 2,198 of the 2,201 new
regions had no close equivalent. See the comparative map and the
machine-readable archived-to-new inventory.

## Region 257 and the axial controls

Twenty-three new polygons overlap the interior of archived region 257.
Candidate 1435 strictly traverses 18 of these and candidate 1509 traverses
12. Five of these 23 have 1509 as their sole hit in the archived C-H
selection. Across the entire new cover, eight regions have that property.
The certified 133-line selection retains 1509, with three uniquely
covered regions in its own selection. It omits 1435.

| Selection evaluated on stated cover | Lines | Regions | Doorways | Components | Winding |
|---|---:|---:|---:|---:|---:|
| Archived C-H, archived cover | 34 | 292/292 | 100/100 | 1 | 24/24 |
| Archived D, archived cover | 33 | 292/292 | 100/100 | 1 | 24/24 |
| Archived C-H, face-extension cover | 34 | 1597/2201 | 87/100 | 1 | 24/24 |
| Archived C-H without 1509, face-extension cover | 33 | 1589/2201 | 87/100 | 1 | 24/24 |
| Matched C-H replay, archived cover | 34 | 292/292 | 100/100 | 1 | 24/24 |
| Recomputed C-H, face-extension cover | 133 | 2201/2201 | 100/100 | 1 | 24/24 |

The new C-H run used 628 complementary lines and 630 after structural
completion. Strict line and doorway incidence was recalculated on the
new polygons with rational predicates. The final map independently
passed clearance on all 133 lines. The reduction uses the existing
single-line unrestricted structural deletion procedure in sheaf order.
The 133-line result is the outcome of that procedure and these coverage
requirements.
The matched Mode A replay used the same current preparation and sheaf
reduction entry points as Mode B. It independently certified at 34 lines
with a different candidate inventory from archived C-H. The atlas uses the
archived C-H inventory in its comparison panel.

## Reproduce

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_face_extension \
  --manifest "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json" \
  --replay-archived-cover \
  --output diagnostics/strict-generalisation/flat40-face-extension-replay
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_face_extension_diagnostics \
  --manifest "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json" \
  --output diagnostics/strict-generalisation/flat40-face-extension-replay
```

The completed run is in
`diagnostics/strict-generalisation/flat40-face-extension-cover-2/`.
Open `face_extension_complete_atlas.pdf` for all 14 vector pages.
The full arrangement and start-state provenance are in `arrangement.json`,
the overlap and incidence results in `coverage.json`, and the axial
selection certificates in `selection.json`.
