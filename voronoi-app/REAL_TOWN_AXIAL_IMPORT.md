# Real-town axial-map import

In the main Streamlit application, select **Import real town plan** under
**Settlement source**. Install the project requirements first to enable PDF
import. The synthetic settlement workflow remains available in the same menu.

1. Upload the original PDF, PNG, TIFF or JPEG. Choose the page or TIFF frame,
   then use the crop controls to isolate the drawing. Review the original
   full page and the classified image.
2. Review the numbered components. Red is a building candidate, green is an
   exclusion, and pale, dark and uncertain candidates require review. A dark
   mark may be a print artefact and can be explicitly included in street space
   if it is inside a street. Leave courtyards and blank exterior unselected.
   If a pale component connects a street to a courtyard or the page exterior,
   split it using corrected GeoJSON and mark any enclosed precinct as excluded.
3. Confirm the outer analysis boundary. Use the drawing rectangle when suitable
   or provide a polygon with role `boundary`. Inspect the cleaning report and
   corrected overlay. Choose one circulation component when several exist.
   Check the approval box before generating an axial map.
4. Generate and review the candidate, complementary, completed and final maps.
   C-H is the default. C-S and bounded exchanges use the same settings and
   operations as the synthetic workflow. A result that fails structural
   completion or independent validation is marked incomplete.
5. Prepare a case bundle to download or save to `imported-towns/` within
   `AGGREGATION_DATA_ROOT` or local `diagnostics/`. Reload using the same
   menu. Each bundle has a unique version, embedded original, SHA-256 manifest,
   the untouched extraction and reviewed GeoJSON, exact interval and geometry
   records, selected stages and structural certificate, and a vector overlay.

## Corrected GeoJSON and entrances

Use the exported extraction as a spatial reference. The importer expects a
FeatureCollection of Polygon or MultiPolygon features, each with a unique
`id` and `properties.role`. Use `building`, `street`, `exclude` or `boundary`.
The coordinate frame has its origin at the bottom left of the **full** rendered
page or image, positive x to the right and positive y up. Units are source pixels
for images and points for PDFs in displayed page orientation. Cropping preserves
this frame. These are local plan coordinates in GeoJSON form. GIS data must be
aligned to the plan before upload.

Use **Entrance-based movement** for points in the same coordinate frame.
Enter one x,y pair per line or upload a Point FeatureCollection. Inferred
shared-boundary points are recorded as synthetic. Movement routing is run
separately after geometry-only certification. Coordinates alone do not establish
whether an entrance historically existed or was publicly accessible.

## Geometry and certification

Raster extraction segments RGB channels and polygonises connected pixel runs.
The coloured preview marks excluded red and green from pale classification and
shows dark annotations and uncertain pixels. The extraction report gives pixel
size and per-class methods. Optional raster simplification is recorded with
symmetric-difference area and defaults to zero. A PDF can supply simple filled
straight paths if their raster agreement for that class is at least 95%.
Compound paths, curves, clipped groups, and unreliable fills fall back by
class to the rendered image. PDF layer names are saved with retained paths.

The review adapter repairs invalid polygon rings when possible, rejects
overlapping building interiors, and snaps approved geometry to a grid of
`2^-bits` plan units, defaulting to 1/16. Coordinates on this binary grid are
directly representable as exact rational values. Review reports repairs,
quantisation and overlay differences, removed overlaps and coverage outside
the chosen boundary. GEOS performs polygon cleaning and overlay before exact
axial analysis. The approved street domain is the reviewed street union
clipped to the boundary and stripped of building and exclusion interiors.
Constrained triangulation preserves holes; optional convex merging preserves
the same domain. The adapter checks the subdivision union and exact area sum
and records positive-length shared edges.

Building blocks use both vertex and edge contacts, as in the original topology
rules. The adapter groups touching circulation holes for winding, including
enclosed non-building land. A group touching the exterior belongs to the
boundary. Axial intervals meeting identified zero-width contacts are omitted,
and contact-connected internal groups can use clearance-screened hull edges as
enclosure supports. It uses original buildings for labels and clearance and
unified block parts for convex supporting corners. Candidate support indices
are mapped to block parts in the exact geometry record. Exact tangents, maximal
intervals, positive-interior coverage, segment intersections, structural
completion, dynamic winding, unrestricted deletion, bounded exchanges and the
independent winding validator reuse the existing engine. Imported data supply
polygons, WKB topology and incidence to that engine, with no generated Voronoi
seeds or dyads. Terrain and settlement aggregation are bypassed in import mode.

The imported enumeration includes occupied support pairs and faces, clearance
certified exterior boundary edges, visible chords from reflex exterior corners,
and enclosed ring edges. Region fallback seeds cover otherwise missed convex
regions. The pool does not enumerate every possible boundary-supported or
open-area direction. A clearance certificate applies to the reported rational
intervals in the approved domain and does not establish historical accuracy or
a globally minimal map.

Candidate enumeration can be expensive on detailed raster boundaries. For a
first review, work on a cropped district. Any extraction simplification
should be chosen explicitly and reviewed for lost narrow passages.

### Subdivision sensitivity

Tests compare disjoint constrained triangles with an alternative subdivision
that merges adjacent triangles when the result is convex. Both subdivisions
pass the union and area checks.

| Fixture | Regions, triangles / merged | Candidates | C-H final lines | Rank |
|---|---:|---:|---:|---:|
| T-junction | 6 / 3 | 15 / 13 | 3 / 1 | 0 / 0 |
| Street loop around a building | 8 / 4 | 8 / 8 | 4 / 4 | 1 / 1 |

In the T-junction, the fallback candidates and selected intervals changed. In
the loop, the candidate intervals were identical and the final interval
geometries changed. Thus the final map depends on the subdivision even when
the topology and candidate geometry are fixed.

PDF path and rendering interface reference. [PyMuPDF Page API](https://pymupdf.readthedocs.io/en/latest/page.html)
