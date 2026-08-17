import random
import sys
from io import BytesIO
from pathlib import Path

import streamlit as st
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import new architecture
from voronoi_app.registry import get_registry
from voronoi_app.orchestrator import run_experiment_pipeline
from voronoi_app.core import ExperimentPipeline, UrbanFormComposition
from voronoi_app.render import fig_aggregation, fig_elevation


def display_figure(figure):
    """Display a Matplotlib figure as a bounded PNG image."""
    image_buffer = BytesIO()
    figure.savefig(image_buffer, format="png", dpi=100, bbox_inches=None)
    image_buffer.seek(0)
    image = Image.open(image_buffer).convert("RGB")
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    st.image(image)

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
    canvas_size = st.slider("Canvas size", 50, 200, 100, 10)
    use_random_seed = st.checkbox("Random seed each run", value=False)
    seed = None if use_random_seed else st.number_input("Seed", 0, 999999, 42, 1)
    
    run_clicked = st.button("▶ Run Experiment", type="primary", use_container_width=True)

# Main content area
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
        
        # Display results
        st.success(f"✅ Experiment completed with seed {seed}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"Aggregation + {selected_representation.replace('_', ' ').title()}")
            display_figure(fig_aggregation(result))
        
        with col2:
            st.subheader("Digital Elevation Model")
            display_figure(fig_elevation(result))
        
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
            import json
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
