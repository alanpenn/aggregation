# Flat seed 40 axial tangent investigation

The corrected settlement and its saved candidate and selection records are identified by output and source hashes in [audit.json](audit.json). The grid was configured for 500 points and produced 484 clipped cells with the original 100 building labels.

The local inventory uses intervals within two canvas units of both named polygons. Independent supporting vertex tests include frontages within five units of either polygon. These operational windows define a bounded local search. The figures show which lines the window includes.

The strict backward baseline has 44 lines, total length 1660.80, and full winding rank 24/24. Across 4,950 reachable doorway pairs, angular mean and maximum are 1.1471 and 3.7839 quarter turns, and metric mean and maximum are 49.1494 and 116.4369 canvas units in the finite certified routing graph.

The globally longest certified interval is candidate 1531 at 103.74 units.

## Buildings 15 and 25

The longest local certified interval is **957** at 43.63 units. The pool contains 31 local intervals. Exact mutual supports between the two named buildings produce candidate IDs 865, 914, 926. The independent search rejected 1 named support seeds and certified 0 absent local intervals.

| Candidate | Length | Baseline intersections | Transverse | Regions | Doorways | Selection history | Rank after addition | Angular mean after addition | Metric mean after addition |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 957 | 43.63 | 7 | 5 | 32 | 17 | Omitted by entrance-guided selection | 24 | 1.1357 | 48.9637 |
| 954 | 43.55 | 7 | 5 | 32 | 17 | Omitted by entrance-guided selection | 24 | 1.1359 | 48.9866 |
| 1208 | 43.47 | 6 | 5 | 33 | 17 | Omitted by entrance-guided selection | 24 | 1.1356 | 48.9569 |
| 865 | 28.39 | 6 | 5 | 25 | 13 | Omitted by entrance-guided selection | 24 | 1.1185 | 48.9433 |
| 926 | 20.64 | 6 | 5 | 18 | 11 | Omitted by entrance-guided selection | 24 | 1.1450 | 49.1134 |
| 914 | 25.58 | 5 | 3 | 17 | 9 | Omitted by entrance-guided selection | 24 | 1.1381 | 49.1002 |

- A named mutual support failed exact clearance through occupied interior at 18.
- Candidate 957 changed angular mean by -0.0114 and maximum by +0.0000. Metric mean changed by -0.1857 and maximum by -0.3342. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 954 changed angular mean by -0.0113 and maximum by +0.0000. Metric mean changed by -0.1628 and maximum by -0.3342. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 1208 changed angular mean by -0.0115 and maximum by +0.0000. Metric mean changed by -0.1924 and maximum by -0.3342. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership geometric extreme, route-ranked.
- Candidate 865 changed angular mean by -0.0286 and maximum by +0.0000. Metric mean changed by -0.2061 and maximum by +0.0000. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 926 changed angular mean by -0.0021 and maximum by +0.0000. Metric mean changed by -0.0359 and maximum by +0.0000. The smallest accepted exchange containing it used 44 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 914 changed angular mean by -0.0090 and maximum by +0.0000. Metric mean changed by -0.0491 and maximum by +0.0000. The tested exchanges containing it yielded no accepted map. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
Best equal-count exchange by angular mean, with metric mean as the tiebreaker. 44 lines and total length 1676.23, with rank 24/24. Add 866, remove 61. Angular mean 1.1170, max 3.7839. Metric mean 48.9411, max 116.4369.
Best lower-count exchange under the same ordering. 43 lines and total length 1649.15, with rank 24/24. Add 865, 1257, remove 61, 149, 1256. Angular mean 1.1282, max 3.7839. Metric mean 49.4554, max 116.4509.

[Numbered comparison PDF](15-25-comparison.pdf) · [High-resolution PNG](15-25-comparison.png)

## Buildings 41 and 43

The longest local certified interval is **1355** at 34.15 units. The pool contains 10 local intervals. Exact mutual supports between the two named buildings produce candidate IDs 1355. The independent search rejected 3 named support seeds and certified 0 absent local intervals.

| Candidate | Length | Baseline intersections | Transverse | Regions | Doorways | Selection history | Rank after addition | Angular mean after addition | Metric mean after addition |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1355 | 34.15 | 7 | 6 | 22 | 10 | Omitted by entrance-guided selection | 24 | 1.1452 | 49.0464 |
| 1354 | 33.82 | 7 | 6 | 22 | 10 | Omitted by entrance-guided selection | 24 | 1.1446 | 49.0315 |
| 1449 | 33.72 | 7 | 6 | 23 | 10 | Omitted by entrance-guided selection | 24 | 1.1444 | 49.0734 |

- A named mutual support failed exact clearance through occupied interior at 10, 42, 11.
- A named mutual support failed exact clearance through occupied interior at 42, 34, 67.
- A named mutual support failed exact clearance through occupied interior at 34, 31, 67.
- Candidate 1355 changed angular mean by -0.0019 and maximum by -0.0167. Metric mean changed by -0.1030 and maximum by -0.3342. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 1354 changed angular mean by -0.0025 and maximum by -0.0210. Metric mean changed by -0.1179 and maximum by -0.3342. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 1449 changed angular mean by -0.0027 and maximum by -0.0210. Metric mean changed by -0.0759 and maximum by -0.3342. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
Best equal-count exchange by angular mean, with metric mean as the tiebreaker. 44 lines and total length 1670.91, with rank 24/24. Add 1421, remove 377. Angular mean 1.1440, max 3.7629. Metric mean 49.1290, max 116.1028.
Best lower-count exchange under the same ordering. 43 lines and total length 1674.68, with rank 24/24. Add 1354, 1470, remove 341, 375, 377. Angular mean 1.1201, max 3.7629. Metric mean 49.1059, max 116.1028.

[Numbered comparison PDF](41-43-comparison.pdf) · [High-resolution PNG](41-43-comparison.png)

## Buildings 6 and 5

The longest local certified interval is **1244** at 37.36 units. The pool contains 25 local intervals. Exact mutual supports between the two named buildings produce candidate IDs 1190. The independent search rejected 3 named support seeds and certified 0 absent local intervals.

| Candidate | Length | Baseline intersections | Transverse | Regions | Doorways | Selection history | Rank after addition | Angular mean after addition | Metric mean after addition |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1244 | 37.36 | 9 | 8 | 31 | 16 | Omitted by entrance-guided selection | 24 | 1.0440 | 48.0193 |
| 1190 | 34.55 | 9 | 8 | 33 | 16 | Omitted by entrance-guided selection | 24 | 1.0435 | 48.0280 |
| 1189 | 34.08 | 9 | 8 | 31 | 16 | Omitted by entrance-guided selection | 24 | 1.0432 | 48.0333 |

- A named mutual support failed exact clearance through occupied interior at 3.
- A named mutual support failed exact clearance through occupied interior at 3, 8.
- A named mutual support failed exact clearance through occupied interior at 3.
- Candidate 1244 changed angular mean by -0.1031 and maximum by -0.2693. Metric mean changed by -1.1301 and maximum by -4.2031. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 1190 changed angular mean by -0.1037 and maximum by -0.2609. Metric mean changed by -1.1214 and maximum by -4.2031. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
- Candidate 1189 changed angular mean by -0.1040 and maximum by -0.2506. Metric mean changed by -1.1161 and maximum by -4.2031. The smallest accepted exchange containing it used 43 lines. It did not win a greedy coverage round or reach the shortcut shortlist. Final corridor map membership none.
Best equal-count exchange by angular mean, with metric mean as the tiebreaker. 44 lines and total length 1673.26, with rank 24/24. Add 1189, remove 111. Angular mean 1.0432, max 3.5333. Metric mean 48.0380, max 112.2339.
Best lower-count exchange under the same ordering. 43 lines and total length 1640.91, with rank 24/24. Add 1189, remove 111, 127. Angular mean 1.0606, max 3.5333. Metric mean 48.5209, max 113.5488.

[Numbered comparison PDF](6-5-comparison.pdf) · [High-resolution PNG](6-5-comparison.png)

## Full-map comparisons

**Best equal-count exchange.** 44 lines and total length 1712.29, with rank 24/24. Add 957, 1244, 1355, remove 174, 111, 375. Angular mean 1.0285, max 3.5033. Metric mean 48.1771, max 116.1028.
**Best lower-count exchange.** 43 lines and total length 1640.91, with rank 24/24. Add 1189, remove 111, 127. Angular mean 1.0606, max 3.5333. Metric mean 48.5209, max 113.5488.
**Best angular route alternative.** 47 lines and total length 1775.94, with rank 24/24. Add 957, 1244, 1355, remove none. Angular mean 1.0283, max 3.5033. Metric mean 47.8233, max 112.2339.
**Best metric route alternative.** 47 lines and total length 1775.94, with rank 24/24. Add 957, 1244, 1355, remove none. Angular mean 1.0283, max 3.5033. Metric mean 47.8233, max 112.2339.

## Selection implications

The archived guided map started with 387 ring-supported lines. That set already met the initial coverage, doorway and connectivity targets. Four shortlisted shortcuts grew it to 391 lines. The three longest local candidates remained outside the shortcut shortlist and thus outside the backward deletion order. The guided-history record includes their exact shortlist ranks.
The best equal-count exchange changes angular mean by -0.1186 and metric mean by -0.9723. The equal line count isolates the movement trade-off from a change in map size.
80 accepted trial entries reduce both means at equal or lower line count.
The bounded search also found a certified map with 1 fewer lines. Shortest-first deletion alone could not make its new lines available.
The leading local tangents were present in the certified pool. Their selection histories identify where each was lost. Shortest-first ordering tests shorter lines earlier, while the guided coverage rule uses junction counts as tiebreakers. One shortcut shortlist uses length as a later tiebreaker before entrance-depth ranking. These three local cases cannot establish a systematic disadvantage across settlements.

The JSON records exact endpoints, supporting vertices or faces, pool intersections, traversed regions, doorway labels, circulation certificates at archived deletions, and both movement distributions for every routed proposal. Transverse intersections use an acute crossing angle of at least 30°. All lines added individually attach to the existing connected component when they intersect it. Multiple crossings can provide alternate routes inside that same component. In the simple line-intersection graph, an added line with d contacts increases cycle rank by d − 1. Geometric circulation winding is checked separately.

One-for-one exchanges test all local nonbaseline candidates against every retained line. Lower-count exchanges use the three longest local omissions and any named-pair omissions as primary additions. They test one addition against pairs from eight ranked removals and two additions against triples from six ranked removals. Second additions are drawn from the full certified pool among intersecting lines. The combinations pass also tests joint additions of the local leaders. These trials establish local exchange opportunities within the stated search budget.

The guided ranking works from necessary coverage and entrance access. The backward pass deletes shortest-first from the guided set and checks exact clearance, region coverage, doorway incidence, connectivity and winding. An absent line never enters its deletion order. The trials distinguish that search restriction from geometric certification and measure route costs that the deletion rule treats as outside its structural objective.

[Vector atlas](numbered-axial-audit.pdf) · [Exact audit and trial results](audit.json) · [Guided selection replay](guided-history.json)
