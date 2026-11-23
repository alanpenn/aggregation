# Extended corrected facewise terrain benchmark

The benchmark covers 36 settlements and 180 method evaluations. 180 valid.
Hill and Converging Valleys use the immutable corrected records from the published benchmark.

## Terrain comparison

| Terrain | Holes, mean (range) | Excluded unassigned, mean (range) | Candidates, mean | Backward lines, mean (range) | Backward length | Angular mean | Metric mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| Flat | 21.33 (15–26) | 0.67 (0–3) | 1509.67 | 45.83 (43–50) | 1722.61 | 1.13 | 49.65 |
| Ridge | 7.33 (0–12) | 34.83 (0–208) | 1513.67 | 35.00 (16–45) | 1192.18 | 1.55 | 61.59 |
| Shoulder | 8.00 (4–12) | 30.17 (0–166) | 1438.67 | 34.83 (24–43) | 1303.24 | 1.17 | 56.86 |
| Twin Peaks | 14.50 (10–20) | 3.83 (0–13) | 1517.00 | 42.83 (39–49) | 1636.16 | 0.97 | 51.43 |
| Hill | 13.50 (10–17) | 0.83 (0–3) | 1449.50 | 42.00 (41–45) | 1604.23 | 1.26 | 57.80 |
| Converging Valleys (Y) | 5.67 (4–7) | 80.17 (1–184) | 1514.33 | 26.67 (23–30) | 1081.48 | 0.90 | 60.46 |

## Corridor substitutions

| Terrain | Method | Valid / evaluated | Angular improves | Metric improves | Both improve |
|---|---|---:|---:|---:|---:|
| Flat | Geometric extreme pair | 6/6 | 5 | 6 | 5 |
| Flat | Route-ranked pair | 6/6 | 5 | 6 | 5 |
| Ridge | Geometric extreme pair | 6/6 | 5 | 5 | 4 |
| Ridge | Route-ranked pair | 6/6 | 6 | 6 | 6 |
| Shoulder | Geometric extreme pair | 6/6 | 5 | 4 | 4 |
| Shoulder | Route-ranked pair | 6/6 | 6 | 5 | 5 |
| Twin Peaks | Geometric extreme pair | 6/6 | 6 | 6 | 6 |
| Twin Peaks | Route-ranked pair | 6/6 | 6 | 5 | 5 |
| Hill | Geometric extreme pair | 6/6 | 6 | 5 | 5 |
| Hill | Route-ranked pair | 6/6 | 6 | 6 | 6 |
| Converging Valleys (Y) | Geometric extreme pair | 6/6 | 4 | 5 | 4 |
| Converging Valleys (Y) | Route-ranked pair | 6/6 | 4 | 5 | 3 |

## Descriptive relationships

These Spearman correlations describe the sampled configurations. The paired CSV reports within-seed differences. Seeds are shared across terrain types and the correlations are descriptive.
- accessible holes and lines · ρ 0.840, n 36
- required regions and lines · ρ 0.687, n 36
- singleton regions and lines · ρ 0.028, n 36
- excluded unassigned and accessible holes · ρ -0.517, n 36
- lines and angular absolute mean · ρ 0.303, n 36
- lines and metric absolute mean · ρ -0.055, n 36
- Geometric extreme pair band aspect ratio and angular change against strict backward · ρ 0.026, n 36
- Geometric extreme pair band aspect ratio and metric change against strict backward · ρ -0.140, n 36
- Route-ranked pair band aspect ratio and angular change against strict backward · ρ -0.035, n 36
- Route-ranked pair band aspect ratio and metric change against strict backward · ρ -0.029, n 36

## Seed-level extremes

- Flat · seed 43 retained 43 backward lines, and seed 45 retained 50.
- Flat · beyond three within-terrain median absolute deviations: seed 45 (50 lines).
- Ridge · seed 45 retained 16 backward lines, and seed 40 retained 45.
- Ridge · beyond three within-terrain median absolute deviations: seed 45 (16 lines).
- Shoulder · seed 42 retained 24 backward lines, and seed 45 retained 43.
- Shoulder · beyond three within-terrain median absolute deviations: seed 42 (24 lines).
- Twin Peaks · seed 44 retained 39 backward lines, and seed 42 retained 49.
- Twin Peaks · beyond three within-terrain median absolute deviations: seed 42 (49 lines).
- Hill · seed 43 retained 41 backward lines, and seed 40 retained 45.
- Hill · beyond three within-terrain median absolute deviations: seed 40 (45 lines).
- Converging Valleys (Y) · seed 40 retained 23 backward lines, and seed 44 retained 30.

## Computational performance

| Terrain | Mean generation seconds | Mean candidate seconds | Mean analysis seconds | Mean worker peak MiB |
|---|---:|---:|---:|---:|
| Flat | 189.87 | 188.67 | 470.22 | 684.55 |
| Ridge | 276.23 | 274.98 | 382.02 | 698.80 |
| Shoulder | 243.86 | 242.64 | 491.96 | 730.02 |
| Twin Peaks | 202.72 | 201.46 | 602.95 | 730.02 |
| Hill | 200.74 | 200.35 | 907.13 | 619.79 |
| Converging Valleys (Y) | 316.58 | 315.84 | 443.56 | 552.94 |

## Aggregation and accessible component exceptions

- ridge-45 uses the open component reached from the original dyad seed. The initial largest-component checkpoint is preserved in its journal. Its largest component contained no assigned open cells.
- shoulder-42 completed 89 dyads · stagnation limit reached.

## Methods and reproducibility

Flat elevation differences are zero. The unchanged slope and contour scores therefore rank eligible neighbors by their seeded random terms. The sorted clipped-face inventory makes the random draw sequence reproducible.
Angular depth uses 90° turn units and zero-cost doorway entry via incident regions. Metric distances apply to the finite certified attachment and axial graph. Peak memory refers to worker high-water RSS. Archived Hill and Y records may lack the finer timing fields collected in the extension. Corridor selection runtime covers the shared bounded search. A map's routing time covers its evaluated network.

Run the new cases and resume their journals with `python -m experiments.extended_terrain --workers 4` from the repository with `PYTHONPATH=src:.`. Export the completed cohort with `python -m experiments.extended_terrain_export`.

[Statistics](statistics.csv) · [Terrain summaries](terrain-summary.csv) · [Paired differences](paired-terrain-differences.csv) · [Vector atlas](numbered-axial-atlas.pdf) · [Visual index](visual-index.json)
