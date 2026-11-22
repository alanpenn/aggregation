"""Export comparable generator-selector rows without rewriting stage records."""

import csv
from collections import Counter
from datetime import datetime
from fractions import Fraction
from itertools import combinations
from math import hypot
from statistics import fmean, median, pstdev


def statistics(values):
    if not values:
        return dict.fromkeys(("mean", "min", "max", "stddev", "median"))
    return {"mean": fmean(values), "min": min(values), "max": max(values),
            "stddev": pstdev(values), "median": median(values)}


def _length(line):
    return hypot(*(float(Fraction(b) - Fraction(a))
                   for a, b in zip(line["start"], line["end"], strict=True)))


def _timing(record):
    if not record or not record["finished_at"]:
        return None
    return (datetime.fromisoformat(record["finished_at"])
            - datetime.fromisoformat(record["started_at"])).total_seconds()


def _projected_v2_failures(audit, topology):
    """Recover the v2 screening totals from its saved domain and accepted supports."""
    from shapely import from_wkb

    from .axial_generator import _parts
    from .exact_enumeration import _supports
    from .experimental_projected_faces import block_rings

    rings = list(block_rings(_parts(from_wkb(topology["occupied_wkb"]))))
    corners = [corner for ring in rings for corner in ring]
    result = Counter(coincident_corners=0, unsupported_convex_pairs=0, unsupported_concave_pairs=0)
    eligible = Counter({
        "same-block-tangent": 0, "projected-face-mutual-tangent": 0,
        "concave-endpoint": 0, "convex-to-convex-face": 0,
    })
    for left, right in combinations(corners, 2):
        if left.point == right.point:
            result["coincident_corners"] += 1
            continue
        supported = (
            (not left.convex or _supports(left, right.point))
            and (not right.convex or _supports(right, left.point))
        )
        if left.convex and right.convex:
            if supported:
                eligible["same-block-tangent" if left.reference.building_id == right.reference.building_id
                         else "projected-face-mutual-tangent"] += 1
            else:
                result["unsupported_convex_pairs"] += 1
        elif supported:
            eligible["concave-endpoint"] += 1
        else:
            result["unsupported_concave_pairs"] += 1
    eligible["convex-to-convex-face"] = sum(
        left.convex and right.convex
        for ring in rings for left, right in zip(ring, ring[1:] + ring[:1])
    )
    result["face_with_nonconvex_endpoint"] = sum(map(len, rings)) - eligible["convex-to-convex-face"]
    if sum(eligible[k] for k in ("same-block-tangent", "projected-face-mutual-tangent")) != audit["mutual_sector_pairs"]:
        raise ValueError("Projected screening totals differ from the saved v2 inventory.")
    for key, count in eligible.items():
        rejected = count - audit["supports_by_source"].get(key, 0)
        if rejected < 0:
            raise ValueError("Recorded projected acceptances exceed the v2 screening totals.")
        result[f"{key}:clearance"] = rejected
    return dict(result)


def _pool_failures(candidate, record, topology):
    audit = candidate.get("audit", {})
    counts = audit.get("counts")
    if counts is not None:
        return {key: count for key, count in counts.items()
                if key.endswith((":occupied-interior", ":domain-or-union", ":not-supporting"))}
    if ("mutual_sector_pairs" in audit
            and record.get("method", {}).get("identity") ==
                "voronoi_app.batch_methods:projected_face_pool"
            and record["method"]["version"] == "2"):
        return _projected_v2_failures(audit, topology)
    return None


def comparison_rows(store, cases):
    """Resolve saved benchmark/pilot cases to flat, explicit comparison rows."""
    from .batch import METHODS
    from .batch_store import STAGES

    cache = {}

    def get(record_id):
        if record_id not in cache:
            cache[record_id] = store.load(record_id) if record_id else ({}, {}, None)
        record, output, _ = cache[record_id]
        return record, output or {}

    references = {
        case["records"].get("candidates"): get(case["records"].get("validation"))[1]
        for case in cases if case["selector"] == "full-pool"
    }
    certificates = {}
    for case in cases:
        ids = case["records"]
        output = get(ids.get("validation"))[1]
        topology = output.get("topology", {})
        if (topology.get("circulation_constraints_satisfied")
                and not topology.get("lines_crossing_effective_occupied_space")):
            summary = output["summary"]
            covers_domain = (
                summary["covered_regions"] == summary["regions"] and summary["components"] == 1
            )
            candidate_id = ids.get("candidates")
            if candidate_id not in certificates or covers_domain:
                certificates[candidate_id] = (ids.get("selection"), covers_domain)
    screening = {}
    for case in cases:
        ids = case["records"]
        rows = {stage: get(ids.get(stage)) for stage in STAGES}
        settlement = rows["settlement"][1]
        candidate = rows["candidates"][1]
        selected = rows["selection"][1]
        measured = rows["measures"][1]
        validated = rows["validation"][1]
        summary = validated.get("summary", {})
        geometry = validated.get("topology", {})
        full = references.get(ids.get("candidates"), {})
        pool = candidate.get("pool_summary", {})
        candidate_id = ids.get("candidates")
        if candidate_id not in screening:
            screening[candidate_id] = _pool_failures(candidate, rows["candidates"][0], rows["topology"][1])
        screened = screening[candidate_id]
        clearance_rejections = candidate.get("geometric_certification", {}).get("clearance_rejections")
        audit = candidate.get("audit", {})
        merged_supports = audit.get("counts", {}).get("deduplicated-supports")
        if "supports_by_source" in audit and "candidates" in pool:
            merged_supports = sum(audit["supports_by_source"].values()) - pool["candidates"]
        pool_rank = full.get("summary", {}).get("winding_rank")
        domain = rows["topology"][1].get("topology", {})
        required_rank = domain.get("required_circulation_rank")
        feasibility = "unproven" if pool else "unavailable"
        if pool.get("uncovered_visibility_regions"):
            feasibility = "impossible-full-visibility-coverage"
        witness_map, covers_domain = certificates.get(candidate_id, (None, False))
        circulation = "certified" if witness_map else "unproven"
        if covers_domain:
            feasibility = "certified"
        methods = {}
        for label, stage in (("generator", "candidates"), ("selector", "selection")):
            method = rows[stage][0].get("method", {})
            spec = METHODS.get(case[label])
            methods.update({
                label: case[label],
                f"{label}_identity": method.get("identity") or
                    (f"voronoi_app.batch_methods:{spec.function}" if spec else None),
                f"{label}_version": method.get("version") or (spec.version if spec else None),
            })
        problems = []
        status = "incomplete"
        for stage, (record, output) in rows.items():
            if not record:
                continue
            if record["status"] != "successful":
                problems.append({"stage": stage, "status": record["status"],
                                 "error": record.get("error", {}).get("message"),
                                 "checks": output.get("failed_checks"),
                                 "geometric_certification": output.get("geometric_certification")})
        if problems:
            status = problems[0]["status"]
        elif rows["validation"][0].get("status") == "successful":
            status = "successful"
        lengths = [_length(line) for line in selected.get("lines", [])]
        axial = measured.get("axial_by_line", {})
        entrances = measured.get("entrance_depth", {})
        raw_depth = [value for value in measured.get("entrance_pair_depths", []) if value is not None]
        yield {
            "case": case.get("case"),
            **{f"{stage}_id": ids.get(stage) for stage in STAGES},
            "settlement_configuration": settlement.get("configuration", case.get("configuration")),
            **methods, "status": status, "failure_reasons": problems,
            **{f"{stage}_status": record.get("status") for stage, (record, _) in rows.items()},
            "validation_failed_checks": validated.get("failed_checks"),
            "candidate_count": pool.get("candidates"),
            "exact_clearance_passes": pool.get("exact_clearance_passes"),
            "candidate_clearance_rejection_ids": clearance_rejections,
            "candidate_clearance_rejected_count": len(clearance_rejections) if clearance_rejections is not None else None,
            "candidate_duplicate_intervals": candidate.get("geometric_certification", {}).get("duplicate_intervals"),
            "candidate_merged_support_count": merged_supports,
            "candidate_screening_rejections": screened,
            "candidate_screened_out_total": sum(screened.values()) if screened is not None else None,
            "intersecting_candidate_pairs": pool.get("intersecting_candidate_pairs"),
            "candidate_components": pool.get("components"),
            "candidate_visibility_regions": pool.get("visibility_regions_covered"),
            "candidate_interior_regions": pool.get("interior_regions_covered"),
            "candidate_regions": pool.get("regions"),
            "pool_circulation": circulation,
            "pool_circulation_witness_map_id": witness_map,
            "pool_feasibility": feasibility,
            "pool_winding_rank": pool_rank,
            "selected_lines": len(selected["line_ids"]) if "line_ids" in selected else None,
            "selected_length_total": sum(lengths) if "lines" in selected else None,
            "axial_components": summary.get("components"),
            "selected_regions_covered": summary.get("covered_regions"),
            "selected_clearance_rejection_ids": geometry.get("lines_crossing_effective_occupied_space"),
            "required_winding_rank": required_rank,
            "required_holes": len(domain["internal_circulation_holes"])
                              if "internal_circulation_holes" in domain else None,
            "selected_winding_rank": summary.get("winding_rank"),
            "entrances_attached": entrances.get("attached_entrances"),
            "entrance_pairs": entrances.get("pairs"),
            "unreachable_entrance_pairs": entrances.get("unreachable"),
            "excluded_entrances": len(measured["excluded_entrances"]) if "excluded_entrances" in measured else None,
            "raw_measures_path": f"records/{ids['measures']}/output.json" if measured else None,
            **{f"{stage}_seconds": _timing(record) for stage, (record, _) in rows.items()},
            **{f"line_length_{k}": v for k, v in statistics(lengths).items()},
            **{f"axial_depth_{k}": v for k, v in statistics([entry["mean_depth"] for entry in axial.values()]).items()},
            **{f"entrance_depth_{k}": v for k, v in statistics(raw_depth).items()},
        }


def export_rows(store, cases, destination):
    from .batch_store import encode

    rows = list(comparison_rows(store, cases))
    if not rows:
        raise ValueError("There are no comparison cases to export.")
    if destination.suffix == ".json":
        with destination.open("xb") as stream:
            stream.write(encode(rows) + b"\n")
    elif destination.suffix == ".csv":
        with destination.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({
                key: (encode(value).decode() if value is None or isinstance(value, (dict, list)) else value)
                for key, value in row.items()
            } for row in rows)
    else:
        raise ValueError("Export destination must end in .json or .csv.")
    return len(rows)
