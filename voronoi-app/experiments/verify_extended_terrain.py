"""Verify completeness and exact plotted interval lineage before publication."""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image

from experiments.extended_terrain import ROOT, SEEDS, TERRAINS, PREVIOUS_TERRAINS
from experiments.strict_generalisation_export import METHODS
from voronoi_app.batch_store import BatchStore


def verify(root=ROOT):
    index = json.loads((root / "visual-index.json").read_bytes())
    manifest = json.loads((root / "export-record.json").read_bytes())
    for relative, checksum in manifest.items():
        if sha256((root / relative).read_bytes()).hexdigest() != checksum:
            raise ValueError(f"Export checksum mismatch for {relative}.")
    cases = {f"{terrain}-{seed}" for terrain in (*TERRAINS, *PREVIOUS_TERRAINS) for seed in SEEDS}
    expected = {(case, method) for case in cases for method in METHODS}
    with (root / "statistics.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(expected) or {(row["case"], row["method"]) for row in rows} != expected:
        raise ValueError("The statistical cohort is incomplete.")
    if index["case_count"] != 36 or index["method_count"] != 180 or len(index["cases"]) != 36:
        raise ValueError("The visual index has incomplete cohort counts.")
    seen = set()
    for case in index["cases"]:
        store = BatchStore(Path(case["record_root"]))
        candidate = case["records"].get("candidates")
        output = store.load(candidate)[1] if candidate else None
        intervals = output["pool"]["candidates"] if output else []
        for method, item in case["methods"].items():
            key = (case["case"], method)
            if key in seen:
                raise ValueError(f"Duplicate indexed entry {key}.")
            seen.add(key)
            for interval in item["selected_intervals"]:
                canonical = intervals[interval["id"]]
                if any(canonical[field] != interval[field] for field in ("id", "start", "end")):
                    raise ValueError(f"An interval in {key} differs from its immutable candidate.")
            with Image.open(root / item["visual"]["png"]) as png:
                if min(png.size) < 2000:
                    raise ValueError(f"Low-resolution map for {key}.")
            vector(root / item["visual"]["pdf"])
            stats = item["stats"]
            if stats["status"] != "valid" and not stats["reason"]:
                raise ValueError(f"Missing failure reason for {key}.")
        for name in ("comparison", "topology_and_corridors"):
            vector(root / case[name]["pdf"])
    if seen != expected:
        raise ValueError("The visual index does not cover every method and case.")
    vector(root / index["atlas"])
    print(f"Verified {len(cases)} cases and {len(rows)} maps. Statuses {dict(Counter(row['status'] for row in rows))}.")


def vector(path):
    contents = path.read_bytes()
    if not contents.startswith(b"%PDF") or b"/Subtype /Image" in contents:
        raise ValueError(f"Expected a vector PDF at {path}.")


if __name__ == "__main__":
    verify()
