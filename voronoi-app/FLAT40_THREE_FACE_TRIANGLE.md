# Flat 40 three-building-face triangle

The proposed triangle exists and is globally maximal. Its absence from the saved Flat 40 cover is explained by incomplete enumeration (case A). The archived journals contain the next required branch on the pending stack for all six starts. Targeted replay through the original crawler accepted the exact triangle from each start.

## Exact geometry

The archived building labels and physical face IDs are distinct from the settlement polygon IDs.

| Building label | Settlement polygon ID | Occupied topology block | Physical face ID | Face length |
| --- | ---: | --- | ---: | ---: |
| 30 | 167 | internal-1 | 136 | 5.166633 |
| 32 | 124 | internal-0 | 305 | 1.215021 |
| 33 | 144 | internal-16 | 367 | 3.792461 |

The audit checked all 120 combinations of exposed faces from the three buildings. Seven combinations placed all three physical faces strictly between the proposed side vertices. Only faces 136, 305 and 367 also satisfied the three outward-facing half-planes and passed independent accessible-space and occupied-interior checks.

Each side contains the complete original building edge and an extension at either end. The three vertices are strictly inside accessible open space. They are approximately (23.247544, 59.267845), (31.511266, 58.227205) and (30.168543, 67.124048). The exact triangle has positive area, is strictly convex, and contains zero occupied interior area or occupied islands. Every facet has positive-length physical contact. Crossing any facet in a convex enlargement would put part of the enlargement inside occupied space. [Exact geometry, line equations, normals and maximality certificates](diagnostics/strict-generalisation/flat40-three-face-triangle-1/triangle-diagnosis.json).

## Directed-path diagnosis

Both handedness conventions closed the same triangle from every generating face, using 37 directed subedges per circuit. In Cartesian coordinates the right-hand path makes left turns and circulates anticlockwise around accessible space. The left-hand path makes right turns and circulates clockwise.

Each circuit adopts three extensions, follows them to their exact destination faces, and releases commitment on arrival. It traverses the complete physical faces and departs on their opposite extensions. Both arms of each face are connected through the noded network. The accepted targeted paths demonstrate that the extension geometry, handedness, turn eligibility, commitment release and final closure all work for this case.

| Hand | Physical face | Scheduled start edge | Target edges already reached | Next edge saved on stack |
| --- | ---: | ---: | ---: | ---: |
| Right | 136 | 627 | 2 | 623 |
| Right | 305 | 1369 | 3 | 6757 |
| Right | 367 | 1608 | 3 | 1614 |
| Left | 136 | 620 | 1 | 622 |
| Left | 305 | 1366 | 1 | 1368 |
| Left | 367 | 1615 | 2 | 1611 |

The prior polygon registry lacks the triangle’s exact vertex hash. The pending continuations are all straight moves. The archived search had yet to process those prefixes. Targeted replay exercised individual paths without advancing the original stacks. The evidence calls for continued enumeration when authorised. No crawler correction is needed for this case.

## Coverage and outputs

The triangle has area **36.061877 square units**. Of that, **5.239306 square units** were uncovered by the saved convex family. An exact overlay including the triangle raises the measured coverage from **81.660873% to 81.726926%**. The area increment equals the exact intersection area between the triangle and the saved uncovered cells.

The [ten-page vector atlas](diagnostics/strict-generalisation/flat40-three-face-triangle-1/flat40-three-face-triangle-atlas.pdf) shows the supporting geometry, both exact circuits, the first pending edges, the maximality certificate and the contribution to the gap. The [portable exact fixture](tests/fixtures/flat40_three_face_triangle.json) retains the three archived building footprints and face endpoints. It is checked by the [triangle regression](tests/test_flat40_three_face_triangle.py). The focused suite passed 24 tests, including the existing L-room and three- and four-building regressions.

The checkpoint and archived maps were preserved. No full enumeration or axial-map selection was run.
