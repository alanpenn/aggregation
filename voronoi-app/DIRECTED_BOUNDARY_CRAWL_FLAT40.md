# Directed physical-boundary convex-region pilot

## Exact L-room reference

The room is the polygon with vertices (0,0), (6,0), (6,2), (2,2),
(2,6), and (0,6). The two directions generate these rectangles
directly from the wall walks:

| Walk | Extension from the re-entrant corner | Rectangle | Area |
|---|---|---|---:|
| Anticlockwise, right hand | (2,2) to (0,2) | [0,6] × [0,2] | 12 |
| Clockwise, left hand | (2,2) to (2,0) | [0,2] × [0,6] | 12 |

The overlap is [0,2] × [0,2], of area 4. The union has area 20 and
equals the room. Area at multiplicity one is 16 and area at
multiplicity two is 4. Each rectangle also has a positive-length
domain-boundary contact on every facet. For this fixture those
contacts prove global convex maximality. No arrangement atoms were
constructed or merged for the reference.

## Construction

A physical face retains its occupied-block ID when one exists, its
exact endpoints in accessible-left ring orientation, and its fixed
outward normal. The directed states reverse traversal while retaining
the same outward half-plane. Ordinary turns must stay convex and
consistent with the previously accepted supporting faces. At a
re-entrant corner the crawler continues straight to the first exact
physical boundary hit. Other precomputed extensions do not act as
stops. The face catalogue records exact crossings and coincident
portions with them. Intersections with an already-traversed
extension can reject a self-crossing walk. At a hit the crawler
resumes wall-following using the least allowed signed turn.

Each originating boundary segment is tried in both directions.
Start points include wall endpoints and exact landing points where a
straight extension can reach a face interior. Walks must close in the
same directed face state and coordinate. The experiment checks simple
closure, positive area, convexity, exact containment, occupied-cell
intersection, and the active outward constraints. Identical
polygons retain all generating paths. Inclusion within the
completed family is the tested maximality criterion for Flat 40.
The pilot does not certify global convex maximality there.

## Flat 40 coverage gate

The same crawler tried 1,560 states on 496 boundary segments. Of
these segments, 413 have occupied-face provenance. There were 77
successful directed closures and **14 distinct, validated polygons**.
The following outcomes account for all attempted starts:

| Outcome | Starts |
|---|---:|
| Ordinary turn conflicts with an active half-plane | 770 |
| No convex departure at the physical hit | 487 |
| Extension conflicts with an active half-plane | 203 |
| Closed and validated | 77 |
| Closed candidate fails independent domain containment | 23 |

The independent overlay nodes the completed boundaries only after
construction. Exact signed boundary jumps distinguish accessible
area from occupied interiors and give integer region multiplicity.
Overlay connector edges have zero jump and are absent from the
crawler. Rational shoelace sums reproduce the archived accessible
area and the multiplicity-weighted sum of region areas.

| Area | Approximate square model units |
|---|---:|
| Archived accessible domain | 7,932.07115 |
| Covered exactly once | 505.71448 |
| Covered more than once | 0 |
| Uncovered | 7,426.35667 |

Coverage is **6.37557%**. Overlap is allowed by the construction. The
retained Flat 40 regions happen to have disjoint interiors. The
pilot fails the full-coverage gate.

No retained region overlaps the interior of archived region 257.
Its entire 27.22434 square model units are uncovered. The physical
contacts with buildings 70 and 76 correspond to directed face
segments 436 and 437. All four original endpoint starts on these
segments reached a physical boundary at which no convex departure
satisfied the active supports. Both that failure and the attempted
paths are shown in the final atlas page. This diagnoses the rule
implemented here, without ruling out every other directed physical
boundary construction.

No gap-filling regions were inserted. No axial-map reduction was
performed. Production code and earlier research outputs remain intact.

## Outputs and replay

- `diagnostics/strict-generalisation/l-room-directed-boundary-1/`
  contains the six-page reference vector atlas and exact marching states.
- `diagnostics/strict-generalisation/flat40-directed-boundary-1/`
  contains the six-page Flat 40 vector atlas, all attempted generating
  paths, and exact coverage and multiplicity polygons.

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
s=diagnostics/strict-generalisation
PYTHONPATH=src:. .venv/bin/python -m experiments.directed_boundary_reference \
  --output "$s/l-room-directed-boundary-replay"
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_directed_boundary \
  --manifest "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json" \
  --reference "$s/l-room-directed-boundary-replay/exact-reference.json" \
  --output "$s/flat40-directed-boundary-replay"
```
