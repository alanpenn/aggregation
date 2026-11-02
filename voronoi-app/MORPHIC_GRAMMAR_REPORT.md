# Morphic Grammar Experiments

Reference: Hillier, B., Leaman, A., Stansall, P. and Bedford, M. (1976). *Space syntax*.
Environment and Planning B, 3, 147-185.

Scope: the **minimum setup** and the **third and fourth syntactic operations** only. Nothing here
tests the eight-syntax theory as a whole, and the historical ideographic parser is not used.

## Implementation

Module `src/voronoi_app/morphic/` (independent of the Streamlit app):

| File | Role |
|---|---|
| `carrier.py` | Carrier space, cells, adjacency, Voronoi carrier builder |
| `morphology.py` | Components, boundary cells, exterior/enclosed open space, cycles, enclosure score |
| `rules.py` | `GenerativeRule` interface, Modes 0/1/2, engine `run_rule`, transformation log |
| `metrics.py` | Quantitative analysis of a configuration |
| `experiment.py` | Config, deterministic experiment ids, comparison/batch runners, CSV/JSON output |
| `report.py` | Plots and per-mode summaries |

Streamlit page: `app/pages/1_Morphic_Grammar_Experiments.py`. Batch: `scripts/run_morphic_batch.py`.
Tests: `tests/test_morphic_grammar.py`.

### Definitions and discretisation assumptions

* **Adjacency**: shared boundary of positive length (> 1e-6). Point contact does not count. Adjacency is
  recomputed from clipped cell polygons, not taken from the Voronoi ridge list, which can include ridges
  lying outside the carrier.
* **Exterior open space**: open cells connected through open adjacency to an open cell touching the carrier boundary.
  **Enclosed open space**: an open component with no boundary cell.
* Because adjacency is edge-only, a ring whose occupied cells meet only at vertices still encloses
  (tested: a ring with a corner removed has no graph cycle yet still encloses its centre).
* **Cycle measure**: cyclomatic number E - V + C of the occupied adjacency graph. On Voronoi cells every
  point where three occupied cells meet adds a trivial 3-cycle, so this mostly counts vertices. The
  **non-trivial cycle** measure is the cyclomatic number minus the number of triangles.
* **Compactness**: 4*pi*A/P^2 of the union of occupied cells (P includes hole boundaries and carrier-edge contact).
  For a disconnected configuration it describes the union.
* Undefined values (e.g. compactness of an empty configuration) are `None` / empty in CSV, never zero.
* Graphs are never mixed: components and cycles use the **occupied adjacency graph**; open-space components
  and connectivity (existing `ConnectivityMeasure`) use the **open-space accessibility graph**.
* The existing `VoronoiGridGenerator` returns int(sqrt(N))^2 cells (196 for N = 200), so the carrier uses its own
  seeded jittered-grid sampler for exactly N cells, plus the app's existing clipped-Voronoi construction.
  The existing grid code is unchanged. Terrain only supplies cell elevations; the rules do not use it.

### Modes

* **Mode 0 random**: any unoccupied cell, uniformly. No adjacency requirement.
* **Mode 1 adjacent (3-syntax)**: one uniformly random seed cell, then a uniformly random unoccupied cell
  sharing a boundary with the aggregate. No compactness or courtyard preference.
* **Mode 2 enclosing (4-syntax operational approximation)**: the 1976 paper does not give a unique local
  algorithm for the fourth operation, so this is a **hypothesis**, not a reconstruction.
  * Target: a protected open interior cell (or small cluster): the cell nearest the carrier centre.
  * Seed: a random neighbour of the target. Then only cells adjacent to the aggregate are eligible; the target is never eligible.
  * **Enclosure score** = fraction of the target's boundary length shared with occupied cells.
  * Selection weight = (1 - s) + s * gain / max_gain, where gain is the length a candidate shares with the target
    and s is the configurable strength (0 = uniform, equal to Mode 1 except for the seed). If no candidate has gain, selection is uniform.
  * Stops when the target lies in an enclosed open component (geometric enclosure), when no candidates remain, or at the cell budget.
* **Mode 2b** (extra, labelled): as Mode 2, but after enclosure it continues uniformly adjacent growth to the cell budget.
  Mode 2 stops after ~6 cells, so its aggregate is much smaller than Mode 0/1; Mode 2b gives a budget-matched comparison.

Eligibility, weighting, transition and termination are separate methods of each rule. Every step logs
step number, cell, eligible-candidate count, rule, and changes in occupied components, enclosed components, cycles and enclosure score.

## Controlled comparison

200 Voronoi cells, flat terrain, 60 occupied cells (Mode 2: until enclosed), seeds 40-69 (30 seeds), strength 1.0, single-cell target.
For each seed one carrier is built and shared by all modes. **The full 30-seed batch ran** (120 runs, ~9 s).
Output: `outputs/morphic_grammar/` (`results.csv`, `runs.json` with configs and step logs, `summary.csv/json`,
`morphologies_seed40.png`, `distributions.png`). Mean (std) over 30 seeds:

| Measure | Random | Adjacent | Enclosing (stops) | Enclosing+continue |
|---|---|---|---|---|
| Occupied cells | 60 | 60 | 5.9 (1.1) | 60 |
| Occupied components | 21.0 (2.6) | 1 | 1 | 1 |
| Enclosed open components | 0.27 (0.51) | 2.50 (1.54) | 1 | 3.10 (1.33) |
| Enclosed open area | 14 (29) | 183 (121) | 49 (10) | 179 (86) |
| Graph cycles (cyclomatic) | 8.3 (3.6) | 61.1 (6.3) | 1 | 50.7 (7.9) |
| Non-trivial cycles | 0.27 (0.51) | 2.50 (1.54) | 1 | 3.10 (1.33) |
| Compactness | 0.025 (0.002) | 0.128 (0.032) | 0.315 (0.031) | 0.091 (0.023) |
| Mean open connectivity | 3.82 (0.11) | 4.62 (0.21) | 5.32 (0.03) | 4.27 (0.12) |
| Any enclosed open space (rate) | 23% | 90% | 100% | 100% |
| Target enclosed (rate) | n/a | n/a | 100% | 100% |

Success of the enclosure operation: 30/30 in both Mode 2 variants (strength 1.0, single-cell target). No run hit the no-candidates termination.
Statistics are descriptive; no significance tests were run.

## Findings

**A. Generative differences.** The modes are clearly distinguishable. Random occupation gives ~21 scattered
components, very low compactness and almost no enclosure. Adjacent aggregation gives one connected, ragged aggregate.
Mode 2 yields a small compact ring around the target.

**B. Emergent structure.** Nothing in Mode 1 mentions enclosure, yet 90% of runs contain at least one enclosed open
component (mean 2.5): purely local adjacency produces enclosed voids by accident, as notches close. Connectedness is guaranteed by the rule;
compactness (~0.13) and the cycle count arise without being specified. Mode 1 is about 5x as compact as Mode 0 (0.128 vs 0.025), solely from adjacency.

**C. Topological consequences.** Raw graph cycles are dominated by trivial vertex triangles (61 cycles but only 2.5 non-trivial in Mode 1), so
the cyclomatic number is a poor proxy for courtyards on Voronoi cells. Non-trivial cycles equal enclosed open components
in these data (equal in all 120 runs; a regularity of this carrier, not a theorem, and the hand-built tests show cases where they diverge).
Mean open connectivity differs mainly through how many open cells lose neighbours to occupation: scattered occupation (Random, large perimeter)
gives 3.82, one aggregate of the same size (Adjacent) gives 4.62, and Enclosing (only ~6 occupied) gives 5.32. This is a perimeter/size effect, not evidence of an
accessibility effect of enclosure.

**D. Theoretical limitations.**
* Adjacency vs. surrounding: a deliberate enclosure preference is a different rule from adjacency, yet adjacent growth already
  encloses space in 90% of runs. Enclosure therefore cannot be used alone to identify the 4-syntax.
* The paper's fourth operation does not fix a target, a score or a stopping rule; these were chosen here. Single-cell targets are enclosed
  by a ring of 5-6 Voronoi cells, which is nearly the cheapest possible outcome, so Mode 2 success is partly by construction.
* The result depends on discretisation: edge-only adjacency, cell-size distribution and the boundary definition all change what counts as enclosed.
* Mode 2 and Mode 1 are not directly comparable on size (5.9 vs 60 cells); Mode 2b equalises size but then mixes two rules.
  Comparisons of compactness across differing sizes are confounded.
* A missing control: how often a Mode 1 aggregate happens to enclose the *same central target cell*. This would give the baseline for "enclosure success" attributable to the preference.

**E. Next steps.** Add that central-target control for Modes 0/1; vary target size and strength (s from 0 to 1); add an explicit
cell-attribute / state relation (needed for operations that depend on cell type, e.g. object vs. space) and multiple object types;
support non-adjacent relations such as separation or ordering between aggregates; add significance tests and larger N; test other carriers
(Cartesian grid, topography-responsive cells) to separate discretisation effects from rule effects.

This experiment does not validate the eight-syntax theory as a whole.

## Reproduce

```bash
cd voronoi-app
.venv/bin/python -m pip install pytest      # once; pytest was not in the venv
PYTHONPATH=src .venv/bin/python scripts/run_morphic_batch.py --smoke   # 3 seeds, writes outputs/morphic_grammar_smoke
PYTHONPATH=src .venv/bin/python scripts/run_morphic_batch.py           # 30 seeds
.venv/bin/python -m pytest tests -q
./run_streamlit.sh                                                      # then open "Morphic Grammar Experiments" in the sidebar
```
