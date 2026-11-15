import json
import random
import sys
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import streamlit as st
import numpy as np
from PIL import Image
from shapely.geometry import LineString
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import new architecture
from voronoi_app.registry import get_registry
from voronoi_app.orchestrator import generate_experiment_axial_map, run_experiment_pipeline
from voronoi_app.core import ExperimentPipeline, UrbanFormComposition
from voronoi_app.render import (
    fig_aggregation, fig_elevation, fig_axial_map, fig_generated_axial_map,
    fig_angular_comparison, fig_axial_diagnostics, fig_certified_axial_map,
    fig_convex_coverage, fig_unresolved_tangents,
)
from voronoi_app.angular import (
    AngularAttachmentError, AngularConnectivityError, LineClearance,
    angular_sample_depths, topological_sample_depths,
)
from voronoi_app.angular_optimisation import optimise_angular_map, spatial_samples
from voronoi_app.axial import AxialMap
from voronoi_app.axial_diagnostics import cached_axial_audit
from voronoi_app.axial_generator import ConvexCoverageError
from voronoi_app.axial_snapshot import load_axial_snapshot, make_axial_snapshot, save_axial_snapshot
from voronoi_app.certified_maps import decode_certified_research, read_certified_fixture_bytes


@st.cache_data(max_entries=2)
def cached_certified_research(manifest, contents):
    return decode_certified_research(manifest, contents)


def display_figure(figure, alt=None):
    """Display a Matplotlib figure as a bounded PNG image."""
    image_buffer = BytesIO()
    figure.savefig(image_buffer, format="png", dpi=100, bbox_inches=None)
    image_buffer.seek(0)
    image = Image.open(image_buffer).convert("RGB")
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    st.image(image, alt=alt)


def store_snapshot(snapshot):
    st.session_state["axial_snapshot"] = json.dumps(snapshot, indent=2, allow_nan=False)
    if snapshot["audit"]["unresolved"]:
        try:
            path = save_axial_snapshot(snapshot, ROOT / "diagnostics")
        except OSError as error:
            st.error(f"Could not save the axial diagnostic snapshot: {error}")
        else:
            st.warning(f"Unresolved tangents saved to {path}")


def run_axial_audit(open_polygons, occupied_polygons, generated):
    """Audit once per session and show throttled phase and classification progress."""
    bar = st.progress(0, text="Preparing axial candidate audit")
    details = st.empty()

    def duration(seconds):
        if seconds is None:
            return "estimating"
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes}m {seconds:02d}s"

    def update(state):
        fraction = (state.examined / state.total if state.total else
                    float(state.unit != "items"))
        bar.progress(
            fraction,
            text=f"{state.phase}: {state.examined:,}/{state.total:,} {state.unit} "
                 f"({fraction * 100:.1f}%)",
        )
        classified = state.valid + state.invalid + state.unresolved
        details.caption(
            f"Elapsed: {duration(state.elapsed)}; estimated remaining in this phase: "
            f"{duration(state.remaining)}. "
            f"Corner pairs classified: {classified:,}/{state.corner_total:,}. "
            f"Valid (audit-accepted): {state.valid:,}; invalid: {state.invalid:,}; "
            f"unresolved: {state.unresolved:,}. "
            "Counts are populated during classification; buffered visibility is not "
            "a geometric validity certificate."
        )

    cache = st.session_state.setdefault("axial_audit_cache", {})
    audit, cached = cached_axial_audit(
        open_polygons, occupied_polygons, generated, cache, progress=update,
    )
    if cached:
        bar.empty()
        details.caption("Reused the completed audit for the same geometry and candidates.")
    return audit


def display_angular_result(result, generated, polygons, angular, clearance, mode, penalty):
    greedy_ids = {line.attributes["candidate_id"] for line in generated.axial_map.lines}
    angular_ids = {line.line_id for line in angular.lines}
    greedy_lines = [line for line in generated.candidate_lines if line.line_id in greedy_ids]
    angular_mean = sum(angular.depths.values()) / len(angular.depths)
    angular_topological = topological_sample_depths(
        angular.lines, angular.attachments, components=angular.sample_components,
    )
    st.subheader("Experimental angular selection")
    st.caption(
        "Bounded local search; neither the fewest-line count nor angular objective "
        "is certified globally optimal. Sample connectors and turns are included."
    )
    if angular.repaired_seed:
        st.warning(
            "The original greedy map was not a safe feasible seed. "
            "Objective improvement is measured from a repaired safe seed."
        )
    if mode == "fewest":
        st.write(
            f"Lexicographic objective (line count, mean angular depth): "
            f"({len(angular.initial_ids)}, {angular.initial_objective:.3f}) initially; "
            f"({len(angular.lines)}, {angular_mean:.3f}) after search. "
            f"Line reduction: {len(angular.initial_ids) - len(angular.lines)}; "
            f"angular-depth change: {angular_mean - angular.initial_objective:+.3f}."
        )
    else:
        st.write(
            f"Objective J = mean angular depth + {penalty:g} × line count: "
            f"{angular.initial_objective:.3f} initially; {angular.objective:.3f} after search "
            f"(improvement {angular.initial_objective - angular.objective:.3f})."
        )
    st.caption(
        f"Search: {angular.iterations} iterations over {angular.pool_size} candidates "
        f"({angular.safe_candidates} passed the conservative safety screen); "
        f"{angular.attachment_rejections} proposals rejected for sample attachment or connectivity. "
        f"Relative to greedy: {len(angular_ids - greedy_ids)} added, "
        f"{len(greedy_ids - angular_ids)} removed, {len(angular_ids & greedy_ids)} retained. "
        f"{angular.excluded_pairs} ordered sample pairs in different accessible components "
        "are excluded."
    )
    st.caption(
        "Accepted search moves: "
        + ", ".join(f"{name}: {count}" for name, count in angular.accepted_moves.items())
        + ". Added and removed counts are net differences; they do not imply unique substitutions."
    )
    angular_topo_mean = sum(angular_topological.values()) / len(angular_topological)
    baseline_angular = baseline_topological = None
    unsafe = [line.line_id for line in greedy_lines
              if not clearance.permits(LineString((line.start, line.end)))]
    if unsafe:
        st.warning(
            f"The greedy reference has {len(unsafe)} lines that failed the strict safety screen; "
            "its spatial-depth measurements are unavailable."
        )
    else:
        try:
            baseline_attachments, baseline_depths = angular_sample_depths(
                angular.samples, greedy_lines, clearance, components=angular.sample_components,
            )
            baseline_angular = sum(baseline_depths.values()) / len(baseline_depths)
            baseline_topo = topological_sample_depths(
                greedy_lines, baseline_attachments, components=angular.sample_components,
            )
            baseline_topological = sum(baseline_topo.values()) / len(baseline_topo)
        except (AngularAttachmentError, AngularConnectivityError) as error:
            st.warning(f"Greedy reference spatial-depth comparison unavailable: {error}")
    st.dataframe([
        {"Map": "Greedy reference", "Lines": len(greedy_lines),
         "Total length": sum(line.length for line in greedy_lines),
         "Convex regions": f"{len(generated.covered_regions)}/{len(generated.coverage_regions)}",
         "Circulation rings": f"{generated.preserved_rings}/{generated.required_rings}",
         "Components": generated.axial_components, "Mean topological depth": baseline_topological,
         "Mean angular depth": baseline_angular},
        {"Map": "Angular search", "Lines": len(angular.lines),
         "Total length": sum(line.length for line in angular.lines),
         "Convex regions": f"{angular.covered_regions}/{len(generated.coverage_regions)}",
         "Circulation rings": f"{angular.preserved_rings}/{angular.required_rings}",
         "Components": angular.components, "Mean topological depth": angular_topo_mean,
         "Mean angular depth": angular_mean},
    ], hide_index=True, alt="Greedy and angular map comparison")
    values = np.asarray(list(angular.depths.values()))
    st.write(
        f"Angular depth distribution: minimum {values.min():.3f}, median {np.median(values):.3f}, "
        f"90th percentile {np.percentile(values, 90):.3f}, maximum {values.max():.3f}."
    )
    sample_means = []
    for i, point in enumerate(angular.samples):
        reachable = [angular.depths[i, j] for j in range(len(angular.samples))
                     if (i, j) in angular.depths]
        sample_means.append({
            "Sample": i, "Coordinates": point,
            "Mean angular depth": sum(reachable) / len(reachable) if reachable else None,
            "Attached candidate": angular.attachments[i].line_id,
            "Attachment": tuple(float(value) for value in angular.attachments[i].point),
        })
    st.dataframe(sorted(sample_means, key=lambda row: (
        row["Mean angular depth"] is None, -(row["Mean angular depth"] or 0),
    )),
                 hide_index=True, alt="Sample angular depths and attachments")
    display_figure(
        fig_angular_comparison(result, polygons, generated.candidate_lines, greedy_ids,
                               angular.lines, angular.samples, angular.depths),
        alt="Greedy and angular lines with sample angular depths",
    )
    display_figure(
        fig_generated_axial_map(result, replace(generated, axial_map=AxialMap(angular.lines)),
                                polygons),
        alt="Experimental angular axial map",
    )


st.set_page_config(page_title="Voronoi Aggregation", layout="wide")
st.title("Voronoi Aggregation Experiments")

# Get registry
registry = get_registry()

# Sidebar controls
with st.sidebar:
    st.header("Experiment Configuration")
    
    # Terrain selection
    st.subheader("Terrain")
    terrain_options = registry.list_terrains()
    terrain_names = sorted(terrain_options)
    selected_terrain = st.selectbox(
        "Terrain type",
        options=terrain_names,
        format_func=lambda x: f"{x.replace('_', ' ').title()} - {terrain_options[x][:50]}...",
        key="terrain_select_v2"
    )
    
    # Get terrain parameters
    terrain = registry.get_terrain(selected_terrain)
    terrain_params = {}
    if terrain.parameters:
        st.write(f"**{selected_terrain.replace('_', ' ').title()} Parameters**")
        for param_name, param_schema in terrain.parameters.items():
            if param_schema.default is None:
                continue
            if param_schema.type == "float":
                terrain_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=param_schema.min_value or 0.0,
                    max_value=param_schema.max_value or 1.0,
                    value=float(param_schema.default or 0.5),
                    key=f"terrain_{param_name}"
                )
            elif param_schema.type == "int":
                terrain_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=int(param_schema.min_value or 1),
                    max_value=int(param_schema.max_value or 100),
                    value=int(param_schema.default or 50),
                    key=f"terrain_{param_name}"
                )
            elif param_schema.type == "choice":
                terrain_params[param_name] = st.selectbox(
                    param_schema.description,
                    options=param_schema.choices or [],
                    key=f"terrain_{param_name}"
                )
    
    st.divider()
    
    # Grid generator selection
    st.subheader("Grid Generator")
    grid_options = registry.list_grids()
    selected_grid = st.selectbox(
        "Grid type",
        options=list(grid_options.keys()),
        format_func=lambda x: f"{x.replace('_', ' ').title()} - {grid_options[x][:50]}...",
        key="grid_select"
    )
    
    # Get grid parameters
    grid = registry.get_grid(selected_grid)
    grid_params = {}
    if grid.parameters:
        st.write(f"**{selected_grid.replace('_', ' ').title()} Parameters**")
        for param_name, param_schema in grid.parameters.items():
            if param_schema.type == "float":
                grid_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=param_schema.min_value or 0.0,
                    max_value=param_schema.max_value or 1.0,
                    value=float(param_schema.default or 0.5),
                    key=f"grid_{param_name}"
                )
            elif param_schema.type == "int":
                grid_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=int(param_schema.min_value or 1),
                    max_value=int(param_schema.max_value or 100),
                    value=int(param_schema.default or 50),
                    key=f"grid_{param_name}"
                )
            elif param_schema.type == "choice":
                grid_params[param_name] = st.selectbox(
                    param_schema.description,
                    options=param_schema.choices or [],
                    key=f"grid_{param_name}"
                )
    
    st.divider()
    
    # Urban form selection
    st.subheader("Urban Form")
    urban_form_options = {
        "simple_dyad": "Simple building-open space pair",
        "front_back_yards": "Building with front and back yards",
        "courtyard_cluster": "Building cluster around courtyard",
    }
    selected_form = st.selectbox(
        "Urban form composition",
        options=list(urban_form_options.keys()),
        format_func=lambda x: urban_form_options[x],
        key="form_select"
    )
    
    st.divider()
    
    # Aggregation and analysis
    st.subheader("Analysis & Aggregation")
    
    agg_options = registry.list_aggregations()
    selected_agg = st.selectbox(
        "Aggregation strategy",
        options=list(agg_options.keys()),
        format_func=lambda x: f"{x.replace('_', ' ').title()} - {agg_options[x][:50]}...",
        key="agg_select"
    )
    
    # Aggregation parameters
    agg_strategy = registry.get_aggregation(selected_agg)
    agg_params = {}
    if agg_strategy.parameters:
        st.write(f"**{selected_agg.replace('_', ' ').title()} Parameters**")
        for param_name, param_schema in agg_strategy.parameters.items():
            if param_schema.type == "float":
                agg_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=param_schema.min_value or 0.0,
                    max_value=param_schema.max_value or 1.0,
                    value=float(param_schema.default or 0.5),
                    key=f"agg_{param_name}"
                )
            elif param_schema.type == "int":
                agg_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=int(param_schema.min_value or 1),
                    max_value=int(param_schema.max_value or 100),
                    value=int(param_schema.default or 50),
                    key=f"agg_{param_name}"
                )
    
    st.divider()
    
    # Measure selection
    st.subheader("Space-Syntax Measure")
    graph_options = {
        "cell_graph": "Cell graph - immediate open-space neighbours",
        "visibility_graph": "Visibility graph - direct clear sightlines",
    }
    selected_representation = st.selectbox(
        "Spatial graph",
        options=list(graph_options),
        format_func=lambda x: graph_options[x],
        key="representation_select",
    )

    measure_options = registry.list_measures()
    selected_measure = st.selectbox(
        "Spatial analysis measure",
        options=list(measure_options.keys()),
        format_func=lambda x: f"{x.replace('_', ' ').title()} - {measure_options[x][:50]}...",
        key="measure_select"
    )
    
    # Measure parameters
    measure = registry.get_measure(selected_measure)
    measure_params = {}
    if measure.parameters:
        st.write(f"**{selected_measure.replace('_', ' ').title()} Parameters**")
        for param_name, param_schema in measure.parameters.items():
            if param_schema.type == "float":
                measure_params[param_name] = st.slider(
                    param_schema.description,
                    min_value=param_schema.min_value or 0.0,
                    max_value=param_schema.max_value or 1.0,
                    value=float(param_schema.default or 0.5),
                    key=f"measure_{param_name}"
                )
    
    st.divider()
    
    # Control settings
    st.subheader("Experiment Control")
    axial_display = st.selectbox(
        "Axial display", ["Existing sightlines", "Axial Map", "All axial candidates",
                          "Axial candidate audit"]
    )
    axial_coverage = st.segmented_control(
        "Axial coverage",
        ["Voronoi cells", "Convex regions (experimental)"],
        default="Voronoi cells",
        help="Convex regions are overlapping boundary-derived approximations, not all maximal spaces.",
    )
    coverage_model = "convex" if axial_coverage == "Convex regions (experimental)" else "cells"
    if axial_coverage is None:
        st.warning("Choose an axial coverage model before running an experiment.")
    selection_method = st.selectbox(
        "Axial selection method",
        ["Greedy (baseline)", "Fewest lines, then angular (experimental)",
         "Angular depth + line penalty (experimental)"],
    )
    angular_mode = "penalty" if selection_method.startswith("Angular depth") else "fewest"
    angular_iterations = 0
    angular_seed = 42
    angular_penalty = 0.1
    if selection_method != "Greedy (baseline)":
        angular_iterations = st.number_input(
            "Angular search iterations", min_value=1, max_value=10000, value=20, step=1,
        )
        angular_seed = st.number_input(
            "Angular search seed", min_value=0, max_value=999999, value=42, step=1,
        )
        if angular_mode == "penalty":
            angular_penalty = st.number_input(
                "Line-count penalty λ", min_value=0.0, value=0.1, step=0.05,
            )
        if coverage_model != "convex":
            st.warning("Angular selection requires experimental convex-region coverage.")
        if axial_display == "Existing sightlines":
            st.warning("Choose an axial map or candidate display for angular selection.")
    canvas_size = st.slider("Canvas size", 50, 200, 100, 10)
    use_random_seed = st.checkbox("Random seed each run", value=False)
    seed = None if use_random_seed else st.number_input("Seed", 0, 999999, 42, 1)
    
    run_clicked = st.button("▶ Run Experiment", type="primary", width="stretch",
                            disabled=(axial_coverage is None or (
                                selection_method != "Greedy (baseline)" and
                                (coverage_model != "convex" or axial_display == "Existing sightlines")
                            )))

# Main content area
if st.checkbox("Show certified research maps", key="show_certified_research"):
    st.subheader("Certified research axial maps")
    st.caption(
        "Saved Y-settlement results, not the current live experiment. Geometry is converted "
        "to floating point for display only; metrics and certification are recorded results, "
        "not recalculated on this page. These maps are not claims of global optimality."
    )
    labels = {
        "reference23": "23 lines — original reference",
        "reference24": "24 lines — original reference",
        "best23": "23 lines — lowest angular depth found",
        "best24": "24 lines — lowest angular depth found",
        "best25": "25 lines — lowest angular depth found",
        "best_all_excluded": "23 lines — four face-hugging lines excluded",
    }
    try:
        manifest, contents = read_certified_fixture_bytes(ROOT / "tests" / "fixtures" / "exact_y")
        research = cached_certified_research(manifest, contents)
    except (OSError, EOFError, ValueError, KeyError, TypeError) as error:
        st.error(f"Certified research maps unavailable: {error}")
    else:
        selected = st.selectbox(
            "Certified reference map", options=list(labels),
            format_func=labels.__getitem__, key="certified_research_map",
        )
        certification = research.certifications[selected]
        metrics = certification["metrics"]
        row = st.columns(4)
        row[0].metric("Selected lines", metrics["count"])
        row[1].metric("Total axial length", f"{metrics['length']:.3f}")
        row[2].metric("Mean angular depth", f"{metrics['angular']:.4f}")
        row[3].metric("Mean topological depth", f"{metrics['topological']:.4f}")
        st.write(
            f"Convex-region coverage: {certification['regions_covered']}/"
            f"{certification['region_count']} · "
            f"Circulation rings: {certification['rings_preserved']}/"
            f"{certification['ring_count']} · "
            f"Axial graph components: {certification['graph_components']}"
        )
        exact_lines = [research.candidates[i] for i in certification["selected"]]
        figure = fig_certified_axial_map(
            research.open_polygons, research.occupied_polygons,
            research.paired_open_cells, exact_lines,
        )
        display_figure(figure, alt=f"Certified research axial map: {labels[selected]}")

if run_clicked:
    if use_random_seed:
        seed = random.randint(0, 999999)
    
    # Build experiment pipeline
    try:
        # Get urban form composition
        if selected_form == "simple_dyad":
            urban_form = UrbanFormComposition.simple_dyad()
        elif selected_form == "front_back_yards":
            urban_form = UrbanFormComposition.front_back_yards()
        elif selected_form == "courtyard_cluster":
            urban_form = UrbanFormComposition.courtyard_cluster()
        else:
            urban_form = UrbanFormComposition.simple_dyad()
        
        pipeline = ExperimentPipeline(
            terrain_provider=selected_terrain,
            terrain_params=terrain_params,
            grid_generator=selected_grid,
            grid_params=grid_params,
            urban_form=urban_form,
            aggregation_strategy=selected_agg,
            aggregation_params=agg_params,
            space_syntax_measure=selected_measure,
            measure_params=measure_params,
            representation=selected_representation,
            canvas_size=float(canvas_size),
            seed=seed,
        )
        
        with st.spinner("🔄 Running experiment..."):
            result = run_experiment_pipeline(pipeline)
        st.session_state["experiment_configuration"] = json.dumps(pipeline.to_dict(), indent=2)
        st.session_state.pop("axial_snapshot", None)
        
        # Display results
        st.success(f"✅ Experiment completed with seed {seed}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"Aggregation + {selected_representation.replace('_', ' ').title()}")
            display_figure(fig_aggregation(result))
        
        with col2:
            st.subheader("Digital Elevation Model")
            display_figure(fig_elevation(result))

        if axial_display in ("Axial Map", "All axial candidates", "Axial candidate audit"):
            st.subheader(axial_display)
            st.caption(
                "Greedy geometric approximation; boundary segments are permitted "
                "and the result is not a canonical axial map. Selected lines "
                "are connected within each open-space component."
            )
            try:
                with st.spinner("Generating axial map..."):
                    generated, polygons = generate_experiment_axial_map(
                        result, coverage_model=coverage_model,
                    )
                open_polygons = {cell: polygon for cell, polygon in polygons.items()
                                 if cell not in result.buildings}
                occupied_polygons = {cell: polygons[cell] for cell in result.buildings}
                angular = None
                clearance = None
                if selection_method != "Greedy (baseline)":
                    occupied = unary_union(list(occupied_polygons.values()))
                    accessible = unary_union(list(open_polygons.values())).difference(occupied)
                    clearance = LineClearance(accessible, occupied)
                    samples = spatial_samples(generated.coverage_regions)
                    greedy_ids = {line.attributes["candidate_id"] for line in generated.axial_map.lines}
                    try:
                        with st.spinner("Searching for a safe angular selection..."):
                            angular = optimise_angular_map(
                                generated.candidate_lines, greedy_ids, generated.coverage_regions,
                                accessible, occupied, samples, mode=angular_mode,
                                penalty=angular_penalty, iterations=angular_iterations,
                                seed=angular_seed,
                            )
                    except ValueError as error:
                        st.error(
                            f"Angular selection unavailable: {error}. "
                            "The existing greedy result is shown below."
                        )
                audit = run_axial_audit(open_polygons, occupied_polygons, generated)
                snapshot = make_axial_snapshot(
                    pipeline.to_dict(), open_polygons, occupied_polygons,
                    generated, audit, result.open_spaces,
                )
                store_snapshot(snapshot)
                if snapshot["audit"]["unresolved"]:
                    st.warning(
                        f"Candidate audit: {snapshot['audit']['missing']} missing and "
                        f"{snapshot['audit']['indeterminate']} numerically unresolved "
                        "mutual tangent pairs."
                    )
                    st.subheader("Unresolved mutual tangents")
                    display_figure(fig_unresolved_tangents(open_polygons, occupied_polygons, audit))
                    st.dataframe(
                        [{"Start": item["start"], "End": item["end"], "Status": item["status"],
                          "Exact visibility": item["exact_visible"],
                          "Occupied interior": item["crosses_occupied_interior"],
                          "Reason": item["reason"]}
                         for item in snapshot["audit"]["unresolved"]],
                        hide_index=True,
                    )
                else:
                    st.caption("Candidate audit found no missing or indeterminate mutual tangents.")
                if axial_display == "Axial candidate audit":
                    display_figure(fig_axial_diagnostics(result, generated, polygons, audit))
                    present = sum(pair.status == "present" for pair in audit.pairs)
                    missing = sum(pair.status == "missing" for pair in audit.pairs)
                    indeterminate = sum(pair.status == "indeterminate clipping" for pair in audit.pairs)
                    unattempted = sum(not pair.attempted for pair in audit.pairs)
                    missed_unattempted = sum(pair.status == "missing" and not pair.attempted
                                             for pair in audit.pairs)
                    missed_attempted = missing - missed_unattempted
                    extension_mismatch = sum(
                        pair.maximal is not None and
                        (pair.generator_interval is None or
                         pair.maximal.hausdorff_distance(pair.generator_interval) > audit.tolerance)
                        for pair in audit.pairs
                    )
                    st.write(
                        f"Boundary vertices: {audit.boundary_vertices}; exposed convex building "
                        f"corners: {audit.convex_building_vertices}; mixed boundary corners "
                        f"excluded: {audit.mixed_boundary_vertices}."
                    )
                    st.write(
                        f"Corner pairs: {audit.possible_pairs}; coincident: {audit.coincident_pairs}; "
                        f"blocked: {audit.blocked_pairs}; visible: {audit.visible_pairs} "
                        f"({audit.buffered_only_pairs} only with tolerance); visible but not "
                        f"mutually occluding: {audit.non_occluding_pairs}."
                    )
                    st.write(
                        f"Mutual tangent pairs: {len(audit.pairs)}; present: {present}; "
                        f"missing: {missing}; clipping indeterminate: {indeterminate}; "
                        f"not attempted: {unattempted}; "
                        f"distinct existing maximal tangent lines: {len(audit.source_indices['occluding'])}."
                    )
                    st.write(
                        f"Missing pairs not attempted: {missed_unattempted}; attempted but "
                        f"missing: {missed_attempted}; independently measurable extension "
                        f"mismatches: {extension_mismatch}."
                    )
                    st.write("Candidate seed replay (sources can overlap):")
                    st.dataframe(
                        [{"Stage": stage, **counts} for stage, counts in audit.stage_counts.items()],
                        hide_index=True,
                    )
                    st.caption(
                        "Candidate source matches can overlap; the plot assigns one color per line. "
                        "Fallback means no boundary, vertex or centroid source was matched. "
                        "Visibility uses the generator's buffered geometry; ambiguous clipping "
                        "is shown separately and is not counted as missing."
                    )
                else:
                    display_figure(fig_generated_axial_map(
                        result, generated, polygons,
                        show_candidates=axial_display == "All axial candidates",
                    ))
                if generated.coverage_model == "convex":
                    st.subheader("Convex-region coverage")
                    st.caption(
                        "Overlapping regions are expanded from triangulation seeds using "
                        "accessible-boundary vertices; they are not all maximal convex spaces. "
                        "Existing candidate endpoints can have floating-point boundary "
                        "penetrations, so obstacle clearance is not certified."
                    )
                    display_figure(
                        fig_convex_coverage(result, generated, polygons),
                        alt="Convex regions, selected lines, and uncovered regions",
                    )
                if angular is not None:
                    assert clearance is not None
                    display_angular_result(
                        result, generated, polygons, angular, clearance,
                        angular_mode, angular_penalty,
                    )
                    st.subheader("Greedy baseline diagnostics")
                axial_columns = st.columns(4)
                axial_columns[0].metric("Candidate lines", generated.candidates)
                axial_columns[1].metric("Selected lines", len(generated.axial_map.lines))
                axial_columns[2].metric(
                    "Cells intersected" if generated.coverage_model == "convex" else "Cells covered",
                    f"{len(generated.covered_cells)}/{generated.open_cells}",
                )
                axial_columns[3].metric("Obstacle rings preserved", f"{generated.preserved_rings}/{generated.required_rings}")
                if generated.coverage_model == "convex":
                    st.metric(
                        "Convex regions covered",
                        f"{len(generated.covered_regions)}/{len(generated.coverage_regions)}",
                    )
                removed = sum(decision.accepted for decision in generated.dominance_decisions)
                st.write(
                    f"Topological dominance reduction: {generated.pre_dominance_lines} to "
                    f"{generated.pre_collective_lines} lines; {removed} removed."
                )
                if generated.depth_pairs:
                    st.caption(
                        f"Mean topological depth among {generated.depth_pairs} comparable "
                        f"retained-line pairs: {generated.mean_depth_before:.3f} before, "
                        f"{generated.mean_depth_after:.3f} after."
                    )
                if generated.dominance_decisions:
                    with st.expander("Topological dominance decisions"):
                        st.caption(
                            "IDs refer to candidate lines; rejected decisions may be "
                            "reconsidered after another line is removed."
                        )
                        st.dataframe(
                            [{"Dominated candidate": decision.dominated,
                              "Dominating candidate": decision.dominator,
                              "Decision": "Removed" if decision.accepted else "Retained",
                              "Reason": decision.reason}
                             for decision in generated.dominance_decisions],
                            hide_index=True,
                            alt="Topological dominance decisions",
                        )
                collective_removed = sum(
                    decision.accepted for decision in generated.collective_decisions
                )
                st.write(
                    f"Collective redundancy reduction: {generated.pre_collective_lines} to "
                    f"{len(generated.axial_map.lines)} lines; {collective_removed} removed."
                )
                if generated.collective_decisions:
                    with st.expander("Collective redundancy decisions"):
                        st.caption(
                            "Candidate IDs are reconsidered after each removal. "
                            "A rejected decision shows the first failing constraint."
                        )
                        st.dataframe(
                            [{"Candidate": decision.candidate,
                              "Decision": "Removed" if decision.accepted else "Retained",
                              "Reason": decision.reason}
                             for decision in generated.collective_decisions],
                            hide_index=True,
                            alt="Collective redundancy decisions",
                        )
                st.caption(
                    "Unassigned open cells are traversable; they are shown in pale sand. "
                    "Paired open cells are white and occupied cells are grey."
                )
                st.caption(
                    "Candidate source matches (may overlap): "
                    + ", ".join(f"{name}: {count}" for name, count in generated.source_counts.items())
                )
                if generated.ambiguous_pairs:
                    st.warning(f"{len(generated.ambiguous_pairs)} visible tangent pairs "
                               "could not be represented safely; inspect the audit.")
                    if axial_display == "Axial candidate audit":
                        st.dataframe(
                            [{"Start": start, "End": end, "Reason": reason}
                             for start, end, reason in generated.ambiguous_pairs],
                            hide_index=True,
                        )
            except ConvexCoverageError as error:
                st.error(f"Axial map generation failed: {error}")
                st.caption("Partial selection only; uncovered convex regions are shown in red.")
                display_figure(
                    fig_convex_coverage(result, error, error.polygons),
                    alt="Partial axial selection and uncovered convex regions",
                )
            except ValueError as error:
                st.error(f"Axial map generation failed: {error}")
        else:
            st.subheader("Axial sightlines")
            st.caption(
                "Approximate clear lines between open-space cells; these are not "
                "a canonical maximal axial map."
            )
            display_figure(fig_axial_map(result))
        
        # Results summary
        st.subheader("📊 Analysis Results")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Buildings", len(result.buildings))
        with col2:
            st.metric("Open Spaces", len(result.open_spaces))
        with col3:
            st.metric("Doors", len(result.doors))
        with col4:
            st.metric("Graph Nodes", result.visibility_graph.number_of_nodes())
        
        # Space-syntax measures
        if result.analysis_results:
            st.subheader(f"🔬 {selected_measure.replace('_', ' ').title()} Measure")
            
            # Summary statistics
            measure_values = list(result.analysis_results.get(selected_measure, {}).values())
            finite_values = [value for value in measure_values if np.isfinite(value)]
            unreachable_count = len(measure_values) - len(finite_values)
            if not finite_values:
                st.info("No measure values were produced for this experiment.")
            else:
                if unreachable_count:
                    st.warning(
                        f"{unreachable_count} graph nodes are unreachable from the rest "
                        "of the graph and are excluded from the distribution."
                    )

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Min", f"{min(finite_values):.3f}")
                with col2:
                    st.metric("Max", f"{max(finite_values):.3f}")
                with col3:
                    st.metric("Mean", f"{np.mean(finite_values):.3f}")
                with col4:
                    st.metric("Std Dev", f"{np.std(finite_values):.3f}")
                
                # Distribution visualization
                import matplotlib.pyplot as plt
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.hist(finite_values, bins=30, edgecolor='black', alpha=0.7)
                ax.set_xlabel(selected_measure.replace('_', ' ').title())
                ax.set_ylabel("Frequency")
                ax.set_title(f"Distribution of {selected_measure.replace('_', ' ').title()}")
                display_figure(fig)
        
        # Configuration summary
        with st.expander("📋 Experiment Configuration (JSON)"):
            config_dict = pipeline.to_dict()
            st.json(config_dict)
    
    except Exception as e:
        st.error(f"❌ Error running experiment: {str(e)}")
        st.error("Check the configuration and try again.")
        import traceback
        st.text(traceback.format_exc())

else:
    st.info(
        "👈 Configure your experiment in the sidebar and click **▶ Run Experiment** to begin. "
        "\n\n**Terrain Types:** Procedurally generated elevation fields"
        "\n\n**Grid Generators:** Standard Voronoi, Cartesian, or Topography-Responsive"
        "\n\n**Urban Forms:** Simple dyads, front/back yards, or courtyard clusters"
        "\n\n**Analysis Measures:** Connectivity, integration, depth, and choice centrality"
    )

st.subheader("Experiment diagnostics")
uploaded_snapshot = st.file_uploader("Load axial diagnostic snapshot", type="json")
if st.button("Rerun saved axial audit", disabled=uploaded_snapshot is None):
    try:
        snapshot_data = json.loads(uploaded_snapshot.getvalue())
        saved_open, saved_occupied, saved_generated, saved_config, saved_paired = (
            load_axial_snapshot(snapshot_data)
        )
        saved_audit = run_axial_audit(saved_open, saved_occupied, saved_generated)
        updated_snapshot = make_axial_snapshot(
            saved_config, saved_open, saved_occupied, saved_generated, saved_audit, saved_paired,
        )
        st.session_state["experiment_configuration"] = json.dumps(saved_config, indent=2)
        store_snapshot(updated_snapshot)
        st.write(
            f"Mutual tangent pairs: {len(saved_audit.pairs)}; "
            f"present: {updated_snapshot['audit']['present']}; "
            f"missing: {updated_snapshot['audit']['missing']}; "
            f"clipping indeterminate: {updated_snapshot['audit']['indeterminate']}."
        )
        display_figure(fig_unresolved_tangents(saved_open, saved_occupied, saved_audit))
    except (ValueError, KeyError) as error:
        st.error(f"Cannot rerun axial diagnostic snapshot: {error}")
if "experiment_configuration" in st.session_state:
    st.download_button(
        "Download experiment configuration", st.session_state["experiment_configuration"],
        file_name="experiment-configuration.json", mime="application/json", on_click="ignore",
    )
if "axial_snapshot" in st.session_state:
    st.download_button(
        "Download axial diagnostic snapshot", st.session_state["axial_snapshot"],
        file_name="axial-diagnostic.json", mime="application/json", on_click="ignore",
    )
