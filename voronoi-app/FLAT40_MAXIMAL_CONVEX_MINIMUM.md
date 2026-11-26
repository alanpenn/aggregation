# Further reduction of the Flat 40 maximal-cover axial maps

**Certified bounds for the frozen pool are 19–29 lines.** The bounded search found two certified 29-line maps. Both satisfy all 596 exact maximal convex-region requirements, all 100 doorway incidences, one connected axial component, exact clearance and independent winding rank 24/24. The exact integer lower-bound certificate leaves an optimality gap.

[Vector atlas](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/flat40-maximal-convex-minimum-atlas.pdf) · [Certified inventories and exchange paths](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/combined-results.json) · [Search configuration](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/configuration.json).

## Frozen controls and direct deletion

The 596 canonical region IDs and 1,534 frozen candidate intervals matched the previous experiment. Recomputing exact candidate incidence reproduced its matrix. Both 31-line inventories reproduced their independent certificates. Their intersection has 30 lines, and their union has 32. The differing entries are C-H candidate 1278 and C-S candidate 1422.

Every attempted single deletion failed. In each control, 30 of 31 deletions fail independent winding, and 19 fail winding alone. Removing candidate 1054 fails only doorway 54. Removing 1137 disconnects the selected graph and also fails winding, convex coverage and doorway requirements. Direct deletion establishes local irreducibility at these two inventories.

| Failed requirements | C-H deletions | C-S deletions |
| --- | ---: | ---: |
| Winding only | 19 | 19 |
| Convex coverage and winding | 4 | 3 |
| Doorway and winding | 1 | 2 |
| Convex coverage, doorway and winding | 5 | 5 |
| Convex coverage, doorway, connectivity and winding | 1 | 1 |
| Doorway only | 1 | 1 |

[Full C-H per-line dependencies](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/B-C-H-direct.json) · [Full C-S per-line dependencies](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/B-C-S-direct.json).

## Cardinality-reducing exchanges

The original two-for-one scans checked all 465 removed pairs and all 1,503 available replacement IDs per control, giving 698,895 proposals per control. Necessary incidence screening used exact region and frozen doorway candidate sets. The surviving proposals were checked for connectivity and winding, and accepted maps were independently certified. Geometry and length played no role in screening.

Each original map yielded 24 successful exchanges across three removed pairs. Every successful pair contains candidate **957** and one of **1519, 1531 or 1532**. Both controls have the same successful removed-pair and replacement patterns, and their 30-line descendants retain the respective 1278 or 1422 starting distinction.

| Removed pair | Certified replacements per control |
| --- | --- |
| 957, 1519 | 349, 364, 367, 1389, 1391, 1425, 1427, 1481, 1501, 1502, 1503, 1504 |
| 957, 1531 | 364, 1389, 1502, 1503, 1504 |
| 957, 1532 | 364, 1389, 1391, 1501, 1502, 1503, 1504 |

Four 30-line maps were chosen deterministically by taking the first certified replacement from the first two successful removed pairs per control. Both branches that replace **957 and 1531 with 364** admit a second exchange. It replaces **45 and 1519 with 1064**, producing the two 29-line maps. The other two sampled 30-line maps gave no further decrease. The 29-line inventories retain their single alternative, 1278 or 1422.

One 29-line map received a complete direct-deletion and two-for-one scan. Neither found a smaller map. Its three-for-two search stopped at 12,000 incidence- and ray-screened structural trials, having exhausted 47 removed triples and reached part of the next. No successful triple exchange was found in that prefix. Four-for-three and the remaining 29-line neighbourhoods were outside the bounded scan. [29-line pair scan](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/descent-29-two-for-one.json) · [Three-for-two checkpoint](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/descent-29-three-for-two.json).

## Alternative maps and the sampled plateau

The complete one-for-one neighbourhoods of the two original controls contain **719 other distinct valid 31-line maps** in the full frozen candidate pool. Across those 719 maps and the two controls, the intersection of their selected inventories is empty. This demonstrates alternative choices for every line within the defined neighbourhood. It makes no claim about line interchangeability under simultaneous substitutions.

The first eight distinct alternatives in lexicographic candidate-ID order received complete two-for-one scans. Those scans found 192 further distinct 30-line maps. Together with the 48 from the two original controls, this gives **240 distinct 30-line maps**. The same 24 successful pair/replacement patterns appeared in each of the ten scanned 31-line parents. The two 29-line descendants came from separate follow-up scans. The cardinality of 31 was a heuristic plateau for these controls, while 29 remains a feasible upper bound.

## Exact lower bound

A rational dual certificate on the convex and doorway incidence requirements proves a lower bound of **17**. Adding 384 necessary winding-ray requirements raises the independently checked bound to **19**. For each of 24 internal occupied blocks, the required enclosing bounded face contains that block’s winding witness. Each of 16 exact forward rays from the witness must cross the face boundary, so at least one chosen axial interval intersects it. A true winding certificate implies all these ray requirements.

The final nonnegative integer weights charge each candidate at most 100,000,000 units across the requirements it can meet. All requirements together carry 1,802,266,642 units. Any valid map must therefore use at least 19 candidates. This check uses integer arithmetic across all 1,534 lines. The ray constraints are necessary conditions for winding. The full bounded-face winding validator still certifies each accepted map. [Ray geometry and integer proof](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/winding-ray-bound.json) · [Independent weight check](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/dual-verification.json).

## Frozen doorway routing

All 244 maps, including both 31-line controls, reached all **4,950 unordered doorway pairs** in both movement modes. The 242 smaller maps all had higher mean angular and metric cost than the 31-line C-H control. The smallest maps had slightly lower angular p95, alongside worse mean angular and metric costs. The labels 29-H and 29-S identify their originating controls.

| Map | Angular mean / median / p95 / maximum | Metric mean / median / p95 / maximum |
| --- | --- | --- |
| 31 C-H | 0.87806 / 0.79264 / 2.11360 / 3.43462 | 48.42977 / 47.27533 / 87.08686 / 117.35502 |
| 31 C-S | 0.89900 / 0.88152 / 2.11360 / 3.43462 | 48.61761 / 47.48279 / 87.75791 / 117.35502 |
| 29-H | 0.89066 / 0.87089 / 2.10711 / 3.71120 | 49.25194 / 48.08761 / 89.79262 / 118.71808 |
| 29-S | 0.91318 / 0.90738 / 2.10711 / 3.71120 | 49.37243 / 48.27350 / 90.02546 / 118.71808 |

| Comparison with 31 C-H | Improved | Worsened | Unchanged | Worst deterioration and doorway indices |
| --- | ---: | ---: | ---: | --- |
| 29-H angular | 416 | 403 | 4,131 | 1.29741 · 17, 86 |
| 29-H metric | 38 | 1,008 | 3,904 | 15.63789 · 17, 72 |
| 29-S angular | 440 | 781 | 3,729 | 1.60575 · 48, 66 |
| 29-S metric | 258 | 1,498 | 3,194 | 15.63789 · 17, 72 |

Across the 242 smaller inventories the mean angular cost ranges from 0.88677 to 1.03587, and the mean metric cost from 48.88129 to 50.29226. [All route arrays, summaries and paired counts](diagnostics/strict-generalisation/flat40-maximal-convex-minimum-1/movement.json).

## Inputs for the configurational programme

- **Axial-line graph.** Reuse the exact intervals and candidate IDs, the frozen intersection records, and [candidate_graph](src/voronoi_app/exact_axial.py#L105). Keep the distinction between the full candidate graph and a selected-map graph.
- **Axial segments.** Reuse the exact intersection-split coordinates and line owners from [MasterNetwork](src/voronoi_app/batch_routing_reference.py#L49). Its edges are the atomic segments. Define the segment-as-node graph and turn-weight convention explicitly before comparing means or centrality.
- **Maximal convex-space graph.** Reuse the canonical rational polygon registry and the exact [convex intersection and area functions](experiments/flat40_region257_inspection.py#L40). A spatial bounding-box filter can generate possible pairs, followed by exact positive overlap area to define each edge.
- **Measures.** Reuse the NetworkX-backed connectivity, depth and choice implementations in [analysis.py](src/voronoi_app/analysis.py). Its integration implementation is inverse mean depth with an offset, despite the RA wording in the docstring. Freeze integration and betweenness normalizations, distance weighting and disconnected-component treatment before calculating Pearson intelligibility or collating the terrain and seed experiments. The verified cross-terrain source inventory provides the basis for stratifying the available settlements.

Production code and the archived 31-line results were preserved. The focused regression suite passed nine tests.
