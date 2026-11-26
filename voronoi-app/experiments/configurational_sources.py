"""Read the verified cohort without regenerating any settlement."""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from shapely import from_wkb

from experiments.flat40_configurational import check, exact_points, read

BENCHMARK = Path("strict-generalisation/cross-terrain-constructive-1")
MIGRATION = "migration-sha256-2026-11-24.json"
MATCH_KEYS = ("seed", "aggregation_strategy", "aggregation_params", "canvas_size",
              "grid_generator", "grid_params", "urban_form")


@dataclass
class Case:
    name: str
    settlement: dict
    topology: dict
    lines: dict
    edges: set
    inventory: dict

    @property
    def buildings(self):
        return [from_wkb(self.settlement["polygons_wkb"][key]) for key in self.settlement["building_labels"]]

    @property
    def accessible(self):
        return from_wkb(self.topology["accessible_wkb"])


def load_cohort(data, expected_migration):
    raw = (data / MIGRATION).read_bytes()
    check(sha256(raw).hexdigest() == expected_migration, "Migration inventory differs from frozen Flat 40 provenance")
    manifest = json.loads(raw)
    verified = {}

    def load(relative, expected=None):
        relative = str(relative)
        raw = (data / relative).read_bytes()
        observed = sha256(raw).hexdigest()
        check(observed == manifest[relative] and (expected is None or observed == expected),
              f"Source hash mismatch: {relative}")
        verified[relative] = observed
        return json.loads(raw)

    inputs = load(BENCHMARK / "inputs.json")
    lineage = load(BENCHMARK / "lineage.json")
    available = {}
    inventory = {}
    for name, row in sorted(inputs.items()):
        config = row["configuration"]
        record_root = Path(row["root"]).relative_to("diagnostics")
        missing = sorted(row["missing"])
        journal = record_root / "cases" / f"{name}.json"
        check(row["journal_sha256"] == lineage[name]["journal_sha256"], f"Journal lineage mismatch {name}")
        item = {"terrain": config["terrain_provider"], "seed": config["seed"], "settings": config,
                "source_journal": str(journal), "journal_sha256": row["journal_sha256"],
                "missing_immutable_files": missing, "study_boundary": None, "building_count": None,
                "accessible_area": None, "occupied_area": None, "settlement_source": None,
                "settlement_sha256": None, "exact_axial_intersections": False,
                "maximal_convex": 596 if name == "flat-40" else None,
                "archived_regional_representation": None, "certified_candidates": None, "archived_CH_lines": None,
                "status": "no archived C-H inventory in this benchmark" if missing else "verified C-H"}
        inventory[name] = item
        if missing:
            item["missing_paths_now_present_unverified"] = [
                path for path in missing if (data / Path(path).relative_to("diagnostics")).is_file()]
            continue
        for path, digest in lineage[name]["verified_members"].items():
            relative = Path(path).relative_to("diagnostics")
            check(manifest[str(relative)] == digest, f"Immutable lineage digest differs: {relative}")
            actual = sha256((data / relative).read_bytes()).hexdigest()
            check(actual == digest, f"Immutable record hash mismatch: {relative}")
            verified[str(relative)] = actual
        journal_record = load(journal, row["journal_sha256"])
        check(journal_record["stages"] == row["records"], f"Stage IDs differ: {name}")

        def stage(key):
            path = record_root / "records" / row["records"][key]["record"] / "output.json"
            return path, read(data / path)

        settlement_path, settlement = stage("settlement")
        _, topology = stage("topology")
        _, candidates = stage("candidates")
        struct = load(BENCHMARK / name / "structural.json")
        selected = load(BENCHMARK / name / "C-H.json")
        check(selected["ids"] == struct["methods"]["C-H"]["ids"] and selected["status"] == "independent_success",
              f"Archived C-H map differs: {name}")
        winding = selected["winding"]
        ids = selected["ids"]
        check(len(ids) == len(set(ids)) == winding["effective_clearance_line_count"]
              and winding["circulation_constraints_satisfied"]
              and winding["independent_circulation_rank"] == winding["required_circulation_rank"],
              f"Archived C-H certification differs: {name}")
        check(all(settlement["configuration"][k] == config[k] for k in (*MATCH_KEYS, "terrain_provider", "terrain_params")),
              f"Settlement settings differ: {name}")
        frozen = load(Path("strict-generalisation/constructive-axial-3") / name / "geometry.json")["candidates"]
        pool = candidates["pool"]["candidates"]
        check(len(pool) == len(frozen) == struct["full_count"], f"Frozen pool differs: {name}")
        chosen = set(ids)
        edges = {tuple(sorted((i, j))) for i in chosen for j in frozen[i]["intersections"] if j in chosen}
        check(len(edges) == selected["metrics"]["intersection_pairs"], f"Archived edge total differs: {name}")
        check(all(frozen[i]["id"] == pool[i]["id"] == i for i in range(len(pool))), f"IDs differ: {name}")
        check(len({r for i in chosen for r in frozen[i]["regions"]}) == struct["regions"]
              and len({d for i in chosen for d in frozen[i]["doorways"]}) == struct["doorways"],
              f"Archived coverage or doorway incidence differs: {name}")
        lines = {i: exact_points((pool[i]["start"], pool[i]["end"])) for i in sorted(chosen)}
        case = Case(name, settlement, topology, lines, edges, item)
        available[name] = case
        item.update(building_count=len(settlement["building_labels"]), accessible_area=case.accessible.area,
                    occupied_area=from_wkb(topology["occupied_wkb"]).area, accessible_bounds=case.accessible.bounds,
                    study_boundary=[0, 0, config["canvas_size"], config["canvas_size"]],
                    settlement_source=str(settlement_path), settlement_sha256=verified[str(settlement_path)],
                    archived_regional_representation=len(candidates["regions_wkb"]), certified_candidates=len(pool),
                    archived_CH_lines=len(ids), exact_axial_intersections=True,
                    occupied_blocks=len(topology["blocks_wkb"]), winding_rank=winding["independent_circulation_rank"])
    by_seed = {}
    for name, case in available.items():
        row = case.inventory
        group = tuple(json.dumps(row["settings"][k], sort_keys=True) for k in MATCH_KEYS) + (row["building_count"],)
        by_seed.setdefault(group, []).append(name)
    matched = max(by_seed.values(), key=len)
    return available, inventory, sorted(matched), dict(sorted(verified.items()))
