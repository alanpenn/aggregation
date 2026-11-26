# Flat 40 resumed directed maximal-convex enumeration

The first resumed milestone established exact **100% accessible-space coverage** with 580 independently certified globally maximal polygons. The resumed ordinary search subsequently discovered the three-face triangle. The coverage certificate and an exhaustive catalogue are separate results. Pending prefixes may still yield other maximal polygons.

## Checkpoint provenance and starting states

The resumed run cloned the latest compatible systematic checkpoint into a new experiment directory. The original journal files and directed network passed SHA-256 comparison. The original 356-region registry reconstructed exactly from its journal closures, including every canonical polygon ID. The 23 input hashes were checked by the verified Flat 40 loader against the shared migration inventory. No journals were imported from the older 36,000-prefix run.

The unchanged network contains 413 exposed building faces, 83 external-boundary faces, 568 extensions and 12,152 directed subedges. Both hands have 1,064 distinct directed starts. Of these, 496 start at physical face endpoints and 568 start at extension landings on physical faces. Each landing gives a distinct closure anchor on its physical face. Pure extension-intersection subdivisions are excluded. The full inventory and per-origin restart status are in the [checkpoint audit](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/checkpoint-audit.json). [Original SHA-256 inventory](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/original-checkpoint-sha256.txt) · [Resumed journal SHA-256 inventory](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/journal-sha256.txt).

## Exact geometry and coverage

| Saved milestone | Explored prefixes | Certified maximal polygons | Exact coverage percentage |
| --- | ---: | ---: | ---: |
| Original checkpoint | 101,582 | 356 | 81.660873% |
| Resumed round 1 | 291,687 | 580 | 100% |
| Resumed round 2 | 587,264 | 596 | 100% |

The accessible area is approximately 7,932.071151 square units. The certified-union uncovered area is exactly zero at every resumed milestone. [Exact union and area by overlap multiplicity](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/coverage-maximal.json) · [Coverage progression](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/coverage-progression.json) · [Each polygon and all its saved generating paths](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/regions.json).

## Triangle and region 257

The earliest saved ordinary triangle closure is in `right/00311/000002.json.gz`, row 75. Right-hand origin 311 starts at directed edge 623 on physical face 136, a landing origin. It closed at prefix 219 for that origin. The triangle’s canonical ID is `fc7cc03eaec6da360a60abf19766450084bffcb362e4b33dfe3a297d78c8359a`. The 36.061877-square-unit triangle contributes exactly zero exclusive area to the resumed full cover. The milestone before its ordinary discovery already covered its entire area. [Discovery and all journaled triangle paths](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/triangle-discovery.json).

Region 257 is covered exactly. Candidate 1435 crosses all 16 certified maximal polygons with positive-area overlap with region 257. Candidate 1509 crosses 14 of those. This is a local strict-incidence comparison. [Per-polygon incidence](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/region-257-incidence.json) · [Exact region 257 overlap map](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/region-257-exact-multiplicity.pdf).

## Search engine and verification

The original directed geometric rules, path-dependent checks and commitment logic run for every expanded prefix. Bounded caches reuse exact face-side predicates and segment intersections. Exact closed bounding boxes avoid an intersection computation only when the boxes are strictly disjoint. There is no state merging, path pruning or geometry repair. Journals record exact outgoing decisions and the original DFS stacks.

On 24 sampled Flat 40 starts, the reference pass took 6.78 seconds and the cached pass took 2.21 seconds. Their compressed journals were byte-identical, including decisions, closure geometry, provenance and pending stacks. Exhaustive reference fixtures also matched exactly in polygons, directed paths, certificates and overlays. The focused suite passed 25 tests. Subsequent batches used four local worker processes with disjoint starting-origin ownership. Per-origin journal writes are atomic. [Cache verification](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/cache-benchmark-bounds.json) · [Regression results](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/regression-results.txt).

The [vector atlas](diagnostics/strict-generalisation/flat40-exhaustive-convex-1/flat40-exhaustive-convex-atlas.pdf) contains the exact coverage and multiplicity maps, both hands, alternative branches, region 257, and the triangle’s first recorded circuit. Production code and earlier experimental files were preserved. This run measured geometry and frozen axial incidence.

## Final enumeration status

Both hands exhausted every origin and every admissible branch. The saved DFS stacks are empty.

| Hand | Origins exhausted / started | Physical faces exhausted / started | Pending prefixes | Exhausted origins without a closure |
| --- | ---: | ---: | ---: | ---: |
| Right | 1,064 / 1,064 | 496 / 496 | 0 | 0 |
| Left | 1,064 / 1,064 | 496 / 496 | 0 | 0 |

The registry contains **596 globally maximal polygons** after **1,515,061 explored prefixes**. It records 12,916 distinct directed generating paths, with 6–130 paths per polygon. There are 0 proven non-maximal and 0 unresolved polygons.

Exact uncovered area is **0**. The maximum overlap is 39, the area-weighted mean is 9.464889, and the area-weighted median is 9. There are 0 uncovered components.

The triangle has 20 ordinary generating paths. The six reference face-endpoint starts account for 6 of the six expected discoveries.

Timed runner segments total 10.09 minutes, excluding the initial interrupted reference segment and atlas rendering. Peak resident memory for an individual parallel worker was 594 MB.
