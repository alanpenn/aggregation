# Vertex supported axial selection on Flat 40

The occupied geometry contains **438 distinct exact coordinates** and **604 building-vertex occurrences**. Each occurrence retains its building cell and label, polygon index, two rational incident-edge vectors, coincident building memberships and exact shared-edge or vertex-only contact records.
The index links 3,068 vertex–candidate pairs across 1,534 certified candidates.

A candidate supports a vertex when its exact interval contains that coordinate and its direction passes the existing supporting-vertex predicate for at least one incident building. The tangent-contact table distinguishes edge-aligned support from a tangent through the vertex alone. The index counts intermediate support contacts as well as generating endpoints. IDs, endpoints, route references, and incidence come from the archived certified pool.

## Geometry and backbone

Extended candidates are at least the pool median length, **22.08 units**. The vertex score combines distinct nonredundant extended families, occupied 15° direction bins, maximum length, and mean transverse family diversity with scaled weights 0.35, 0.30, 0.20, and 0.15. E ranks candidates using 55% of their strongest supporting vertex score and 45% of D's static geometric tie-break order score. E selects the first 12 nonredundant candidates before common coverage, connectivity, winding repair, reduction, and exchange. Doorway route costs are evaluated afterward.

The highest-scoring vertex decile has median distance **4.55** to an archived transverse intersection, versus **4.90** for the remaining vertices. The intersections are a junction proxy from the independently archived map. The score's transverse-diversity term and shared geometry mean this single-case contrast is descriptive.

## Map comparison

| Method | Stage | Lines | Winding | Angular mean | Metric mean |
|---|---|---:|---:|---:|---:|
| D | archived_count | 44 | 24/24 | 0.8562 | 48.472 |
| D | constructive | 34 | 24/24 | 0.8691 | 48.691 |
| D | exchanged | 33 | 24/24 | 0.8691 | 48.691 |
| strict-backward | baseline | 44 | 24/24 | 1.1471 | 49.149 |

E stalled at winding rank 23/24 with 100 lines. It covered every required region and doorway and formed one connected network. The comparison reports movement for the certified controls.

The independent termination check found a shared enclosure for internal-0, internal-4. It counted as a single winding class. [Exact termination certificate](termination-winding.json)

## Independent tangent checks

| Candidate | E rank | Supporting building labels | E backbone | E partial | E final | D final |
|---|---:|---|---|---|---|---|
| 957 | 336 | 18, 87 | False | False | False | False |
| 1244 | 160 | 1, 5 | False | False | False | False |
| 1355 | 215 | 41, 43 | False | False | False | False |
| 865 | 884 | 15, 25 | False | False | False | False |
| 1189 | 169 | 1, 6 | False | False | False | False |
| 1190 | 515 | 5, 6 | False | True | False | True |
| 1208 | 305 | 12, 87 | False | False | False | True |
| 1354 | 802 | 11, 43 | False | False | False | False |

The named candidates appear only in the evaluation. The experiment uses Flat 40 as specified in the supplied brief. The final contact-type bullet ends mid-sentence, so face contact here means an exact shared polygon edge and vertex-only contact means a coincident point without such an edge.

[Numbered vector atlas](numbered-axial-atlas.pdf) · [Exact vertex index](vertices.json) · [Axial support contacts](tangent-contacts.json) · [Comparison CSV](comparison.csv) · [Target evaluation](targets.json) · [Map index](visual-index.json)
