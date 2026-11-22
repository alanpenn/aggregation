# Facewise dyad growth audit

The original Y 20 settlement is needed to establish its seed,
configuration, cell identities, parent choices and growth sequence.
The workspace and sibling research exports, the Downloads axial
snapshot, the known valley archive and repository history did not
yield an identifiable Y 20 record. The Downloads snapshot and
compressed Y axial fixture are seed 42. This audit does not assign
the Y 40 or Y 41 results to Y 20. The named Y 20 buildings and its
first invalid placement remain unverified, and no Y 20 map was
generated.

## Confirmed mechanism in Y seeds 40 and 41

I recovered the recorded parent choices by tracing the unmodified
slope-preference strategy. The trace was used only after the replay
matched the saved sites, ordered building IDs and original dyad
pairs, and every cell polygon matched its saved WKB bytes. I then
counted components after every placement using the topology
module's positive-length face graph over those saved polygons.

| Case | First bad dyad | First disconnected growth step | Zero-length parent links | Zero-length building links | Final assigned-open components |
|---|---|---|---:|---:|---:|
| Y 40 | 78 | 81 | 2 | 6 | 3 |
| Y 41 | 78 | 79 | 4 | 3 | 4 |

At Y 40 building 81, the recorded parent is cell 65, the new
open cell is 109 and the building cell is 175. Both required
faces have zero length. Their polygon distances are 2.958 and
7.940 coordinate units, respectively. At Y 41 building 79, parent
17 and new open cell 21 are 12.290 units apart, while building 42
shares a genuine face of length 1.252 with cell 21. Both openings
started separate components when appended.

The following table is **Y 40 only**. It illustrates why shared
earlier-open adjacency needs to be distinguished from connection
to the original seed component. The full Y 40 audit also found
invalid links at buildings 84 and 94.

| Building label | Building cell | Paired open cell | Parent open cell | Parent face | Building face | Reaches original open component |
|---:|---:|---:|---:|---:|---:|---|
| 78 | 219 | 65 | 64 | 3.381 | 0 | Yes |
| 81 | 175 | 109 | 65 | 0 | 0 | No |
| 82 | 5 | 20 | 42 | 3.802 | 0 | Yes |
| 87 | 153 | 131 | 109 | 5.337 | 3.839 | No |
| 95 | 14 | 37 | 16 | 2.947 | 0.581 | No |
| 97 | 307 | 417 | 439 | 4.610 | 0 | Yes |
| 98 | 11 | 15 | 16 | 2.862 | 0 | No |

Buildings 87 and 95 have two genuine required faces in Y 40.
They extend components that had already detached. The verified
prefix records give component counts, geometric contact types
and full-precision face lengths for all 200 placements.

## Why aggregation admitted these edges

`SlopePreferenceStrategy._build_adjacency` maps every SciPy
`voronoi.ridge_points` edge to a neighbour pair. The strategy
uses that graph both to choose a new open cell and to choose
its building. This graph describes the original Voronoi diagram,
including ridges outside the experiment canvas.

`ExperimentOrchestrator._finite_voronoi_polygons` extends infinite
rays, forms convex polygons and clips them to the canvas. The
topology stage then builds a geometric face graph using
`left.boundary.intersection(right.boundary).length > 0`. A point
contact has length zero. It can be a block contact in the separate
occupied-block rule. It cannot extend the face-connected open
graph.

The audit found 66 Y 40 and 69 Y 41 ridge neighbours without a
geometric face. Every raw finite ridge or infinite ridge ray in
those discrepancy sets clipped to zero length inside the canvas.
The broken placement links had empty boundary intersections.
Their positive polygon separation rules out a rounding tolerance
or point-contact explanation for these steps. The saved polygon
bytes matched reconstruction exactly. The demonstrated defect is
the use of unclipped adjacency during aggregation. Later topology
is detecting the missing faces under the intended rule.

Y 40's 57 excluded open cells include assigned cells 109, 131
and 152. Y 41's 119 excluded open cells include assigned cells
21, 43, 15 and 14. The faulty growth links explain how aggregation
entered disconnected open components in those cases. The later
counts also include unassigned cells, so the counts cannot be
attributed one-for-one to invalid dyads.

## Proposed correction and regression check

Compute the authoritative clipped polygon inventory before the
first dyad is placed. Extract the existing topology face predicate
into a shared adjacency helper and construct the placement graph
from the same polygon inventory. Pass that graph to
`SlopePreferenceStrategy` for the initial building, open growth
and paired-building checks. Preserve the chosen parent open-cell
ID at each successful placement. Downstream topology should use
the same saved polygon inventory and predicate. Keep the occupied
vertex-contact rule separate. Existing records should retain
their original geometry and placement history.

The regression test injects that proposed graph into an otherwise
unchanged strategy. It verifies that a vertex-only link is rejected
by the face predicate and that the actual recorded parents and
paired building cells have positive face lengths at every successful
placement. It also counts the face-connected components of every
assigned-open prefix. The audit and circulation test run passed
nine tests. No production aggregation function was changed.

## Supporting maps and data

- Y 40 [numbered settlement](diagnostics/facewise-growth-audit/Y-40-face-audit.pdf) · [before and after the first disconnect](diagnostics/facewise-growth-audit/Y-40-first-disconnect.pdf) · [all placements and ridge discrepancies](diagnostics/facewise-growth-audit/verified/converging_valleys-40.json)
- Y 41 [numbered settlement](diagnostics/facewise-growth-audit/Y-41-face-audit.pdf) · [before and after the first disconnect](diagnostics/facewise-growth-audit/Y-41-first-disconnect.pdf) · [all placements and ridge discrepancies](diagnostics/facewise-growth-audit/verified/converging_valleys-41.json)

Dashed red lines mark recorded links with no face in the saved geometry.
Solid teal marks actual shared faces. Both PNG and vector PDF copies
are saved. The verified JSON files link the corresponding settlement
records and their manifest hashes.
