"""Streamlit controls for the active convex-space representation."""
import json

import streamlit as st

from experiments.live_maximal_cover import advance_cover, read_checkpoint
from experiments.flat40_exchange_atlas import Atlas, page
from experiments.flat40_maximal_convex_axial import exact_incidence, variant
from experiments.flat40_face_extension import points
from experiments.near_collinear_consolidation import certificate, verified_study
from voronoi_app.research_data import data_root


def cover_controls(snapshot, root):
    directory = root / "diagnostics" / "live-maximal-cover"
    try:
        record = read_checkpoint(snapshot, directory)
        if not record or not record["enumeration_complete"]:
            st.caption("Cover construction runs in local, resumable batches for this settlement.")
            budget = st.number_input("Search prefixes per hand", min_value=1, max_value=10000,
                                     value=1000, key="maximal_cover_budget")
            if st.button("Construct or resume maximal cover", key="advance_maximal_cover"):
                with st.spinner("Exploring both handed searches and saving a checkpoint"):
                    record = advance_cover(snapshot, directory, budget)
        if not record:
            st.info("Construct the maximal cover before selecting axial lines.")
            return None
        complete = record["enumeration_complete"]
        st.caption("Enumeration complete" if complete else "Enumeration checkpoint · incomplete")
        for hand, row in zip(("Right hand", "Left hand"), record["progress"], strict=True):
            st.caption(f'{hand} · {row["origin"]:,}/{row["total_origins"]:,} starts exhausted · '
                       f'{row["popped"]:,} prefixes explored')
        st.write(f'{record["distinct"]:,} distinct closed polygons · '
                 f'{record["rejected_transitions"]:,} rejected transitions')
        if complete:
            st.write(f'{len(record["regions"]):,} globally maximal · {record["unresolved"]:,} unresolved · '
                     f'{record["nonmaximal"]:,} non-maximal · {record["coverage"]:.6f}% exact coverage · '
                     f'maximum overlap {record["maximum_overlap"]}')
            if not record["ready"]:
                st.error("The exhausted search did not certify a complete maximal cover for this settlement.")
            else:
                return record
    except (OSError, ValueError, RuntimeError, MemoryError) as error:
        st.error(f"Maximal cover unavailable: {error}")
    return None


def saved_flat40(root, display_figure):
    st.subheader("Saved Flat 40 · maximal-cover C-H")
    st.caption("Archived deterministic C-H configuration · corrected Flat 40 reference")
    if st.button("Load and verify saved Flat 40", key="load_maximal_flat40"):
        try:
            with st.spinner("Verifying archived inputs and structural certificate"):
                st.session_state["verified_maximal_flat40"] = load_flat40(root)
        except (OSError, ValueError, RuntimeError) as error:
            st.error(f"Saved Flat 40 is unavailable: {error}. Check AGGREGATION_DATA_ROOT and the handover.")
    if "verified_maximal_flat40" in st.session_state:
        data, atlas = st.session_state["verified_maximal_flat40"]
        st.success("Saved C-H passed independent exact structural validation.")
        st.write("596 globally maximal polygons · 100% exact accessible-space coverage · enumeration complete · "
                 "0 unresolved polygons · maximum overlap 39")
        st.write(f'1,534 certified candidates · {len(data["ids"])} selected · '
                 f'{data["coverage"]}/596 regions · {data["doorways"]}/100 doorways · '
                 f'{data["components"]} component · winding {data["winding"]["independent_circulation_rank"]}/24')
        fig, (ax,) = page("Flat 40 · certified C-H", "31 archived selected lines")
        atlas.base(ax)
        for i in data["ids"]:
            atlas.line(ax, i, "#236e9e")
        display_figure(fig, alt="Saved Flat 40 maximal-cover C-H axial map")


def load_flat40(root):
    from experiments.verify_flat40_transfer import verify_records

    verify_records()
    manifest = data_root(root / "diagnostics") / "migration-sha256-2026-11-24.json"
    study, ch, _, provenance = verified_study(manifest)
    directory = root / "diagnostics" / "strict-generalisation" / "flat40-maximal-convex-axial-selection-1"
    read = lambda name: json.loads((directory / f"{name}.json").read_bytes())
    if read("provenance")["lineage"] != provenance["lineage"]:
        raise ValueError("Saved maximal-cover selection has a different Flat 40 lineage.")
    saved = read("comparison")["maps"]["B-C-H"]["certificate"]
    matrix = read("incidence-B")
    registry = json.loads((root / "research" / "flat40" / "maximal-regions.json").read_bytes())["regions"]
    exact = exact_incidence(study.lines, {key: points(registry[key]) for key in matrix["region_order"]})
    if exact["by_region"] != matrix["by_region"]:
        raise ValueError("Saved Flat 40 incidence differs from the exact polygon registry.")
    result = certificate(variant(study, matrix), set(read("B-C-H")["ids"]))
    if result != saved or (len(study.lines), len(result["ids"]), result["coverage"],
                           result["doorways"], result["components"]) != (1534, 31, 596, 100, 1):
        raise ValueError("Saved Flat 40 certificate did not reproduce.")
    return result, Atlas(study, ch)
