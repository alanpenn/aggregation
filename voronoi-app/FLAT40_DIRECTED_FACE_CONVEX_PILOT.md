# Flat 40 directed face-extension pilot

The crawler completed valid circuits in both handedness conventions.
The full enumeration remains unfinished. This run deliberately stopped
at a recorded budget and publishes a **checkpointed sample**, with the
exact remaining path stacks and starting positions.

## Verified source and search

The run verified the corrected Flat 40 records against the shared
SHA-256 migration inventory. Directed polygons were constructed from
archived occupied and accessible geometry alone. The frozen axial lines
entered only the later local incidence diagnosis and visual overlays.

The reference crawler's transition and closure code was shared with
the checkpoint iterator. An outward-rounded spatial index prefilters
segment pairs, and exact rational intersections still decide noding.
Both reference fixtures passed before and after the Flat 40 run.

| Search quantity | Count |
|---|---:|
| Physical boundary segments, including frame | 496 |
| Exposed occupied-face segments within those | 413 |
| Extensions with originating face and admissible hand | 568 |
| Exact junctions shared by multiple tracks | 3,286 |
| Directed subedges before contextual pruning | 12,152 |
| Explored path prefixes | 36,000 |
| Admissible outgoing decisions across explored prefixes | 36,836 |
| Rejected outgoing decisions | 88,221 |
| Dead-end path prefixes with no valid closure | 998 |
| Accepted closed directed paths, deduplicated by exact ordered state | 604 |
| Distinct validated polygons | 236 |

No rejection was recorded at the exact repeated-state gate in the
sampled prefixes. Earlier turn, side, and active-support rules can prune
a route before that gate. Branching retains all admissible successors.
The checkpoint journals contain rejected alternatives, valid closures,
exact directed path prefixes and the pending DFS stacks.

The global schedule spent 12,000 prefixes per hand. It completed two
right-hand and three left-hand origins out of 1,064 per hand, with four
pending prefixes per hand in the current origins. An independently
labelled schedule around 257 spent 6,000 prefixes per hand. It completed
14 and 11 local origins, respectively, out of 27 per hand, with three
pending prefixes per hand. These schedules are saved independently.
They are a bounded exploration of two start orders and provide no full
search completeness claim.

## Geometric checks and overlap

All 236 output polygons independently passed convexity, exact
accessible containment, occupied-cell intersection, island exclusion
and outward support checks. The completed family contains 181 polygons
strictly contained in another completed polygon. The independent
enlargement test proved non-maximality for 189 and saved a witness for
each. Forty-seven have positive-length physical boundary contact on
every facet. That is a sufficient global maximality certificate for
those 47 polygons. A complete enumeration could return more regions
and additional paths. The 236 polygons are kept in the plots so the
visual record preserves both valid circuits and maximality failures.

The integer overlay was constructed only after crawling. It labels
exact faces by multiplicity and verifies both domain area and the
multiplicity-weighted sum of polygon areas.

| Measure | Archived | Previous extension cover | Current directed sample |
|---|---:|---:|---:|
| Region count | 292 | 2,201 | 236 |
| Accessible-space coverage | 100% | 100% | 44.53367% |
| Maximum overlap | 11 | 11 | 129 |
| Area-weighted mean overlap | 3.33140 | 3.98633 | 20.45926 |
| Non-maximal polygons proved | 292 | 2,200 | 189 |
| Occupied-interior or island violations | 0 | 0 | 0 |

The archived coverage and maximum were independently replayed. The
292 archived enlargement witnesses are saved alongside the earlier
experiment's 2,200 verified precedents. These are certificates for the
specific tested polygons, separate from the incompleteness of the new
enumeration.

Flat 40 accessible area is approximately 7,932.07115 square units. The
sample covers 3,532.44225 and leaves 4,399.62890 uncovered in four
components joined by positive-length accessible edges. No filler
polygons were added. The nonzero minimum multiplicity is 1 and the
area-weighted median is 0, reflecting uncovered area. The full exact
distribution and gap geometry are in `coverage.json`. The high
maximum reflects concentrated, frequently nested outputs in the
sampled areas. It should not be interpreted as a full-cover statistic.

## Handedness and region 257

Of the sampled regions, 153 have a right-hand path and 110 a left-hand
path, with 27 found by both. Right-hand paths add about 74.34262 square
units beyond the left-hand sample and left-hand paths add about
85.18532 beyond the right-hand sample. This demonstrates distinct
coverage contributions in the explored family. Necessity in a
completed family remains unresolved.

On accepted paths, there were 573 right-hand and 331 left-hand turns
from one extension to another at a junction strictly in open space.
These occurred on 340 right-hand and 198 left-hand paths. This
counts transitions on paths, including distinct starts that generate
the same polygon.

Thirty-six sampled polygons overlap archived region 257. Twenty-one
have right-hand provenance only, eight left-hand only, and seven
both. Twenty admit a certified convex enlargement and 16 have a
global facet-contact maximality proof. Candidate 1435 strictly
traverses all 36, and 1509 traverses 34. These facts describe the
sample and do not establish either candidate's redundancy. The
atlas shows a local generating path and a non-maximality witness.

## Resume

The verified inputs, exact oriented support network, compressed
per-hand search journals, completed paths, geometry and certificates
are in `diagnostics/strict-generalisation/directed-face-convex-flat40-1/`.
The global runner resumes the saved exact stacks using the same
crawler and checkpoint code. Further budget adds work to the
existing journals:

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
out=diagnostics/strict-generalisation/directed-face-convex-flat40-1
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_oriented_crawler \
  --manifest "$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json" \
  --output "$out" --states-per-hand 12000 --batch 1000
```

The current 12-page atlas is vector throughout. Seven focused tests
passed, including the five earlier fixture tests, checkpoint
equivalence and archived Flat 40 output checks. No axial reduction
was run. Production code and earlier experimental outputs were
preserved.
