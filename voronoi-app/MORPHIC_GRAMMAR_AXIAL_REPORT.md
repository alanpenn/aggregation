# Morphic Grammar - Emergent Axial Structure

## Scope and implementation

This work extends the cellular grammar experiments to derive sampled axial
structures from continuous open-space geometry. It does not reintroduce the
historical ideographic parser and does not claim to validate all eight
syntaxes in Hillier, Leaman, Stansall and Bedford (1976).

The existing grammar remains modular:

| Module | Responsibility |
|---|---|
| `src/voronoi_app/morphic/carrier.py` | Stable cells, clipped Voronoi polygons and edge adjacency |
| `src/voronoi_app/morphic/rules.py` | Random, adjacent and enclosing occupation; recorded transitions |
| `src/voronoi_app/morphic/open_space.py` | Continuous union of open-cell polygons |
| `src/voronoi_app/morphic/axial.py` | Sampled maximal-line approximation, axial graph and measures |
| `src/voronoi_app/morphic/axial_experiment.py` | Reproducible trajectories, stages, geometry references and saved results |
| `src/voronoi_app/morphic/axial_statistics.py` | Paired exploratory tests for shared stages |
| `src/voronoi_app/morphic/axial_viz.py` | Morphology, line, graph, distribution and trajectory plots |
| `app/pages/2_Morphic_Grammar_Emergent_Axial_Structure.py` | Interactive three-view Streamlit experiment |

The page analyses selected growth stages and keeps generation separate from
axial measures. Axial integration, intelligibility and other global measures
are calculated only after each growth state is generated; they are not used
to select cells.

## Representations and definitions

* **Cell graph:** Voronoi cells connected when their clipped polygons share a
  boundary of positive length. Point contact is not adjacency.
* **Open geometry:** union of polygons for unoccupied cells. This is geometric
  openness, not pedestrian accessibility: the grammar has no door or
  permeability constraints.
* **Candidate line:** a straight line cast through an interior sample at a
  sampled orientation, clipped to one contiguous segment of open geometry.
* **Sampled maximal line:** the longest such contiguous segment containing its
  sample. It cannot cross occupied polygons or cross a void in the open
  geometry.
* **Selected axial representation:** a greedy cover of interior samples by
  candidate lines, preferring the line that covers most uncovered samples,
  then the longer line. This is a deterministic approximation, not a
  conventional, complete or unique axial map.
* **Axial intersection graph:** selected lines are nodes; an edge exists only
  when the line geometries intersect inside open geometry. Disconnected
  open-space systems are not joined.
* **Global integration:** Hillier-Hanson real relative asymmetry convention:
  `Integration = 1 / RRA`, `RRA = RA / Dk`,
  `RA = 2(MD - 1)/(k - 2)` and
  `Dk = 2*(k*(log2((k+2)/3)-1)+1)/((k-1)*(k-2))`.
  Each axial graph component is analysed independently. Components smaller
  than three lines and degenerate cases have missing integration.
* **Local integration:** the same RRA definition on the node's reachable
  neighbourhood within topological radius 3 by default.
* **Intelligibility:** Pearson correlation between axial connectivity and
  global integration. The report also gives R-squared and valid observation
  count. Correlation is missing if fewer than three valid observations or
  either variable is constant.
* **Cycle rank:** `E - V + C` on the axial intersection graph.

## Validation and tests

The sampled extractor was tested on hand-built straight, L-, T-, cross-, ring-,
courtyard-with-entrance and disconnected open geometries. Tests check that
every returned segment stays in the open domain, expected intersections
exist, a ring's central void is not crossed, and disconnected spaces remain
disconnected. The sample-coverage fraction is reported at every stage; it was
1.0 in all pilot and full-batch snapshots.

The five-seed pilot completed 15 mode/seed runs with 65 snapshots, shared
carrier geometry per seed, 100% sample coverage and no analysis failures.
After that validation, the full experiment completed: **30 seeds x 3 modes =
90 runs and 390 snapshots**, with 30 shared carriers and no analysis failures.

Test command:

```bash
.venv/bin/python -m pytest tests -q
```

Result: **81 passed, 1 skipped, 1 failed.** The failure,
`test_fig_aggregation_draws_black_door_lines`, is a pre-existing legacy render
test: it supplies a fake Voronoi object without a `points` attribute. The same
failure was reproduced on the earlier `e285550` revision, before this work.
The new axial tests and the existing grammar tests pass. The Streamlit page was
also run with `streamlit.testing.v1.AppTest` on reduced smoke settings; it
completed without exceptions. This verifies app execution, not visual browser
inspection.

## Full controlled experiment

Configuration: 200 Voronoi cells; flat terrain; 60 occupied cells; seeds 40-69;
analysis every 10 occupied cells; sample spacing 8; angular step 15 degrees;
local radius 3. Each mode for a seed reused the same carrier geometry. The
existing enclosing rule stops after its target becomes enclosed, so it
typically occupies only 5-6 cells; its final results are **not size matched**
to the 60-cell modes and are not included in common-stage paired tests.

### Results at 60 occupied cells (mean and standard deviation across seeds)

| Measure | Random occupation | Adjacent aggregation |
|---|---:|---:|
| Axial lines | 26.43 (1.45) | 21.30 (1.80) |
| Mean line length (geometry units) | 51.03 (3.20) | 65.79 (6.94) |
| Axial graph components | 3.53 (1.36) | 4.83 (1.49) |
| Axial graph cycle rank | 28.87 (9.49) | 41.90 (14.29) |
| Mean axial connectivity | 3.91 (0.74) | 5.52 (1.36) |
| Mean axial depth | 2.52 (0.37) | 1.75 (0.38) |
| Mean global integration (RRA) | 1.53 (0.33) | 3.54 (1.87) |
| Mean intelligibility R-squared | 0.679 (0.211) | 0.748 (0.146) |

Enclosing aggregation stopped after **5.90 (1.06)** occupied cells on average.
At that final stage its mean axial-line count was 19.47 (0.63), mean line
length 99.93 (2.69), axial graph components 1.90 (0.31), mean global
connectivity 9.75 (0.93), mean axial depth 1.42 (0.07), mean global
integration 5.14 (0.58), and mean intelligibility R-squared 0.864 (0.078).
These high values are descriptive only and confounded by its much smaller
occupied count and different open-space extent.

### Paired exploratory tests

Random and adjacent modes were compared at 60 occupied cells, paired by seed
(n=30), using two-sided Wilcoxon signed-rank tests. Holm correction was applied
across the four reported outcomes.

| Outcome (adjacent minus random) | Mean paired difference | Raw p | Holm p |
|---|---:|---:|---:|
| Axial line count | -5.13 | 1.61e-6 | 3.21e-6 |
| Mean line length | +14.76 | 5.59e-9 | 2.24e-8 |
| Mean global integration | +2.01 | 4.71e-7 | 1.41e-6 |
| Intelligibility R-squared | +0.069 | 0.221 | 0.221 |

These are exploratory comparisons, not a preregistered analysis. The
enclosing mode is not included because it has no shared 60-cell stage.

### Developmental trajectory

| Occupied cells | Random: mean line count | Random: mean line length | Random: R-squared | Adjacent: mean line count | Adjacent: mean line length | Adjacent: R-squared |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 19.00 | 103.29 | 0.801 | 18.23 | 98.43 | 0.838 |
| 20 | 20.67 | 94.01 | 0.841 | 19.07 | 90.26 | 0.792 |
| 40 | 23.80 | 72.83 | 0.880 | 20.77 | 77.13 | 0.794 |
| 60 | 26.43 | 51.03 | 0.679 | 21.30 | 65.79 | 0.748 |

The enclosing mode has only its terminal snapshot because its target is
enclosed before the first 10-cell interval.

## Interpretation of the research questions

**RQ1 - Emergent linearity.** The sampled extractor finds extended visibility
lines in all modes without linearity preferences in the generation rules.
Line lengths change substantially with occupation. This shows that the
geometry yields elongated visibility segments; it does not establish that the
approximation recovers conventional urban axial lines.

**RQ2 - Generative differentiation.** At the matched 60-cell stage, paired
tests distinguish random from adjacent aggregation in line count, line length
and mean integration under this extraction method. The intelligibility
difference is not statistically significant after the stated test
(Holm-adjusted p=0.221). Enclosing aggregation differs descriptively, but
stops far earlier and is not a matched comparison.

**RQ3 - Intelligibility.** Mean R-squared is high in both matched modes, but
has no significant paired difference at 60 cells. It is not monotonic during
growth: the random mode peaks around 40 cells in this batch, while adjacent
aggregation declines at first and then levels. These conclusions are sensitive
to the sampled axial representation and the integration convention.

**RQ4 - Developmental trajectory.** Both matched modes show increasing line
counts and declining mean line length as occupation grows. At 60 cells,
adjacent aggregation has fewer, longer lines than random occupation. The
enclosing mode cannot support the same trajectory because of early stopping.

**RQ5 - Emergence versus prescription.** Connected or scattered cellular
growth produces different visibility and intersection graphs without
optimising global measures. However, the candidate directions, spatial sample
spacing, coverage tolerance and greedy selection are themselves modelling
choices; observed line patterns are not independent of the extraction
procedure.

## Limitations and next work

1. **Axial extraction is approximate.** A finite angle set and spatial samples
   can miss lines, alter intersections and produce different selected covers
   as settings change. Full sample coverage is not proof of an exhaustive or
   minimal axial map.
2. **Sensitivity has not been tested.** Vary sample spacing, angular
   resolution and greedy coverage settings; compare with a better-validated
   axial-map algorithm before making strong claims.
3. **Open is not accessible.** The open geometry is not constrained by doors,
   pedestrian permeability or movement cost. Those require a separate
   accessibility representation.
4. **Unequal enclosure stopping.** Mode 2 has far fewer occupied cells.
   Compare it with a budget-matched continuation variant and with random and
   adjacent baselines' probability of enclosing the same designated target.
5. **No terrain effect.** Flat terrain is recorded; generation ignores terrain
   in this initial experiment.
6. **Statistical scope.** The paired tests are exploratory, limited to random
   versus adjacent at 60 occupied cells. The 30 seeds are not evidence about
   all carriers or parameter settings.

The results do not validate the eight-syntax theory as a whole, nor establish
an urban design principle.

## Reproduce and inspect

```bash
cd voronoi-app
PYTHONPATH=src .venv/bin/python scripts/run_morphic_axial_batch.py --pilot
PYTHONPATH=src .venv/bin/python scripts/run_morphic_axial_batch.py
./run_streamlit.sh
```

Open the **Morphic Grammar - Emergent Axial Structure** page in Streamlit.
The full outputs are in `outputs/morphic_axial_batch/`: complete per-run
records and transformations in `axial_runs.json`, carrier WKB references in
`carriers/`, stage summaries, paired-test results, and representative plots.
The five-seed pilot is in `outputs/morphic_axial_batch_pilot/`.
