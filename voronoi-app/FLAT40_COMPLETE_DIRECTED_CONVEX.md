# Flat 40 directed maximal-convex crawl

The checkpoint generated **356 independently certified maximal convex polygons**, covering **81.660873%** of corrected Flat 40’s accessible space. Both hands started on all 496 physical faces. The unresolved stacks preclude a conclusion about settlement-wide completeness.

## Inputs and traversal

The run loaded the saved corrected Flat 40 fixture through the existing verified study loader. The [exact network and provenance](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/geometry.json) record 23 verified input hashes, the migration manifest hash, source lineage and experimental code hashes. The network’s 496 physical faces comprise 413 exposed building faces and 83 exposed external-frame segments. Its 568 extensions and 12,152 directed subedges have exact rational endpoints.

The experimental crawler gives each physical face a fixed normal into accessible space. It permits approaches towards the originating building or external face, retaining the destination through intermediate junctions. Each hand has one permissible orientation along a given physical face. The schedule includes that orientation at its physical endpoint and at distinct extension landings, which can be closure anchors in the interior of a physical face. It uses unique directed starting-edge IDs within each hand. The full route, active supports and transition history survive each checkpoint. Prefixes with different histories stay distinct. A geometric region ID deduplicates only closed polygons.

The run allowed up to 48 additional explored prefixes per origin. Every admissible outgoing continuation discovered at an expanded prefix was explored or retained on the origin’s exact depth-first stack.

| Progress | Right hand | Left hand |
| --- | ---: | ---: |
| Physical faces started | 496 | 496 |
| Physical faces fully exhausted | 9 | 7 |
| Physical faces pending | 487 | 489 |
| Distinct starts initiated | 1,064 | 1,064 |
| Starts fully exhausted | 20 | 14 |
| Starts pending | 1,044 | 1,050 |
| Exhausted starts without a closure | 0 | 0 |
| Prefixes explored | 50,787 | 50,795 |
| Pending stack entries | 3,728 | 3,627 |

A pending entry is an unexplored prefix and can generate descendants. [Per-hand progress](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/progress.json).

## Validation and exact coverage

All 356 distinct closed polygons passed independent convexity, accessible containment, occupied-interior exclusion and oriented-support checks. The 1,305 distinct closed directed paths were checked for closure, handedness and commitment to the recorded destination. Every polygon facet had positive-length physical contact sufficient to block strict convex enlargement. There were zero proven non-maximal or unresolved closed polygons. The journal records 4,956 rejected intermediate turns during commitment and 20 invalid-cycle attempts. The four-building regression still exercises a premature second turn. The Flat 40 checkpoint gives evidence about the branches examined so far.

| Measure | Checkpoint |
| --- | ---: |
| Accessible area | 7,932.071151 |
| Covered area | 6,477.398576 |
| Uncovered area | 1,454.672574 |
| Coverage | 81.660873% |
| Uncovered components in the exact overlay | 31 |
| Maximum overlap multiplicity | 20 |
| Area-weighted mean multiplicity | 2.906042 |
| Area-weighted median multiplicity | 2 |

The overlap distribution includes uncovered accessible space at multiplicity zero. The all-valid and certified-maximal maps coincide at this checkpoint. Each gap is classified as search pending. No settlement-wide geometric counterexample has been established. The earlier 46.51435% committed checkpoint used a different starting schedule and prefix budget. The comparison does not isolate the contribution of external faces. [Exact areas, components and multiplicity geometry](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/coverage-maximal.json) · [Per-region certificates and paths](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/regions.json).

## Branching and region 257

There were 8,778 distinct branching prefixes and 265 prefixes where different outgoing edges led to distinct completed maximal polygons. The first atlas example is a right-hand junction near (71.920780, 61.700363) with continuations along directed edges 1852 and 10178, supported by faces 426 and 428. The two resulting polygons contribute approximately 219.814 and 1.370 square units exclusive of one another. Other polygons may cover those differences. Whether either branch is essential to settlement-wide coverage remains open. [Exact branch records](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/branch-alternatives.json) · [Branch comparison](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/branch-01.pdf).

The 13 certified maximal polygons with positive-area overlap with archived region 257 cover its entire area of approximately 27.224338 square units. Frozen candidate 1435 crosses all 13 through positive-length interior. Candidate 1509 crosses 11, and those 11 are also crossed by 1435. This is a local incidence result. The effect on the archived selection requirement for candidate 1509 remains unresolved. [Exact region 257 union](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/region-257-coverage.json) · [Per-polygon axial incidence](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/region-257-incidence.json) · [Enlarged vector map](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/region-257.pdf) · [300 dpi local image](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/region-257-300dpi.png).

## Fixture gate and reproducibility

All 14 reference fixtures were exhausted in both hands and achieved exact complete coverage using globally certified maximal polygons. The L room produced exactly the two expected rectangles with four square units of overlap. The concave external fixture produced completed paths with mixed building and external-extension turns in both hands. The reflection regression checks three fixtures in the test suite. The focused suite passed 23 tests. [Fixture certificates](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/fixtures.json) · [Regression results](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/regression-results.txt).

The [18-page vector atlas](diagnostics/strict-generalisation/flat40-complete-directed-convex-1/flat40-complete-directed-convex-atlas.pdf) contains physical normals, the extension network, paths in both hands, a committed approach, branch alternatives, all-valid and certified overlap maps, and the local region 257 analysis.

To resume, use the same source checkout, manifest and output path. The explicit budget applies to each unfinished origin. Use a single writer for this checkpoint. The journal appends new numbered batches, and a mismatched geometry or crawler code hash stops replay.

```sh
data_root="${AGGREGATION_DATA_ROOT:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data}"
export AGGREGATION_DATA_ROOT="$data_root"
out=diagnostics/strict-generalisation/flat40-complete-directed-convex-1
manifest="$data_root/migration-sha256-2026-11-24.json"
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_complete_directed_convex \
  --manifest "$manifest" --output "$out" --prefixes-per-origin 48
```

The previous pilot and archived inputs were preserved. No reduced axial-map selection was run.
