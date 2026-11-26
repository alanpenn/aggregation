# Six-terrain configurational pilot

## A–B. Angular audit and corrected Flat 40 reference

The historical model assigns deflections to edges of an undirected segment adjacency graph. A shortest walk has no arrival heading, so two consecutive edges can reuse the same junction without travelling the intervening segment. The three-arm fixture yields 28.072486° along such an adjacency walk and 151.927513° in the continuous model. A physical reversal uses a 180° endpoint transition and traverses the segment back. The directed model passed independent exhaustive state-path and path-multiplicity comparisons, including an equal-angle pair where the labelled metric tie-break removes one route.

Topological degree, hop depth, integration, choice and intelligibility reproduced the frozen pilot. The historical angular implementation also replayed without discrepancy. The correction retains the same segment elements and degree; it changes the set of admissible angular paths. Its centrality counts all tied optimal routes between physical segment midpoints, with both endpoint orientations free.

| Reference | Depth old → continuous (°) | Integration old → continuous | Mean choice old → continuous | Intelligibility old → continuous | Choice Gini old → continuous | Top-10 overlap |
|---|---:|---:|---:|---:|---:|---:|
| 31-H | 112.93714 → 159.40558 | 0.00907 → 0.00641 | 0.04406 → 0.03328 | 0.19608 → 0.20221 | 0.52638 → 0.59275 | 6/10 |
| 29-H | 120.06674 → 169.86115 | 0.00858 → 0.00605 | 0.04801 → 0.03664 | 0.20214 → 0.20228 | 0.53164 → 0.60840 | 5/10 |

31-H changed 16,655 angular pair costs (16,655 higher, 0 lower). Atom 72 remains highest-choice. New top-ten atoms are [42, 44, 54, 59].

29-H changed 11,461 angular pair costs (11,461 higher, 0 lower). Atom 70 remains highest-choice. New top-ten atoms are [38, 40, 42, 50, 57].

Archived doorway routes are a different, terminal-specific check. Mean angular costs are 0.87806 and 0.89066 for 31-H and 29-H respectively.

## C–D. Comparable inputs

Six corrected settlements share seed 40, 100 buildings, a 100 × 100 study canvas, a 500-point Voronoi generator and the same facewise aggregation settings. The archived Valley terrain is Converging Valleys. Its verified main accessible component is much smaller than the others. The controlled axial and segment comparison uses the same archived C-H procedure throughout, including Flat's 34-H historical control. The certified Flat 31-H and 29-H remain the method reference and sensitivity pair. Flat 41 is the sole supplementary C-H seed. The remaining 29 cases have no archived C-H inventory in the benchmark. Their source stage files are present on the shared drive and are audited separately under the archived strict-backward method.

| Case | Accessible area | Occupied area | Candidates | C-H lines | Archived regional polygons | Certified maximal polygons |
|---|---:|---:|---:|---:|---:|---:|
| Converging Valleys 40 | 4079.35 | 5920.65 | 1273 | 17 | 205 | Unavailable |
| Flat 40 | 7932.07 | 2067.93 | 1534 | 34 | 292 | 596 |
| Flat 41 | 7925.24 | 2074.76 | 1499 | 32 | 276 | Unavailable |
| Hill 40 | 7895.26 | 2104.74 | 1492 | 34 | 270 | Unavailable |
| Ridge 40 | 7897.58 | 2102.42 | 1614 | 27 | 255 | Unavailable |
| Shoulder 40 | 7866.15 | 2133.85 | 1562 | 26 | 265 | Unavailable |
| Twin Peaks 40 | 7649.65 | 2350.35 | 1469 | 26 | 258 | Unavailable |

Individual areas in the table are numerical summaries of saved WKB. Exact axial endpoints and overlaps are retained in the graph exports. The archived regional polygons are the earlier coverage representation. A verified complete globally maximal cover is available only for Flat 40, so there is no six-terrain maximal-convex comparison.

## E–G. Matched configurational contrasts

| Terrain | Axial depth / r | Segment-hop depth / r | Angular depth (°) / r | Metric depth / r | Angular choice Gini | Angular choice top 10% |
|---|---:|---:|---:|---:|---:|---:|
| Converging Valleys 40 | 2.544 / 0.820 | 5.008 / 0.508 | 175.212 / 0.242 | 55.608 / 0.440 | 0.698 | 50.0% |
| Flat 40 | 2.421 / 0.840 | 6.809 / 0.499 | 166.617 / 0.235 | 55.095 / 0.267 | 0.606 | 37.5% |
| Hill 40 | 2.758 / 0.781 | 6.629 / 0.420 | 200.010 / 0.195 | 72.526 / 0.221 | 0.616 | 35.5% |
| Ridge 40 | 2.792 / 0.876 | 7.351 / 0.407 | 183.650 / 0.267 | 57.190 / 0.396 | 0.721 | 54.4% |
| Shoulder 40 | 3.120 / 0.794 | 6.009 / 0.481 | 237.112 / 0.254 | 83.285 / 0.317 | 0.710 | 49.1% |
| Twin Peaks 40 | 2.234 / 0.937 | 6.070 / 0.504 | 154.322 / 0.223 | 62.959 / 0.288 | 0.608 | 38.3% |

Axial hops show the greatest observed choice Gini in Shoulder 40 and its largest integration IQR in Ridge 40.

Angular segments show the greatest observed choice Gini in Ridge 40 and its largest integration IQR in Converging Valleys 40.

Flat 40's shared convex graph has 596 nodes and 10,540 edges, mean depth 3.922, and intelligibility 0.453. Exact cover multiplicity areas are exported with the sampled overlay.

Integration is reach fraction times inverse one-plus-depth. Degree is the physical adjacency degree even under angular or metric travel. Choice excludes endpoints and distributes equal-path credit. Clustering is unweighted physical clustering. The graph summaries include component sizes, diameters, degree distributions, node dispersion and locations of high-choice elements. Raw depth and integration retain their representation-specific units and meaning.

## H. Seed sensitivity

- Axial hops intelligibility spans 0.156 across six seed-40 cases. Flat 40 versus Flat 41 changes by 0.156.
- Segment hops intelligibility spans 0.101 across six seed-40 cases. Flat 40 versus Flat 41 changes by 0.127.
- Angular segments intelligibility spans 0.073 across six seed-40 cases. Flat 40 versus Flat 41 changes by 0.013.
- Metric segments intelligibility spans 0.218 across six seed-40 cases. Flat 40 versus Flat 41 changes by 0.002.

Two Flat seeds provide one within-terrain contrast for C-H. Each other terrain has a single independently realised settlement in that cohort. The separate strict-backward seed audit keeps the selection method fixed across the wider cohort. The observed ranges are descriptive and cannot separate seed, terrain and settlement morphology effects.

## Recovered seed cohort

The shared migration archive supplied all 348 stage files marked missing in
the earlier benchmark. Their checksums matched. The supplementary run
verified 469 source files and analysed the saved strict-backward maps for all
36 settlements under the same graph definitions. These results form a
separate cohort from C-H.

Shoulder 42 had 89 realised buildings. It is retained as an illustrative
case. The matched settings set comprises 35 settlements with 100 buildings.
Within-terrain ranges use the five or six eligible seeds for each terrain.
Between-terrain means use the five seeds shared by every terrain, 40, 41,
43, 44 and 45.

| Strict-backward measure | Range between matched terrain means | Largest observed within-terrain range |
|---|---:|---:|
| Axial intelligibility | 0.282 | 0.514 |
| Segment-hop intelligibility | 0.174 | 0.217 |
| Continuous angular intelligibility | 0.100 | 0.221 |
| Metric segment intelligibility | 0.067 | 0.199 |
| Continuous angular choice Gini | 0.084 | 0.114 |
| Segment-hop choice Gini | 0.101 | 0.088 |

For all four intelligibility measures, at least one terrain's observed
seed range exceeds the range between matched terrain means. Segment-hop
choice Gini shows the reverse pattern in this cohort. These are descriptive
ranges and do not establish a general terrain effect.

[Seed figures](strict-backward-seeds/seed-variability.pdf) · [Seed observations](strict-backward-seeds/observations.csv) · [Seed statistics](strict-backward-seeds/variability.json) · [Recovered source inventory](strict-backward-seeds/source-inventory.json) · [Seed-run verification](strict-backward-seeds/verification.json)

## I. Spatial relationships

The Flat 40 lattice supplies 499 accessible locations and 357 with all three representations present. Nearest line and segment assignments and polygon coverage were evaluated with rational predicates. The sampled fields use axial hop scores, continuous angular segment scores and convex hop scores.

Integration field Pearson r is axial–segment 0.754, axial–convex 0.423, segment–convex 0.468.

Choice field Pearson r is axial–segment 0.422, axial–convex 0.186, segment–convex -0.026.

These correlations describe spatial co-location at the specified lattice and radius. They can vary with sampling scale, decision to average covering polygons, and line proximity thresholds.

## J. Remaining evidence

A controlled maximal-convex comparison requires five separately checkpointed exhaustive covers with certificates for their own accessible domains. Further C-H seed inference requires reduced inventories beyond the seven saved cases. The present contrasts combine topography, changes in accessible area and building/open-space morphology mediated by aggregation.

[Vector atlas](atlas.pdf) · [Frozen definitions](configuration.json) · [Source inventory](source-inventory.json) · [Verified hashes](verified-hashes.json) · [Metrics](statistics.json) · [Comparison CSV](terrain-comparison.csv) · [Angular fixtures](angular-fixtures.json) · [Angular audit](flat40-angular-audit.json) · [Spatial overlay](flat40-spatial-overlay.json) · [Runtime](runtime.json)

[Reproduction commands](reproduce.md) · [Regression results](regression-results.txt) · [Export verification](export-verification.json)
