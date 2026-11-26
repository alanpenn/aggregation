# Voronoi Aggregation App

Experimental research platform for computational urban design, Voronoi aggregation, and space-syntax analysis.

## Architecture

This application has been refactored into a **modular, extensible research platform** with pluggable components for:

- **Terrain Providers** (6 types: Flat, Hill, Ridge, Shoulder, Valley, Twin Peaks)
- **Grid Generators** (Voronoi, Cartesian)
- **Aggregation Strategies** (Slope preference, future: distance, visibility)
- **Space-Syntax Measures** (Mean Depth, Connectivity, Integration, Choice)
- **Representations** (Cell graph, Dual graph, geometric Axial maps)
- **Morphic grammar** (deterministic graph rewriting with bounded evaluation and traces)

See [ARCHITECTURE_PROGRESS.md](ARCHITECTURE_PROGRESS.md) for detailed refactoring status and extension guide.

## Features

- Interactive Streamlit UI with parameter controls
- Procedural terrain generation
- Voronoi and Cartesian grid generation
- Dyad-based urban aggregation with slope preference
- Visibility graph computation
- Space-syntax analysis (connectivity, integration, choice measures)
- Axial-line intersection graphs usable by the configurational measures
- Optional greedy axial map of open cells with enclosed-obstacle ring checks
- Reproducible graph grammar rules for generating spatial structures
- Experiment serialization to JSON
- Reproducible research with seed control

### Axial map approximation

Choose **Axial Map** under **Experiment Control** before running an experiment.
The **Axial coverage** control defaults to **Voronoi cells**; **Convex regions
(experimental)** selects the alternative described below.
Choose **All axial candidates** to inspect the full candidate set separately
from the selected lines.
Choose **Axial candidate audit** to compare candidates with visible mutual
tangents between exposed convex building corners. The audit is independent of
selection and does not change the generator. It reports mixed building/canvas
corners separately, uses buffered visibility, and flags numerical clipping
ambiguities rather than counting them as missing. Candidate origins may overlap;
the plot assigns one color per line, and fallback denotes lines not matched to
the other replayed source categories. This exhaustive diagnostic runs when an
axial map is requested and can be slow. Its progress display distinguishes
candidate-source replay from pair classification; the time remaining is an
estimate for the current phase only. "Valid" means accepted by the existing
buffered audit, not certified exact geometric validity. Invalid counts include
coincident, blocked and non-occluding pairs; clipping ambiguities are unresolved.
The last completed audit is cached per Streamlit session using the exact open and
occupied polygons, ordered candidate endpoints and ambiguity records. The
geometry-derived tolerance has no independent user setting. Repeating the same
audit reuses the result; changing an audit input or the audit implementation
invalidates it. Other widget interactions do not themselves rerun the audit.

After an experiment, use **Experiment diagnostics** to download its configuration.
For a generated axial map, the diagnostic snapshot also contains the exact open
and occupied polygons, candidate lines, and unresolved tangent evidence. When
missing or indeterminate tangents are detected, the app automatically saves a
uniquely named JSON snapshot in `diagnostics/` on the server and highlights their
seed segments and independently clipped intervals. This directory is ignored by
Git; keep or remove its files according to your data-retention needs. Upload a
snapshot and choose **Rerun saved axial audit** to audit its saved geometry and
candidates without regenerating the settlement. The saved candidates and rejection
reasons describe the original run; rerunning the audit does not regenerate them.
Snapshots contain the experiment geometry and configuration, so share them only
with intended recipients.
The map uses the same clipped cell polygons as the visibility analysis. Every
cell without a building is accessible, including cells not assigned to a dyad;
only building cells obstruct movement and visibility. Unassigned open cells are
shown in pale sand and are not added to the aggregation's dyads. The existing
cell and visibility graph representations still describe paired open spaces.
With the default coverage model, the map selects lines greedily to enter every
accessible cell and retains closed line routes around occupied holes in the
open-space union. The display reports the number
of candidates, selected lines, covered cells, and preserved obstacle rings;
generation errors are reported in the app. The generation result also reports
axial and open-space component counts.

For experimental convex coverage, the accessible polygons are first dissolved
and occupied geometry subtracted. Zero-tolerance simplification removes redundant
boundary vertices only when the domain remains geometrically equal. Constrained
triangles of each component seed overlapping convex regions; each seed grows
by taking its convex hull with domain-boundary vertices whenever the result
remains within the component. Duplicate regions are removed and each component's
region union must equal that original accessible component using GEOS predicates.
Components without dyad cells remain traversable and are covered independently;
they are not connected to another component by the selection. A line covers a
region only if it enters its interior. The same candidate set, greedy scoring,
ring checks and connectivity rules are used, but the coverage targets are
these regions rather than cells.
The app shows region coverage and marks uncovered regions in the diagnostic plot.
If candidates cannot cover every region, generation fails and the plot shows the
partial selection and uncovered regions instead of a completed axial map.

The grown regions are maximal only with respect to the finite boundary-vertex
anchors and the chosen seeds. They do not enumerate all continuous maximal
convex spaces, and different triangulation seeds can change the approximation.
The region construction depends on the dissolved domain rather than internal
cell boundaries, but candidate generation still uses cell centroids, so
regenerating candidates after refinement may change the selected map.
Floating-point geometry and boundary tangencies remain limitations. The convex
mode requires Shapely 2.1 or later and GEOS 3.10 or later.
Existing candidate endpoints can have tiny floating-point penetrations into
occupied interiors, including in the experimental selection; obstacle clearance
is therefore not certified. Convex coverage does not repair candidate geometry.
Hill seed 42 has an end-to-end regression that can take many minutes:

```bash
HILL42_FULL_REGENERATION=1 .venv/bin/python -m pytest -q tests/test_axial_generator.py -k hill_seed42_convex_axial_map
```

#### Experimental angular selection

With **Convex regions (experimental)** coverage, **Axial selection method**
offers two bounded local searches in addition to the unchanged greedy baseline.
The first compares solutions lexicographically by line count and then mean
angular depth; the second minimises mean angular depth plus λ times line count.
The requested iteration count and seed control the repeatable search over
additions, deletions, one-for-one and two-for-two substitutions, and bounded
two-for-one and three-for-two exchanges. It starts with the greedy solution
when that is geometrically valid and feasible, or attempts a safe repaired seed.
It screens all candidates before constructing a pool of at most 192 lines,
including feasible greedy lines, occupied-hole boundary lines, coverage
candidates, and long tangent, boundary and centroid alternatives. If required
initial and ring-boundary candidates exceed this limit, or the bounded pool
cannot satisfy coverage, the app reports the failure. Neither mode guarantees
a globally minimum line count or angular objective.

The same fixed set of up to 12 deterministic, spatially dispersed points is used
for both maps. Each point is attached to the nearest visible point on the
selected linework; connector segments are checked against the accessible domain
and occupied interiors, and their entry and exit turns contribute to angular
depth. Movement states preserve direction: straight costs zero, a right turn
costs one, and reversal costs two. Exact rational segment intersections avoid
joining merely nearby lines. Topological depths use the same sample attachments
and count changes between axial lines. Pairs in different accessible components
are excluded and reported, rather than treated as having finite depth. The
comparison shows the samples, their attachments, per-sample mean depth,
distribution, and an overlay of common and differing lines.

Angular selection conservatively rejects candidates when GEOS does not cover
them with the accessible domain, and also checks the stored coordinates using
exact rational occupied-interior and domain-complement predicates. This may
reject some valid boundary tangencies, but never deliberately displaces an
unsafe line. Coverage, circulation rings and per-component connectivity must
still pass the existing constraints. Unresolved tangent candidates are not
reconstructed or inserted. An unsafe greedy baseline is labelled as such and
its angular depth is not presented as a valid comparison; if no safe feasible
seed can be found, angular selection fails explicitly and the greedy result
remains available as a reference.

The separate `voronoi_app.exact_axial` experiment reconstructs candidates from
their seeds, stores rational maximal endpoints and provenance, and applies exact
interior coverage, intersection, connectivity and ring checks to greedy and
bounded angular selection. It also adds a safe interior seed for any otherwise
uncovered convex region. Its predicates treat the input polygon coordinates as
exact binary64 values and check both the occupied union and each original
occupied polygon; domain construction and convex regions are still produced by
GEOS. The existing Streamlit and float-based selectors are unchanged.

Newly generated floating-point candidates retain their defining seed pairs,
including deduplicated alternatives. Older snapshots contain only rounded
endpoints and source labels: reconstructing those lines uses their stored
endpoints as new seeds, not as recovered original provenance. A line rejected
by the exact check is reported rather than silently moved. Floating-point
display of an exact candidate is not its authoritative geometric representation.

For a saved audit snapshot, the exact experiment can be run without Streamlit:

```python
import json
from pathlib import Path
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.angular_optimisation import spatial_samples
from voronoi_app.exact_axial import generate_exact_candidate_pool, greedy_selection, angular_selection

snapshot = json.loads(Path("diagnostics/your-snapshot.json").read_text())
opened, occupied, saved, _, _ = load_axial_snapshot(snapshot)
tangents = [(item["start"], item["end"]) for item in snapshot["audit"]["unresolved"]]
problem = generate_exact_candidate_pool(opened, occupied, saved.candidate_lines, tangents)
greedy, _, _ = greedy_selection(problem.pool, problem.regions, problem.accessible, problem.obstacles)
angular = angular_selection(
    problem.pool, greedy, problem.regions, problem.accessible, problem.clearance,
    problem.obstacles, spatial_samples(problem.regions), iterations=120, seed=42,
)
print("Rejected seeds:", len(problem.pool.rejected), "Fallback regions:", problem.pool.fallback_regions)
print("Greedy / angular lines:", len(greedy), len(angular.selected))
```

Inspect the rejected seeds before treating the pool as complete. In particular,
rejecting an unsafe endpoint-based legacy seed does not prove that the original
supporting line was invalid. The bounded angular search is not an optimality
certificate.

For a fresh exact pool without legacy endpoints, enumerate original occupied
convex-corner pairs and building faces instead:

```python
from voronoi_app.exact_enumeration import (
    exact_pool_to_dict, generate_fresh_exact_candidate_pool,
)
from voronoi_app.exact_axial import bounded_two_for_one_selection

problem, audit = generate_fresh_exact_candidate_pool(opened, occupied)
Path("diagnostics/fresh-exact-candidates.json").write_text(
    json.dumps(exact_pool_to_dict(problem.pool))
)
greedy, _, _ = greedy_selection(problem.pool, problem.regions, problem.accessible, problem.obstacles)
samples = spatial_samples(problem.regions, count=12)
angular = angular_selection(
    problem.pool, greedy, problem.regions, problem.accessible, problem.clearance,
    problem.obstacles, samples, iterations=120, seed=42,
)
exchanges = bounded_two_for_one_selection(
    problem.pool, angular.selected, problem.regions, problem.accessible,
    problem.clearance, problem.obstacles, samples,
)
print("Enumeration:", audit.counts, "Domain/union rejections:", len(audit.domain_rejections))
print("Greedy / bounded angular lines:", len(greedy), len(exchanges.selected))
```

`exact_pool_from_dict` restores the rational coordinates, region coverage,
deduplicated supports, and their original building IDs and vertex indices.
Ring and fallback seeds that are not building vertices have empty vertex
references. The fresh pool contains vertex tangents, occupied-face extensions,
required ring supports, and region fallbacks when needed; it does not recreate
open-cell-centroid candidates. Occupied polygons with interior rings are
explicitly rejected because their face provenance is not yet supported. Union or accessible-domain exclusions are
retained even when separate original polygons permit a shared boundary. The
two-for-one search has bounded candidate and feasibility checks and does not
establish global optimality.

#### Replaying the exact Y-settlement references

The app's live path is `orchestrator.generate_experiment_axial_map` ->
`axial_generator.generate_axial_map`, with optional bounded optimisation in
`angular_optimisation.optimise_angular_map`. It operates on floating-point
`AxialLine` objects. It does **not** load the certified research pool or maps.

To inspect an exact pool for a new settlement, choose **Exact axial candidates**,
run an experiment, and then click **Run exact candidate enumeration**. The app
uses the original occupied and open cell polygons from that experiment; it does
not require the Y fixtures or run a selector. The pool remains in session state
until a new experiment is run. Changing sidebar parameters alone does not change
the current experiment. Filter by support type, length or building and inspect
the rational interval and all its supporting vertices. Only plotting converts
line coordinates to floats. Candidate IDs are local to the generated pool.

Enumeration checks all convex vertex pairs and can take minutes on large
settlements. Domain/union exclusions are conservative and available for review;
they are not classified as numerical failures. Accepted-support completeness is
checked within the implemented support rules only, not for all possible lines.
The underlying settlement coordinates are binary64 values represented as exact
rationals, while the domain overlay and convex decomposition use GEOS.

An isolated experimental boundary-endpoint enumerator investigates additional
exact support rules; it is not used by the app or either selector. Its
definition, comparisons and limitations are documented in
[boundary-endpoint research](BOUNDARY_ENDPOINT_RESEARCH.md).

The separate Hill angular-fidelity experiment combines the saved exact and
boundary-endpoint pools, fixes sample attachments, and checks convex coverage,
component connectivity, specified ring witnesses and angular-depth bounds.
Its sparse routing and bounded search do not affect the app or certify global
optimality. See [the experiment report](ANGULAR_FIDELITY_RESEARCH.md) for
inputs, replay commands, results and numerical limitations.

The separate research path uses `exact_enumeration.generate_fresh_exact_candidate_pool`
and `exact_pool_from_dict`, with exact predicates, coverage, connectivity,
rings and selection in `exact_axial`. `angular` supplies the common sample
attachment and directional-routing calculations. Exact selectors use the
per-origin routing implementation; the live selector still uses the per-pair
method, which is also retained as an independent replay check.

`tests/fixtures/exact_y/` preserves the original settlement snapshot and
1,651-candidate pool as losslessly compressed JSON, plus the 36-sample
24-line reference, 23-line reference, and Pareto certifications as unchanged
JSON. `manifest.json` records SHA-256 and length of each **uncompressed**
original, and geometry/provenance identity hashes independent of candidate
ordering. The replay additionally checks IDs: identities are sorted rational
interval endpoints and sorted support records, including source, exact endpoints
and their building/vertex references. Candidate IDs are not geometric identity.

Run the six saved-map certifications and the routing comparisons with:

```bash
.venv/bin/python -m pytest -q tests/test_exact_replay.py tests/test_angular.py
```

Full re-enumeration of the saved Y pool is deliberately opt-in because it is
slow. It compares all canonical exact intervals and their complete provenance,
checks every candidate's clearance, and verifies the recorded rejection counts:

```bash
EXACT_Y_REGENERATE=1 .venv/bin/python -m pytest -q -s tests/test_exact_replay.py -k fresh_y_pool
```

The replay checks original-polygon and domain clearance, all 267 convex regions,
the three saved-method ring witnesses, connectedness and 1,260 ordered sample
pairs. Recorded length and mean depths use absolute tolerance `1e-10` with no
relative tolerance; per-pair vs per-origin depths use absolute tolerance
`1e-12`. The saved exact coordinates represent the input binary64 values as
rationals; domain overlay and convex decomposition still depend on GEOS.
Dependencies are not fully version-pinned, so a different Shapely/GEOS version
can change the decomposition and cause an explicit replay failure rather than
proving the references are invalid. The fixture protects the certified maps,
not the entire history or all intermediate search artifacts.

To restore the five original files without overwriting existing files, run
from this directory:

```bash
python - <<'PY'
import gzip
import hashlib
import json
from pathlib import Path

fixtures = Path("tests/fixtures/exact_y")
manifest = json.loads((fixtures / "manifest.json").read_text())
target = Path("restored-exact-y")
target.mkdir(exist_ok=True)
for name, entry in manifest["files"].items():
    source = fixtures / entry["fixture"]
    raw = gzip.decompress(source.read_bytes()) if source.suffix == ".gz" else source.read_bytes()
    if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(f"Fixture checksum mismatch: {name}")
    with (target / name).open("xb") as restored:
        restored.write(raw)
    print(target / name)
PY
```

Select **Show certified research maps** on the main page to display any of the
six saved maps over their original settlement. The adapter verifies fixture
checksums and lineage, keeps rational candidates and support records intact,
and converts coordinates only for rendering. The displayed metrics and
coverage, connectivity and ring status are saved certification results, not
recalculated on each view. These maps are separate from the current experiment
and never enter its floating-point generator or selector. The fixture directory
must accompany the app; missing or corrupted inputs produce an explicit error.
To integrate exact selection into live experiments would require separate
review of feasibility, performance and failure reporting.

This is not a canonical minimum axial map. Candidate directions are limited to
boundary edges, mutually visible tangent pairs of exposed convex building corners, mutually visible open-cell
centroids, and fallback lines through uncovered cell interior points. Candidates are extended along their supporting
line through the connected accessible interval containing the seed, with a
scale-relative tolerance for numerical boundary contact and deduplication. Ambiguous
tangents that are visible only within tolerance, or whose extension encounters
an uncovered sub-tolerance gap, are reported rather than silently bridged.
The audit's independent clipping uses the exactly covered seed as an anchor;
it cannot establish maximality beyond an ambiguous numerical gap. Ring checks
apply to occupied holes, not arbitrary graph cycles, and boundary-following
routes are permitted. A single closed route may enclose more than one
obstacle. The greedy result is not guaranteed to be globally minimal, and
the number of candidates and computation time grow with geometric complexity
and the square of the number of open cells.
Selected lines are connected within each open-space component using exact
intersections, including overlaps. Generation fails explicitly if the available
candidates cannot provide that connectivity.

A final topological dominance pass removes a selected line only when another
selected line has all of its other line connections and removal preserves the
chosen coverage model, connectivity, and occupied-obstacle ring checks.
Connections are recalculated after each removal. A subsequent collective
redundancy pass checks each remaining line against the same constraints, even
without a single dominating line, and repeats until no line can be removed.
The app shows accepted and rejected decisions using candidate IDs and reports
mean topological depth over the same retained-line pairs before and after the
dominance pass. Collective removals can increase depth between retained lines.
These checks do not preserve every geometrically distinct route; the result is
irreducible under single-line deletion, not necessarily globally minimal.
These passes are for topological maps, not angular-depth optimisation.

## Requirements

- Python 3.11+
- Project virtual environment in `.venv`

## Running the App

From the project root:

```bash
./run_streamlit.sh
```

The script activates the venv, sets PYTHONPATH, and starts Streamlit on port 8501.

### Complementary tangents and structural reduction

Generate a settlement, choose **Complementary tangents + structural reduction** under **Axial selection method**, and click **Generate complementary axial map**. The method builds the certified candidate pool from the current settlement. It indexes exact supporting tangents at exposed convex vertices of the aggregated occupied blocks. The frozen pair score multiplies the smaller of the two intersection degrees by half of one plus the Jaccard distance between their intersection sets. This favours pairs whose two members both reach other lines and whose connections differ. Vertices with a single tangent contribute that tangent. Candidates without indexed support are carried into the starting pool for structural testing.

Completion adds certified intervals for missing strict convex-region coverage, doorway incidence, connectivity and independent circulation. Coverage repair uses the shortest eligible interval with the canonical candidate ID breaking ties. Connectivity and winding repairs have bounded search budgets. An incomplete result remains available for inspection and is marked uncertified.

**Sheaf-priority (C-H)** is the default. It tries to remove redundant members of geometrically similar corridor sheaves first. **Shortest-first (C-S)** considers shorter lines first. Both reuse the same completed pool and test every deletion for coverage, doorway access, connectivity and independent winding. Dynamic winding checks recompute which independent circulations remain as the graph changes. Final certification also verifies exact clearance and checks winding independently.

Optional **Geometric exchanges** try bounded substitutions and reduce again, preferring fewer lines, then shorter total length, then more distinct transverse crossings. The search finds a valid sparse map when it succeeds. It does not prove a global minimum. Archive replay uses the frozen historical exchange acceptance policy to reproduce its original inventories.

Choose a stage to inspect the full, complementary, completed, reduced or exchange-improved map. Toggle building numbers, vertices, regions, doors and line categories. Select a candidate ID to inspect its certified interval and incidences. The summary table reports structural checks and the effect of reduction. Use **Run angular and metric doorway analysis** separately to compare available maps on the same settlement. Angular routes use zero-cost doorway entry and exit turns. Metric routes use finite certified regional connectors. Routes are calculated only on request.

Geometry, completion, reduction and route results are cached separately in the current browser session. Display changes reuse stored results, and changing reduction order reuses the completed pool. Large settlements can take substantial time or memory. The interactive time limit is checked between search steps.

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Run the test suite with the command above to see the current result.

With the immutable benchmark fixtures installed, replay Flat 40 and the six other corrected settlements with:

```bash
VORONOI_ARCHIVE_TESTS=1 PYTHONPATH=src:. .venv/bin/python -m pytest -q tests/test_complementary_axial_archive.py
```

## Project Structure

```
voronoi-app/
├── app/
│   └── streamlit_app.py          # Main UI (being updated)
├── src/voronoi_app/
│   ├── core.py                   # Core abstractions
│   ├── registry.py               # Component registry
│   ├── terrain.py                # Terrain providers
│   ├── grid_generators.py        # Grid strategies
│   ├── aggregation.py            # Aggregation strategies
│   ├── analysis.py               # Space-syntax measures
│   ├── axial.py                  # Axial-line map and graph conversion
│   ├── grammar.py                # Morphic graph grammar evaluation
│   ├── orchestrator.py           # Experiment orchestration
│   ├── config.py                 # Legacy config (preserved)
│   ├── engine.py                 # Legacy engine (preserved)
│   ├── render.py                 # Rendering (works with new architecture)
│   └── runner.py                 # Legacy runner (preserved)
├── tests/
│   ├── test_render_doors.py      # Legacy rendering test
│   └── test_architecture.py      # New architecture tests
├── ARCHITECTURE_PROGRESS.md      # Detailed progress & extension guide
└── README.md                     # This file
```

## Extension Guide

To add a new terrain type, grid generator, or space-syntax measure:

1. **Create your implementation** - Subclass the appropriate abstract base
2. **Register it** - Add to `voronoi_app/registry.py` in `register_defaults()`
3. **Add tests** - Create test cases in `tests/test_architecture.py`
4. **Update UI** - Wire selector controls in `streamlit_app.py` (coming soon)

See [ARCHITECTURE_PROGRESS.md](ARCHITECTURE_PROGRESS.md) for detailed examples and API reference.

## Batch axial robustness experiments

Run the pilot from the repository root. Choose a store you intend to keep.

```bash
.venv/bin/python -m voronoi_app.batch --store /path/to/batch-store pilot
```

The pilot pairs candidate and selection methods on four small settlements with
two grid and terrain configurations and two seeds. It reuses each settlement
and topology, then reuses each certified pool across selectors. It reports
coverage, clearance, independent circulation, connectivity, axial depth, and
entrance reachability. The small, coupled configurations are for finding
robustness problems. They do not support estimates of terrain effects. The
full-pool selector provides a feasibility reference.

Each invocation of `run` prints a new record ID and its status. Use the
appropriate earlier record as `--parent` to start a new branch.

```bash
batch=(.venv/bin/python -m voronoi_app.batch --store /path/to/batch-store)
"${batch[@]}" run settlement --params settlement-config.json
"${batch[@]}" run topology --parent "$settlement_id"
"${batch[@]}" run candidates --parent "$topology_id" --method projected-faces
"${batch[@]}" run selection --parent "$candidate_id" --method entrance-guided
"${batch[@]}" run measures --parent "$selection_id" --params route-config.json
"${batch[@]}" run validation --parent "$measures_id"
"${batch[@]}" inspect "$selection_id"
```

Set each shell variable to the printed ID for that stage. A settlement
parameter file can specify any `ExperimentPipeline` fields, including the seed,
terrain, grid, and aggregation parameters. Use `preserve-settlement` instead of
`generate-settlement` to import an existing settlement in the batch settlement
output format. Include `configuration`, exact binary64 cell polygons in
`polygons_wkb` as WKB hex, `building_labels` keyed by cell, `dyad_open_cells`,
and `doors` as open-cell and building-cell pairs.

- To change the candidate generator, run `candidates` again with the same
  topology ID. The built-in methods are `fresh-exact` and `projected-faces`.
- To change the selector, run `selection` again with the same candidate ID.
  The built-in methods are `exact-greedy`, `entrance-guided`, and `full-pool`.
  The entrance-guided adapter consumes the saved pool directly and records
  a connector limit and extra-line budget.
- To change route analysis, run `measures` again with the same selection ID.
  For example, `route-config.json` can contain `{"connector_limit": 32}`.
  Validation can start from a measures record or directly from a selection
  record for geometric and topological checks.
- To register a revision outside the built-in adapters, pass
  `--method package.module:function --version VERSION` for the stage. Trusted
  methods receive a dictionary of verified upstream outputs keyed by stage
  and the JSON parameter object. They return
  `voronoi_app.batch_store.StageResult(output, valid=True)`, with a JSON object
  as output. A replacement that feeds an existing downstream adapter should
  keep that stage's data format.

The store keeps each attempt in `records/<id>/record.json`, with its stage
output in `output.json`. Records link to the original settlement and the
immediate input by ID and SHA-256. They record parameters, output hashes,
method identity and version, runtime versions, and archived Python source
hashes. Settlement and topology records retain cell and block geometry,
candidate records retain exact rational intervals and support provenance,
and selection records retain the selected exact line geometry. Route records
include doorway order, connectors, and the upper-triangular pair depths
in that order. A null depth represents an unreachable pair.

`export-source RECORD_ID NEW_DIRECTORY` checks the source hashes and restores
the package as it was recorded. Use it with the recorded Python and dependency
versions to run that revision. For custom methods, also preserve any external
dependencies or inputs they use. The store archives the custom method's
defining source file alongside the package source.

**Successful** means the stage completed and passed its own checks.
**Invalid** means it returned an output that failed a check.
**Failed** means the method raised an error, recorded with its traceback.
**Incomplete** means the attempt was started but never finished, for example
after interruption. Restart an incomplete stage from its recorded parent to
create a new attempt. A selection can complete successfully and be marked
invalid by a separate validator. Earlier records remain available in all cases.

### Preserved Hill 42 and Y 42 benchmark

See [the preserved-fixture research report](PRESERVED_AXIAL_BENCHMARK.md) for
the comparison and source limitations.

`python -m experiments.preserved_axial_benchmark --help` lists the preserved
snapshot, cell or label inventory, and saved doorway-result inputs for this
benchmark. Use the same store for all stages. Each run writes its case manifest
under `benchmarks/<id>/cases.json`, plus one checkpoint manifest per generator
branch. Source file hashes and doorway provenance are recorded in the imported
settlement outputs.

Export the case manifest as one row per generator–selector combination:

```bash
.venv/bin/python -m voronoi_app.batch --store diagnostics/preserved-axial-benchmark \
  export-comparison diagnostics/preserved-axial-benchmark/benchmarks/ID/cases.json \
  /path/to/new-comparison.csv
```

Use a `.json` destination for typed values. CSV encodes missing values as
`null` and structured cells as JSON. Depth statistics use population standard
deviation over the available values, with unreachable entrance pairs counted
separately. The raw per-line and pair data remain in each measures record.
Pool circulation is certified when validation supplies a clear winding
witness from that pool. The export records the full pool's rank separately.
A missing region in the entire pool proves that no subset
can meet the coverage requirement. An unverified winding rank alone leaves
subset feasibility open.

### Sheaf-aware reduction experiment

The [sheaf research report](SHEAF_REDUCTION_RESEARCH.md) compares backward
orders, local sheaf subsets and bounded substitutions on the preserved maps.
Run `python -m experiments.sheaf_reduction --help` for the batch replay
arguments and optional JSON search settings.

### Full-pool doorway routing reference

The [routing benchmark report](FULL_POOL_ROUTING_REFERENCE.md) records
fixed-connector full-pool costs, comparisons with preserved reductions, and
the separate continuous-space metric reference. It includes the command
for comparing a new validated map with a saved full-pool result.

### Route-efficient sparse maps

The [sparse-map pilot](ROUTE_EFFICIENT_SPARSE_RESEARCH.md) evaluates individual
line deletions, corridor sheaf exchanges and bounded route-budget searches
against the preserved full-pool routing records.

### Extreme corridor diagonals

The [extreme-diagonal experiment](EXTREME_DIAGONAL_RESEARCH.md) compares
geometric pairs, repairs and route-ranked alternatives on controlled
street grids and the preserved Hill and Y settlements.

### Doorway angular depth through convex regions

The [convex-region incidence experiment](REGION_INCIDENCE_ANGULAR_RESEARCH.md)
evaluates free axial entry and exit at incident convex regions and reports
the separate archived geometric-connector metric results.

### Strict convex coverage and doorway repair

The [strict coverage experiment](STRICT_CONVEX_COVERAGE_RESEARCH.md) audits
saved selections for interior traversal, repairs missing regions and
compares backward reductions with and without a geometric metric
reachability requirement.

### Extreme corridors under strict coverage

The [strict corridor reassessment](STRICT_CORRIDOR_REASSESSMENT.md) compares
geometric and route-ranked opposed pairs from the strictly validated Hill
and Y maps and audits gaps in the geometric metric connector inventory.

### Convex-region metric attachment

The [regional metric and joint corridor experiment](CONVEX_METRIC_CORRIDOR_RESEARCH.md)
certifies unrestricted line eligibility within incident convex regions
and evaluates simultaneous corridor replacements.

### Strict axial generalisation

The [paired terrain generalisation experiment](STRICT_AXIAL_GENERALISATION_RESEARCH.md)
generates Hill and Converging Valleys for seeds 40–45 and compares strict
coverage, angular incidence and regional metric routes with numbered maps.

## Default convex and axial workflow in Streamlit

New live settlement sessions default to **Maximal overlapping convex regions
(directed face-extension crawler)** and **C-H sheaf-priority reduction** with
bounded geometric exchanges enabled. Explicit method choices stay in the
session while you adjust settings or generate another settlement.

1. Set the settlement parameters and select **Run Experiment**.
2. Select **Construct or resume maximal cover**. The crawler extends oriented
   physical faces into accessible space, explores both handed traversals, and
   follows admissible branches while respecting commitment to the originating
   face. A checkpoint preserves unfinished traversal stacks.
3. Once both searches are exhausted, the app checks exact containment,
   facet-contact maximality and exact full accessible coverage. It retains every
   distinct certified maximal polygon, including overlapping ones. A lack of
   complete certification leaves axial selection unavailable for that cover.
4. Select **Generate complementary axial map**. The existing certified
   candidate generator supplies the pool. C-H uses the active maximal cover
   through exact positive-length interior incidence, then runs complementary
   selection, structural completion, unrestricted deletion, its configured
   exchanges and independent structural validation.

The default checkpoint budget is 1,000 explored prefixes per hand per click.
Increase it or continue in smaller batches as appropriate. Checkpoints are
local under `diagnostics/live-maximal-cover/` and keyed by exact settlement
data and crawler source. Opening the same settlement and choosing the maximal
method reuses its checkpoint. Other settlements may take longer to exhaust,
and the crawler may fail to certify a full cover. Both cases are shown
explicitly. There are no extra Python package requirements.

Choose **Shortest-first (C-S)** in the reduction-order menu to compare the two
complementary methods using the same cover and candidate pool. The coverage
menu also retains the previous convex and cell options for the legacy
selectors. The exact entrance-depth display uses its existing legacy workflow.
Saved axial audit snapshots retain their original coverage metadata. The
real-town import has its own reviewed geometry and subdivision controls.

**Show saved Flat 40 maximal-cover reference** loads the archived deterministic
C-H inventory. With the shared inputs available, it verifies the source
lineage, exact incidence and structural certificate and displays 596 maximal
polygons, 1,534 candidates and the 31-line C-H map. See the [work Mac
handover](WORK_MAC_HANDOVER.md) for the data root and checksums.
