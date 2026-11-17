# Shortest-path tangent backbone: research plan

## Hypothesis and scope

In a polygonal accessible domain, a Euclidean shortest path between points
that are not directly visible can bend at accessible-domain boundary vertices.
Its intermediate vertex-to-vertex segments belong to a finite visibility
graph. We will investigate whether maximal axial lines containing frequently
used obstacle-supported segments can provide a useful sparse representation of
the domain.

These are different objects and must be measured separately:

1. **Direct visibility:** a clear straight origin–destination segment, whose
   Euclidean length is already minimal.
2. **Metric shortest paths:** paths through visible domain-boundary vertices,
   with lengths measured in the plane.
3. **Internal obstacle-supported segments:** vertex-to-vertex path segments
   whose endpoints have occupied-building boundary support. A visible edge is
   not automatically a shortest-path tangent; test its local support and
   record non-tangent cases separately.
4. **Maximal axial lines:** certified candidates whose rational intervals
   geometrically contain those segments. An extended line and a path segment
   are not interchangeable merely because they overlap.
5. **Angular routes:** paths in a selected, noded segment or axial network,
   evaluated with the existing directional angular-cost convention.

Metric shortest-path completeness does **not** imply minimum-angular-route
completeness. Geometric containment of individual segments also does not by
itself preserve their order, junctions, accessibility or a complete route.
Neither candidate-pool completeness nor a uniquely correct or globally minimal
axial map is assumed.

This branch initially contains only this plan. Do not change production
generation, selection, exact enumeration, certified fixtures or saved results.
The first implementation should be an independent, reproducible experiment.

## Input and geometry

Use the preserved Converging Valleys/Y seed-42 snapshot and the original
displayed building numbering. The prior research archive documented in
[HANDOVER.md](./HANDOVER.md) includes the precise diagnostic input, prepared
3,214-candidate combined pool and saved selections. Confirm their checksums,
configuration, occupied polygon coordinates and labels before calculating.
The existing 29-line connectivity-prioritised selection is
`selection-results.json` → `connectivity.selected`; keep its candidate-index
mapping tied to the archived `prepared.json`. Also retain the unified greedy
29-line map, the 24-line connectivity-exchange map and the separately targeted
23-line map for comparison. Treat the 32-line legacy float replay separately:
its pool and clearance representation differ.

Treat original binary64 polygon coordinates as exact rationals for predicates.
The accessible-domain union, complement and convex decomposition are
GEOS-constructed; exact checks certify against that constructed geometry and
the original occupied polygons, not an independently exact polygon overlay.
Preserve separate accessible components. Check shared vertices, coincident
edges, collinear contacts, holes, the outer boundary and zero-width contacts
explicitly. Do not infer traversability through a pinch point solely from
topological contact: define and validate the adopted boundary-contact policy,
and report ambiguous cases rather than joining components silently.

## Experiment design

### 1. Construct the visibility graph

- Extract accessible-domain exterior and hole vertices, including vertices on
  the outer boundary; retain original building and boundary provenance.
- Canonicalise identical rational coordinates so shared vertices have one
  graph node with all supports. Exclude zero-length edges and distinguish
  vertices on an accessible boundary from building seams hidden inside the
  occupied union.
- For each eligible vertex pair in the same accessible component, use existing
  exact clearance predicates against original occupied interiors and the
  constructed domain. Permit only boundary contacts allowed by the explicit
  policy; record rejected and numerically or topologically unresolved edges.
- A graph edge may touch an additional boundary vertex or lie along a face.
  Node such contacts consistently and preserve provenance; do not identify
  every visible edge as a mutual tangent.

### 2. Define reproducible origins and destinations

- Generate spatial samples using the centres of a fixed 16-by-16 grid over
  the settlement extent, retaining points certified in accessible space.
  Add a checked representative point for any accessible component not sampled
  by the grid. Store coordinates, component IDs, generation settings and any
  rejected or ambiguous points.
- Separately sample origins and destinations on positive-length accessible
  building-boundary intervals. Start with the one-third point as an origin and
  the two-thirds point as a destination of each eligible interval, excluding
  shared endpoints and occupied-union seams.
  Retain building labels and interval provenance, and report any boundary
  points that cannot be classified reliably.
- Evaluate ordered pairs within the same component, separately reporting
  spatial-to-spatial and building-boundary-to-building-boundary results.
  Preserve cross-component disconnection. Fix the sample sets and graph
  connections before comparing selections; do not reattach samples to each map.

### 3. Calculate metric paths and segment use

- Test each direct segment with the same exact visibility policy. For
  non-visible pairs, add the fixed sample-to-vertex visibility edges and find
  Euclidean shortest paths on the graph. Include sample-to-vertex edges in
  paths but distinguish them from internal vertex-to-vertex edges.
- Rational predicates certify visibility, not sums of Euclidean lengths:
  edge lengths can be irrational. Use controlled-precision or interval-based
  distance comparisons; report unresolved near-ties instead of claiming an
  exact metric optimum from floating-point Dijkstra alone.
- Record one deterministically chosen shortest-path witness per resolved pair,
  along with equal-cost alternatives when they can be reliably identified.
  A count based on one witness is a sampled utilisation measure, not exact
  all-pairs betweenness. Report directly visible pairs, inaccessible pairs,
  ties and unresolved cases separately.
- For each internal segment, retain rational endpoints, adjacent path
  directions, obstacle supports, local tangent classification and ordered
  pair IDs. Aggregate occurrence counts and, if ties are resolved, a clearly
  defined fractional weight. Keep segments without occupied support as a
  separate boundary class.

### 4. Map segments to the certified axial pool

- An axial interval covers a segment only when both rational segment endpoints
  lie on that same certified interval; test exact collinearity and interval
  containment. Retain every matching candidate and its provenance, not just
  the first match. Record valid segments absent from the existing pool.
- For each saved exact selection, report the number and weight of required
  segments geometrically covered, plus uncovered high-utilisation segments.
  Distinguish vertex-to-vertex tangent segments from endpoint connectors and
  other boundary-supported segments.
- Separately test functional route preservation: ordered segment continuity,
  noded intersections, valid connections to the fixed terminals and the
  availability and cost of a complete path. A collection of individually
  covered segments is not automatically a preserved route.
- Evaluate angular performance afterward with identical fixed terminal
  constructions and the existing angular model. Report unreachable pairs and
  compare common reachable pairs; do not infer angular fidelity from metric
  path coverage.

### 5. Diagnostics and validation

Produce numbered settlement plots with identical extents showing heavily used
metric-path segments, their supporting buildings and the selected axial lines.
Highlight high-weight segments omitted by the 29-line map and report whether
they occur in the full certified pool. Save rational graph and segment records,
sample definitions, path/edge weights, coverage and unresolved cases alongside
the figures and a manifest of input hashes and solver settings.

Add deterministic tests for direct visibility, obstacle-corner paths,
outer-boundary paths, shared and coincident vertices, allowed face contacts,
occupied-interior rejection, disconnected components, ties and unresolved
metric comparisons. Test exact interval containment separately from complete
route preservation. Include an opt-in replay against the archived Y inputs,
and verify that production files and fixtures remain unchanged.

## First implementation steps

1. Restore the verified research archive into a fresh working directory and
   validate the snapshot, candidate records and saved selection identities.
2. Implement and test a standalone exact-predicate visibility graph and
   deterministic sample generator, with explicit ambiguity reporting.
3. Add metric path witnesses, segment utilisation records and exact
   candidate-containment comparisons; then produce the numbered diagnostics.
4. Evaluate complete route and angular preservation as a separate stage before
   proposing any new axial selection or generation rule.
