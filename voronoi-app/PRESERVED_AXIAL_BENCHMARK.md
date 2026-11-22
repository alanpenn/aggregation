# Preserved Hill 42 and Y 42 axial benchmark

## Implementation review

The existing batch runner and store already supported independent, versioned
stages, hash-verified parent records, immutable branch outputs, source archives,
and distinct successful, invalid, failed, and incomplete outcomes. Existing
tests covered branching, preserved inputs, and tamper detection. The stage
adapters already exposed two candidate generators, three selectors, and
separate measures and validation.

This benchmark adds source-checked fixture import, an exact pool inventory
with intersection and coverage counts, and reusable CSV and JSON comparison
exports. The pool adapters are version 2 because their output now includes
the inventory. The geometric and selection algorithms are unchanged.
A store fix normalizes JSON keys before hashing so imported numeric cell IDs
retain the same parameter digest after serialization. Earlier records were
preserved.

## Sources and topology

The two imports each preserve 484 cell polygons as WKB, 100 original building
labels, and 100 dyad-open-cell identities. Hill's snapshot geometry was compared
cell by cell against the separately preserved WKT inventory. Y's geometry and
label inventory were checked against their recorded SHA-256 hashes. Snapshot
configuration metadata was retained.

The original snapshots do not include a contemporaneous door table. Each
fixture has a 100-pair inventory saved by an earlier entrance study that had
reconstructed the settlement. This benchmark imports those previously saved
pairings and checks them against the dyad and building identities. It does not
reconstruct or infer any doorway pairing. The original aggregation trace and
grid graph were unavailable in the supplied inventories. Source names, hashes,
and recovery limitations are retained in the settlement records.

| Settlement | Open cells in main component | Internal occupied blocks | Circulation holes |
|---|---:|---:|---:|
| Hill 42 | 382 | 11 | 11 |
| Y 42 | 384 | 3 | 3 |

Hill's cells 335 and 383 are both singleton secondary open components. The
validator treats them as effectively occupied. Cell 335 is assigned to the
building block that joins the exterior boundary block. Cell 383 is assigned
to an internal occupied block. Y has no excluded open component. These counts
are asserted only in the fixture runner.

## Comparison policy

Both built-in generators and all three selectors are attempted against the
same preserved domain for each settlement. Selectors share the candidate
record within each generator branch. The full-pool selector supplies an
explicit constructive feasibility check when its independent validation
passes. An uncovered visibility region in the entire pool proves that no
subset can provide complete coverage. A failed search or insufficient
winding rank in one evaluated network leaves subset feasibility unproven.

Pool screening counts refer to support attempts and candidate intersection
counts refer to distinct intersecting line pairs. These are separate from
clearance rejections among constructed maximal intervals. The exact and
projected generators screen different support families, so their counts of
screened-out attempts have different denominators. Depth statistics retain
raw per-line and entrance-pair outputs, with unavailable quantities represented
by nulls. Timings are elapsed wall time from stage records. Four concurrent
generator branches can compete for CPU, so these times describe this run.

## Candidate generation

| Settlement | Generator | Candidates passing exact clearance | Intersecting pairs | Interior coverage | Visibility coverage |
|---|---|---:|---:|---:|---:|
| Hill 42 | Fresh exact | 1,347 / 1,347 | 59,590 | 266/266 | 266/266 |
| Hill 42 | Projected faces | 1,346 / 1,346 | 59,587 | 265/266 | 266/266 |
| Y 42 | Fresh exact | 1,651 / 1,651 | 112,126 | 267/267 | 267/267 |
| Y 42 | Projected faces | 1,651 / 1,651 | 112,126 | 267/267 | 267/267 |

All four interval pools are connected and contain no duplicates or
post-construction clearance rejections. The two Y pools have identical
exact intervals. The Hill fresh pool contains all the projected intervals
plus the interior-coverage fallback for region 76. All projected intervals
also match their respective saved research runs endpoint for endpoint.
Pre-construction rejection totals and reasons are included in the export.

## Repeatability

Both topology replays had identical output SHA-256 hashes. The Y fresh
exact greedy selection and its independent validation also reproduced
their respective output hashes. The 29-line greedy selection matches the
preserved Y greedy reference endpoint for endpoint. The benchmark saves
one settlement and one topology per fixture, and one candidate pool per
generator and fixture. Selector branches reference those existing pools.

## Complete comparison

| Settlement | Generator | Selector | Status | Lines | Total length | Components | Regions covered | Winding rank | Unreachable entrance pairs | Mean axial depth | Mean entrance depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hill 42 | fresh-exact | exact-greedy | invalid | 42 | 1404.82 | 1 | 266 | 5 | 197 | 4.80 | 3.64 |
| Hill 42 | fresh-exact | entrance-guided | successful | 130 | 3072.96 | 1 | 266 | 11 | 0 | 3.80 | 2.14 |
| Hill 42 | fresh-exact | full-pool | successful | 1347 | 31935.00 | 1 | 266 | 11 | 0 | 3.33 | 1.30 |
| Hill 42 | projected-faces | exact-greedy | failed | — | — | — | — | — | — | — | — |
| Hill 42 | projected-faces | entrance-guided | successful | 130 | 3076.28 | 1 | 266 | 11 | 0 | 3.81 | 2.14 |
| Hill 42 | projected-faces | full-pool | successful | 1346 | 31930.67 | 1 | 266 | 11 | 0 | 3.33 | 1.30 |
| Y 42 | fresh-exact | exact-greedy | invalid | 29 | 1171.88 | 1 | 267 | 3 | 2150 | 4.24 | 1.98 |
| Y 42 | fresh-exact | entrance-guided | successful | 70 | 2512.68 | 1 | 267 | 3 | 0 | 3.07 | 1.50 |
| Y 42 | fresh-exact | full-pool | successful | 1651 | 47524.75 | 1 | 267 | 3 | 0 | 3.37 | 1.07 |
| Y 42 | projected-faces | exact-greedy | failed | — | — | — | — | — | — | — | — |
| Y 42 | projected-faces | entrance-guided | successful | 70 | 2527.25 | 1 | 267 | 3 | 0 | 3.05 | 1.50 |
| Y 42 | projected-faces | full-pool | successful | 1651 | 47524.75 | 1 | 267 | 3 | 0 | 3.37 | 1.07 |

All four full-pool references passed independent validation, giving ranks
11/11 on Hill and 3/3 on Y. The valid maps kept full visibility coverage,
one connected axial component, exact clearance and zero unreachable
pairs among the geometrically valid doors. No candidate-generation stage
failed. The 12 combinations consist of eight successful, two invalid
and two failed cases.

The [CSV](diagnostics/preserved-axial-benchmark/benchmarks/41e80158f7d14cb9aefd57ab62a49145/comparison.csv)
and [JSON](diagnostics/preserved-axial-benchmark/benchmarks/41e80158f7d14cb9aefd57ab62a49145/comparison.json)
exports include timing, detailed failures, rejection totals and statistics.
Depth means for the invalid greedy maps use their reachable pairs only.

## Before extending to seeds 40–45

1. Register selector requirements alongside method versions. In particular,
   record whether coverage means any visible boundary contact or must
   include an interior traversal, and whether a pool must carry explicit
   ring seeds. Keep unsupported combinations in the experiment matrix as
   diagnosed outcomes.
2. Control candidate identity and ordering. The two Y generators supply
   identical intervals, but their entrance-guided selections share only
   52 of 70 intervals. Treat canonical geometric ordering or an explicit
   tie-break policy as a versioned variant, then rerun both fixtures before
   attributing selection differences to geometry.
3. Save intersection graphs, doorway connectors, and certified circulation
   witnesses as reusable analyses keyed by candidate and parameter hashes.
   This run recomputes those inputs across branches. Use stable execution
   settings and repeated timing trials for runtime comparisons.
4. Use a paired seed-by-configuration matrix, keep the geometry and entrance
   validation criteria fixed, and report unavailable routes separately from
   rejected maps. Retain every planned case and predeclare the outcomes
   used to compare selectors.

## Selector findings

The entrance-guided method produced valid maps on all four saved pools.
It retained 130 lines on Hill and 70 on Y, smaller than the full-pool
reference on either settlement. For each equal-count pair, fresh exact
gave the shorter total length: 3,072.95 versus 3,076.28 on Hill and
2,512.68 versus 2,527.25 on Y. Their mean entrance depths were close.
These are the most economical valid maps among the tested selectors.
The benchmark does not establish a global minimum.

The Hill projected pool failed at greedy selection because its region 76
has boundary visibility but no interior traversal. The Y projected pool
failed at greedy selection because the greedy seed did not satisfy the
selector's obstacle-circulation check. The fresh pools returned greedy maps,
but independent validation found:

- Hill, 42 lines. Winding rank 5/11 and 197 unreachable entrance pairs.
- Y, 29 lines. Winding rank 3/3 and full region coverage, with 2,150
  unreachable pairs among the 99 geometrically valid entrances.

The Y inventory includes one doorway with no usable shared-face midpoint
under the routing check. Its saved pairing remains in the settlement record.
Hill uses all 100 saved pairings. Reachability for the valid entrance-guided
maps is 4,950/4,950 on Hill and 4,851/4,851 on Y.
