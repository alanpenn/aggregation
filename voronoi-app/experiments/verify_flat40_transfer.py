"""Verify the portable Flat 40 records and optionally the full transfer bundle."""
import argparse
from fractions import Fraction
from hashlib import file_digest, sha256
import json
from pathlib import Path
import sys
import tarfile

from voronoi_app.batch_store import encode
from voronoi_app.research_data import data_root

PROJECT = Path(__file__).resolve().parents[1]
BASE = PROJECT / "diagnostics" / "strict-generalisation"
BUNDLE = "flat40-research-2026-11-26"


def load(path):
    return json.loads(path.read_bytes())


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify_records():
    cover = load(PROJECT / "research" / "flat40" / "maximal-regions.json")
    regions = cover["regions"]
    check(len(regions) == cover["region_count"] == 596, "Expected 596 regions.")
    for key, row in regions.items():
        check(sha256(encode(row["vertices"])).hexdigest() == key
              and row["maximality"]["status"] == "proved_global"
              and Fraction(row["area"]) > 0, f"Invalid region certificate {key}")
    exhaustive = BASE / "flat40-exhaustive-convex-1"
    overlay = load(exhaustive / "coverage-progression.json")[-1]
    check(Fraction(overlay["coverage"]["uncovered_area"]) == 0
          and overlay["globally_maximal"] == 596
          and all(not p["pending_stack_entries"] for p in overlay["progress"].values()),
          "Incomplete exact cover.")
    selection = BASE / "flat40-maximal-convex-axial-selection-1"
    for name in ("B-C-H", "B-C-S"):
        row = load(selection / f"{name}.json")
        winding = row["certificate"]
        check(len(set(row["ids"])) == 31 and winding["circulation_constraints_satisfied"]
              and winding["independent_circulation_rank"] == 24
              and winding["effective_clearance_line_count"] == 31, f"Invalid selection {name}")
    minimum = BASE / "flat40-maximal-convex-minimum-1"
    rows = load(minimum / "combined-results.json")["smaller"]
    best = [r for r in rows if len(r["ids"]) == 29]
    check(len(best) == 2, "Expected two 29-line maps.")
    for row in best:
        cert = row["certificate"]
        check(cert["coverage"] == 596 and cert["doorways"] == 100 and cert["components"] == 1
              and cert["winding"]["independent_circulation_rank"] == 24
              and cert["winding"]["effective_clearance_line_count"] == 29,
              "Invalid 29-line certificate.")
    dual = load(minimum / "dual-verification.json")["with_winding_rays"]
    check(dual["verified_bound"] == 19 and dual["candidates_checked"] == 1534, "Invalid lower bound.")
    print("Verified compact records: 596 regions, zero uncovered area, two 31-line and two 29-line maps, bound 19.")


def verify_bundle():
    location = data_root() / "transfers" / BUNDLE
    manifest = load(location / f"{BUNDLE}.json")
    expected = load(PROJECT / "research" / "flat40" / "transfer.json")
    archive = location / f"{BUNDLE}.tar.gz"
    with archive.open("rb") as stream:
        checksum = file_digest(stream, "sha256").hexdigest()
    check(checksum == manifest["sha256"] == expected["archive_sha256"], "Archive SHA-256 differs.")
    with (location / f"{BUNDLE}.json").open("rb") as stream:
        check(file_digest(stream, "sha256").hexdigest() == expected["manifest_sha256"],
              "Archive manifest SHA-256 differs.")
    with tarfile.open(archive) as source:
        seen = {}
        for member in source:
            check(member.isfile() and member.name not in seen and member.name in manifest["files"],
                  f"Unexpected archive member {member.name}")
            with source.extractfile(member) as stream:
                seen[member.name] = file_digest(stream, "sha256").hexdigest()
    check(seen == manifest["files"], "Archived file inventory differs.")
    print(f"Verified all {len(seen):,} transfer archive files.")


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    verify_records()
    if args.archive:
        verify_bundle()


if __name__ == "__main__":
    main()
