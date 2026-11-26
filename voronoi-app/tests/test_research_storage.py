import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments import research_storage
from voronoi_app.research_data import ENV, copy_verified, data_path, logical_path, sha256_file


def test_local_and_configured_paths(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV, raising=False)
    assert data_path("strict-generalisation/facewise-1") == Path("diagnostics/strict-generalisation/facewise-1")
    monkeypatch.setenv(ENV, str(tmp_path))
    dataset = data_path("strict-generalisation/facewise-1")
    assert dataset == tmp_path / "strict-generalisation/facewise-1"
    assert logical_path(dataset) == Path("diagnostics/strict-generalisation/facewise-1")
    with pytest.raises(ValueError):
        data_path("../outside")


def test_verified_copy_preserves_conflicting_destinations(tmp_path):
    source, target = tmp_path / "source", tmp_path / "destination" / "record"
    source.write_bytes(b"immutable")
    original = sha256_file(source)
    assert copy_verified(source, target, original) == "copied"
    assert copy_verified(source, target, original) == "identical"
    source.write_bytes(b"new")
    assert copy_verified(source, target) == "conflict"
    assert sha256_file(target) == original
    with pytest.raises(ValueError, match="checksum mismatch"):
        copy_verified(source, target.parent / "unpublished", original)
    assert not (target.parent / "unpublished").exists()
    assert list(target.parent.iterdir()) == [target]


def test_isolated_writer_does_not_modify_shared_records(tmp_path, monkeypatch):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "record.json").write_text("original")
    def execute(command, *, cwd, env):
        scratch = Path(env[ENV])
        assert scratch.parent == Path(cwd)
        assert (scratch / "record.json").read_text() == "original"
        (scratch / "record.json").write_text("changed in private scratch")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(research_storage.subprocess, "run", execute)
    monkeypatch.setattr(research_storage.subprocess, "check_output", lambda *args, **kwargs: "test\n")
    for _ in range(2):
        assert research_storage.run_isolated(root, "experiments.example", []) == 0
    runs = list((root / "runs").iterdir())
    assert len(runs) == 2
    assert (root / "record.json").read_text() == "original"
    for run in runs:
        record = json.loads((run / "run.json").read_bytes())
        assert record["files"] == {"record.json": sha256_file(run / "record.json")}
        assert research_storage.verify(root, run / "run.json", run=True) is False
