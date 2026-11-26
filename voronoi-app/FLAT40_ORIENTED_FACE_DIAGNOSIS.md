# Flat 40 outward-facing support diagnosis

## What the original construction did

The archived generator canonicalised each exposed segment by sorting its
two endpoints. It kept the occupied-block and source-face IDs but did
not store the directed occupied-ring segment or an outward normal.
Both extensions were then inserted as undirected arrangement edges.
The recorded successors for a given handedness came from the exact
angular order. The growth step used unions of adjacent atoms and an
exact convexity test. It did not intersect the parent building
half-planes.

Reconstructing the semantic normals from the original occupied rings
revealed **zero inward-facing physical supports and zero inward-facing
physical originating faces** among all **2,201** polygons. Replaying
**452** local junction decisions from the archived incident orders
agreed with the saved walks. Opposite walks do not reverse occupied
side. The visible westward and southward polygons are on the other side
of the **extension** of some building faces. The extension is an
artificial arrangement edge in that position. Its parent face does not
physically touch the polygon.

There were 3,290 backward-facing polygon–parent associations involving
only artificial extension edges. Locally, 19 of the 23 polygons
overlapping region 257 had at least one such association (28 in total).
Two examples are:

| Region | Parent face | Minimum signed value | Maximum | Recorded role |
|---|---|---:|---:|---|
| `832e2f71317f1779` | `internal-8:14:439` | −5.54783 | 0 | Artificial extension 1 |
| `be803cfa4b93d618` | `internal-13:1:435` | −2.48063 | 0 | Artificial extension 0 |

The signed value is `n · (x − a)`, where `a` is on the physical face and
`n` is its exact outward normal, without length normalisation. Values in
the table are display approximations. The audit stores the exact
extrema, both original endpoint orderings, ring orientation, normals,
extension endpoints, and generating paths. The negative extrema in
these examples are geometric evidence about the same infinite line on
opposite sides. They are not errors in the original face's normal.

## Separate oriented experiment

The corrected version keeps a direction-invariant outward normal for
each occupied ring segment. A polygon can claim a physical support
only where its boundary has positive-length contact with that
physical face and all its vertices satisfy the outward half-plane.
The same test is applied to claimed originating physical faces.
Artificial edges retain their generating face and direction as
provenance. A backward-facing parent is explicitly recorded as
ineligible to act as a support. The algorithm does not impose remote
building half-planes on a candidate.

The independent replay tested convexity and exact convex union of
member atoms, accessible-domain partition edge incidence and area,
positive occupied-interior intersection, maximality against each single
adjacent atom, and full union coverage. It also rechecked clearance for
1435 and 1509. The checked construction remains maximal under single
adjacent-atom enlargement. It does not establish global convex
maximality under arbitrary merges or paths. Of the resulting polygons,
932 have no direct occupied-face support and are bounded by arrangement
or domain edges.

All 2,201 geometry IDs and rational outlines survived. The correction
changes how supports are interpreted, while exact covered area,
individual atomic multiplicities (1–11), and axial incidence are
unchanged. Both handedness conventions and both directions remain
represented. The fixtures cover opposing faces, concavity, vertex
contact, an occupied island, and reversal of a physical ring. All
seven focused tests passed.

## Consequence for region 257

Of the 23 new regions overlapping old region 257, 1435 strictly
traverses 18 and 1509 traverses 12. Five are covered only by 1509 in the
archived C-H map. There are eight such regions across the entire
face-extension cover. Those counts are unchanged by the oriented
classification. No reduced axial-map run was performed.

The 25-page vector atlas includes the matched before/after comparison,
one detailed page per local polygon with exact purple seed paths and
physical arrows, and the regenerated transparent and integer overlap
maps. The atlas and full rational records are in
`diagnostics/strict-generalisation/flat40-oriented-face-cover-1/`.
