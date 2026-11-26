# Flat 40 convex-enlargement diagnosis

## Four exact counterexamples

| Previous atlas page | Region | Old area | Enlarged area | Witness |
|---|---|---:|---:|---|
| 3 | `21a7aa91ea9375bf` | 4.31254 | 19.00742 | Simultaneous union with atoms 2244 and 2302 |
| 9 | `6810e25061ad27b9` | 5.37479 | 7.55492 | Simultaneous union with atoms 2376 and 2389 |
| 14 | `880286b22d381950` | 15.83048 | 20.12246 | Simultaneous union with atoms 2191 and 2361 |
| 18 | `c99826db684d98fa` | 2.10439 | 3.99939 | Convex hull with a new rational point beyond an extension edge |

The values are display approximations in square model units. The exact
vertices, fractions, archived generating walks, edge provenance and
certificates are in `local-witnesses.json`. The four-page vector atlas
shows each witness on the original numbered settlement, with matching
extents before and after.

Each witness is a strict convex superset of its predecessor. The test
rebuilds the rational convex hull, verifies positive area growth, checks
an interior point in the archived accessible component, and rejects any
positive-length interior crossing of its entire boundary inventory.
As a separate screen it clips each overlapping occupied cell against
the proposed convex hull and requires zero area of intersection. This
also excludes a wholly enclosed occupied island. No archived candidate
or selected axial map participates in these geometric tests.

## Edge provenance

All 15 examined edges coincide over positive length with a certified
axial candidate. Their generating records are occupied faces or
extensions of those faces. The arrangement derives from the occupied
blocks and the accessible-domain boundary, with no axial candidate
input. Coincidence occurs because the candidate generator also uses
occupied-face supports.

Five of the edges have positive-length contact with occupied geometry.
A convex enlargement crossing one of those facets would put the contact
inside its interior, contradicting the accessible-domain boundary test.
The other ten are extension-only facets. Every one admits its own valid
crossing witness, saved under its edge record. The examination identifies
no extra independent vertex tangent or axial edge in the generating
arrangement. The underlying problem is that the old maximality search
required a convex intermediate union after taking **one whole atom**.
It could neither take two complementary atoms simultaneously nor stop
inside an atom at a new rational boundary.

## Revised experimental search

The experiment retains archived directed and handed start provenance and
keeps physical outward normals. For each predecessor it tries rational
outward points across each facet and adopts the greatest certified
area increase among the attempted witnesses. The four targeted cases
also carry forward valid simultaneous-atom witnesses. One-sided
physical contacts remain supporting constraints wherever the enlarged
polygon touches them. Artificial boundaries have no terminal authority
in the enlargement test. The search is bounded and makes no general
claim of maximality for enlarged polygons.

For the overlap overlay, exact noding combines revised region boundaries
with the existing arrangement as scaffolding. Each oriented boundary
contributes its signed integer increment across the dual faces. Counts
start at zero in the exterior and are propagated with consistency checks.
The exact domain area telescopes across the verified boundary
segments. Each overlay face has a rational shoelace area and an exact
integer count. Multiplicity areas are represented by those rational
terms grouped by count, with decimal totals for display.

## Whole-settlement enlargement and maximality

The search found a strict enlargement for 2,200 of the 2,201 predecessors.
No region was deleted. There are 2,201 distinct revised convex polygons.
The sole unchanged polygon, `9c4c7985a835b676`, has positive-length
contact with the accessible-domain boundary on all four facets. Each
facet blocks any convex superset crossing its supporting line. Since
a strict superset must cross at least one of these lines, this certifies
global maximality of that polygon. The exact facet contact intervals are
in `facet-maximality.json`. Maximality of the other 2,200 revised polygons
remains unresolved. Their certificates establish strict valid enlargement
of the archived geometry.

The exact revised overlay has 57,596 accessible faces, zero uncovered
area and zero occupied-island violations. The total accessible area
remains 7,932.07115 square model units.

| Coverage multiplicity | Previous cover area | Revised cover area |
|---|---:|---:|
| 0 | 0 | 0 |
| 1 | 84.65684 | 46.73765 |
| 2 | 619.92095 | 256.63585 |
| 3 | 2251.54167 | 674.30968 |
| 4 or more | 4975.95170 | 6954.38798 |
| Maximum multiplicity | 11 | 29 |
| Area-weighted mean multiplicity | 3.98633 | 7.18315 |
| Area-weighted median multiplicity | 4 | 7 |

The overlap counts are exact. The displayed band areas are
approximations of the rational per-face terms in `exact-overlap.json`.

## Frozen axial incidence

The revised family has 26 polygons overlapping the interior of archived
region 257. Candidate 1435 traverses 24 of them and candidate 1509
traverses 17. In the archived 34-line C-H selection, the number of
requirements met solely by 1509 falls from eight to two across the
settlement and from five to two near region 257. Removing 1509 from
that fixed selection still leaves these two requirements unmet.

C-H reduction ran after the exact union and geometry checks passed.
It reduced the revised cover to **76 lines** using the original 1,534
maximal intervals. The final map independently certified 2,201/2,201
regions, 100/100 doorways, one connected component, 24/24 winding,
and all 76 clearances. It retains 1435. Candidate 1509 is absent.
Candidate **1483** is the selected hit for both remaining regions
that relied on 1509 in the archived C-H map.

The 76-line result compares with 133 lines for the preceding
face-extension cover and 34 for the archived cover. These figures
refer to different sets of strict coverage constraints. Full geometric
coverage, convexity, occupied-interior exclusion and orientation were
evaluated independently of line count. The replay identified 1,839
positive-length physical contacts on the enlarged family, with no
inward-facing supports.

## Records and replay

The four targeted diagnostics, exact witnesses, full overlap map,
and revised selection are stored in
`diagnostics/strict-generalisation/flat40-convex-enlargement-1/`.
The cover generation first runs the targeted procedure, then the
full pass against a new output directory. Set the manifest to the
shared migration SHA-256 inventory.

```sh
export AGGREGATION_DATA_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
s=diagnostics/strict-generalisation
out="$s/flat40-convex-enlargement-replay"
manifest="$AGGREGATION_DATA_ROOT/migration-sha256-2026-11-24.json"
arrangement="$s/flat40-face-extension-cover-2/arrangement.json"
audit="$s/flat40-oriented-face-cover-1/orientation-audit.json"
oriented="$s/flat40-oriented-face-cover-1/oriented-cover.json"
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_convex_enlargement \
  --manifest "$manifest" --source "$arrangement" --audit "$audit" --oriented "$oriented" --output "$out"
PYTHONPATH=src:. .venv/bin/python -m experiments.flat40_enlarged_cover \
  --manifest "$manifest" --arrangement "$arrangement" --audit "$audit" --oriented "$oriented" --output "$out"
```

Eight focused regression tests passed. Production selection and previous
experimental versions remain intact.
