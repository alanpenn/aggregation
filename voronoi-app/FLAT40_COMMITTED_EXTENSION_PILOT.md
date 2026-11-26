# Flat 40 committed extension approaches

## Geometric rule

The new experiment distinguishes travel on a physical boundary, uncommitted
travel away from a source along its extension, and committed travel on an
adopted extension towards its physical source. Directed state determines
the phase and, for a commitment, the exact destination face ID. Legal
entry into a toward-going state is the oriented turn onto that extension.
The permitted successors preserve the same track and heading until the
exact anchor is reached. At the anchor the only legal continuation is the
designated physical face in the appropriate handed direction. Other
extension intersections and unrelated physical boundaries cannot discharge
the commitment.

The preflight checks the exact suffix from adoption point to anchor.
It rejects intermediate physical-boundary contacts and checks accessible
interior. Since the open suffix has no boundary crossings, its interior
classification is constant. The fixed outward half-plane, active supports,
and ordinary convex-turn checks remain in force. Accepted geometry is
separately checked for exact accessible containment and occupied-interior
and island exclusion. The per-hand journals record outgoing directed IDs
and rejection reasons. Each ID resolves to an exact interval, phase,
and destination in the saved geometry and commitment index.

## Reference cases

The L-room still yields the two original overlapping rectangles. The
three-block 6 × 6 target still closes in both directions at (6,6), and
the family still covers all 49 square units. With commitment it has five
distinct polygons, compared with seven under the earlier rule.

The new four-block fixture adds block E at the eastern boundary.
For the right-hand example the older rule joins D's extension, turns
again at (7,6) before reaching D, and closes a smaller circuit. The revised
rule permits the first turn, passes straight through (7,6), reaches D's
actual face at (7,7), and closes a valid circuit. The mirrored example
checks the left-hand rule. The fixture atlas draws both old and new
paths from exact coordinates. A separate regression supplies a blocked
suffix across an occupied island and checks the specific boundary
rejection. The revised fixtures retain full exact coverage.

## Matched Flat 40 checkpoint

| Measure | Earlier rule | Commitment |
|---|---:|---:|
| Explored prefixes | 36,000 | 36,000 |
| Distinct accepted closed paths | 604 | 369 |
| Distinct convex polygons | 236 | 66 |
| Proven non-maximal polygons | 189 | 0 |
| Globally maximal by facet-contact proof | 47 | 66 |
| Fraction with facet-contact proof | 19.92% | 100% |
| Exact accessible-domain coverage, displayed as % | 44.53367% | 46.51435% |
| Uncovered components | 4 | 6 |
| Maximum overlap | 129 | 18 |
| Area-weighted mean overlap | 20.45926 | 3.16791 |
| Area-weighted median overlap | 0 | 0 |
| Polygons overlapping archived region 257 | 36 | 16 |

The runs have identical directed-edge geometry and global and local
start schedules. Each uses 12,000 prefixes per hand globally and
6,000 per hand in the region 257 schedule. The revised run allowed
1,553 committed-entry transitions and 1,418 arrivals among the explored
outgoing decisions. It blocked 803 proposed turns during commitment.
No approach failed the physical preflight on the archived network.
Entry and arrival counts describe explored decisions. They should not
be divided to estimate a completion rate because the checkpoint retains
unexplored successors and some branches fail other traversal constraints.

All 66 polygons were independently validated. Each has positive-length
accessible-boundary contact on every facet, which proves global
maximality for that polygon. A strict convex superset must cross at
least one such facet and would put a physical boundary contact in its
interior. The result shows a higher maximal fraction **within the
matched-budget sample**. It does not prove that the revised rule returns
only maximal polygons on every input. Both searches remain incomplete.
The new run reaches different later origins within the same start order
because it prunes sooner. The uncovered areas are gaps in these
checkpointed families.

## Deliverables

The 14-page vector comparison atlas includes the two fixture views, the
region 257 comparison, selected Flat 40 paths, and semi-transparent and
exact integer overlap maps. The run is in
`diagnostics/strict-generalisation/flat40-committed-extension-1/`.
`matched-comparison.json` stores the quantitative comparison.
`coverage.json` contains rational overlay faces and multiplicities.
`regions.json` and the per-hand journals retain the exact completed
paths, certificates, rejected alternatives and pending route stacks.
`commitment-metadata.json` maps every directed edge to its traversal
phase and exact destination when applicable.

The earlier source and experiment were left intact. No earlier search
was resumed and no axial reduction was run.
