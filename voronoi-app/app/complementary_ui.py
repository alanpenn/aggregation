"""Session-local Streamlit controls for certified complementary maps."""

from hashlib import sha256
from pathlib import Path
from time import monotonic

import streamlit as st
from shapely import from_wkb

from voronoi_app.complementary_axial import ComplementaryStudy, settlement_key
from voronoi_app.render import fig_complementary_axial_map

METHOD = "Complementary tangents + structural reduction"
STATE = "complementary_axial"
UI_TIME_LIMIT_SECONDS = 900
STAGES = ("Certified candidate generation", "Convex-vertex indexing", "Complementary tangent selection",
          "Structural completion", "Dynamic structural reduction", "Geometric exchanges",
          "Independent final validation")
STAGE_LABELS = {"full": "Full certified candidate pool", "complementary": "Complementary-tangent selection",
                "completed": "Structurally completed pool", "reduced": "Reduced axial map",
                "exchanged": "Exchange-improved map"}
COLORS = {"Certified candidate": "#54768a", "Complementary tangent": "#226691", "Coverage addition": "#bd662c",
          "Doorway addition": "#917026", "Connectivity addition": "#29826c",
          "Winding addition": "#7646a1", "Exchange addition": "#ae415d"}


def current_version():
    root = Path(__file__).resolve().parents[1] / "src" / "voronoi_app"
    digest = sha256()
    for path in sorted(root.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def session_for(snapshot, cover=None):
    key = settlement_key(snapshot, current_version() + (cover["key"] if cover else ""))
    saved = st.session_state.get(STATE)
    if not saved or saved["key"] != key:
        saved = {"key": key, "reductions": {}, "exchanges": {}, "movement": {}, "reference_maps": {}, "last": None}
        st.session_state[STATE] = saved
    return saved


def progress_for(status, stages):
    started = monotonic()
    bar = status.progress(0)
    detail = status.empty()
    step = 0

    def progress(stage, message=None):
        nonlocal step
        elapsed = round(monotonic() - started)
        if elapsed >= UI_TIME_LIMIT_SECONDS:
            raise TimeoutError("The interactive time budget was reached. Try a smaller grid or fewer dyads.")
        if stage in stages:
            step = max(step, stages.index(stage) + 1)
        bar.progress(step / len(stages), text=f"{stage} · {elapsed}s")
        if message:
            detail.caption(message)
    return progress


def generate(saved, snapshot, order, use_exchanges, progress, cover=None):
    if "study" not in saved:
        started = monotonic()
        saved["study"] = ComplementaryStudy.from_settlement(
            snapshot, progress, maximal_regions=cover["regions"] if cover else None)
        saved["pool_seconds"] = monotonic() - started
    study = saved["study"]
    if "prepared" not in saved:
        saved["prepared"] = study.prepare(progress)
    prepared = saved["prepared"]
    if prepared.failure:
        return prepared.failure
    if order not in saved["reductions"]:
        saved["reductions"][order] = study.reduce_prepared(prepared, order, progress)
    result = saved["reductions"][order]
    if result.certified and use_exchanges:
        if order not in saved["exchanges"]:
            saved["exchanges"][order] = study.improve(result, order, progress)
        result = saved["exchanges"][order]
    saved["last"] = (order, use_exchanges)
    return result.failure


def category_map(study, prepared, exchanged):
    categories = {i: ("Complementary tangent",) for i in prepared.stages["complementary"]}
    chosen = set(categories)
    for step in prepared.repairs:
        stage = step["stage"]
        for i in step["add"]:
            names = []
            if stage in ("coverage", "singleton", "strict-region"):
                if any(i in members and chosen.isdisjoint(members) for members in study.regions.values()):
                    names.append("Coverage addition")
                if any(i in members and chosen.isdisjoint(members) for members in study.doors):
                    names.append("Doorway addition")
            if not names:
                names.append({"connectivity": "Connectivity addition", "circulation": "Winding addition"}
                             .get(stage, "Coverage addition"))
            categories[i] = tuple(names)
            chosen.add(i)
    if exchanged:
        for attempt in exchanged.exchanges:
            if attempt["accepted"]:
                for i in attempt["accepted"]["added"]:
                    categories[i] = ("Exchange addition",)
    return categories


def summary_table(summaries):
    return [{
        "Stage": STAGE_LABELS[stage],
        "Lines": row["count"],
        "Length": round(row["length"], 2),
        "Strict convex coverage": f'{row["regions"]}/{row["required_regions"]}',
        "Doorway access": f'{row["doorways"]}/{row["required_doorways"]}',
        "Components": row["components"],
        "Winding rank": f'{row["rank"]}/{row["required_rank"]}',
        "Exact clearance": f'{row["clear"]}/{row["count"]}',
    } for stage, row in summaries.items()]


def render_movement(saved, study, result):
    if not result or not result.certified:
        return
    st.subheader("Certified doorway movement")
    if len(study.doors) < 2:
        st.info("At least two eligible doorways are required for movement analysis.")
        return
    picks = {"final": "Current complementary map", "full": "Full certified pool",
             "greedy": "Exact greedy comparator"}
    target = st.selectbox("Movement analysis map", list(picks), format_func=picks.get,
                          key="complementary_route_target")
    if st.button("Run angular and metric doorway analysis", key="complementary_movement"):
        try:
            with st.status("Calculating certified doorway routes", expanded=True) as status:
                selection = result
                if target != "final":
                    references = saved["reference_maps"]
                    if target not in references:
                        references[target] = study.reference_map(target)
                    selection = references[target]
                if not selection.certified:
                    raise ValueError(selection.failure)
                if selection.ids not in saved["movement"]:
                    route = study.movement(selection, progress_for(status, ("Certified doorway movement",)))
                    if not route["valid"]:
                        raise ValueError("At least one eligible doorway pair is unreachable.")
                    saved["movement"][selection.ids] = route
                status.update(label="Certified doorway routes complete", state="complete")
        except MemoryError:
            st.error("Doorway movement exceeded available memory. Try fewer grid cells.")
        except (ValueError, RuntimeError, TimeoutError) as error:
            st.error(f"Movement analysis failed: {error}")
    comparisons = []
    selections = [(picks[key], entry) for key, entry in saved["reference_maps"].items()]
    for mode in ("sheaf", "shortest"):
        for phase, bucket in (("Reduced", saved["reductions"]), ("Exchanged", saved["exchanges"])):
            if mode in bucket:
                selections.append((f"{mode.title()} · {phase}", bucket[mode]))
    for name, selection in selections:
        if selection.ids not in saved["movement"]:
            continue
        route = saved["movement"][selection.ids]
        comparisons.append({"Map": name, "Lines": len(selection.ids),
                            "Doorway pairs": len(route["pairs"]), "Angular mean": route["angular"]["mean"],
                            "Angular p95": route["angular"]["p95"], "Metric mean": route["metric"]["mean"],
                            "Metric p95": route["metric"]["p95"]})
    if comparisons:
        st.dataframe(comparisons, hide_index=True, alt="Certified movement comparisons for this settlement")


def display_complementary(result, snapshot, order, use_exchanges, display_figure, cover=None):
    st.subheader(METHOD)
    saved = session_for(snapshot, cover)
    st.caption(f"Current settlement seed {result.pipeline.seed}. Fresh exact enumeration can take several minutes.")
    if st.button("Generate complementary axial map", type="primary", key="generate_complementary"):
        error = None
        with st.status("Preparing complementary axial map", expanded=True) as status:
            progress = progress_for(status, STAGES)
            try:
                error = generate(saved, snapshot, order, use_exchanges, progress, cover)
            except MemoryError:
                error = "This settlement exceeded available memory. Try a smaller grid or fewer dyads."
            except (ValueError, RuntimeError, TimeoutError) as problem:
                error = str(problem)
            status.update(label="Complementary computation incomplete" if error else "Complementary map ready",
                          state="error" if error else "complete", expanded=bool(error))
        saved["error"] = error
    if saved.get("error"):
        st.error(saved["error"])
    if "prepared" not in saved:
        return

    study, prepared = saved["study"], saved["prepared"]
    selected_order, selected_exchange = saved["last"] or (order, use_exchanges)
    if saved["last"] and saved["last"] != (order, use_exchanges):
        st.info("Showing the last generated settings. Generate the map to apply the new order or exchange setting.")
    reduced = saved["reductions"].get(selected_order)
    exchanged = saved["exchanges"].get(selected_order) if selected_exchange else None
    final = exchanged or reduced
    stages, summaries = dict(prepared.stages), dict(prepared.summaries)
    for key, selection in (("reduced", reduced), ("exchanged", exchanged)):
        if selection:
            stages[key], summaries[key] = selection.ids, selection.summary
    if final and final.certified:
        st.success("The final map passed independent exact structural validation.")
        removed = len(prepared.stages["completed"]) - len(reduced.ids)
        moves = sum(x["accepted"] is not None for x in final.exchanges)
        added = sum(len(x["accepted"]["added"]) for x in final.exchanges if x["accepted"])
        st.caption(f"{1 - len(final.ids) / len(study.lines):.1%} reduction from the full pool · "
                   f"{removed} deletions before exchanges · {moves} accepted exchanges · {added} added by exchanges · "
                   f"{len(final.ids) - len(reduced.ids):+d} lines after exchanges · "
                   f"{prepared.seconds + reduced.seconds + (exchanged.seconds if exchanged else 0):.1f}s selection · "
                   f"{reduced.winding_checks + (exchanged.winding_checks if exchanged else 0):,} dynamic winding checks")
    elif final or prepared.failure:
        st.warning("Diagnostic geometry is available. The final selection is uncertified.")
    st.dataframe(summary_table(summaries), hide_index=True, alt="Exact axial stage statistics")
    st.caption(f"Certified candidate generation and indexing: {saved.get('pool_seconds', 0):.1f}s.")
    if prepared.repairs:
        with st.expander("Structural repair additions"):
            st.dataframe(prepared.repairs, hide_index=True, alt="Certified repair candidate IDs by structural requirement")
    counts = [len(v["supported"]) for v in prepared.vertices]
    unindexed = set(range(len(study.lines))) - {i for v in prepared.vertices for i in v["supported"]}
    st.caption(f"{len(counts)} convex vertices · {sum(n < 2 for n in counts)} with fewer than two supported tangents · "
               f"{len(unindexed)} unindexed candidates retained provisionally at preselection.")
    excluded = study.inputs["analysis"].get("excluded_doorways", [])
    if excluded:
        st.caption(f"{len(excluded)} doorways were excluded from exact doorway incidence.")

    stage = st.selectbox("Axial map stage", list(stages), index=len(stages)-1,
                         format_func=STAGE_LABELS.get, key="complementary_stage")
    labels = st.checkbox("Show original building numbers", value=True, key="complementary_building_numbers")
    vertices = st.checkbox("Show convex supporting vertices", key="complementary_vertices")
    regions = st.checkbox("Show strict convex regions", key="complementary_regions")
    doors = st.checkbox("Show eligible doorways", key="complementary_doors")
    categories = category_map(study, prepared, exchanged if stage == "exchanged" else None)
    visible = st.multiselect("Visible line categories", list(COLORS), default=list(COLORS),
                             key="complementary_categories")
    groups = {name: [] for name in visible}
    for i in stages[stage]:
        names = ("Certified candidate",) if stage == "full" else categories.get(i, ("Certified candidate",))
        name = next((category for category in names if category in groups), None)
        if name is not None:
            groups[name].append(study.lines[i])
    displayed = st.selectbox("Inspect a candidate ID", [None, *stages[stage]],
                             format_func=lambda i: "Choose a candidate" if i is None else str(i),
                             key=f"complementary_inspect_{stage}")
    if displayed is not None:
        candidate = study.lines[displayed]
        measure = study.measures[displayed]
        supports = [v for v in prepared.vertices if displayed in v["supported"]]
        st.write({"Candidate ID": displayed, "Length": round(candidate.length, 4),
                  "Exact endpoints": [list(map(str, p)) for p in (candidate.start, candidate.end)],
                  "Supporting vertices": [{"vertex": v["id"], "point": v["point"], "buildings": v["members"]}
                                          for v in supports],
                  "Transverse connections": len(measure["transverse"]),
                  "Strict convex regions": measure["regions"],
                  "Selected at vertices": sorted(prepared.anchors[displayed]),
                  "Stage provenance": categories.get(displayed, ("Certified candidate",))})
    outlines = ([from_wkb(value) for value in study.inputs["candidates"]["regions_wkb"].values()]
                if regions else ())
    building_labels = {int(i): n for i, n in snapshot["building_labels"].items()}
    display_figure(fig_complementary_axial_map(
        study.polygons, building_labels, study.inputs["topology"]["topology"]["excluded_open_cells"],
        groups, COLORS, show_labels=labels, vertices=prepared.vertices if vertices else (),
        regions=outlines, doorways=study.inputs["analysis"]["incidence"]["doorways"] if doors else (),
        highlighted=study.lines[displayed] if displayed is not None else None,
    ), alt=f"{STAGE_LABELS[stage]} on numbered settlement geometry")
    render_movement(saved, study, final)
