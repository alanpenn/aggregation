# Boundary-endpoint candidate investigation

This experiment does not change either generator, selector, or certified fixture.
The experimental implementation is
[`experimental_boundary_candidates.py`](src/voronoi_app/experimental_boundary_candidates.py).
The full exact candidate records, support/contact provenance and angular results
are supplied separately as session artifacts.

## Definition

Inputs are original occupied polygons and the domain formed by the union of all
open polygons minus the occupied union. Each stored binary64 coordinate is
treated as an exact rational; the union and difference themselves are still
constructed by GEOS, not by an exact polygon-overlay algorithm.

For every distinct pair `(B, V)`:

1. `B` is a vertex of an accessible-domain boundary ring whose incoming and
   outgoing edges have nonzero exact cross product, or an original occupied
   polygon vertex on that boundary. Collinear subdivision vertices that are
   not building vertices are excluded. Vertices shared by buildings qualify.
2. `V` is an original convex occupied-polygon vertex locally supporting the
   line `BV`: the incident edges lie on the same side or on the line, tested
   by exact cross products. At a shared vertex, one qualifying original building
   is sufficient; all colocated building/vertex references are retained.
3. Reject a seed crossing an original occupied interior or the interior of the
   occupied union or accessible complement. Contacts with a vertex or face are
   allowed; shared occupied seams inside the union are not.
4. Compute the exact maximal connected interval containing `BV` and accept it
   only when `B` is one of its endpoints. Other collinear building or boundary
   vertices may lie anywhere on the interval.
5. Deduplicate unordered exact interval endpoints, retaining all accepted
   defining pairs and all collinear original building and boundary vertices,
   including every reference at shared coordinates.

The spatial index is only an outward-rounded bounding-box prefilter; acceptance
uses rational predicates. No angle sampling or distance tolerance is used.
The count is exhaustive **only for this rule and the constructed domain**.
The original occupied-polygon format must satisfy the existing exact
enumerator's polygon validation; occupied polygons with holes are unsupported.

## Results

New means not present in the existing exact pool by canonical rational interval,
not merely a new support or a different candidate ID. The Y baseline is the
checksum-verified 1,651-line fixture. Hill was compared against a newly
generated, unmodified exact pool. The four smaller app-generated examples use
three dyads; Voronoi uses 30 configured points and Cartesian resolution 6.

| Settlement | Baseline | Accepted supports | Distinct | Existing | New | Seconds |
|---|---:|---:|---:|---:|---:|---:|
| Voronoi seed 11 | 23 | 32 | 31 | 7 | 24 | 0.25 |
| Voronoi seed 42 | 29 | 40 | 40 | 4 | 36 | 0.32 |
| Cartesian seed 11 | 14 | 16 | 15 | 0 | 15 | 0.16 |
| Cartesian seed 42 | 18 | 24 | 20 | 1 | 19 | 0.20 |
| Preserved Y | 1,651 | 3,063 | 2,752 | 1,189 | 1,563 | 412.74 |
| Hill seed 42 | 1,372 | 2,323 | 2,104 | 866 | 1,238 | 296.40 |

Hill exact baseline generation took 165.03 seconds. Times are individual runs
and are not benchmarks across machines. They precede a subsequent check that
also recovers original building vertices omitted from overlay ring coordinate
lists. No such omitted boundary vertices occur in Y or Hill; the four small
settlements were rerun and their intervals and counts were unchanged. The
rejection categories partition all
ordered boundary/corner pairs: coincident vertices, corner not supporting,
original occupied interior, union/domain, and boundary not a maximal endpoint.
Their counts, plus duplicate-support counts, are in the candidate artifacts.

The 21.0679-unit Hill line is recovered, with shared endpoint references
`167:5` and `190:0` (displayed buildings 9 and 19), and supporting vertex
`209:1` (displayed building 2). It runs from approximately
`(36.6712570643, 64.7203152207)` to `(43.1615123572, 44.6770393014)`.
The shared point is not a mutual occluding corner of the **accessible union**,
so the live generator misses it. Crucially, the existing **exact** generator
already includes the same exact interval: its candidate 555 is supported by
individual buildings 167 and 209. Thus it is not a new interval relative to the
exact Hill baseline. That baseline's support records only the locally
supporting `167:5` reference; the experimental contact records both buildings
at the shared point.

The exact interval reconstructed from live candidate 588's support is also
already in the exact Hill baseline (candidate 592). Candidate IDs are local to
these particular runs.

## Angular experiments

Every addition was evaluated against a fixed reference with identical
attachments and all 1,260 ordered pairs. Angular costs are deflection divided
by a right angle. Per-origin results were checked against the per-pair
implementation for both baseline maps and one improved addition in each.

* Y uses the saved best-23 map and the saved 36 spatial samples, attached once
  to the baseline. Of 30 long new intervals crossing at least two reference
  lines, 11 improved at least one pair. One interval supported by `483:4` and
  shared vertices `207:2`/`208:4` improved 216 pairs, maximum 0.03857, changing
  the mean from 4.30003 to 4.29342. Other tested intervals improved no pairs.
* Hill reconstructs the exact intervals of the live selected lines from their
  saved permissible supports. The reconstructed network has components
  39, 1, 1. The test uses midpoints on 36 of the 39 main-component lines;
  these are fixed on-network stops, not a representative area sample.
  Adding exact candidate 588 improves 30 pairs, maximum 0.14173, mean
  3.65462 to 3.65125. Adding the 21.0679 line improves none of these pairs.
  Two other new intervals improve 42 and 130 pairs respectively.

No sample is reattached after adding a line. Therefore these changes are
network effects rather than attachment changes; adaptive-attachment effects
were not measured. The sample and candidate subsets do not establish angular
path completeness or prove that any line is generally redundant. Every Y
reference convex region is already covered before adding any tested line.

## Other missing classes and numerical representation

A deterministic rectangle-with-obstacle test exhibits both an unobstructed
boundary-vertex-to-boundary-vertex diagonal and an interior horizontal
sightline absent from both finite rules. The latter is one of a continuum of
valid sightlines, so neither pool can represent all possible maximal lines.
Face extensions, mutually supporting corners and collinear multiple contacts
are already represented where their specified supports pass clearance; the
new construction additionally represents some endpoint/corner combinations.
Further boundary-boundary and unsupported-sightline objectives need explicit
definitions rather than arbitrary angular samples.

For 588, the original support is retained as binary64 vertices. The live
`_maximal_interval` computes projections and reconstructs endpoints in floats.
Those rounded endpoints no longer lie exactly on the support: their exact
signed cross products with the two support vertices are about `-1.09e-15` and
`2.72e-14`. GEOS says the stored segment is covered by the domain, but exact
binary-rational checking detects a crossing of building 6. The rational
interval reconstructed from the original support has zero cross products and
passes exact checks against all original buildings and the constructed domain.

A safe integration should retain rational intervals and all source/contact
provenance as authoritative, certify those intervals before selection, and
convert to floats only in a one-way display adapter. Merge by canonical exact
interval rather than local IDs, retain the present production and fixture paths
until differential tests establish compatibility, and choose a new selection
objective explicitly. The current optional `AngularNetwork` float-geometry
clearance path must not be used as an exact certificate; this experiment
certified exact inputs separately before constructing the network.
