# Flat 40 recombination across the three saved unions

**The saved parent linework cannot produce a valid map below 34 lines.** All 15 direct deletion runs and all six bounded exchange runs ended at 34. The union-only search produced a genuine new 34-line map, and the full-pool search produced a 34-line map with shorter total axial length. The existing 33-line Algorithm D map still has fewer lines.

## Verified parents and unions

The four parent records match their source hashes and exact candidate IDs. F-S and F-H exchange are the same selection. All parent intervals, geometry and provenance refer to the restored corrected Flat 40 settlement. The independent parent certificates and fresh union certificates establish clearance, 292 strict regions, 100 doorways, one connected component and winding rank 24/24.

| Union | Parents | Unique lines | Shared by all its parents | Total axial length |
|---|---|---:|---:|---:|
| U1 | F-S and C-S | 39 | 29 | 1,947.03 |
| U2 | F-H and C-H | 41 | 27 | 2,013.90 |
| U3 | F-S, C-S and C-H | 41 | 27 | 2,013.90 |

U2 and U3 contain identical candidate IDs. The full versus C-S intersection and Jaccard similarity are 29 and 0.744. The full versus C-H values are 27 and 0.659. C-S and C-H share 32 lines, with Jaccard similarity 0.889. The union inventories give the provenance of every candidate.

## Deletion and exchanges

| Order | U1 | U2 | U3 |
|---|---|---|---|
| Shortest first | F-S | F-S | F-S |
| Longest first | C-S | C-H | C-H |
| Sheaf priority | F-S | F-S | F-S |
| Lowest marginal transverse degree | F-S | F-S | F-S |
| Geometric redundancy | F-S | F-S | F-S |

Direct deletion removed five lines from U1 and seven from U2 and U3. Every final direct map passed a complete single-deletion sweep, and every distinct final inventory passed the independent full winding validator. Cached exact certificates were shared for duplicate inventories. Individual run records contain deletion order, attempts, runtime, peak process RSS, candidate IDs and certification. The exhaustive U3 proof from the earlier experiment establishes the lower bound for all three unions. It is stronger than the direct runs' local irreducibility.

The two exchange modes used the same three distinct direct maps as starts, with up to 96 structurally tested proposals per exchange type per round and two rounds. It tried one added line for one or two deleted lines, and two added lines for three or four deleted lines. Proposals used corridor affinity, shared coverage and transverse connectivity. The objective was line count, then total length, then distinct transverse crossing sites. Accepted proposals passed the full face validator before renewed strict deletion. No route costs entered the search.

| Phase | Attempted exchanges | Accepted | Best count | Best total length | Outside candidates in best |
|---|---:|---:|---:|---:|---|
| Union only | 1,501 | 4 | 34 | 1,725.21 | — |
| Full-pool exchange | 1,847 | 6 | 34 | 1,626.80 | 365, 1043 |

All accepted exchanges were one-for-one. Union-only search from F-S replaced 1128 and 965 with 1212 and 1072, producing a new 34-line map of length 1,738.75. The shortest feasible union map was the existing C-H parent. Full-pool exchange from C-H replaced 1519 and 1072 with 365 and 1043, saving 98.41 units against C-H. This 5.7% length improvement required outside intervals and did not reduce line count. The archived Algorithm D control reaches 33 using 17 outside candidates. The new full-pool search was bounded, so the 34-line result is not a lower bound on the full pool.

[Union certificates and provenance](unions.json) · [Union-only exchange history](union-exchanges.json) · [Full-pool exchange history](full-exchanges.json) · [Final exact interval inventories](final-inventories.json)

## Geometry and structural necessity

The exact U3 enumeration found 128 minimum maps, 125 of them absent from the parent inventory. All consist of 27 mandatory lines plus one line from each of seven independently interchangeable pairs. U1 contains five complete pairs and fixes the other two choices, leaving 32 minimum maps. Five of the seven U3 pairs meet the archived corridor geometry and strict-region similarity thresholds. The 1278/1422 pair differs by 80.35° and covers different regions. Its interchangeability follows from validation of the whole map. Pair geometry alone would not have identified it.

The full validator tested each single deletion from the three parents, the new bounded union-only map, the shortest novel exact map, and the best full-pool result. In the new bounded union-only map, 21 lines were needed for strict regions, nine for doorways, two for connectivity and 30 for independent winding. These categories overlap. The inventory records the union candidates' exact supporting vertices, strict regions, doorways and transverse neighbors.

Candidate 957 is supported by buildings 18 and 87 and candidate 1244 by buildings 1 and 5. Both survive in the parents and the tested new results. Removing 957 merges the winding classes for internal blocks 9 and 11, giving rank 23. Removing 1244 merges internal blocks 2, 4 and 21, giving rank 22. In both cases all occupied blocks can still be enclosed. In the best full-pool result, 957 also provides unique strict coverage of region 274. These changes show that lines can preserve a similar corridor or enclosure geometry while serving different roles in the full network.

[Candidate incidence, exact supporting vertices and winding faces](line-analysis.json) · [Exact per-line deletion audit and flexibility by union](necessity.json) · [Pair geometry by union](union-line-similarities.json)

## Numbered atlas

The 28-page atlas contains the three distinct parents, U3 by parent provenance, all 15 direct maps, the best union-only and full-pool exchange maps, and the 33-line Algorithm D control. Comparative pages use the same coordinates. The three building close-ups distinguish retained parent lines, deleted union lines and lines added from outside U3. All pages have matching vector PDFs and 400 dpi PNGs. The shortest PNG dimension across the atlas is 2,673 pixels.

[Numbered vector atlas](flat-40-numbered-atlas.pdf) · [Individual PDF and PNG index](visual-index.json)

## Independent movement evaluation

All 4,950 doorway pairs were reachable for every one of the 26 reported outputs and controls. Duplicate candidate inventories shared the same calculated route arrays. The full-pool reference means were 0.3927 angular units and 43.0284 metric units. The movement record includes angular and metric medians, maxima, p95s, full-reference excesses and the worst deteriorating doorway pairs for each output. The earlier 128-map enumeration provides the exact structural bound. Routing here covers the saved experiment outputs and controls.

| Map | Lines | Axial length | Angular mean | Angular p95 | Metric mean | Metric p95 |
|---|---:|---:|---:|---:|---:|---:|
| F-S parent | 34 | 1,774.45 | 0.8890 | 2.0306 | 49.279 | 90.041 |
| C-S parent | 34 | 1,736.39 | 0.8867 | 2.0030 | 49.227 | 89.946 |
| C-H parent and best union-only | 34 | 1,725.21 | 0.8817 | 1.9808 | 48.780 | 88.598 |
| New bounded union-only map | 34 | 1,738.75 | 0.8920 | 2.0402 | 49.270 | 90.041 |
| Best full-pool exchange | 34 | 1,626.80 | 0.9035 | 2.1136 | 48.822 | 88.629 |
| Algorithm D | 33 | 1,628.66 | 0.8691 | 2.0396 | 48.691 | 88.573 |
| Strict backward | 44 | 1,660.80 | 1.1471 | 2.4735 | 49.149 | 89.809 |

The best full-pool exchange had 1.86 units less total line length than Algorithm D, while Algorithm D used one fewer line and had lower mean angular and metric costs. The C-H union-only result preserved a better angular p95 than Algorithm D. The novel union result expands the set of structurally valid solutions, but its mean route costs are higher than C-H's. The full-pool exchange lowered total interval length, while slightly increasing both mean route costs relative to C-H. Shorter axial linework did not automatically make doorway journeys shorter.

[Comparison CSV for all 26 outputs and controls](comparison.csv) · [Independent route arrays and worst doorway pairs](movement.json)

The runner saves each deletion case and completed exchange phase independently. Rerunning it resumes missing cases using the saved exact inputs. All previous Flat 40 directories and production algorithms were preserved. The 22 focused regression tests passed.
