from pathlib import Path

import pytest

from voronoi_app.batch import run_stage
from voronoi_app.batch_export import export_rows
from voronoi_app.batch_store import BatchStore, StageResult


def interrupted(inputs, parameters):
    raise KeyboardInterrupt


def rejects(inputs, parameters):
    return StageResult({"reason": "test rejection"}, valid=False)


def test_records_keep_status_and_detect_tampering(tmp_path):
    store = BatchStore(tmp_path)
    invalid = store.run("settlement", f"{__name__}:rejects", "test-1", {})
    assert invalid["status"] == "invalid"
    assert store.load(invalid["id"])[1] == {"reason": "test rejection"}
    with pytest.raises(ValueError, match="Expected successful settlement"):
        run_stage(store, "topology", None, {}, invalid["id"])
    failed = store.run("settlement", f"{__name__}:missing", "test-1", {})
    assert failed["status"] == "failed" and failed["error"]["type"] == "AttributeError"
    with pytest.raises(KeyboardInterrupt):
        store.run("settlement", f"{__name__}:interrupted", "test-1", {})
    attempts = [store.load(path.name)[0] for path in (tmp_path / "records").iterdir()]
    assert {record["status"] for record in attempts} == {"failed", "invalid", "incomplete"}
    path = tmp_path / "records" / invalid["id"] / "output.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="Output hash mismatch"):
        store.load(invalid["id"])


def test_restart_and_branch_from_each_saved_stage(tmp_path):
    store = BatchStore(tmp_path)
    config = {"seed": 11, "grid_generator": "cartesian", "terrain_provider": "hill",
              "grid_params": {"resolution": 5}, "aggregation_params": {"max_dyads": 5}}

    def success(stage, method=None, parameters=None, parent=None, version=None):
        record = run_stage(BatchStore(tmp_path), stage, method, parameters or {}, parent, version)
        assert record["status"] == "successful", record
        return record["id"]

    settlement = success("settlement", parameters=config)
    topology = success("topology", parent=settlement)
    candidates = success("candidates", parent=topology)
    candidate_path = Path(tmp_path, "records", candidates, "record.json")
    before = candidate_path.read_bytes()
    alternate = success("candidates", "projected-faces", parent=topology)
    first = success("selection", "exact-greedy", parent=candidates)
    second = success("selection", "voronoi_app.batch_methods:retain_pool",
                     parent=candidates, version="alternative-1")
    assert first != second and alternate != candidates
    assert candidate_path.read_bytes() == before
    measures = success("measures", parent=first)
    revised = success("measures", parameters={"connector_limit": 12}, parent=first)
    validation = success("validation", parent=measures)
    direct = success("validation", parent=first)
    case = {"case": "replay", "generator": "fresh-exact", "selector": "exact-greedy",
            "records": {"settlement": settlement, "topology": topology, "candidates": candidates,
                        "selection": first, "validation": direct}}
    destination = tmp_path / "comparison.csv"
    assert export_rows(store, [case], destination) == 1
    assert "entrance_depth_mean" in destination.read_text()
    assert ",null," in destination.read_text()
    with pytest.raises(FileExistsError):
        export_rows(store, [case], destination)
    for record_id in (alternate, first, second, measures, revised, validation, direct):
        assert store.load(record_id)[0]["settlement_id"] == settlement
    assert store.load(validation)[1]["summary"]["entrance_depth"] is not None
    assert store.load(direct)[1]["summary"]["entrance_depth"] is None
    generated, payload, _ = store.load(settlement)
    assert payload["configuration"]["seed"] == 11 and payload["doors"] and payload["polygons_wkb"]
    assert generated["runtime"]["sources"]
    source = generated["method"]["source"]["sha256"]
    assert (tmp_path / "source" / f"{source}.py").is_file()
    recovered = tmp_path / "recovered"
    store.export_source(settlement, recovered)
    assert (recovered / "voronoi_app" / "batch_methods.py").read_bytes() == (
        tmp_path / "source" / f"{source}.py"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        store.export_source(settlement, recovered)
    import_parameters = {**payload, "building_labels": {int(i): label
                                                       for i, label in payload["building_labels"].items()}}
    imported = success("settlement", "preserve-settlement", parameters=import_parameters)
    assert imported != settlement and store.load(imported)[0]["output_sha256"] == generated["output_sha256"]
