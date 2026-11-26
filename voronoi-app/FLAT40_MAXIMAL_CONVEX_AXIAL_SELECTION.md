# Flat 40 axial selection with the certified maximal convex cover

Replacing the archived 292-region cover with the complete 596-region maximal convex cover changed both reduced axial maps from **34 to 31 lines**. Both 31-line maps traverse all 596 designated regions and pass exact clearance, all 100 doorway requirements, network connectivity and independent winding rank 24/24. They each traverse 288 of the archived 292 polygons.

[14-page vector atlas](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/flat40-maximal-convex-axial-selection-atlas.pdf) · [Exact comparison and structural certificates](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/comparison.json).

## Frozen inputs and feasibility

The original corrected settlement, 1,534 exact candidate intervals and identifiers, doorway link sets, graph, winding validator, priority rules, repair procedure and bounded exchange settings were held fixed. Angular doorway entrance incidence and metric stops remained on the archived routing protocol for every map. The 44-line strict backward map and 33-line Algorithm D map remained archival controls. The certified polygons were loaded by their exact canonical hashes. An independent rational overlay reproduced the saved multiplicity areas and exact zero uncovered accessible area without rerunning the convex crawler.

Both incidence matrices were recomputed from exact geometry using positive-length interior traversal. They exclude boundary-only and vertex-only contact.

| Requirement | Archived cover A | Maximal cover B |
| --- | ---: | ---: |
| Exact polygons | 292 | 596 |
| Candidate–region incidences | 23,574 | 55,757 |
| Fewest traversing candidates per polygon | 3 | 23 |
| Most traversing candidates per polygon | 226 | 222 |
| Polygons with zero or one candidate | 0 | 0 |

The same 628-line complementary pool started each treatment. The archived cover required adding candidate 1212 for region 233 before deletion. The maximal cover required no repair. Both archived final maps and their pre-exchange inventories reproduced exactly. The new maps reached 31 lines during deletion. Their accepted exchanges changed line identity while leaving the count at 31. [Archived matrix](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/incidence-A.json) · [Maximal matrix](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/incidence-B.json) · [Input hashes](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/provenance.json) · [Selection configuration](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/configuration.json).

## Cross-cover and structural results

| Map | Lines | Archived A | Maximal B | Doorways | Components | Independent winding | Intersections | Uniquely traversed in designated cover | 1509 retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Archived C-H | 34 | 292/292 | 596/596 | 100/100 | 1 | 24/24 | 98 | 41 | Yes |
| Maximal C-H | 31 | 288/292 | 596/596 | 100/100 | 1 | 24/24 | 90 | 44 | No |
| Archived C-S | 34 | 292/292 | 596/596 | 100/100 | 1 | 24/24 | 98 | 39 | Yes |
| Maximal C-S | 31 | 288/292 | 596/596 | 100/100 | 1 | 24/24 | 89 | 39 | No |

Both maximal-cover maps miss archived regions **49, 140, 233 and 257**. Their exact polygon union has area approximately **64.703206 square units**. This is the union of archived polygons without a selected interior traversal. It measures constraint coverage rather than accessible-area loss. In both archived maps, those regions were uniquely traversed by 822, 1072, 1212 and 1509, respectively. [Archived coverage exceptions map](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/14.pdf).

C-H shares 29 lines across the covers. Its archived-only lines are 822, 1072, 1212, 1453 and 1509. Its maximal-only lines are 824 and 1410. C-S shares 30 lines. Its archived-only lines are 822, 1072, 1212 and 1509. Its maximal-only line is 824. On the maximal cover the two procedures differ by one substitution. C-H selects 1278 where C-S selects 1422. The common three-line reduction is a cover effect under both procedures. The remaining difference in line identity and movement is heuristic-sensitive. This experiment establishes feasible maps under the specified selectors. It does not establish the global minimum line count.

Clipped lengths are descriptive. They are 1,725.209 and 1,616.870 for archived and maximal C-H, and 1,736.389 and 1,627.923 for archived and maximal C-S. The exact midpoint records, graph degrees, transverse intersections and coverage redundancy are available with the selected inventories.

## Region 257 and candidate 1509

Candidate 1509 is the only selected traversal of archived region 257 in both archived maps. Removing it alone from either original inventory leaves all doorways, a connected graph and independent winding rank 24/24. It removes exactly one archived coverage constraint and zero maximal-cover constraints. Candidate 1435 does not strictly traverse archived region 257. It does traverse all 16 maximal polygons overlapping the archived region, while 1509 traverses 14.

Over the complete frozen matrices, 1509 traverses 15 archived and 43 maximal polygons. None of its 43 maximal incidences is unique within either archived selected inventory. Both maximal-cover selectors delete 1509 during direct reduction, and both final maps independently satisfy every designated requirement. This establishes dispensability for these two outcomes. [Enlarged vector comparison](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/10.pdf) · [300 dpi local map](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/region-257-300dpi.png).

## Doorway movement

Every map reaches every one of the 4,950 unordered doorway pairs. The archived maps replayed with zero angular error and a maximum metric difference of 2.85 × 10⁻¹⁴ in saved route costs.

| Map | Angular mean / median / p95 / max | Metric mean / median / p95 / max |
| --- | --- | --- |
| Archived C-H | 0.88167 / 0.83893 / 1.98081 / 3.43462 | 48.78003 / 47.63160 / 88.59845 / 118.11961 |
| Maximal C-H | 0.87806 / 0.79264 / 2.11360 / 3.43462 | 48.42977 / 47.27533 / 87.08686 / 117.35502 |
| Archived C-S | 0.88672 / 0.90146 / 2.00299 / 3.43462 | 49.22705 / 47.97983 / 89.94621 / 118.11961 |
| Maximal C-S | 0.89900 / 0.88152 / 2.11360 / 3.43462 | 48.61761 / 47.48279 / 87.75791 / 117.35502 |

The paired comparison uses archived C-H. Counts treat differences within 10⁻⁹ as unchanged. The p95 deterioration is calculated among worsening pairs.

| Map and cost | Improved | Worsened | Unchanged | Mean difference | p95 deterioration | Worst deterioration and doorway indices |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Maximal C-H angular | 677 | 606 | 3,667 | −0.00361 | 0.88152 | 1.16056 · 12, 80 |
| Maximal C-H metric | 1,547 | 433 | 2,970 | −0.35026 | 2.44459 | 14.17207 · 75, 95 |
| Archived C-S angular | 58 | 296 | 4,596 | +0.00506 | 0.58742 | 0.80249 · 9, 66 |
| Archived C-S metric | 189 | 716 | 4,045 | +0.44703 | 12.91780 | 12.91780 · 66, 67 |
| Maximal C-S angular | 468 | 765 | 3,717 | +0.01734 | 0.88152 | 1.16056 · 12, 80 |
| Maximal C-S metric | 1,498 | 640 | 2,812 | −0.16242 | 9.46324 | 14.29422 · 69, 95 |

The maximal cover makes geographically more numerous but more heavily traversed polygons available as selection constraints. The resulting maps are smaller under both procedures and exhibit different movement trade-offs. Maximal C-H lowers both mean costs while raising the angular p95. Maximal C-S lowers mean metric cost and raises mean angular cost against archived C-H. [Full route arrays, paired differences, and worst-pair records](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/movement.json).

## Reproducibility

The focused suite passed 11 tests. A separate replay reproduced both incidence matrices and all six start and selection records byte for byte. Logging every direct deletion and exchange validation proposal also preserved the four selection records byte for byte. The original datasets and production algorithms were preserved.

[Regression results](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/regression-results.txt) · [Determinism replay](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/determinism-replay.log) · [Full proposal replay](diagnostics/strict-generalisation/flat40-maximal-convex-axial-selection-1/proposal-replay.log).
