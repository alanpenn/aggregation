"""Streamlit review, axial analysis and case exchange for imported plans."""
from hashlib import sha256
from fractions import Fraction
from io import BytesIO
import json
from zipfile import BadZipFile

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from PIL import Image
import streamlit as st
from shapely.errors import GEOSException
from shapely.geometry import box, shape
from shapely.geometry.polygon import orient

from voronoi_app.imported_town import (
    analyse_entrances, analyse_town, collection, feature, polygon_parts, review_geometry,
)
from voronoi_app.research_data import data_path, unavailable
from voronoi_app.town_case import case_bytes, load_case, save_case
from voronoi_app.town_plan_source import ExtractionSettings, extract_plan, plan_pages

VIEWS = ("Original plan", "Classified figure-ground", "Corrected polygons", "Convex street regions",
         "Certified candidate pool", "Complementary tangents", "Structurally completed pool",
         "Final reduced map")
STAGES = {4: "full", 5: "complementary", 6: "completed"}
FILL = {"building": "#d07870", "approved_domain": "#cde5ec", "exclude": "#a0c193",
        "street": "#cde5ec", "pale": "#cde5ec", "boundary": "none", "block": "none",
        "selected_domain": "#cde5ec", "convex_region": "none",
        "annotation": "#9581b1", "uncertain": "#e4ab4d"}


@st.cache_data(max_entries=4, show_spinner=False)
def cached_extract(payload, name, settings):
    return extract_plan(payload, name, settings)


def polygons_on(ax, geometry, *, face, edge, alpha, width):
    for polygon in polygon_parts(geometry):
        polygon = orient(polygon)
        rings = [polygon.exterior, *polygon.interiors]
        vertices = [p for ring in rings for p in ring.coords]
        codes = [code for ring in rings
                 for code in [Path.MOVETO, *([Path.LINETO] * (len(ring.coords)-2)), Path.CLOSEPOLY]]
        ax.add_patch(PathPatch(Path(vertices, codes), facecolor=face, edgecolor=edge,
                               alpha=alpha, linewidth=width))


def map_figure(records, *, background=None, extent=None, opacity=.55, thickness=1.,
               labels=True, lines=(), initial=None, highlight=None, vertices=()):
    figure, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    if background is not None:
        ax.imshow(background, extent=extent, alpha=opacity)
    strokes = {"boundary": "#435165", "block": "#832b2a", "convex_region": "#307c95"}
    for record in records:
        role = record["properties"]["role"]
        geometry = shape(record["geometry"])
        polygons_on(ax, geometry, face=FILL[role], edge=strokes.get(role, "#60717b"),
                    alpha=.65 if FILL[role] != "none" else .9, width=1.25 if role == "block" else .55)
        if labels and role in {"building", "convex_region", "pale", "exclude", "annotation", "uncertain"}:
            x, y = geometry.representative_point().coords[0]
            ax.text(x, y, str(record["id"]),
                    fontsize=7, ha="center", va="center", color="#212d36")
    if lines:
        def color(identifier):
            if identifier == highlight:
                return "#e04e27"
            return "#d18713" if initial is not None and identifier not in initial else "#17457d"
        ax.add_collection(LineCollection([segment for _, segment in lines],
                          colors=[color(i) for i, _ in lines],
                          linewidths=[thickness * (2.8 if i == highlight else 1.) for i, _ in lines],
                          alpha=.85))
    if vertices:
        coordinates = [[float(Fraction(v)) for v in p] for p in vertices]
        ax.scatter(*zip(*coordinates), s=10, c="#5c1749", zorder=5)
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_axis_off()
    return figure


def display(figure, alt):
    st.pyplot(figure, alt=alt)
    plt.close(figure)


def source_settings(payload, name):
    pages = plan_pages(payload, name)
    columns = st.columns(2)
    page = columns[0].number_input("Page or frame", 1, pages, key="town_page") if pages > 1 else 1
    resolution = columns[1].number_input("Extraction resolution (long edge, pixels)", 64, 6000, 1200, 100)
    with st.expander("Crop and classification thresholds"):
        x0, x1 = st.slider("Horizontal drawing region (%)", 0, 100, (0, 100))
        y0, y1 = st.slider("Vertical drawing region (%) from top", 0, 100, (0, 100))
        margin = st.slider("Red or green margin over other channels", 1, 150, 28)
        pale = st.slider("Minimum pale channel intensity", 100, 255, 180)
        chroma = st.slider("Maximum pale colour spread", 0, 155, 42)
        dark = st.slider("Dark-mark threshold", 0, 200, 100)
        minimum = st.number_input("Minimum polygon area (extraction pixels)", 1, 1000, 8)
        simplify = st.number_input("Extraction simplification (plan units)", min_value=0., value=0., step=.25)
        vector = (st.checkbox("Prefer reliable PDF vectors", True)
                  if name.lower().endswith(".pdf") else False)
    return ExtractionSettings(page=int(page), resolution=int(resolution),
                              crop=(x0/100, y0/100, x1/100, y1/100), colour_margin=margin,
                              pale_min=pale, pale_chroma=chroma, dark_max=dark,
                              min_pixels=int(minimum), simplify=simplify, prefer_vector=vector)


def review_input(extraction, key):
    records = extraction.features["features"]
    xmin, xmax, ymin, ymax = extraction.extent
    boundary = feature("analysis-boundary", "boundary", box(xmin, ymin, xmax, ymax))
    st.download_button("Download extraction GeoJSON", json.dumps(extraction.features, indent=2),
                       "extraction.geojson", "application/geo+json")
    corrected = st.file_uploader("Corrected GeoJSON (optional)", type=["geojson", "json"],
                                 key=f"town_corrected_{key}")
    if corrected:
        return json.loads(corrected.getvalue())
    ids = {role: [r["id"] for r in records if r["properties"]["role"] == role]
           for role in ("building", "exclude", "pale", "annotation", "uncertain")}
    ambiguous = [*ids["pale"], *ids["uncertain"], *ids["annotation"]]
    st.caption("Use the polygon labels in the classified view. If a pale polygon joins streets to a yard or "
               "the exterior, split it in corrected GeoJSON before approving it.")
    buildings = st.multiselect("Buildings to retain", ids["building"], default=ids["building"],
                               key=f"town_buildings_{key}")
    streets = st.multiselect("Approve street and passage polygons", ambiguous,
                             placeholder="Select polygon IDs from the classified map",
                             help="Select a dark or uncertain polygon only if it belongs inside a street.",
                             key=f"town_streets_{key}")
    use_crop = st.checkbox("Use the drawing-region rectangle as the analysis boundary",
                           help="Use Crop and classification thresholds to adjust the rectangle. "
                                "For an irregular boundary, upload corrected GeoJSON.",
                           key=f"town_boundary_{key}")
    excluded = st.multiselect("Other polygons to mark as enclosed or excluded", ambiguous,
                              key=f"town_excluded_{key}")
    reclassified = st.multiselect("Other extracted polygons that are buildings",
                                  [i for i in ambiguous if i not in streets and i not in excluded],
                                  key=f"town_reclassified_{key}")
    if set(streets) & set(excluded):
        raise ValueError("A polygon cannot be both an approved street and an exclusion.")
    chosen = {**{i: "building" for i in [*buildings, *reclassified]},
              **{i: "exclude" for i in [*ids["exclude"], *excluded]},
              **{i: "street" for i in streets}}
    output = [record | {"properties": record["properties"] | {"role": chosen[record["id"]]}}
              for record in records if record["id"] in chosen]
    return collection([*output, boundary] if use_crop else output)


def entrance_controls(analysis, key):
    with st.expander("Entrance-based movement"):
        st.caption("Enter coordinates in the plan coordinate system, or upload Point features in the "
                   "same system. Entrance routing is reported separately from map certification.")
        upload = st.file_uploader("Entrance points (GeoJSON)", type=["geojson", "json"], key=f"town_doors_{key}")
        manual = st.text_area("Manual entrance points (one x,y pair per line)", key=f"town_door_text_{key}")
        inferred = st.checkbox("Include experimental entrances at shared building–street edges",
                               key=f"town_synthetic_doors_{key}")
        if st.button("Calculate entrance routes", key=f"town_route_{key}"):
            records = [{"coordinates": list(map(float, row.split(","))), "status": "manually marked"}
                       for row in manual.splitlines() if row.strip()]
            if upload:
                data = json.loads(upload.getvalue())
                if data.get("type") != "FeatureCollection":
                    raise ValueError("Use a FeatureCollection of entrance points.")
                for item in data["features"]:
                    if item["geometry"]["type"] != "Point":
                        raise ValueError("Entrance geometry must be Point.")
                    records.append({"id": item.get("id", len(records)+1),
                                    "coordinates": item["geometry"]["coordinates"], "status": "imported"})
            if inferred:
                from shapely import get_parts
                from voronoi_app.angular import _exact_point
                for name, polygon in analysis.study.inputs["settlement"]["building_labels"].items():
                    building = analysis.study.polygons[int(name)]
                    shared = analysis.domain.boundary.intersection(building.boundary)
                    for number, part in enumerate(get_parts(shared), 1):
                        if part.geom_type == "LineString" and part.length > 0:
                            a, b = max(zip(part.coords, part.coords[1:]),
                                       key=lambda pair: sum((x-y)**2 for x, y in zip(*pair)))
                            midpoint = [float((x+y)/2) for x, y in zip(_exact_point(a), _exact_point(b))]
                            records.append({"id": f"{polygon} (inferred {number})", "coordinates": midpoint,
                                            "status": "synthetic"})
            if not records:
                raise ValueError("Provide at least one entrance point.")
            analyse_entrances(analysis, records)
            st.session_state.pop("town_bundle", None)
        if analysis.movement:
            st.json(analysis.movement, expanded=False)


def summary_block(summary, failure):
    if failure or not summary["certified"]:
        st.warning(f"Structurally incomplete. {failure or 'Independent validation did not pass.'}")
    else:
        st.success("Independently certified for the selected circulation component.")
    columns = st.columns(5)
    for column, label, value in zip(columns, ("Lines", "Convex regions", "Components", "Winding rank", "Clear lines"),
            (summary["count"], f"{summary['regions']}/{summary['required_regions']}", summary["components"],
             f"{summary['rank']}/{summary['required_rank']}", f"{summary['clear']}/{summary['count']}")):
        column.metric(label, value)


def analysis_geometry(town, analysis):
    return [*[r for r in town.approved["features"] if r["properties"]["role"] != "street"],
            feature("approved streets", "approved_domain", town.streets),
            *(feature(str(i), "block", p) for i, p in analysis.blocks.items())]


def reviewed_preview(town, extraction):
    records = [r for r in town.approved["features"] if r["properties"]["role"] != "street"]
    display(map_figure([*records, feature("streets", "approved_domain", town.streets)],
                       background=extraction.crop_image, extent=extraction.extent),
            "Reviewed polygonal geometry and resulting street space")


def show_import(root):
    st.header("Real-town figure-ground")
    mode = st.radio("Research case", ("Import a plan", "Reload a saved case"), horizontal=True)
    try:
        if mode == "Import a plan":
            import_flow(root)
        else:
            reload_flow(root)
    except (ValueError, RuntimeError, OSError, KeyError, IndexError, TypeError, GEOSException, BadZipFile) as error:
        st.error(str(error))


def import_flow(root):
    source = st.file_uploader("Original town plan", type=["pdf", "png", "tif", "tiff", "jpg", "jpeg"])
    if source is None:
        st.info("Upload the original PDF or image to begin. Pale areas need explicit approval before analysis.")
        return
    payload = source.getvalue()
    settings = source_settings(payload, source.name)
    extraction = cached_extract(payload, source.name, settings)
    extraction_key = sha256(payload + repr(settings).encode()).hexdigest()[:20]
    view = VIEWS.index(st.selectbox("Map view", VIEWS, index=1))
    if view == 0:
        st.image(extraction.original, alt="Original source page before classification or crop", width="stretch")
    elif view == 1:
        st.image(extraction.preview, alt="Plan classified as buildings, pale areas, exclusions, dark marks, and uncertain pixels",
                 width="stretch")
        st.caption("Red buildings · Green land · Blue pale candidates · Purple potential annotations · Amber uncertain")
        candidates = map_figure(extraction.features["features"], background=extraction.crop_image,
                                extent=extraction.extent)
        display(candidates, "Detected polygon identifiers for geometry review")
        st.json(extraction.audit, expanded=False)
    with st.expander("Review polygons and analysis boundary", expanded=True):
        document = review_input(extraction, extraction_key)
        roles = {r["properties"].get("role") for r in document["features"]}
        if "street" not in roles:
            st.info("Select at least one polygon under **Approve street and passage polygons**, "
                    "or supply a feature with role `street` in corrected GeoJSON.")
        if "boundary" not in roles:
            st.info("Check **Use the drawing-region rectangle as the analysis boundary**, "
                    "or supply a feature with role `boundary` in corrected GeoJSON.")
        if not {"street", "boundary"} <= roles:
            return
        bits = st.number_input("Binary fractional bits for coordinate quantisation", 0, 20, 4)
        town = review_geometry(document, grid_bits=int(bits))
        st.json(town.report, expanded=False)
        component = st.selectbox("Circulation component", list(range(len(town.components))), index=None
                                 if len(town.components) > 1 else 0,
                                 format_func=lambda i: f"{i+1} · area {town.components[i].area:,.1f} · "
                                                       f"{len(town.components[i].interiors)} holes")
        approval_key = sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()[:20]
        approved = st.checkbox("Approve these polygons after checking streets, precincts and the exterior",
                               key=f"town_approve_{extraction_key}_{approval_key}_{bits}")
    if component is None or not approved:
        if view == 2:
            reviewed_preview(town, extraction)
        return
    order = st.radio("Reduction order", ("sheaf", "shortest"), horizontal=True,
                     format_func={"sheaf": "C-H · Sheaf priority", "shortest": "C-S · Shortest first"}.get)
    merge = st.checkbox("Merge adjacent triangles where their union is convex")
    exchange = st.checkbox("Enable bounded exchanges after reduction")
    run_key = (extraction_key, approval_key, bits, component, order, merge, exchange)
    if st.button("Generate and certify axial map", type="primary"):
        with st.status("Generating certified axial map", expanded=True) as status:
            def progress(stage, detail=None):
                status.update(label=stage)
                if detail:
                    status.write(detail)
            analysis = analyse_town(town, component, order=order, merge=merge, exchange=exchange,
                                    progress=progress)
            status.update(label="Analysis finished", state="complete", expanded=False)
            st.session_state["town_result"] = (run_key, analysis)
            st.session_state.pop("town_bundle", None)
    cached = st.session_state.get("town_result")
    if cached is None or cached[0] != run_key:
        if view == 2:
            reviewed_preview(town, extraction)
        return
    analysis = cached[1]
    result = analysis.result
    stats = result.summary if result else analysis.prepared.summaries["completed"]
    summary_block(stats, analysis.prepared.failure or (result.failure if result else None))
    with st.expander("Structural certificate and candidate audit"):
        st.json({"structure": stats, "enumeration": analysis.audit, "contacts": analysis.contacts},
                expanded=False)
    st.caption("Coverage, connectivity, clearance and winding are checked on the approved geometry. "
               "The candidate pool includes enumerated occupied supports and selected domain-boundary families.")
    if view >= 2:
        render_analysis(extraction, town, analysis, view)
    if result and result.certified:
        entrance_controls(analysis, approval_key)
    options = {"order": order, "merge_convex": merge, "exchange": exchange}
    case_controls(root, source.name, payload, extraction, town, component, analysis, options, run_key)


def render_analysis(extraction, town, analysis, view):
    records = analysis_geometry(town, analysis)
    if view == 3:
        records += [feature(i, "convex_region", p) for i, p in analysis.regions.items()]
    with st.expander("Overlay settings"):
        backdrop = st.checkbox("Show source beneath geometry", True)
        opacity = st.slider("Source opacity", 0., 1., .55)
        thickness = st.slider("Axial line thickness", .25, 5., 1.)
        labels = st.checkbox("Show polygon labels", True)
    chosen = (analysis.prepared.stages[STAGES[view]] if view in STAGES else
              (analysis.result.ids if analysis.result else ()) if view == 7 else ())
    highlight = st.selectbox("Highlight candidate", chosen, index=None) if chosen else None
    initial = set(analysis.prepared.stages["complementary"]) if view == 6 else None
    vertices = [v["point"] for v in analysis.prepared.vertices if v.get("supported")] if view == 5 else []
    lines = [(i, (analysis.study.lines[i].start, analysis.study.lines[i].end)) for i in chosen]
    figure = map_figure(records, background=extraction.crop_image if backdrop else None,
                        extent=extraction.extent, opacity=opacity, thickness=thickness,
                        labels=labels, lines=lines, initial=initial, highlight=highlight, vertices=vertices)
    display(figure, VIEWS[view])
    if view == 6:
        st.caption("Blue complementary selection · Amber structural completion additions")


def case_controls(root, name, payload, extraction, town, component, analysis, options, run_key):
    if st.button("Prepare versioned research case"):
        overlay = BytesIO()
        selected = analysis.result.ids if analysis.result else analysis.prepared.stages["completed"]
        figure = map_figure(analysis_geometry(town, analysis),
                            lines=[(i, (analysis.study.lines[i].start, analysis.study.lines[i].end))
                                   for i in selected])
        figure.savefig(overlay, format="svg")
        plt.close(figure)
        bundle = case_bytes(name, payload, extraction, town, component, analysis, overlay.getvalue(), options)
        st.session_state["town_bundle"] = (run_key, bundle)
    saved = st.session_state.get("town_bundle")
    if saved and saved[0] == run_key:
        bundle = saved[1]
        st.download_button("Download research case", bundle, "town-case.zip", "application/zip")
        if st.button("Save in research data directory"):
            st.success(f"Saved {save_case(bundle, local=root / 'diagnostics')}")


def reload_flow(root):
    directory = data_path("imported-towns", local=root / "diagnostics")
    files = sorted(directory.glob("*.zip"))
    selected = st.selectbox("Saved version", files, index=None, format_func=lambda file: file.stem)
    upload = st.file_uploader("Research case ZIP", type=["zip"])
    if upload is not None:
        payload = upload.getvalue()
    elif selected is not None:
        try:
            payload = selected.read_bytes()
        except OSError as error:
            raise ValueError(unavailable(selected)) from error
    else:
        st.caption(f"Research cases are stored in {directory}")
        return
    record, saved = load_case(payload)
    view = st.selectbox("Saved map view", VIEWS, index=7)
    summary = record["final"]["summary"] if record["final"] else record["summaries"]["completed"]
    summary_block(summary, record["preparation_failure"] or (record["final"] or {}).get("failure"))
    st.caption(f"{record['source_name']} · case {record['version']}")
    if view == "Original plan":
        st.image(Image.open(BytesIO(saved["original-page.png"])), alt="Original research case source page")
    elif view == "Classified figure-ground":
        st.image(Image.open(BytesIO(saved["classification.png"])), alt="Saved classified plan")
    else:
        features = json.loads(saved["analysis.geojson"])["features"]
        geometry = [r for r in features if r["properties"]["role"] not in {"selected_domain", "street"}
                    and (r["properties"]["role"] != "convex_region" or view == "Convex street regions")]
        stage = {VIEWS[i]: name for i, name in STAGES.items()}.get(view)
        chosen = set(record["stages"][stage] if stage else (record["final"] or {}).get("ids", ())
                     if view == "Final reduced map" else ())
        lines = [(r["id"], r["geometry"]["coordinates"])
                 for r in json.loads(saved["axial.geojson"])["features"] if r["id"] in chosen]
        backdrop = st.checkbox("Show saved source beneath geometry")
        crop = Image.open(BytesIO(saved["source-crop.png"])) if backdrop else None
        initial = set(record["stages"]["complementary"]) if view == "Structurally completed pool" else None
        vertices = [v["point"] for v in record["vertices"] if v.get("supported")] if view == "Complementary tangents" else []
        display(map_figure(geometry, lines=lines, background=crop, extent=record["source_extent"],
                           initial=initial, vertices=vertices), view)
    st.download_button("Download saved vector overlay", saved["overlay.svg"], "overlay.svg", "image/svg+xml")
    st.download_button("Download approved polygons", saved["approved.geojson"], "approved.geojson",
                       "application/geo+json")
    st.download_button("Download original source", saved["source"], record["source_name"],
                       "application/octet-stream")
