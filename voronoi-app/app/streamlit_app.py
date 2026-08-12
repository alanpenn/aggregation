import random
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voronoi_app.config import ExperimentConfig
from voronoi_app.render import fig_aggregation, fig_elevation
from voronoi_app.runner import run_experiment

st.set_page_config(page_title="Voronoi Aggregation", layout="wide")
st.title("Voronoi Aggregation Experiments")

with st.sidebar:
    st.header("Parameters")

    num_points = st.slider("Number of points", 100, 1000, 500, 50)
    canvas_size = st.slider("Canvas size", 50, 200, 100, 10)
    slope_preference = st.slider("Slope preference", 0.0, 1.0, 0.95, 0.05)
    max_dyads = st.slider("Max buildings", 10, 200, 100, 10)
    stagnation_limit = st.number_input("Stagnation limit", 100, 5000, 1000, 100)

    use_random_seed = st.checkbox("Random seed each run", value=False)
    seed = None if use_random_seed else st.number_input("Seed", 0, 999999, 42, 1)

    run_clicked = st.button("Run experiment", type="primary")

if run_clicked:
    if use_random_seed:
        seed = random.randint(0, 999999)

    config = ExperimentConfig(
        num_points=num_points,
        canvas_size=canvas_size,
        slope_preference=slope_preference,
        max_dyads=max_dyads,
        stagnation_limit=stagnation_limit,
        seed=seed,
    )

    with st.spinner("Running simulation..."):
        result = run_experiment(config)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Aggregation + visibility")
        st.pyplot(fig_aggregation(result), clear_figure=True)

    with col2:
        st.subheader("Digital elevation model")
        st.pyplot(fig_elevation(result), clear_figure=True)

    st.subheader("Summary")
    st.write(
        {
            "Buildings placed": len(result.buildings),
            "Open spaces": len(result.open_spaces),
            "Doors": len(result.doors),
            "Graph nodes": result.visibility_graph.number_of_nodes(),
            "Graph edges": result.visibility_graph.number_of_edges(),
            "Seed used": seed,
        }
    )
else:
    st.info("Adjust parameters in the sidebar, then click **Run experiment**.")
