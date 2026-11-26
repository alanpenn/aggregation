# Flat 40 configurational pilot

All three graph representations use the corrected Flat 40 settlement. The common metric is global hop distance. The segment-only angular supplement uses minimum summed turn angle with hops as a secondary criterion.

| Graph | Nodes | Edges | Components | Mean degree | Mean depth | Mean integration | Mean choice | Intelligibility r |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 31-H axial | 31 | 90 | 1 | 5.80645 | 2.28602 | 0.30719 | 0.04435 | 0.86844 |
| 31-H segment | 211 | 540 | 1 | 5.11848 | 6.49253 | 0.13422 | 0.02628 | 0.53751 |
| 31-H angular | 211 | 540 | 1 | 5.11848 | 112.93714 | 0.00907 | 0.04406 | 0.19608 |
| 29-H axial | 29 | 73 | 1 | 5.03448 | 2.39163 | 0.29793 | 0.05154 | 0.87296 |
| 29-H segment | 175 | 438 | 1 | 5.00571 | 6.09603 | 0.14188 | 0.02946 | 0.52542 |
| 29-H angular | 175 | 438 | 1 | 5.00571 | 120.06674 | 0.00858 | 0.04801 | 0.20214 |
| 34-H axial | 34 | 98 | 1 | 5.76471 | 2.42068 | 0.29587 | 0.04440 | 0.84017 |
| 34-H segment | 230 | 588 | 1 | 5.11304 | 6.80854 | 0.12887 | 0.02548 | 0.49871 |
| Maximal convex | 596 | 10540 | 1 | 35.36913 | 3.92207 | 0.20432 | 0.00492 | 0.45276 |

## Reduction sensitivity

Relative to 31-H, 29-H removes candidate IDs [45, 957, 1519, 1531] and adds [364, 1064]. Changes below use only identical candidate IDs or identical rational segment endpoints.

| Comparison | Matched nodes | 31-H only | 29-H only | Mean integration change | Integration Pearson r |
|---|---:|---:|---:|---:|---:|
| axial | 27 | 4 | 2 | -0.005072 | 0.9633 |
| segment | 137 | 74 | 38 | +0.007854 | 0.9391 |
| angular | 137 | 74 | 38 | -0.000231 | 0.9683 |

The 29-H map has lower integration on the axial-line graph and higher integration on the hop-based segment graph. Angular segment integration falls. The matched-node comparisons show the same directions of change, so they persist when comparing the same lines or segments. Axial intelligibility changes little, while the angular segment model shows a weaker degree–integration relationship than the hop-based segment model on either selection.

The archived doorway mean angular cost moves from 0.87806 to 0.89066, and mean metric cost moves from 48.42977 to 49.25194. Both arrays contain all 4,950 pairs. These are external checks on interpretation, independent of the graph measures.

## Validation

The source candidate pool and selected inventories passed SHA-256 checks. The three axial graphs reproduced the selected edges in the frozen candidate intersection archive. The 596 polygon IDs, exact areas and global maximality records were checked against the registry, and the archived uncovered area is exactly zero.

## Interpretation and limits

Raw node counts and degrees reflect different representations. Normalisation does not make an axial hop, segment hop and convex overlap interchangeable. Angular segment depth is in degrees and cannot be compared numerically to hop depth. The undirected segment adjacency supplement measures relations among segments and can permit consecutive transitions at the same junction. Convex polygon transparency reveals overlapping footprints. Interior dots represent individual polygon scores where fills blend. Pearson coefficients are descriptive within this settlement. One seed cannot establish a terrain effect, general transferability or superiority of a line inventory.

[Frozen configuration](configuration.json) · [Spatial atlas and distributions](atlas.pdf) · [Graph statistics](statistics.json) · [Node scores](nodes.csv) · [Exact graph geometry and edges](graphs.json) · [Source hashes](inputs.json)

[Reproduction commands](reproduce.md)
