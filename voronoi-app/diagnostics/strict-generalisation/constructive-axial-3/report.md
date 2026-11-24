# Constructive axial map selection from local geometry

The experiment covers 7 corrected settlements. 5 constructive maps and 5 exchange-stage maps passed structural and movement checks. 5 exchange-stage maps use fewer lines than the corresponding archived strict backward map. 4 case–method pairs have a matched-count result with lower means for both movement measures.

## Flat 40 target recovery

| Method | Candidate | Geometric rank | Backbone | Final exchange map | Geometrically similar final IDs | Entered or left at |
|---|---:|---:|---|---|---|---|
| A | 957 | 214 | — | — | 1035 | — |
| A | 1244 | 318 | — | — | 1190 | — |
| A | 1355 | 379 | — | — | — | — |
| A | 865 | 533 | — | — | — | — |
| A | 1189 | 380 | — | — | 1190 | — |
| A | 1354 | 385 | — | — | — | — |
| B | 957 | 151 | — | — | — | — |
| B | 1244 | 229 | — | — | — | — |
| B | 1355 | 234 | — | — | — | — |
| B | 865 | 302 | — | — | — | — |
| B | 1189 | 245 | — | — | — | — |
| B | 1354 | 249 | — | — | — | — |
| B-coverage | 957 | 127 | — | — | — | — |
| B-coverage | 1244 | 161 | — | — | — | coverage add |
| B-coverage | 1355 | 251 | — | — | — | — |
| B-coverage | 865 | 257 | — | — | — | — |
| B-coverage | 1189 | 173 | — | — | — | — |
| B-coverage | 1354 | 267 | — | — | — | — |
| D | 957 | 151 | — | — | 1208 | — |
| D | 1244 | 229 | — | — | 1190 | — |
| D | 1355 | 234 | — | — | — | — |
| D | 865 | 302 | — | — | — | — |
| D | 1189 | 245 | — | — | 1190 | — |
| D | 1354 | 249 | — | — | — | — |

Across 2 valid Flat 40 exchange maps, exact recovery occurred in 0 of 12 target–method combinations. The similarity rule identified retained alternatives in 6 combinations.

D's geometric rank column uses the static B order for marginal-score ties. The D checkpoint contains the actual marginal contributions and exact winding gains at each step. Similarity uses the same overlap, orientation and separation rules as suppression. A similar interval may have different movement consequences.

## Flat 40 comparisons

| Method | Map | Lines | Total length | Angular mean | Angular p95 | Metric mean | Metric p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| strict-backward | baseline | 44 | 1660.80 | 1.1471 | 2.4735 | 49.149 | 89.809 |
| full-pool | reference | 1534 | 40278.60 | 0.3927 | 1.0501 | 43.028 | 78.662 |
| A | archived_count | 44 | 2563.49 | 0.9114 | 1.9927 | 49.312 | 89.997 |
| A | constructive | 34 | 1622.71 | 0.9503 | 2.1136 | 49.487 | 90.068 |
| A | exchanged | 34 | 1622.71 | 0.9503 | 2.1136 | 49.487 | 90.068 |
| A | matched_exchange | 34 | 1622.71 | 0.9503 | 2.1136 | 49.487 | 90.068 |
| D | archived_count | 44 | 2554.71 | 0.8562 | 2.0125 | 48.472 | 88.223 |
| D | constructive | 34 | 1627.72 | 0.8691 | 2.0396 | 48.691 | 88.573 |
| D | exchanged | 33 | 1628.66 | 0.8691 | 2.0396 | 48.691 | 88.573 |
| D | matched_exchange | 34 | 1675.35 | 0.8691 | 2.0396 | 48.691 | 88.573 |
| audit-43 | control | 43 | 1640.91 | 1.0606 | 2.3522 | 48.521 | 87.960 |
| audit-44 | control | 44 | 1712.29 | 1.0285 | 2.2905 | 48.177 | 87.541 |

At 44 lines, the D control uses 2554.71 total axial length compared with 1660.80 in the archived map. The equal-count movement comparison therefore allows different total lengths.

## Economy and generality

| Method | Fewer lines after exchanges | Median line difference | Matched-count cases improving both means | Median construction seconds | Median backbone retained | Median coverage retained | Median circulation retained |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 2/2 | -12.5 | 1 | 153.46 | 5 | 17.5 | 7 |
| B | 1/1 | -15 | 1 | 110.80 | 6 | 15 | 4 |
| D | 2/2 | -12.5 | 2 | 102.03 | 10.5 | 10.5 | 7.5 |

| Settlement | Archived backward | A exchanged | B exchanged | B-coverage exchanged | D exchanged |
|---|---:|---:|---:|---:|---:|
| flat-40 | 44 | 34 | — | — | 33 |
| hill-40 | 45 | — | — | — | — |
| converging_valleys-40 | 23 | — | — | — | — |
| ridge-40 | 45 | — | — | — | — |
| shoulder-40 | 32 | — | — | — | — |
| twin_peaks-40 | 41 | 26 | 26 | — | 27 |
| flat-41 | 44 | — | — | — | — |

**D** leads the reported comparison when methods are ordered by number of valid cases, median line-count difference, cases improving both matched-count means, and median construction time, in that order. The order makes explicit how economy and computation are traded off against movement in this summary.

Backbone retention counts measure how much of the original 12-line selection survives. The statistics count retained additions by stage and the additions made before reduction. Timings are wall-clock measurements from a mixture of sequential and parallel runs. Memory is the worker's high-water mark.

Matched comparisons use the frozen geometric exchange criterion. When a feasible map was already smaller than the archive, the archived-count variant adds the highest-ranked candidates that preserve the certificate until the count matches. These controls compare route performance at the same count. Their outcome also reflects the effect of those extra lines.

## Local geometry and subsequent movement

- Angular excess · redundancy ρ=0.600, coverage ρ=-0.500, length ρ=-0.300, distribution ρ=-0.300, diversity ρ=-0.200 (5 map observations).
- Metric excess · redundancy ρ=0.900, distribution ρ=-0.700, coverage ρ=-0.400, length ρ=0.200, diversity ρ=-0.200 (5 map observations).

The correlations use within-settlement variation across methods. They describe this sample, which shares candidate pools and cases, and do not establish independent predictive performance. Differences in count, coverage repair and winding completion can also change route costs.

## Unresolved selections

- flat-40 · B · rank 23/24 · No bounded exact face bundle improved winding.
- flat-40 · B-coverage · rank 22/24 · No bounded exact face bundle improved winding.
- converging_valleys-40 · A · rank 5/6 · No bounded exact face bundle improved winding.
- converging_valleys-40 · B · rank 5/6 · No bounded exact face bundle improved winding.
- converging_valleys-40 · B-coverage · rank 5/6 · No bounded exact face bundle improved winding.
- converging_valleys-40 · D · rank 5/6 · No bounded exact face bundle improved winding.
- ridge-40 · A · rank 11/12 · No bounded exact face bundle improved winding.
- ridge-40 · B · rank 11/12 · No bounded exact face bundle improved winding.
- ridge-40 · B-coverage · rank 11/12 · No bounded exact face bundle improved winding.
- ridge-40 · D · rank 11/12 · No bounded exact face bundle improved winding.
- shoulder-40 · A · rank 8/11 · No bounded exact face bundle improved winding.
- shoulder-40 · B · rank 8/11 · No bounded exact face bundle improved winding.
- shoulder-40 · B-coverage · rank 8/11 · No bounded exact face bundle improved winding.
- shoulder-40 · D · rank 9/11 · No bounded exact face bundle improved winding.
- twin_peaks-40 · B-coverage · rank 9/10 · No bounded exact face bundle improved winding.
- flat-41 · A · rank 13/15 · No bounded exact face bundle improved winding.
- flat-41 · B · rank 13/15 · No bounded exact face bundle improved winding.
- flat-41 · B-coverage · rank 12/15 · No bounded exact face bundle improved winding.
- flat-41 · D · rank 13/15 · No bounded exact face bundle improved winding.
- hill-40 · A · rank 13/17 · No bounded exact face bundle improved winding.
- hill-40 · B · rank 15/17 · No bounded exact face bundle improved winding.
- hill-40 · B-coverage · rank 14/17 · No bounded exact face bundle improved winding.
- hill-40 · D · rank 12/17 · No bounded exact face bundle improved winding.

The repair audit counted the additional certified supports in the available archived face bundles for each unenclosed block. Under the frozen 18-line cap, none of the audited bundles enclosing the missing blocks in Y 40, Ridge 40 and Shoulder 40 was eligible. These are sizes of particular witness bundles. A different arrangement of certified lines can provide a smaller enclosure, as the archived strict maps demonstrate. In the two Flat 40 B attempts, every occupied block was already enclosed, while some enclosures contributed the same winding class. Those attempts stalled on independence.

[Repair diagnostics](repair-diagnostics.json)

## Frozen design and reproduction

A ranks by exact maximal length. B and B-coverage blend min-max scaled length, transverse family count, the span of family centres along the interval, positive-interior coverage and a redundancy penalty. D recomputes marginal region, doorway, transverse and component gains at each step, and evaluates exact winding gain for its four best local proposals. D gives weights 1 to each new region and doorway, 2 to each new transverse connection, 5 to each component merge, −5 to each redundant selected neighbour and 12 to each unit of exact winding gain, with a unit cost per accepted line. Each method starts with a 12-line backbone. Two transverse intervals belong to the same family if linked by the recorded similarity relation. Grouping is transitive. The similarity threshold is 10 degrees, two units at both projected overlap ends, 65% overlap of the shorter interval and 55% convex-coverage Jaccard similarity. Projected overlap and separation at both overlap ends preserve crossing diagonals that fan apart.

Completion adds forced singletons, repairs region and doorway coverage, connects components, and uses geometry to propose separating lines where distinct occupied blocks are enclosed together. The exact winding validator checks every accepted split and any small face-support bundle used as a fallback. The preliminary bundle-only Flat 40 pilot stalled below full rank. This repair was frozen before the cross-terrain runs. Backward cleanup removes redundant selected lines subject to the exact certificate. Exchanges minimize count, then favor higher aggregate geometric ranks. The saved trials include one-for-one, one-for-two and two-for-three proposals. Angular and metric routes are evaluated after selection and omitted from all rankings and exchange decisions.

Run `PYTHONPATH=src:. python -m experiments.constructive_axial --workers 6` from the application directory. The runner resumes certified geometry, selection and movement checkpoints. Render the completed run with `PYTHONPATH=src:. python -m experiments.constructive_axial_export`.

The finite metric graph uses certified regional stops and connectors. Angular entry and exit use the certified convex-incidence terminal sets. Exact candidate IDs in the atlas use the archived pool coordinates.

[Geometric design](design.json) · [Runtime source hashes](runtime-source.json) · [Candidate measures](candidate-measures.csv) · [Statistics](statistics.csv) · [Target recovery](flat40-targets.json) · [Map index](visual-index.json) · [Numbered vector atlas](numbered-axial-atlas.pdf)
