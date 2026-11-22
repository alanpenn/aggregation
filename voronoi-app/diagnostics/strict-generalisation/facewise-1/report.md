# Corrected facewise axial and movement experiment

## Executive summary

The export includes 12 of 12 settlements and 60 of 60 method records (60 valid).
Hill had more strict backward lines in 6 of 6 seed pairs with a validated result on both terrains.

## Aggregation, topology and circulation

The legacy growth rule admitted Voronoi ridge neighbours with no positive-length clipped face. The corrected strategy builds the clipped face graph before placing the seed dyad and uses it for both links of each extension. Independent placement certificates recompute the face lengths and verify unique assignments, the recorded parent, and seed connectivity at every growth prefix.
Slope and contour scores retain their original formula and weights. The corrected candidate order follows cell IDs, so random scores and growth histories can diverge even when a legacy seed never placed an invalid dyad.
The grid and aggregation use the archived seed with NumPy's legacy random stream and Python's seeded random stream for aggregation. Each immutable batch record lists method, package source hashes, runtime versions and parent output hashes.

| Case | Cohort | Dyads | Assigned-open components | Excluded assigned | Excluded unassigned | Internal blocks | Geometric holes |
|---|---|---:|---:|---:|---:|---:|---:|
| hill-40 | legacy | 100 | 1 | 0 | 0 | 16 | 16 |
| hill-40 | corrected | 100 | 1 | 0 | 0 | 17 | 17 |
| converging_valleys-40 | legacy | 100 | 3 | 3 | 54 | 6 | 6 |
| converging_valleys-40 | corrected | 100 | 1 | 0 | 184 | 6 | 6 |
| hill-41 | legacy | 100 | 1 | 0 | 0 | 13 | 13 |
| hill-41 | corrected | 100 | 1 | 0 | 0 | 15 | 15 |
| converging_valleys-41 | legacy | 100 | 4 | 4 | 115 | 2 | 2 |
| converging_valleys-41 | corrected | 100 | 1 | 0 | 130 | 6 | 6 |
| hill-42 | legacy | 100 | 1 | 0 | 2 | 11 | 11 |
| hill-42 | corrected | 100 | 1 | 0 | 2 | 16 | 16 |
| converging_valleys-42 | legacy | 100 | 1 | 0 | 0 | 3 | 3 |
| converging_valleys-42 | corrected | 100 | 1 | 0 | 29 | 5 | 5 |
| hill-43 | legacy | 100 | 1 | 0 | 4 | 7 | 7 |
| hill-43 | corrected | 100 | 1 | 0 | 3 | 13 | 13 |
| converging_valleys-43 | legacy | 100 | 3 | 1 | 4 | 2 | 2 |
| converging_valleys-43 | corrected | 100 | 1 | 0 | 1 | 7 | 7 |
| hill-44 | legacy | 100 | 1 | 0 | 3 | 15 | 15 |
| hill-44 | corrected | 100 | 1 | 0 | 0 | 10 | 10 |
| converging_valleys-44 | legacy | 100 | 1 | 0 | 1 | 8 | 8 |
| converging_valleys-44 | corrected | 100 | 1 | 0 | 3 | 6 | 6 |
| hill-45 | legacy | 100 | 1 | 0 | 1 | 17 | 17 |
| hill-45 | corrected | 100 | 1 | 0 | 0 | 10 | 10 |
| converging_valleys-45 | legacy | 100 | 2 | 0 | 0 | 8 | 8 |
| converging_valleys-45 | corrected | 100 | 1 | 0 | 134 | 4 | 4 |

In Y 40 and Y 41 the disconnected assigned-open cells disappeared. The unassigned exclusions increased from 54 to 184 and from 115 to 130, respectively. They are cells cut off from the main accessible component by the corrected building arrangement. Y 45 also has a large unassigned exclusion. See the aggregation table for the seed-specific counts.
The open-space graph uses positive shared length. Occupied blocks group both vertex and face contacts. The two rightmost columns independently compare occupied-block requirements with holes of the accessible polygon.

## Axial selection and movement

Angular costs are in quarter turns with zero angular entry and exit cost through incident regions. Metric costs include certified regional connectors and travel along the selected intervals. They are shortest paths in the finite certified graph.
Each eligible doorway is the exact shared-face midpoint of the saved building–open dyad. Regional attachments allow certified projections and feasible interval endpoints on every line traversing an incident convex region. The same doorway pair order is used within each settlement. The full-pool arrays are computed once and saved with that order.
Absolute excess is computed per comparable pair against the full pool. Proportional excess uses the positive full-pool cost as the denominator. The statistics file reports zero baselines and the number of undefined proportions.
Strict entrance-guided starts from winding supports and adds lines for incidence and angular access. Strict backward applies shortest-first iterative deletion from the guided set with structural checks. The two corridor methods share the legacy physical band screen and trial limits. The extreme pair is ordered geometrically within a band. The route-ranked method ranks admissible trials by the archived angular and length criteria.

| Case | Method | Status | Lines | Winding/required | Angular mean | Metric mean |
|---|---|---|---:|---:|---:|---:|
| hill-40 | Full certified pool | valid | 1492 | 17/17 | 0.5334 | 46.3853 |
| hill-40 | Geometric extreme pair | valid | 46 | 17/17 | 1.1157 | 53.9651 |
| hill-40 | Route-ranked pair | valid | 46 | 17/17 | 1.1110 | 53.8262 |
| hill-40 | Strict backward | valid | 45 | 17/17 | 1.2404 | 54.9887 |
| hill-40 | Strict entrance-guided | valid | 426 | 17/17 | 1.0606 | 47.5930 |
| converging_valleys-40 | Full certified pool | valid | 1273 | 6/6 | 0.3257 | 52.1460 |
| converging_valleys-40 | Geometric extreme pair | valid | 24 | 6/6 | 0.8189 | 59.2449 |
| converging_valleys-40 | Route-ranked pair | valid | 24 | 6/6 | 0.8089 | 59.2243 |
| converging_valleys-40 | Strict backward | valid | 23 | 6/6 | 0.8609 | 59.2663 |
| converging_valleys-40 | Strict entrance-guided | valid | 91 | 6/6 | 0.6291 | 57.1211 |
| hill-41 | Full certified pool | valid | 1511 | 15/15 | 0.5282 | 47.6992 |
| hill-41 | Geometric extreme pair | valid | 43 | 15/15 | 1.3622 | 57.8809 |
| hill-41 | Route-ranked pair | valid | 43 | 15/15 | 1.3616 | 57.9047 |
| hill-41 | Strict backward | valid | 42 | 15/15 | 1.3824 | 58.3049 |
| hill-41 | Strict entrance-guided | valid | 340 | 15/15 | 1.0984 | 50.9211 |
| converging_valleys-41 | Full certified pool | valid | 1505 | 6/6 | 0.4581 | 53.5426 |
| converging_valleys-41 | Geometric extreme pair | valid | 28 | 6/6 | 1.0237 | 59.3917 |
| converging_valleys-41 | Route-ranked pair | valid | 28 | 6/6 | 1.0231 | 59.3696 |
| converging_valleys-41 | Strict backward | valid | 28 | 6/6 | 1.0235 | 59.3622 |
| converging_valleys-41 | Strict entrance-guided | valid | 125 | 6/6 | 0.8923 | 57.1173 |
| hill-42 | Full certified pool | valid | 1429 | 16/16 | 0.5144 | 47.6256 |
| hill-42 | Geometric extreme pair | valid | 43 | 16/16 | 1.1010 | 60.7433 |
| hill-42 | Route-ranked pair | valid | 43 | 16/16 | 1.0903 | 60.6225 |
| hill-42 | Strict backward | valid | 42 | 16/16 | 1.1534 | 61.9123 |
| hill-42 | Strict entrance-guided | valid | 423 | 16/16 | 0.8628 | 48.6428 |
| converging_valleys-42 | Full certified pool | valid | 1549 | 5/5 | 0.3187 | 55.6909 |
| converging_valleys-42 | Geometric extreme pair | valid | 26 | 5/5 | 0.6158 | 61.9371 |
| converging_valleys-42 | Route-ranked pair | valid | 26 | 5/5 | 0.6152 | 61.9853 |
| converging_valleys-42 | Strict backward | valid | 26 | 5/5 | 0.6143 | 62.0662 |
| converging_valleys-42 | Strict entrance-guided | valid | 172 | 5/5 | 0.5213 | 57.7589 |
| hill-43 | Full certified pool | valid | 1423 | 13/13 | 0.6100 | 49.6603 |
| hill-43 | Geometric extreme pair | valid | 42 | 13/13 | 1.2264 | 59.5098 |
| hill-43 | Route-ranked pair | valid | 42 | 13/13 | 1.2261 | 59.3407 |
| hill-43 | Strict backward | valid | 41 | 13/13 | 1.2552 | 59.4982 |
| hill-43 | Strict entrance-guided | valid | 351 | 13/13 | 1.0243 | 51.5374 |
| converging_valleys-43 | Full certified pool | valid | 1670 | 7/7 | 0.3188 | 53.5496 |
| converging_valleys-43 | Geometric extreme pair | valid | 30 | 7/7 | 1.0326 | 61.6140 |
| converging_valleys-43 | Route-ranked pair | valid | 29 | 7/7 | 1.0446 | 62.8309 |
| converging_valleys-43 | Strict backward | valid | 29 | 7/7 | 1.0446 | 62.8368 |
| converging_valleys-43 | Strict entrance-guided | valid | 151 | 7/7 | 0.6779 | 57.1723 |
| hill-44 | Full certified pool | valid | 1382 | 10/10 | 0.5250 | 45.4326 |
| hill-44 | Geometric extreme pair | valid | 42 | 10/10 | 1.2710 | 56.0809 |
| hill-44 | Route-ranked pair | valid | 42 | 10/10 | 1.2604 | 55.8267 |
| hill-44 | Strict backward | valid | 41 | 10/10 | 1.2909 | 57.0499 |
| hill-44 | Strict entrance-guided | valid | 388 | 10/10 | 0.9464 | 46.5932 |
| converging_valleys-44 | Full certified pool | valid | 1554 | 6/6 | 0.3567 | 50.1756 |
| converging_valleys-44 | Geometric extreme pair | valid | 31 | 6/6 | 0.9971 | 58.7273 |
| converging_valleys-44 | Route-ranked pair | valid | 31 | 6/6 | 0.9971 | 58.7341 |
| converging_valleys-44 | Strict backward | valid | 30 | 6/6 | 1.0653 | 59.4750 |
| converging_valleys-44 | Strict entrance-guided | valid | 103 | 6/6 | 0.9756 | 58.3005 |
| hill-45 | Full certified pool | valid | 1460 | 10/10 | 0.4831 | 47.3922 |
| hill-45 | Geometric extreme pair | valid | 41 | 10/10 | 1.1892 | 54.6801 |
| hill-45 | Route-ranked pair | valid | 41 | 10/10 | 1.1856 | 54.7861 |
| hill-45 | Strict backward | valid | 41 | 10/10 | 1.2431 | 55.0371 |
| hill-45 | Strict entrance-guided | valid | 305 | 10/10 | 0.9691 | 49.1387 |
| converging_valleys-45 | Full certified pool | valid | 1535 | 4/4 | 0.2932 | 53.1103 |
| converging_valleys-45 | Geometric extreme pair | valid | 25 | 4/4 | 0.6541 | 58.7815 |
| converging_valleys-45 | Route-ranked pair | valid | 25 | 4/4 | 0.6465 | 58.5442 |
| converging_valleys-45 | Strict backward | valid | 24 | 4/4 | 0.7712 | 59.7710 |
| converging_valleys-45 | Strict entrance-guided | valid | 135 | 4/4 | 0.6160 | 55.7114 |

### Matched strict backward counts

| Seed | Legacy Hill | Corrected Hill | Legacy Y | Corrected Y | Corrected Hill minus Y |
|---|---:|---:|---:|---:|---:|
| 40 | 49 | 45 | 22 | 23 | 22 |
| 41 | 43 | 42 | 23 | 28 | 14 |
| 42 | 38 | 42 | 28 | 26 | 16 |
| 43 | 39 | 41 | 23 | 29 | 12 |
| 44 | 44 | 41 | 36 | 30 | 11 |
| 45 | 48 | 41 | 31 | 24 | 17 |

## Corridor hypothesis

Geometric extreme pair yielded 12 validated substitutions, 0 with fewer lines, 9 with both mean costs at or below strict backward, and 0 meeting both criteria.
Route-ranked pair yielded 12 validated substitutions, 0 with fewer lines, 10 with both mean costs at or below strict backward, and 0 meeting both criteria.
The physical screen retained 95 bands across 12 analyzed settlements.

## Legacy comparison and limits

The archived and corrected cohorts share seeds and terrain parameters. Building assignments and doorway populations can differ, so comparisons between cohorts use aggregate measures. Route excess within a cohort uses consistent doorway pairs.
The corridor search uses the archived physical screen, pair limits and ranking. The outcomes apply to the tested alternatives. Worker peak RSS is a process high-water mark, and evaluation timing excludes case-wide candidate generation. The convex coverage proof uses the certified constrained triangle cover and containment of each seed triangle in its expanded hull. Exact geometric and routing certificates apply to saved intervals and their incidence graph. The candidate family is enumerated from the existing support-generation procedure.
The Y 41 candidate attempt first failed the overlapping-hull union check. The retry certified coverage from the constrained triangle cover and seed containment with the same hull construction. The initial failure and successful retry remain in the case journal.
Differences in worker concurrency and archived runtime environments affect timing comparisons. The study uses six seeds per terrain, so consistency across the matched seeds is a descriptive result.

## Research priorities

Investigate cases with missing candidates, region incidence or winding before drawing terrain-level conclusions. Use the geometry and route arrays to test sensitivity to convex partition and support enumeration.

## Reproduce or resume

From the repository root, use the same environment as the recorded stage manifests. Successful stages are resumed from the case journals.

```sh
PYTHONPATH=src:. .venv/bin/python -m experiments.facewise_rerun --workers 2
PYTHONPATH=src:. .venv/bin/python -m experiments.facewise_rerun_export --wait
```

[Numbered vector atlas](numbered-axial-atlas.pdf) · [Visual index](visual-index.json) · [Statistics](statistics.csv) · [Legacy method comparisons](legacy-method-comparisons.csv)
