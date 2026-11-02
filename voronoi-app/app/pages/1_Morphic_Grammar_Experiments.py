import sys
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from voronoi_app.morphic.experiment import (  # noqa: E402
    MODE_LABELS, MorphicConfig, run_batch, run_comparison,
)
from voronoi_app.morphic.report import (  # noqa: E402
    fig_comparison, fig_distributions, legend_text, summarise,
)
from voronoi_app.registry import get_registry  # noqa: E402

st.set_page_config(page_title="Morphic Grammar Experiments", layout="wide")
st.title("Morphic Grammar Experiments")
st.caption(
    "Hillier, Leaman, Stansall & Bedford (1976): minimum setup and the third and fourth "
    "syntactic operations. Mode 2 is an operational approximation of the fourth operation "
    "- a testable hypothesis, not a reconstruction."
)


def show(figure):
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
    buffer.seek(0)
    image = Image.open(buffer).convert("RGB")
    image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    st.image(image)


with st.sidebar:
    st.header("Morphic grammar")
    modes = st.multiselect(
        "Generative modes",
        options=["random", "adjacent", "enclosing"],
        default=["random", "adjacent", "enclosing"],
        format_func=lambda m: MODE_LABELS[m],
    )
    include_continue = st.checkbox(
        "Also run Mode 2b (enclose, then keep growing to the cell budget)",
        value=True,
        help="Mode 2 stops once the target is enclosed, so it uses far fewer occupied cells. "
             "Mode 2b gives a budget-matched comparison.",
    )
    num_cells = st.number_input("Cell count", 30, 2000, 200, step=10)
    occupied_target = st.number_input("Occupied-cell target", 1, int(num_cells) - 1, 60)
    seed = st.number_input("Random seed", 0, 1_000_000, 40)
    terrain = st.selectbox("Terrain", list(get_registry().terrains), index=0)
    st.caption("Terrain only supplies cell elevations here; the rules do not use it.")
    strength = st.slider("Enclosure preference strength (Mode 2)", 0.0, 1.0, 1.0, 0.05)
    target_size = st.number_input("Enclosure target size (cells)", 1, 6, 1)
    repetitions = st.number_input("Repetitions (consecutive seeds)", 1, 100, 1)
    show_graph = st.checkbox("Overlay open-space accessibility graph", value=False)
    run = st.button("Run experiment", type="primary")

if run:
    selected = list(modes) + (["enclosing_continue"] if include_continue and "enclosing" in modes else [])
    if not selected:
        st.warning("Select at least one mode.")
    else:
        base = MorphicConfig(
            num_cells=int(num_cells), occupied_target=int(occupied_target), seed=int(seed),
            terrain=terrain, enclosure_strength=float(strength), target_size=int(target_size),
        )
        with st.spinner("Running..."):
            first = run_comparison(base, selected)
            batch = (
                run_batch(range(int(seed), int(seed) + int(repetitions)), selected, base)
                if repetitions > 1 else None
            )
        st.session_state["morphic"] = {"first": first, "batch": batch}

state = st.session_state.get("morphic")
if not state:
    st.info("Choose settings in the sidebar and press **Run experiment**.")
    st.stop()

first, batch = state["first"], state["batch"]
largest = max(len(r.result.occupied) for r in first.values())
step = st.slider("Replay step (cells occupied)", 0, largest, largest)

st.subheader("Morphology (identical carrier geometry and seed across modes)")
show(fig_comparison(first, step=step, show_open_graph=show_graph))
st.caption(legend_text() + " Colours are morphological categories, not space-syntax values.")

st.subheader("Measurements (final configuration)")
rows = []
for mode, run_ in first.items():
    rows.append({"mode": MODE_LABELS[mode], "experiment_id": run_.experiment_id,
                 "termination": run_.result.termination, **run_.metrics})
st.dataframe(rows, width="stretch")
st.caption(
    "Cycles are the cyclomatic number of the OCCUPIED adjacency graph; open connectivity is the "
    "degree in the OPEN-space accessibility graph. Missing values are empty, not zero."
)

for mode, run_ in first.items():
    with st.expander(f"Transformation log - {MODE_LABELS[mode]}"):
        st.dataframe([t.to_dict() for t in run_.result.transformations], width="stretch")

if batch:
    st.subheader(f"Repetitions: {repetitions} seeds")
    st.dataframe(summarise(batch), width="stretch")
    show(fig_distributions(batch))
