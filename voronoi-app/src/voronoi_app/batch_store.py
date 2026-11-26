"""Immutable batch stage records and verified input lineage."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib import import_module, metadata
from inspect import getsourcefile
import json
import os
from pathlib import Path
import platform
import traceback
from uuid import UUID, uuid4

from .research_data import ENV, unavailable

STAGES = ("settlement", "topology", "candidates", "selection", "measures", "validation")
STATUSES = ("incomplete", "failed", "invalid", "successful")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(data):
    return sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StageResult:
    output: dict
    valid: bool = True


def atomic_write(path, data):
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("xb") as stream:
        stream.write(data)
    temporary.replace(path)


class BatchStore:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "records").mkdir(parents=True, exist_ok=True)
        (self.root / "source").mkdir(exist_ok=True)
        self._runtime = None

    def _directory(self, record_id):
        if UUID(record_id).hex != record_id:
            raise ValueError(f"Invalid record ID {record_id!r}")
        return self.root / "records" / record_id

    @staticmethod
    def _read(path):
        try:
            return path.read_bytes()
        except OSError as error:
            if not os.environ.get(ENV):
                raise
            raise FileNotFoundError(unavailable(path)) from error

    def load(self, record_id):
        directory = self._directory(record_id)
        raw = self._read(directory / "record.json")
        record = json.loads(raw)
        if (record["id"] != record_id or record["schema"] != 1
                or record["status"] not in STATUSES
                or digest(encode(record["parameters"])) != record["parameters_sha256"]):
            raise ValueError(f"Invalid record metadata for {record_id}")
        output = None
        if record["output_sha256"] is not None:
            payload = self._read(directory / "output.json")
            if digest(payload) != record["output_sha256"]:
                raise ValueError(f"Output hash mismatch for {record_id}")
            output = json.loads(payload)
        return record, output, digest(raw)

    def _inputs(self, stage, parent_id):
        index = STAGES.index(stage)
        if bool(index) != bool(parent_id):
            raise ValueError("The settlement stage takes no parent. All other stages require one.")
        inputs = {}
        expected_hash = None
        chain = STAGES[:index]
        if stage == "validation" and self.load(parent_id)[0]["stage"] == "selection":
            chain = chain[:-1]
        for expected in reversed(chain):
            if parent_id is None:
                raise ValueError(f"Missing {expected} input in the lineage")
            parent, payload, manifest_hash = self.load(parent_id)
            if parent["stage"] != expected or parent["status"] != "successful" or payload is None:
                raise ValueError(f"Expected successful {expected} input, got {parent['stage']} ({parent['status']})")
            if expected_hash is not None and manifest_hash != expected_hash:
                raise ValueError(f"Input record hash mismatch for {parent_id}")
            inputs[expected] = (parent, payload, manifest_hash)
            link = parent["parent"]
            parent_id = link["id"] if link else None
            expected_hash = link["record_sha256"] if link else None
        if parent_id is not None:
            raise ValueError("The settlement lineage has an unexpected parent.")
        return inputs

    def _save_source(self, name, path):
        content = path.read_bytes()
        key = digest(content)
        blob = self.root / "source" / f"{key}.py"
        if blob.exists():
            if digest(blob.read_bytes()) != key:
                raise ValueError(f"Saved source hash mismatch for {blob.name}")
        else:
            atomic_write(blob, content)
        return {"name": name, "sha256": key}

    def export_source(self, record_id, destination):
        """Restore the recorded package source into a new directory."""
        record, _, _ = self.load(record_id)
        runtime = record.get("runtime")
        if not runtime:
            raise ValueError("This attempt has no recorded method source.")
        destination = Path(destination).resolve()
        files = {}
        for entry in runtime["sources"]:
            path = (destination / entry["name"]).resolve()
            if not path.is_relative_to(destination):
                raise ValueError("The archived source contains an invalid path.")
            content = (self.root / "source" / f"{entry['sha256']}.py").read_bytes()
            if digest(content) != entry["sha256"]:
                raise ValueError(f"Saved source hash mismatch for {entry['name']}")
            files[path] = content
        external = record["method"]["source"]
        if not external["name"].startswith("voronoi_app."):
            content = (self.root / "source" / f"{external['sha256']}.py").read_bytes()
            if digest(content) != external["sha256"]:
                raise ValueError("Saved external method source hash mismatch.")
            files[destination / "external-method.py"] = content
        destination.mkdir(parents=True, exist_ok=False)
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def _method_sources(self, function):
        if self._runtime is None:
            package = Path(__file__).parent
            sources = [self._save_source(f"voronoi_app/{p.relative_to(package).as_posix()}", p)
                       for p in sorted(package.rglob("*.py"))]
            import shapely
            self._runtime = {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "dependencies": {n: metadata.version(n) for n in
                                 ("numpy", "scipy", "networkx", "shapely")},
                "geos": shapely.geos_version_string,
                "sources": sources,
            }
        path = getsourcefile(function)
        if path is None or not Path(path).is_file():
            raise ValueError("The method must be a Python function with an available source file.")
        return self._save_source(function.__module__, Path(path))

    def run(self, stage, method, version, parameters, parent=None):
        """Save an attempt first, then commit its result or recorded failure."""
        if stage not in STAGES or not isinstance(parameters, dict) or not version:
            raise ValueError("A known stage, version and JSON parameter object are required.")
        parameters = json.loads(json.dumps(parameters, allow_nan=False))
        parameter_hash = digest(encode(parameters))
        inputs = self._inputs(stage, parent)
        previous = next(iter(inputs.values()), None)
        record_id = uuid4().hex
        directory = self._directory(record_id)
        directory.mkdir()
        record = {
            "schema": 1, "id": record_id, "stage": stage, "status": "incomplete",
            "method": {"identity": method, "version": version},
            "parameters": parameters, "parameters_sha256": parameter_hash,
            "settlement_id": inputs["settlement"][0]["id"] if inputs else record_id,
            "parent": {"id": parent, "record_sha256": previous[2],
                       "output_sha256": previous[0]["output_sha256"]} if previous else None,
            "started_at": now(), "finished_at": None, "output_sha256": None,
        }
        path = directory / "record.json"
        atomic_write(path, encode(record))
        try:
            module, separator, name = method.partition(":")
            if not separator or not module or not name:
                raise ValueError("Method identity must have form module:function.")
            function = getattr(import_module(module), name)
            record["method"]["source"] = self._method_sources(function)
            record["runtime"] = self._runtime
            atomic_write(path, encode(record))
            result = function({key: row[1] for key, row in inputs.items()}, json.loads(encode(parameters)))
            if not isinstance(result, StageResult) or not isinstance(result.output, dict):
                raise TypeError("Batch methods must return StageResult with a JSON object.")
            payload = encode(result.output)
            atomic_write(directory / "output.json", payload)
            record.update(status="successful" if result.valid else "invalid",
                          output_sha256=digest(payload))
        except Exception as error:
            record.update(status="failed", error={"type": type(error).__name__,
                          "message": str(error), "traceback": traceback.format_exc()})
        record["finished_at"] = now()
        atomic_write(path, encode(record))
        return record
