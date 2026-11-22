# Doorway shortest-path tangent experiment: Y seed 42

## What is and is not preserved

The aggregation model stores a door as an `(open cell, building cell)` pair.
The current slope-preference implementation creates one pair when each
building is added. The general result format is a list and can represent
multiple pairs for one building, but this reconstructed run has one per
building.

The Streamlit renderer computes polygon centroids and draws a short line
between them; it does not store or draw a defined entrance point. The axial
snapshot saves building polygons and the set of paired open cells, but not
the individual pairings or original Voronoi data. In particular, 73 buildings
have more than one geometrically adjacent paired-open cell, so their pairs
cannot be inferred uniquely from snapshot adjacency alone.

We reconstructed the grid and aggregation from the snapshot configuration.
All 484 saved polygons, the building and paired-open cell sets, and all
building labels match the preserved records exactly. This **does not prove**
that the reconstructed door pairings match the original session: those
pairings were not saved.

Following the user's assumption, this experiment places a doorway at the
exact rational midpoint of the positive-length face shared by the reconstructed
dyad's **saved, canvas-clipped** polygons. This is a new experimental point,
not a claim that the renderer stored it or drew it at that location. Shared
faces and midpoints use exact fractions of the original binary64 polygon
coordinates. A face with no unique positive-length overlap is reported, not
guessed. Exact clearance is certified relative to the constructed GEOS
accessible-domain overlay, which is not an independently exact construction.

Of 100 buildings and 100 reconstructed conceptual doors, 99 have distinct,
valid doorway positions with certified connectors reaching open-space interior.
The remaining dyad, open cell 439 and building cell 395 (building label 99),
has no shared face in the clipped snapshot and is excluded. Its original
Voronoi ridge lies beyond the canvas. No reconstructed building lacks a
conceptual pair, but building 99 lacks a valid in-domain entrance. Consequently
the analysis does not claim complete results for all 100 buildings.

## Method and validation

The saved graph has 462 vertices and 6,532 edges; its saved digest and input
manifest are checked, and every edge is rechecked with exact clearance.
Certified doorway-to-vertex connectors and direct doorway-to-doorway links use
the same predicates, with legitimate boundary following. One single-source
metric tree is calculated per valid entrance; a deterministic eight-entrance
pilot is compared with the corresponding all-to-all records.

Only different-building, unordered doorway pairs are counted. The 99 valid
entrances yield 4,851 within-component pairs and no same-building pairs.
There are 314 direct and 4,537 occluded routes, with no unreachable pairs.
Metric edge lengths are floating-point Euclidean lengths; `1e-10` relative
tolerance flags near-equal graph alternatives. No pair was flagged in this
run; that is not an exact uniqueness certificate. The record contains one
deterministic witness per pair, not all tied routes.

Every witness is split at graph vertices using the same procedure as the
earlier backbone study; a used segment has building provenance at both ends.
All 177 used segments are flagged tangent-supported. Each unordered journey
contributes at most once to each segment. Endpoint coordinates, building
provenance, pairs of contributing buildings, candidate IDs, selected-map
containment and the path witnesses are saved in the result records.

An independent audit checked every witness's graph edges, terminal connectors
and length: maximum length reconstruction error was `2.84e-14`; all 314
direct lengths matched Euclidean distance. The first 100 paths' noded segments
were independently checked against the aggregate. Tests cover exact face
midpoints, missing faces, direct and obstacle-avoiding paths, and agreement
with the existing shortest-path implementation.

## Tangent structure and coverage

The 4,851 journeys use 177 distinct segments, with 15,247 total
journey-segment uses. The ten most-used segments account for **40.62%** of
those uses. The five highest-use segments have endpoint building labels
3–3, 23–23, 26–2, 59–59 and 59–59, and carry respectively 924, 889, 825,
672 and 602 journeys. Same-building endpoint labels may describe
boundary-following edges; the journeys themselves are between different
buildings.

| Candidate map | Used segments contained | Share of journey-segment uses |
|---|---:|---:|
| Full certified pool | 177 / 177 | 100.00% |
| Unified greedy, 29 lines | 6 / 177 | 3.60% |
| Connectivity-prioritised, 29 lines | 2 / 177 | 2.60% |
| Completed structural backbone, 66 lines | 9 / 177 | 8.27% |
| Reduced structural backbone, 35 lines | 3 / 177 | 2.79% |

These are exact collinear containment measures, **not** tests that the
selected maps preserve the corresponding complete routes.

## Comparison with previous sampling

The saved 187-segment reference combines **41,412 spatial** and **1,024
building-boundary** sampled journeys: 42,436 in total, not a pure uniform
spatial sample. The doorway analysis uses 4,851 unordered building-pair
journeys. Each distribution has its own denominator; the proportions below
must not be interpreted as sampling the same population.

The doorway and saved sample backbones share 98 segments; 79 occur only in
the doorway set and 89 only in the saved sample set. Spearman rank
correlation of utilisation over the 98 common segments is **0.605**. The
top-ten share of journey-segment uses is **40.62%** for doorways versus
**51.60%** for the mixed saved sample. On this measure the doorway distribution
is less concentrated, not more concentrated. Doorways give a distinct,
building-related spatial pattern, but spatial meaningfulness is not
quantified and no general superiority is established.

For examples, graph edge `(292, 302)` is used by 150 doorway journeys
(3.09%) and no saved sampled journeys; `(202, 203)` by 132 (2.72%) versus
30 (0.071%). Conversely, `(286, 326)` is used by 8,528 saved journeys
(20.09%) and no doorway journeys; `(45, 50)` by 7,834 (18.46%) and none.
The machine-readable records retain the full ranked sets and the explicit
1%-versus-0.1% prominence thresholds.

## Reproduction

The independent runner is `python -m experiments.doorway_backbone`. It
requires the preserved archive, snapshot, candidate and selection directories,
visibility results and structural results. It creates a new output directory
exclusively; it does not overwrite previous experiments.

```sh
MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experiments.doorway_backbone \
  --archive /Users/ucft654/Developer/aggregation-valley-research-2026-11-17.tar.gz \
  --snapshot /Users/ucft654/Downloads/axial-diagnostic.json \
  --data-dir /Users/ucft654/.copilot/session-state/3191f707-b920-4e07-817a-e0bca07f81eb/files/valley42-exchange-2026-11-17 \
  --selection-dir /Users/ucft654/.copilot/session-state/3191f707-b920-4e07-817a-e0bca07f81eb/files/valley-connectivity-2026-11-17 \
  --visibility-dir /Users/ucft654/Developer/aggregation-y-shortest-path-2026-11-17 \
  --structural-dir /Users/ucft654/Developer/aggregation-y-connectivity-backbone-2026-11-17-v3 \
  --output-dir /path/to/a/new/doorway-output-directory
```

The first full run took 321.8 seconds including figures and peaked at
342,474,752 bytes resident memory on macOS. The repeated run took 325.3
seconds and peaked at 337,674,240 bytes. The two runs produced identical
paths, segment records, map selections and pilot routes; the second adds
explicit interior-connector records. Its `doorway-results.json.gz` SHA-256 is
`39a9a96c7f390e90bcd7e2387ce99cf0bee31ba27d8d0ce6942a96fbb9d6a5b6`.
Both runs are preserved separately. Figure files show numbered buildings
and entrances, graph connectors, utilisation, distribution overlap, and
segments absent from the connectivity-prioritised map.

Headless regressions: 242 passed, 9 skipped and the slow
`test_default_voronoi_experiment_coverage_and_rings` was deselected.
The focused saved-geometry and rendering suite passed 20 tests. Pylance syntax
checks timed out.
