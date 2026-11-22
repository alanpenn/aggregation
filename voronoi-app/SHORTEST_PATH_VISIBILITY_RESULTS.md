# Y seed-42 shortest-path visibility experiment

This is an experimental measurement, not an axial selector. It uses the
preserved Converging Valleys/Y seed-42 snapshot, original numbered building
polygons, saved 3,214-line certified candidate pool and saved selections.
Inputs are checked against the manifest of the verified research archive before
construction; the archive SHA-256 is
`9128d543e2527588a3562ca2767f6b81de6daed9ecc412d8e376008c373bf3b7`.
Missing or changed inputs cause an error rather than regeneration.

## Method and limitations

The accessible domain is the GEOS overlay of the open polygons minus occupied
polygons. Rational predicates use the exact binary64 coordinates of that
constructed overlay and the original obstacles; this is not an independently
exact construction of the overlay. Visibility permits boundary following and
tangential contacts but excludes occupied interiors. Original building vertex
references are retained, including shared vertices. Vertices belonging to more
than one domain ring are conservatively excluded from routes because the
topology at a pinch may be ambiguous. This settlement has no such vertices.

Graph nodes include all constructed-domain ring vertices and original building
vertices lying exactly on a ring. Of 462 graph vertices, 399 have original
building references; the remaining vertices describe the constructed domain.
The graph has 6,532 visible edges and 99,959 rejected pairs. Edge records
independently flag boundary following and mutual obstacle tangent support:
859 edges follow a boundary and 1,651 have tangent support, including 397
with both properties.

Spatial terminals are the accessible members of a deterministic 16-by-16 grid:
204 points, with 52 grid points omitted. Ordered, distinct point pairs are
evaluated. Boundary terminals come from 32 deterministically stratified
accessible building-boundary intervals among 391 eligible intervals. The
origin and destination are at one-third and two-thirds of each sampled
interval; all 32-by-32 ordered origin/destination combinations are evaluated.
This boundary sample is not exhaustive.

Visibility and segment containment are exact rational tests. Euclidean edge
lengths and shortest-path sums are floating point. A deterministic shortest
path witness is recorded; alternate predecessors or destination connections
within `1e-10 * max(1, path_length)` are flagged as near-ties, not certified
equalities. Collinear subdivisions can create multiple representations of the
same geometric path. Utilisation depends on the sampled terminals and chosen
witnesses and is not an exhaustive continuous-space betweenness measure.

Path legs are noded at boundary vertices, and obstacle-to-obstacle segments
are counted at most once per journey. Exact candidate representation requires
both segment endpoints to lie on the *same* candidate interval; a crossing
alone does not count. Results separately report all used obstacle-supported
segments and those with mutual tangent support. The usage-weighted denominator
is the total number of recorded journey-edge uses. Geometric containment does
not establish whole-route preservation or minimum-angular-path fidelity.
The legacy 32-line float map is excluded: it used a different candidate pool
and some stored intervals failed exact clearance.

## Observed results

The 42,436 ordered journeys comprise 7,982 directly visible and 34,454
occluded pairs; none was unreachable or in a different component. The
recorded witnesses used 187 distinct obstacle-to-obstacle segments, all
classified as mutual tangent supported. Their 245,126 journey-edge uses are
highly concentrated: 21 segments were used at most twice, the busiest two
were each used 18,402 times, the median was 104 uses, and the ten busiest
accounted for 51.60% of all journey-edge uses. No near-ties were flagged at
the stated tolerance; this does not certify exact uniqueness. A journey may
use multiple segments, so these
percentages are not percentages of complete journeys. The full utilisation
histogram and per-edge journey references are in the result records.

| Saved map | Distinct segments contained | Journey-edge uses contained |
|---|---:|---:|
| Full certified pool, 3,214 lines | 187/187 (100%) | 245,126/245,126 (100%) |
| Greedy, 29 lines | 12/187 (6.42%) | 15,334/245,126 (6.26%) |
| Connectivity, 29 lines | 5/187 (2.67%) | 1,548/245,126 (0.63%) |
| Connectivity after exchanges, 24 lines | 5/187 (2.67%) | 1,548/245,126 (0.63%) |
| Targeted exchange, 23 lines | 5/187 (2.67%) | 1,548/245,126 (0.63%) |

These are exact collinear containment measurements, not route or angular
performance scores. All 187 used segments were in the full certified pool;
the low selected-map containment does not itself demonstrate that those maps
cannot support good approximate routes.

## Reproduction

Use the archived files, not a newly generated settlement. Set `ARCHIVE` to the
verified archive, `SNAPSHOT` to its preserved `axial-diagnostic.json`, `DATA`
to the preserved `valley42-exchange-2026-11-17` directory, `SELECTIONS` to
the preserved `valley-connectivity-2026-11-17` directory, and `OUT` to a
nonexistent output directory. The scripts refuse to overwrite results.

```sh
MPLBACKEND=Agg .venv/bin/python -m experiments.shortest_path_visibility \
  --archive "$ARCHIVE" --snapshot "$SNAPSHOT" --data-dir "$DATA" \
  --selection-dir "$SELECTIONS" --output-dir "$OUT"
MPLBACKEND=Agg .venv/bin/python -m experiments.shortest_path_routes \
  --snapshot "$SNAPSHOT" --data-dir "$DATA" --output-dir "$OUT"
MPLBACKEND=Agg .venv/bin/python -m experiments.shortest_path_backbone \
  --snapshot "$SNAPSHOT" --data-dir "$DATA" \
  --selection-dir "$SELECTIONS" --output-dir "$OUT"
```

For the optional independent saved-graph clearance regression, set
`SHORTEST_PATH_VISIBILITY_DATA="$OUT"` and
`SHORTEST_PATH_SNAPSHOT="$SNAPSHOT"` when running
`tests/test_experimental_visibility.py`. The graph, sampled terminals, paths,
edge provenance, selected-candidate matches and figures are saved under `OUT`.

The reported run used Python 3.12.13, Shapely 2.1.2 with GEOS 3.13.1,
and SciPy 1.18.0. All 6,532 saved graph edges passed a separate
`LineClearance.permits_exact` regression. The broader headless suite passed
229 tests, with 3 tests skipped and one slow default-Voronoi test
deselected. A separate copy of the eight result files was checked
byte-for-byte against the originals.
