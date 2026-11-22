# Strict axial selection across paired terrain seeds

The experiment pairs Hill and Converging Valleys for seeds 40–45.
Every generated case starts from the same aggregation setup used in
the preserved benchmark. The Voronoi grid has 500 points and jitter
ratio 1, the canvas is 100 units wide, and slope-preference
aggregation uses a 100-dyad maximum, slope and contour weights of
0.95 and a stagnation limit of 1,000. The recorded terrain parameters
remain specific to the terrain. Seed 42 reproduces the preserved
polygon bytes, building labels and original doorway-pair lists on
both terrains. All other cases are generated from their own seeds.

## Strict lineage and methods

Each case saves settlement, topology, fresh-exact candidates, full
selection and analysis as versioned records. Main open space uses
positive-length cell adjacency. Building blocks use face and vertex
contacts. Boundary-connected blocks merge into the boundary block,
and disconnected open components become effectively occupied. The
topology stage records both the number of internal occupied blocks,
which sets the required winding rank, and geometric circulation hole
counts. These are separate measurements.

Each original building/open-cell pairing is preserved. An eligible
door is the exact midpoint of its unique shared face in the main
open component and must pass exact clearance at that point. The
analysis records exclusions with their geometry reason. It verifies
doorway closure incidence and axial positive interior traversal
against independent rational predicates in the doorway regions.
The candidate pool is independently rechecked for exact clearance.
Winding capability can be certified by a subset of exact ring-boundary
supports in the pool. The record identifies the proof used and the
automatically determined required rank. Every selected map is also
checked against the exact winding validator.

The strict entrance-guided method starts from circulation supports,
adds lines for interior coverage and doorway incidence, then adds at
most eight shortcuts ranked by doorway line-change depth. This
ranking uses incident lines. It has no geometric doorway caps.
Strict backward reduction tests shortest-first passes on the guided
map until a complete pass accepts no deletion. Its line count is
a one-deletion local result. Singleton full-pool region and doorway
sets separately identify certified lines forced by those constraints
in any strict selection.

The metric master uses every eligible line in a doorway's incident
regions, with certified regional projection and endpoint stops.
Metric routing splits the exact axial edges at those stops. Angular
routing keeps the independently verified directed axial movement
graph with free entry and exit via incidence. The two routes have
separate baseline arrays. Proportional deterioration is a fraction
of the corresponding full-pool cost and is undefined for zero
baselines. The export counts undefined comparisons. Metric distances
are shortest paths over the finite certified stops used here.

## Corridor proposals and comparison design

Axial lines at least 20 units long propose physical bands. Nine
cross-sections sample occupied banks within 12 units on each side.
The axis is refitted through the midpoints of the banked sections,
then checked again. The rule requires at least seven two-sided
sections, fitted length at least 20, and length-to-width ratio at
least 3. Width is the median banked cross-section. Duplicate bands
are screened by overlap of their certified member sets. The number
of tested corridors is determined by the rule on each settlement.
Before choosing the reported corridor maps, a separate versioned
screen requires seven sections banked by actual buildings and
checks the central 80% of the fitted axis for occupied-interior
crossing. This removes cross-section false positives without
discarding their archived trials. Discovery is a bounded proposal
procedure and can miss corridors.

Each corridor searches the entire certified pool for long,
oppositely inclined pairs intersecting exactly. It compares the
geometric extreme pair with the best mean-angular pair among the
first eight geometric candidates that are considered, including
the extreme pair. Every proposed swap holds the rest of the
strict backward map fixed and is validated globally. A method's
consolidated row keeps the feasible proposal with lowest count,
then lowest angular mean, then shortest total length. The
corridor-level CSV retains same-band alternatives for matched-count
comparisons. Unsupported cases and invalid proposals remain
distinguishable.

The twelve cases are paired by seed. Route comparisons are
matched on identical doorway pairs. Bands within a settlement are
correlated, so length-to-width associations are exploratory.
Runtime is the stage's elapsed time during parallel execution.
Peak memory is the maximum resident set size measured in the case
worker. Raw route arrays and all exact endpoints for the reported
maps are retained in the batch and geometry exports.

## Generated topology

In these twelve cases the detected circulation-hole count equals
the automatically derived internal occupied-block count. The last
two columns count disconnected open cells subsequently treated as
effectively occupied.

| Seed | Hill holes | Y holes | Hill excluded open cells | Y excluded open cells |
|---:|---:|---:|---:|---:|
| 40 | 16 | 6 | 0 | 57 |
| 41 | 13 | 2 | 0 | 119 |
| 42 | 11 | 3 | 2 | 0 |
| 43 | 7 | 2 | 4 | 5 |
| 44 | 15 | 8 | 3 | 1 |
| 45 | 17 | 8 | 1 | 0 |

The topology result is consistent across this paired sample. Hill
has more required winding classes at all six seeds. Y's much larger
excluded components at seeds 40 and 41 are configuration-specific
features that influence its accessible domain and eligible doorways.

## Strict backward results by paired seed

| Seed | Hill eligible doors | Y eligible doors | Hill lines | Y lines | Hill minus Y |
|---:|---:|---:|---:|---:|---:|
| 40 | 100 | 92 | 49 | 22 | 27 |
| 41 | 100 | 94 | 43 | 23 | 20 |
| 42 | 100 | 99 | 38 | 28 | 10 |
| 43 | 100 | 95 | 39 | 23 | 16 |
| 44 | 100 | 97 | 44 | 36 | 8 |
| 45 | 100 | 98 | 48 | 31 | 17 |

Hill retained more lines for every paired seed under the same
backward rule. The median was 43.5 on Hill and 25.5 on Y, with
a median paired difference of 16.5 lines. These counts describe
the outcomes of the fixed reduction order. A result from one
terrain or seed does not set a lower bound for another map.

The strict guided method protects the saved ring-support seed while
building coverage and doorway access. That seed contains 422
supports on Hill 40 and 412 on Hill 41, which explains why their
guided outcomes exceed 400 lines. Backward reduction can remove
many of those supports after validating alternative winding paths.
The large guided-to-backward savings therefore depend in part on
the chosen starting procedure.

## Corridor and movement findings

The physical screen retained 103 of 273 proposed bands. It rejected
170 fitted axes whose central portion enters occupied space. The
retained count varied from 4 to 12 per settlement, and their
length-to-width ratios ranged from 3.00 to 13.11. These are screened
corridor bands from the proposal rules. Several bands can represent
parts of the same physical street.

Of the 103 screened bands, six had no qualifying opposed pair.
The geometric extreme pair was valid in 89 bands and failed a
strict check in eight. Bounded route ranking found a valid pair
in 90 bands, including one recovered geometric failure. Among
the 89 bands where both methods were valid, the ranked pair
lowered mean angular depth in 68 and tied in 21. This comparison
uses the same line count inside each band. The extreme pair is an
eligible option for the ranking, so the informative results are
the size of the gain and the metric trade-off. The average
angular gain was 0.0037 turn units. Mean metric cost improved
in 59 bands, worsened in 20 and tied in 10.

The data show little association between aspect ratio and the
benefit of the geometric extreme pair over the backward map.
Spearman's rank correlation was 0.055 for mean angular
improvement and 0.016 for metric improvement among feasible
geometric replacements. The rank advantage over the extreme
pair had correlations of 0.277 for angular cost and 0.319 for
metric cost. These are exploratory associations among dependent
bands. There are only six screened replacements at the same
line count as the original backward map, so the sample cannot
establish a reliable aspect-ratio effect at matched economy.

The same-count corridor substitutions improve mean angular
depth in all six available settlements. Both geometric and
ranked choices improve mean metric cost in five of these six.
The counterexample is Hill 45, where the ranked substitution
changes the angular mean from 1.3190 to 1.3136 but increases
mean metric cost from 53.668 to 53.708. In the other six
settlements the reported corridor swap adds one line. None
reduces the backward line count. Corridor pairs can therefore
tune routes in a compact map, with gains depending on the
selected band and the route objective.

The singleton incidence test proves a different kind of
necessity from the backward line count. It forces between
zero and four distinct lines on Hill and between zero and one
on Y. Hill has more in five seed pairs and ties at seed 44.
Other lines can be indispensable to a particular selected
map without being globally forced in the certified pool.
The higher Hill winding ranks and larger reduced maps are
consistent across these seeds. These paired results do not
establish that terrain alone causes the line-count difference.

## Validation, performance and records

All twelve generated configurations completed and all 60
reported method rows passed strict validation. All reported
maps reach every eligible pair for both angular and metric
analysis. Every proposed metric connector passed its geometric
certification. The excluded doorway pairings remain in the
settlement records with exact identities and exclusion reasons.
All 25 exclusions were on Y. Seventeen lacked a shared face in
the saved geometry and eight open cells were outside the main
component.
The full and selected maps preserve the corresponding required
winding ranks. Raw pair arrays, exact endpoints and the physical
screen winners are linked to their saved records.

Per-worker generation and candidate preparation took 164–324
seconds. Analysis took 311–981 seconds. Peak resident memory
during those stages was 374–609 MiB per worker. The reported
analysis uses the bank-centred axis version. The initial
axis-based attempts interrupted during the correction remain
in the batch store. Fifteen targeted tests passed.

- [60 settlement–method rows](diagnostics/strict-generalisation/pilot-1/comparison.csv)
- [48 paired method comparisons](diagnostics/strict-generalisation/pilot-1/paired-comparisons.csv)
- [273 corridor proposals and physical screen results](diagnostics/strict-generalisation/pilot-1/corridors.csv)
- [Numbered Hill 42 maps](diagnostics/strict-generalisation/pilot-1/numbered-maps/hill-42.png)
- [Numbered Y 42 maps](diagnostics/strict-generalisation/pilot-1/numbered-maps/converging_valleys-42.png)
- [Y 42 exact selected geometry](diagnostics/strict-generalisation/pilot-1/selected-geometry/converging_valleys-42.json)

The diagnostic directory includes all twelve numbered maps and
exact geometry JSON files. Case journals under its `cases`
directory link the complete configurations, topology, source
hashes and validation records. To replay in a fresh directory,
use `python -m experiments.strict_generalisation prepare --output PATH`,
then `analyze --output PATH` and `export --output PATH` with the
same module. Both computational stages accept a worker count.

## Visual appendix

The [84-page vector atlas](diagnostics/strict-generalisation/pilot-1/visual-report/visual-appendix.pdf)
is grouped by terrain and seed. Every settlement has a five-method
side-by-side comparison, a corridor-change diagnostic and five
individual final maps. Each of the 60 selections also has a
3,705 × 4,173 PNG and a separate vector PDF. The
[visual index](diagnostics/strict-generalisation/pilot-1/visual-report/INDEX.md)
links each map to its exact statistical CSV line, atlas page, analysis
record and Streamlit selection ID. A
[machine-readable index](diagnostics/strict-generalisation/pilot-1/visual-report/index.csv)
provides the same joins for automated inspection.

Every panel preserves the original building numbers on grey polygons
and uses the same map coordinates and axial stroke weight. Pale teal
shows the main accessible open component. The settlement boundary is
drawn explicitly. A lower opacity makes the dense certified pools
easier to read. Captions identify the configuration parameters,
generator, selection, line count, circulation requirement, winding
rank, strict coverage and validation. All 60 published selections
were valid. The renderer also supports uncovered-region, missing-ring
and disconnected-line overlays for selected maps that fail validation.

The geometry check compared every plotted selection with the exact
candidate intervals and saved selection IDs before rendering and
confirmed the plotted segment arrays. The statistical index was
checked against the CSV row content. Visual inspection across all
twelve comparison sheets shows the dense certified pools giving way
to sparse networks on both terrains. The main open-space exclusions
in Y 40 and Y 41 remain visible as unshaded areas across every panel.
Small corridor substitutions are easier to inspect in the
[Hill 42 change map](diagnostics/strict-generalisation/pilot-1/visual-report/hill-42-corridor-changes.png)
and its counterparts. Blue lines survive backward reduction and the
corridor swap, orange lines were removed by the swap, and purple
lines were added. Visual inspection supplements the exact coverage
and winding checks.

To reopen a map in the independent read-only viewer, run
`.venv/bin/streamlit run app/strict_axial_viewer.py` and select the
ID from the visual index. The `selection` query parameter accepts
the same ID. The viewer displays the saved map and comparison
artifacts without rebuilding the settlement or rerunning selection.
