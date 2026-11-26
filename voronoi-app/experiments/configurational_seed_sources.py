"""Verify the supplementary archived strict-backward cohort."""

from hashlib import sha256
import json
from pathlib import Path

from shapely import from_wkb

from experiments.configurational_sources import BENCHMARK, MIGRATION, MATCH_KEYS, Case
from experiments.flat40_configurational import check, exact_points


def load_strict_cohort(data, expected_migration):
    """Recover the historical strict-backward cohort from the shared manifest."""
    raw = (data / MIGRATION).read_bytes()
    check(sha256(raw).hexdigest() == expected_migration, "Migration digest mismatch")
    manifest = json.loads(raw)
    verified = {}

    def verify(relative, *, decode=False, expected=None):
        relative = str(relative)
        payload = (data / relative).read_bytes()
        observed = sha256(payload).hexdigest()
        check(observed == manifest[relative] and (expected is None or expected == observed),
              f"Strict cohort hash mismatch: {relative}")
        verified[relative] = observed
        return json.loads(payload) if decode else None

    entries = verify(BENCHMARK / "inputs.json", decode=True)
    cases = {}
    missing = {}
    for name, row in entries.items():
        root = Path(row["root"]).relative_to("diagnostics")
        journal_path = root / "cases" / f"{name}.json"
        required = [str(journal_path)] + [
            str(root / "records" / stage["record"] / filename)
            for stage in row["records"].values() for filename in ("record.json", "output.json")]
        unavailable = [path for path in required if path not in manifest or not (data / path).is_file()]
        if unavailable:
            missing[name] = unavailable
            continue
        journal = verify(journal_path, decode=True, expected=row["journal_sha256"])
        check(journal["stages"] == row["records"], f"Strict cohort journal differs: {name}")
        saved = {}
        for key, stage in row["records"].items():
            folder = root / "records" / stage["record"]
            record = verify(folder / "record.json", decode=True)
            stage_type = "validation" if key in {"analysis", "physical_screen"} else key
            check(record["id"] == stage["record"] and record["stage"] == stage_type, f"Stage metadata differs: {name}/{key}")
            output = verify(folder / "output.json", decode=key in {"settlement", "topology", "candidates", "analysis"},
                            expected=record["output_sha256"])
            if output is not None:
                saved[key] = output
        archived = saved["analysis"]["maps"]["strict_backward"]
        published = row["published_strict"]
        certificate = archived["constraints"]
        ids = archived["line_ids"]
        check(ids == published["result"]["line_ids"] and certificate == published["result"]["constraints"],
              f"Strict-backward publication and archive differ: {name}")
        check(certificate["valid"] and certificate["components"] == 1
              and not any(certificate[k] for k in ("clearance_rejections", "missing_regions", "missing_rings", "unattached_doors"))
              and certificate["rank"] == certificate["required_rank"], f"Strict-backward certificate incomplete: {name}")
        pool = saved["candidates"]["pool"]["candidates"]
        by_id = {entry["id"]: entry for entry in published["selected_intervals"]}
        check(set(by_id) == set(ids), f"Published strict-backward geometry differs: {name}")
        for i in ids:
            check(pool[i]["id"] == i and all(pool[i][attr] == by_id[i][attr] for attr in ("start", "end")),
                  f"Strict-backward interval differs: {name}/{i}")
        config = saved["settlement"]["configuration"]
        check(all(config[k] == row["configuration"][k] for k in (*MATCH_KEYS, "terrain_provider", "terrain_params")),
              f"Strict cohort configuration differs: {name}")
        settlement = saved["settlement"]
        topology = saved["topology"]
        meta = {"terrain": config["terrain_provider"], "seed": config["seed"], "settings": config,
                "building_count": len(settlement["building_labels"]),
                "study_boundary": [0, 0, config["canvas_size"], config["canvas_size"]],
                "settlement_source": str(root / "records" / row["records"]["settlement"]["record"] / "output.json"),
                "certified_candidates": len(pool), "archived_regional_representation": len(saved["candidates"]["regions_wkb"]),
                "winding_rank": certificate["rank"], "line_count": len(ids),
                "archived_intersection_count": archived["intersections"],
                "source_method": "archived strict_backward"}
        meta["settlement_sha256"] = verified[meta["settlement_source"]]
        lines = {i: exact_points((pool[i]["start"], pool[i]["end"])) for i in sorted(ids)}
        case = Case(name, settlement, topology, lines, set(), meta)
        meta["accessible_area"] = case.accessible.area
        meta["occupied_area"] = from_wkb(topology["occupied_wkb"]).area
        cases[name] = case
    return cases, missing, dict(sorted(verified.items()))
