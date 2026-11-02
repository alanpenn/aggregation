import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from voronoi_app.morphic.axial_experiment import (  # noqa: E402
    AxialExperimentConfig,
    run_axial_batch,
    save_axial_batch,
)
from voronoi_app.morphic.axial_viz import (  # noqa: E402
    fig_axial_graph_diagnostics,
    fig_axial_snapshot,
    fig_axial_trajectories,
    summarise_axial_runs,
)
from voronoi_app.morphic.axial_statistics import paired_final_tests  # noqa: E402
from voronoi_app.morphic.report import legend_text  # noqa: E402
from voronoi_app.registry import get_registry  # noqa: E402

MODE_LABELS = {
    "random": "Mode 0 - Random occupation",
    "adjacent": "Mode 1 - Adjacent aggregation (3-syntax)",
    "enclosing": "Mode 2 - Enclosing aggregation (4-syntax approximation)",
}

st.set_page_config(page_title="Morphic Grammar - Emergent Axial Structure", layout="wide")
st.title("Morphic Grammar - Emergent Axial Structure")
st.caption(
    "Axial structure is derived from the continuous union of open-cell polygons, not from cell "
    "adjacency or the growth history. The sampled maximal-line method is a reproducible "
    "approximation, not a complete or unique conventional axial map."
)


def show(figure):
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
    buffer.seek(0)
    image = Image.open(buffer).convert("RGB")
    image.thumbnail((2200, 1800), Image.Resampling.LANCZOS)
    st.image(image)


with st.sidebar:
    st.header("Controlled experiment")
    modes = st.multiselect(
        "Generative modes",
        options=list(MODE_LABELS),
        default=["random", "adjacent", "enclosing"],
        format_func=lambda mode: MODE_LABELS[mode],
    )
    num_cells = st.number_input("Voronoi cell count", 30, 1000, 200, step=10)
    occupied_target = st.number_input(
        "Occupied-cell target",
        1,
        int(num_cells) - 1,
        min(60, int(num_cells) - 1),
    )
    seed = st.number_input("First random seed", 0, 1_000_000, 40)
    repetitions = st.number_input("Repetitions", 1, 30, 1)
    interval = st.number_input("Analysis interval (occupied cells)", 1, 60, 10)
    terrain = st.selectbox("Terrain", list(get_registry().terrains), index=0)
    st.caption("Terrain is recorded but not used by these first-stage growth rules.")
    st.subheader("Axial extraction (approximation)")
    sample_spacing = st.number_input("Interior sample spacing", 2.0, 30.0, 8.0, 1.0)
    angle_step = st.select_slider(
        "Angular resolution (degrees)",
        options=[5, 10, 15, 20, 30, 45],
        value=15,
    )
    local_radius = st.number_input("Local integration radius", 1, 10, 3)
    colour_by = st.selectbox(
        "Colour axial lines by",
        ["length", "connectivity", "global_integration_rra", "local_integration_rra"],
        format_func=lambda value: {
            "length": "Geometric length",
            "connectivity": "Axial connectivity",
            "global_integration_rra": "Global integration (RRA)",
            "local_integration_rra": "Local integration (RRA)",
        }[value],
    )
    run = st.button("Run axial experiment", type="primary")

if run:
    if not modes:
        st.warning("Select at least one generative mode.")
    else:
        config = AxialExperimentConfig(
            num_cells=int(num_cells),
            occupied_target=int(occupied_target),
            seed=int(seed),
            terrain=terrain,
            sample_spacing=float(sample_spacing),
            angle_step_degrees=float(angle_step),
            local_radius=int(local_radius),
            analysis_interval=int(interval),
        )
        seeds = range(int(seed), int(seed) + int(repetitions))
        with st.spinner(
            f"Generating cells and analysing {repetitions * len(modes)} mode/seed runs..."
        ):
            runs = run_axial_batch(seeds, modes, config)
            identity = hashlib.sha1(
                json.dumps(
                    {
                        "config": config.__dict__,
                        "modes": modes,
                        "repetitions": int(repetitions),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:10]
            output_dir = ROOT / "outputs" / "morphic_axial" / identity
            save_axial_batch(runs, output_dir)
        st.session_state["morphic_axial"] = {
            "runs": runs,
            "modes": modes,
            "identity": identity,
            "output_dir": str(output_dir),
        }

state = st.session_state.get("morphic_axial")
if not state:
    st.info("Set the experiment controls and press **Run axial experiment**.")
    st.stop()

runs = state["runs"]
modes = state["modes"]
first_seed_runs = {
    mode: next(run for run in runs if run.config.mode == mode)
    for mode in modes
}

st.subheader("Developmental trajectory")
st.dataframe(summarise_axial_runs(runs), width="stretch")
if len(runs) > len(modes):
    show(fig_axial_trajectories(runs))
if "random" in modes and "adjacent" in modes:
    st.markdown("**Exploratory paired comparison at the occupied-cell target**")
    st.dataframe(
        paired_final_tests(
            runs,
            mode_a="random",
            mode_b="adjacent",
            step=first_seed_runs["random"].config.occupied_target,
        ),
        width="stretch",
    )
    st.caption(
        "Wilcoxon signed-rank tests match seeds and use Holm adjustment across four measures. "
        "These exploratory comparisons do not include Mode 2 when enclosure stops before the "
        "occupied-cell target."
    )

st.subheader("Emergent structure by mode")
for mode, run_result in first_seed_runs.items():
    with st.expander(f"{MODE_LABELS[mode]} (seed {run_result.config.seed})", expanded=True):
        snapshots = run_result.snapshots
        step_options = [snapshot.step for snapshot in snapshots]
        selected_step = st.select_slider(
            f"Occupied cells - {mode}",
            options=step_options,
            value=step_options[-1],
            key=f"axial_step_{mode}",
        )
        snapshot = next(item for item in snapshots if item.step == selected_step)
        st.caption(
            f"Carrier {run_result.carrier_id}; {snapshot.representation.candidate_count} "
            f"candidate maximal lines; method: {snapshot.representation.method}; "
            f"settings: {snapshot.representation.settings}; "
            f"sample coverage: {snapshot.axial_metrics['sample_coverage_fraction']:.1%}"
        )

        st.markdown("**View A - Cellular morphology**")
        # The first coordinated figure includes this view beside the axial lines.
        fig = fig_axial_snapshot(
            run_result.carrier, snapshot, run_result.generation.target, colour_by
        )
        show(fig)
        st.caption(
            legend_text()
            + " Axial-line colours use the selected measure; morphology categories remain distinct."
        )
        st.markdown("**View C - Axial graph and configurational diagnostics**")
        show(fig_axial_graph_diagnostics(snapshot))

        metrics = snapshot.axial_metrics
        st.write({
            "axial_lines": metrics["axial_line_count"],
            "axial_intersections": metrics["intersection_count"],
            "axial_components": metrics["component_count"],
            "cycle_rank": metrics["cycle_rank"],
            "global_integration_convention": "Hillier-Hanson RRA, Integration = 1/RRA",
            "intelligibility_pearson": metrics["intelligibility_pearson"],
            "intelligibility_r_squared": metrics["intelligibility_r_squared"],
            "intelligibility_n": metrics["intelligibility_n"],
            "undefined_integration_lines": sum(
                value is None for value in metrics["global_integration_rra"].values()
            ),
        })

st.caption(
    f"Saved configurations, carrier geometries, growth histories, axial graphs and measures in "
    f"`{state['output_dir']}` (experiment id {state['identity']})."
)

with st.expander("Method and limitations"):
    st.markdown(
        """
        - Open geometry is the union of unoccupied Voronoi polygons. It represents geometric openness,
          not pedestrian permeability; no door or access restrictions are part of this grammar.
        - The replaceable `sampled_maximal_lines_v1` extractor samples interior locations and directions,
          retains maximal contiguous line-of-sight segments, and greedily covers the samples. Angular and
          spatial sampling affect the result; it is not claimed to be a complete or unique axial map.
        - Intersections are edges in a separate axial graph only when lines cross inside open geometry.
          Disconnected open-space systems remain disconnected.
        - Global/local integration use Hillier-Hanson real relative asymmetry (RRA), with each graph
          component analysed separately. Components of fewer than three lines and degenerate cases are
          undefined. Intelligibility is Pearson correlation between axial connectivity and global
          integration; it is undefined for insufficient or constant observations.
        - Axial measures are outcomes only; generative rules do not optimise integration, intelligibility
          or any other global configurational measure.
        """
    )
