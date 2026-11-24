# Movement across the 128 minimum axial maps of Flat 40

The 128 structurally valid 34-line maps differ measurably in movement. The choice between 1278 and 1422 accounts for 98.69% of the variation in mean metric distance and 48.64% in mean angular depth. For both means the effects are mostly additive. The two best means occur in different maps, and the 33-line Algorithm D control still has better mean angular and metric results than any U3 map.

## Verified family and fixed choices

The restored corrected Flat 40 geometry and full 1,534-interval certified pool match the archived source and exact pool hashes. The replay independently checked the parents and U3, reproduced all 128 minimum inventories, and certified each map with the exact face validator. All 208 connected, incidence-complete 33-line candidates failed winding. Every retained factorial map has 34 lines, 292 strict convex regions, all 100 doorways, one connected component, independent winding rank 24/24 and exact clearance.

The mandatory-line hash initially differed because integer keys were sorted differently before and after JSON serialisation. The mandatory IDs and all their recorded evidence were identical. A canonical JSON comparison then matched every deterministic enumeration field, including the mandatory inventory, rejection counts and minimum-map certificates. Runtime is outside the replay comparison.

The seven-bit ID lists the factors in this order. A zero selects the lower candidate ID.

| Factor | Choice 0 | Choice 1 |
|---:|---:|---:|
| 1 | 492 | 493 |
| 2 | 640 | 739 |
| 3 | 965 | 1072 |
| 4 | 1128 | 1212 |
| 5 | 1226 | 1228 |
| 6 | 1278 | 1422 |
| 7 | 1410 | 1453 |

No candidate was added to the family. No movement outcome changed a selected inventory. Each angular and metric checkpoint uses the same ordered 4,950 unordered doorway pairs. Angular routing uses zero entry and exit turn costs and 90° units. Metric routing uses the finite certified regional connector graph, including feasible projections and interval endpoints.

[Verified binary inventory and structural certificates](inventory.json) · [Reproduced exact enumeration](reproduced-enumeration/results.json)

## Complete performance distribution

All 633,600 map–doorway-pair combinations were reachable under both definitions. The following are population summaries across the full 128-map family.

| Response | Min | Max | Mean | Median | Population SD | IQR | 5th percentile | 95th percentile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Angular mean | 0.8775 | 0.8920 | 0.8850 | 0.8853 | 0.00389 | 0.00517 | 0.8777 | 0.8917 |
| Angular p95 | 1.9808 | 2.0402 | 2.0109 | 2.0168 | 0.02242 | 0.04469 | 1.9808 | 2.0402 |
| Metric mean | 48.7698 | 49.2902 | 49.0292 | 49.0284 | 0.22717 | 0.43501 | 48.7725 | 49.2868 |
| Metric p95 | 88.5985 | 90.0414 | 89.3336 | 89.3414 | 0.64943 | 1.23184 | 88.5985 | 90.0414 |
| Axial length | 1,725.209 | 1,774.447 | 1,749.828 | 1,749.828 | 13.94756 | 19.91815 | 1,726.080 | 1,773.575 |

| Criterion | Representative map | Best value | Tied inventories |
|---|---|---:|---:|
| Mean angular | `0000001` | 0.877504 | 4 |
| Mean metric | `0110000` | 48.769787 | 4 |
| Angular p95 | `0000000` | 1.980813 | 32 |
| Metric p95 | `0000000` | 88.598453 | 32 |
| Total length | `0011001` | 1,725.208834 | 1 |
| Balanced means | `0000001` | 0.015595 | 4 |

The balanced score gives equal weight to the two means after min–max normalisation within U3. The Pareto frontier contains 24 maps at six distinct mean-cost points. These are finite-family optima. The full candidate inventories and bit vectors for every optimum and Pareto map are in the performance record. The complete movement checkpoints include median and maximum costs, excess above the full certified reference and worst doorway pairs for each selection.

[Performance and exact inventories](performance.json) · [128-row comparison CSV](performance.csv) · [Route indices and doorway ordering](routing-index.json) · [Pareto and factorial plots](movement-factorial.pdf)

## Factorial effects

The entries are mean changes when switching from the lower to the higher candidate ID, averaged across 64 matched contexts. Lower angular and metric costs are preferable.

| Choice switched | Angular mean | Angular p95 | Metric mean | Metric p95 | Axial length |
|---|---:|---:|---:|---:|---:|
| 492 → 493 | +0.00114 | +0.00265 | +0.05085 | +0.14362 | +0.091 |
| 640 → 739 | +0.00408 | +0.04230 | −0.00749 | 0 | +1.557 |
| 965 → 1072 | +0.00358 | +0.00357 | −0.00769 | 0 | −15.033 |
| 1128 → 1212 | 0 | 0 | 0 | 0 | −20.665 |
| 1226 → 1228 | 0 | 0 | 0 | 0 | +0.712 |
| 1278 → 1422 | +0.00543 | +0.01041 | +0.45134 | +1.29018 | +11.052 |
| 1410 → 1453 | −0.00022 | 0 | +0.00302 | −0.01507 | −0.128 |

Main effects explain 99.434% of angular-mean variance and 99.9985% of metric-mean variance. Factor 6 dominates metric mean and metric p95. Factors 2 and 3 add substantial angular-mean effects. Factor 2 accounts for 89.0% of angular-p95 variance. Angular p95 is more context-sensitive than either mean, with 3.88% of variance from pairwise interactions and 0.78% from higher orders.

The largest interaction in the two means is between factors 3 and 6. Switching to 1422 raises angular mean by 0.00602 when 965 is selected and by 0.00485 when 1072 is selected, averaging over the remaining factors. The corresponding metric increases are 0.45303 and 0.44964. Neither interaction changes which candidate is preferable in that pair. The sign of every detectable mean main effect holds across all 64 contexts. The report uses orthogonal finite contrasts with no inferential significance tests. The data gives all 21 pairwise contrasts, higher-order terms, variance shares and conditional ranges.

[Complete factorial contrasts and geometry predictors](factorial.json)

## Local geometry, winding and doorway effects

Of the five pairs with movement effects, the longer alternative improved mean angular depth once and mean metric distance twice. Greater full-pool transverse degree improved angular mean in two and metric mean in one of five non-tied comparisons. Counts of regions, doorways, mandatory intersections, distinct transverse families and longitudinal spread are available by line. The seven comparisons yield descriptive associations and do not independently establish predictive accuracy. Factors 4 and 5 did not measurably alter any doorway route in any context. If minimising line length alongside movement, choosing 1212 and 1226 is therefore supported throughout this family.

Without either 1278 or 1422, every one of the 64 common contexts retains strict coverage, doorway incidence and a connected network. In each case, blocks 5 and 12 remain enclosed but share one winding class, and rank falls to 23. Either candidate restores the missing independent separation. With all other choices set to zero, 1278 serves winding boundaries of blocks 2, 4, 5, 12 and 13. The 1422 boundaries are for blocks 2, 5, 11, 12 and 13. They therefore achieve equal rank with different circuit geometry. Other retained lines cover their differing regions. For example, candidate 1369 covers regions 228 and 229 when 1278 is selected, and candidates 1080, 1195 and 1244 cover regions 196–198 when 1422 is selected. The machine record lists the compensating lines for every context.

Changing 1278 to 1422 affected 254 doorway pairs angularly and 678 metrically in at least one context. The maximum absolute changes were 0.8025 angular units for buildings 10–67 and 12.918 metric units for buildings 35–67. In the displayed zero context, the latter journey goes from 64.168 to 77.086 units. Neither endpoint was within 10 units of either alternative for eight affected angular pairs and zero affected metric pairs. A small geometric shift can reach further. The near-parallel 492/493 switch affected 966 metric pairs, including 133 with both ends more than 10 units from either line. All pairs' absolute changes, context counts and origin/destination building summaries are recorded.

[Fixed and context-dependent candidate geometry](candidate-geometry.json) · [1278/1422 circuit and compensation audit](dissimilar-pair.json) · [Certified route comparison](alternative-routes.json) · [Doorway-level effects](doorway-effects.json)

## Controls and practical choice

| Control | U3 membership | Lines | Axial length | Angular mean | Angular p95 | Metric mean | Metric p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| Algorithm D | Outside | 33 | 1,628.66 | 0.8691 | 2.0396 | 48.691 | 88.573 |
| Strict backward | Outside | 44 | 1,660.80 | 1.1471 | 2.4735 | 49.149 | 89.809 |
| C-H | `0011001` | 34 | 1,725.21 | 0.8817 | 1.9808 | 48.780 | 88.598 |
| Best full-pool exchange | Outside | 34 | 1,626.80 | 0.9035 | 2.1136 | 48.822 | 88.629 |

Even the separate best U3 means exceed Algorithm D by 0.0084 angular units and 0.0789 metric units. The best U3 angular p95 improves on Algorithm D by 0.0588. The best U3 metric p95 is about 0.025 worse. The factorial range shows that route tails and mean costs can prefer different structurally valid maps. For this family, select 1278 for both means, decide explicitly how to trade angular against metric cost for the other active factors, and use length to break route-neutral ties. Local line descriptors alone did not consistently select the better mean route. The results apply within the exact 41-line U3 union.

[Numbered principal atlas](flat-40-factorial-atlas.pdf) · [Complete 128-map contact sheet](flat-40-all-128-maps.pdf) · [Individual PDF, principal PNG and exact inventory index](visual-index.json)

The shared routing build and 128 evaluations took 248.34 seconds with peak RSS of 659.9 MiB. Each map has a separately resumable checkpoint. The 22 focused regression tests passed. Previous records and production algorithms were preserved.
