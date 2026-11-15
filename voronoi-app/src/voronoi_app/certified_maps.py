"""Load preserved exact research maps for display, without running selection."""

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .axial_snapshot import load_axial_snapshot
from .exact_enumeration import exact_pool_from_dict


ARTIFACTS = (
    "axial-648f8da1364449a6aa70fd24038eea21.json",
    "exact-y-fresh-candidates.json",
    "exact-y-24-forced-reference.json",
    "exact-y-23-pareto-reference.json",
    "exact-y-pareto-results.json",
)


@dataclass(frozen=True)
class CertifiedResearchMaps:
    open_polygons: dict
    occupied_polygons: dict
    paired_open_cells: set
    candidates: list
    certifications: dict


def read_certified_fixture_bytes(directory: Path):
    """Read inputs for a cache key that changes whenever a fixture changes."""
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest["version"] != 1 or set(manifest["files"]) != set(ARTIFACTS):
        raise ValueError("Unsupported or incomplete research fixture manifest")
    contents = []
    for name in ARTIFACTS:
        filename = manifest["files"][name]["fixture"]
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError(f"Invalid research fixture filename for {name}")
        contents.append((directory / filename).read_bytes())
    return manifest_bytes, tuple(contents)


def decode_certified_research(manifest_bytes: bytes, contents: tuple[bytes, ...]):
    """Verify artifact bytes and retain exact candidate objects for rendering."""
    manifest = json.loads(manifest_bytes)
    if manifest["version"] != 1 or set(manifest["files"]) != set(ARTIFACTS):
        raise ValueError("Unsupported or incomplete research fixture manifest")
    if len(contents) != len(ARTIFACTS):
        raise ValueError("Incomplete research fixture inputs")
    artifacts = {}
    for name, content in zip(ARTIFACTS, contents):
        entry = manifest["files"][name]
        raw = gzip.decompress(content) if entry["fixture"].endswith(".gz") else content
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Research fixture checksum mismatch: {name}")
        artifacts[name] = json.loads(raw)

    reference = artifacts["exact-y-24-forced-reference.json"]
    results = artifacts["exact-y-pareto-results.json"]
    for key, name in (
        ("settlement_sha256", ARTIFACTS[0]), ("pool_sha256", ARTIFACTS[1]),
        ("baseline_sha256", ARTIFACTS[2]), ("reference23_sha256", ARTIFACTS[3]),
    ):
        if results[key] != manifest["files"][name]["sha256"]:
            raise ValueError(f"Research artifact lineage mismatch: {key}")
    if (reference["settlement_source"] != ARTIFACTS[0]
            or reference["pool_source"] != ARTIFACTS[1]
            or reference["settlement_sha256"] != results["settlement_sha256"]
            or reference["pool_sha256"] != results["pool_sha256"]):
        raise ValueError("Research reference geometry does not match the candidate pool")

    opened, occupied, _, _, paired = load_axial_snapshot(artifacts[ARTIFACTS[0]])
    pool = exact_pool_from_dict(artifacts[ARTIFACTS[1]])
    if len(pool.candidates) != 1651:
        raise ValueError("Unexpected research candidate pool size")
    certifications = results["certifications"]
    expected = {"reference23", "reference24", "best23", "best24", "best25",
                "best_all_excluded"}
    if set(certifications) != expected:
        raise ValueError("Unexpected certified map set")
    for name, result in certifications.items():
        ids = result["selected"]
        if (len(ids) != result["metrics"]["count"] or len(ids) != len(set(ids))
                or any(not isinstance(i, int) or isinstance(i, bool) or i < 0
                       or i >= len(pool.candidates) for i in ids)):
            raise ValueError(f"Invalid candidate selection for certified map {name}")
        if (result["regions_covered"] != result["region_count"]
                or result["rings_preserved"] != result["ring_count"]
                or result["graph_components"] != 1 or result["unsafe_lines"]):
            raise ValueError(f"Recorded certification failed for map {name}")
    return CertifiedResearchMaps(opened, occupied, paired, pool.candidates, certifications)
