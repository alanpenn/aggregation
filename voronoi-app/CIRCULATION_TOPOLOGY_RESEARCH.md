# Generalized circulation topology: Hill 42 and Y 42

## Purpose and scope

This is an experimental topology validator. It does not change the
settlement, production axial generator, selector, or saved selections. The
derived classification preserves each original cell ID and its original
`building`, `dyad_open`, or `unfilled_open` class.

The open-cell graph includes every geometrically open Voronoi cell, including
unfilled cells. Two open cells are edge-adjacent only when their polygon
boundaries share positive length. The largest edge-connected component is
main; ties are broken by sorted cell IDs. Every other component is treated as
effectively occupied for the topology and clearance tests.

Original building cells are first grouped by any shared boundary contact,
including vertex contact. Each excluded open component is similarly grouped
by face or vertex contacts. It is merged into a building block only when it
touches exactly one such block; with no or multiple contacts it is preserved
as a distinct effectively occupied block and its reason is recorded. Any
resulting occupied component touching the exterior boundary of the union of
all cells, including at a vertex, is merged into a special boundary block.

Independent circulation holes are enumerated from interior rings of the main
open-space union; their geometry is compared with the derived occupied blocks.
For each internal block, selected lines are first checked against the main
open component and all effectively occupied cells. Rejected lines do not
participate in ring validation. The remaining exact-rational linework is
noded and traversed into bounded faces. A block has a circulation witness
only when an exact positive-winding face contains the entire block, including
every cell-boundary segment; containing only the block's representative point
is insufficient. The winding vectors of these full-block faces are also
ranked over the rationals. A map satisfies circulation preservation only when
that rank equals the number of internal blocks; multiple blocks inside one
face do not count as independent cycles.
Hole and block counts are derived from geometry; no expected ring count is
hard-coded.

The original cell coordinates are binary64 Voronoi-overlay coordinates.
Cell adjacency, block contact, component unions, hole extraction and outer
boundary are therefore GEOS-based. Axial linework predicates, noding,
face-winding checks and clearance predicates use exact rational values of
those stored binary64 coordinates. This is certification relative to the
constructed GEOS domain, not an independently exact Voronoi overlay.

## Preserved inputs and selections

Inputs are verified by SHA-256 before analysis:

- Hill polygons and selected map: `hill42-corridor-pool.json`,
  `hill42-axial-map-data.json`.
- Y polygons and dyad cells: `axial-diagnostic.json`.
- Y certified candidates and selections: `prepared.json`,
  `selection-results.json`, and connectivity-backbone `results.json.gz`.

Each settlement has 484 cells: 100 original building cells, 100
dyad-associated open cells, and 284 unfilled open cells. The Hill selected
map is the saved 41-line map. Y comparisons use the saved unified greedy
29-line map, connectivity-prioritized 29-line map, and completed structural
66-line map.

## Results

| Settlement / selected map | Main open cells | Excluded open components | Resulting occupied blocks (boundary + internal) | Internal holes | Winding rank | Missing axial rings |
|---|---:|---:|---:|---:|---:|---:|
| Hill 42, saved 41-line map | 382 | 2, each 1 cell | 12 (1 + 11) | 11 | 0 / 11 | 11 |
| Y 42, unified greedy 29 | 384 | 0 | 4 (1 + 3) | 3 | 3 / 3 | 0 |
| Y 42, connectivity 29 | 384 | 0 | 4 (1 + 3) | 3 | 3 / 3 | 0 |
| Y 42, completed structural 66 | 384 | 0 | 4 (1 + 3) | 3 | 3 / 3 | 0 |

Hill's main component contains 100 dyad-open and 282 unfilled-open cells. Its
excluded singleton components are cells **335** and **383**. Cell 335 touches
exactly one original building block and is merged into the 21-cell boundary
block; cell 383 touches exactly one original building block and is merged into
an internal block. Neither requires an ambiguous standalone assignment. The
derived occupied blocks are the boundary block plus 11 internal blocks of
sizes `35, 14, 14, 4, 4, 4, 2, 1, 1, 1, 1`. They correspond one-to-one with
the 11 holes of the main open-space component. All 11 lack a valid
selected-network winding witness. Of the old 41 selected lines, 35 cross the
new effectively occupied space or leave the main accessible component and
are excluded from ring detection; the six remaining lines produce no
bounded axial faces. The old Hill output's `preserved_rings=11` was certified
against its earlier classification and is not evidence that those rings
survive this amended topology.

Y has a single open component containing all 384 open cells. Its four
occupied blocks consist of a 74-cell boundary block and three internal blocks
of sizes `24, 1, 1`. There are three independent holes, each associated with
one internal block.
All three Y selections preserve a separate positive-winding closed face for
each internal block, giving rank 3 / 3; no selected line is rejected by
effective-space clearance.

The Y maps produced 9, 42, and 495 bounded faces, respectively; the
validator identifies only the faces that witness internal blocks. These face
counts are not circulation-hole counts.

## Topology-validator tests

Deterministic tests cover:

- largest-component selection with deterministic tie breaking;
- inclusion of unfilled open cells in the graph;
- merging an excluded component with its unique building block;
- retaining and reporting an excluded component touching multiple building
  blocks;
- boundary-block classification from vertex-only contact;
- geometry-derived hole association and positive winding;
- missing-ring reporting when no closed route is present; and
- rejecting a selected line crossing an effectively occupied cell.

Two additional regressions verify that one face enclosing two occupied blocks
has winding rank 1, while two separate circuits have rank 2. Thus per-block
point coverage and graph-cycle counts cannot falsely certify independent
circulation classes.

The topology and exact-axial tests passed: **23 passed**. The full headless
suite passed **248 tests**, with 9 skipped and the slow default-Voronoi test
deselected. No production selection or generator code was changed.

## Hill 42: why blocks 2 and 17 lacked valid circuits

The preserved Hill geometry has 382 cells in its largest open component, two
excluded singleton open components, and 11 internal occupied blocks / holes.
Displayed labels **2** and **17** are singleton blocks `internal-8` (cell 209,
hole-6) and `internal-10` (cell 342, hole-9), respectively; neither shares an
occupied component with another building.

The old saved 41-line map yields 24 bounded faces before clearance filtering.
Its old point-style test reaches representative points in all 11 blocks, but
the corresponding winding-vector rank is only **5**. Only four whole blocks
are contained by face 5, whose point vector covers six blocks; its full-block
vector is therefore not six independent cycles. Across all unfiltered faces,
the whole-block rank is only **2**, and those faces use invalid lines. After
the amended exact clearance check, 35 of the 41 selected lines are rejected,
the remaining six form no bounded face, and the valid-map rank is **0 / 11**.

Face 5 contains the representative points of both target blocks, but contains
the whole block 2 cell **209** only partially; it does contain cell 342 for
label 17. Its boundary uses 30 selected candidates:
`88, 104, 129, 130, 154, 173, 199, 210, 220, 233, 238, 247, 250, 251, 260,
277, 306, 317, 321, 331, 352, 358, 359, 365, 372, 374, 383, 410, 7613,
12204`. Only `104, 154, 210, 247, 260, 359` pass exact clearance; `250` and
`358` leave the main accessible component, while the other 22 cross occupied
cell interiors. In particular, selected candidates `129` and `277` cross
cell 209, so the apparent circuit around label 2 is not geometrically valid.
The label-17 face witness is likewise unusable because its boundary is not
clear of other occupied cells.

This is not a late collective-removal failure. The saved pre-dominance set has
43 lines, of which only eight pass the amended clearance, and already has
rank **0 / 11**. Dominance then removes candidates `111` and `209`; the
41-line pre-collective and final sets both still have rank zero. No collective
removal was applied. The old validator's point-witness rule, together with the
old accessible-space classification and its unverified floating-point pool,
is the root cause: it counted covered obstacle points without requiring
independent, exact-clearance cycles around complete blocks.

The preserved full pool contains 15,659 candidates; 6,783 pass exact
clearance against the amended domain. Its 333 saved ring candidates include
only 84 exact-clearance-safe intervals, and those intervals have rank zero.
Nevertheless, exact safe cycles for both named blocks exist in the full pool:

| Block | Exact maximal candidate IDs | Lines | Total length |
|---|---|---:|---:|
| Label 2 / `internal-8` | `15536, 140, 606, 700, 12109, 13776, 13924` | 7 | 158.035145 |
| Label 17 / `internal-10` | `14270, 105, 560, 561, 13807, 13984, 14540, 15339, 15414` | 9 | 146.618016 |

These are 16 distinct added maximal intervals with total length **304.653160**.
Taken together, the target-only repair network has rank **2 / 11** and still
misses the other nine blocks: repairing labels 2 and 17 does not satisfy other
circulation requirements. For the other nine holes, exact maximal candidates
seeded from their accessible-domain boundaries provide 319 distinct intervals.
Together with the 16 target candidates, these yield an experimental
**335-line** cycle-only network of total length **6144.980697**, with exact
clearance, full-cell containment, and winding rank **11 / 11**. None of the
six legacy lines that happen to pass clearance is needed in this witness
network. This is a feasibility demonstration, not a minimality claim or a
production selection change.

The deterministic repair script verifies the preserved input hashes, reports
each block's cells, displayed labels and witness candidate IDs, checks every
candidate against exact clearance, and writes a numbered diagnostic map and
full JSON record. Its focused topology regressions pass: **8 passed**.
Artifacts are in
`/Users/ucft654/Developer/aggregation-circulation-repair-hill42-seed42-v4/`:

- `hill42-circulation-repair-diagnostic.png`
- `hill42-circulation-repair-results.json`

## Reproduction and artifacts

The runner is `python -m experiments.circulation_topology`; it creates a
fresh output directory only. It writes the complete derived classes,
open-cell adjacency graph, excluded-component assignments, occupied blocks,
hole/block associations, winding witnesses, selected line coordinates, input
hashes, and diagnostic maps.

The verified output is in
`/Users/ucft654/Developer/aggregation-circulation-topology-2026-11-18-v3/`:

- `topology-results.json`
- `hill-circulation-topology.png`
- `y-circulation-topology.png`

The results JSON SHA-256 is
`66572d101126d723bfcc05d173206f002af7d81a87fb4548cedef28a922b19b1`.

## Topology-rule axial-map visualizations

The latest maps are in
`/Users/ucft654/Developer/aggregation-circulation-topology-axial-maps-2026-11-18-v2/`.
Hill's plot distinguishes its six clearance-valid lines from the 35 rejected
legacy lines and shows that none of the 11 internal rings is preserved. The Y
plot separates the greedy, connectivity-prioritized, and completed structural
maps into comparable panels; all three preserve their three internal rings.

## Hill 42 witness-network reduction

The follow-up experiment starts from the saved 335-line repair. For each block,
it tries deleting candidates from longest to shortest, with candidate ID as
the tie breaker. A deletion succeeds if an exact bounded face still contains
the whole block. The union of the retained candidates is then checked for
exact clearance and full winding rank with the circulation validator.

The resulting subset uses **103 lines** with total length **1899.686819**,
down from 335 lines and 6144.980697. The exact validator reports winding rank
**11 / 11**, zero missing axial rings, and zero clearance rejections.
The local witnesses for displayed labels 2 and 17 shrink from 7 to 3
and from 9 to 4 lines, respectively.

Run with the preserved Hill inputs and the v4 repair JSON:

```sh
.venv/bin/python -m experiments.hill42_circulation_reduction \
  --hill-data "$HILL_INPUTS/hill42-corridor-pool.json" \
  --hill-map "$HILL_INPUTS/hill42-axial-map-data.json" \
  --hill-repair "$HILL_REPAIR/hill42-circulation-repair-results.json" \
  --output /tmp/hill42-circulation-reduction-results.json
```

The search is a greedy subset reduction of the saved repair candidates.
The experiment evaluates exact circulation and clearance. Route coverage,
connectivity, and angular fidelity are outside the measured criteria.
