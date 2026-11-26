"""Verify a research handover and optionally restore files without replacing local data."""

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


MANIFEST = "research-handover-manifest.json"
PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / "src"))
from voronoi_app.research_data import copy_verified, data_root


def safe_path(name):
    path = PurePosixPath(name)
    if (path.is_absolute() or path.as_posix() != name or len(path.parts) < 2
            or path.parts[0] != "diagnostics" or ".." in path.parts or "\\" in name):
        raise ValueError(f"Unsafe archive path: {name!r}")
    return path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_verified(archive, staging):
    with tarfile.open(archive, "r:gz") as bundle:
        entries = bundle.getmembers()
        names = [entry.name for entry in entries]
        if len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError("Duplicate members or missing archive manifest.")
        if any(not entry.isfile() for entry in entries):
            raise ValueError("All archive members must be regular files.")
        manifest = json.load(bundle.extractfile(MANIFEST))
        records = manifest["files"]
        by_name = {row["path"]: row for row in records}
        if len(by_name) != len(records) or set(by_name) != set(names) - {MANIFEST}:
            raise ValueError("Archive inventory does not match the manifest.")
        for entry in entries:
            if entry.name == MANIFEST:
                continue
            destination = staging / safe_path(entry.name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(entry) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
            expected = by_name[entry.name]
            if entry.size != expected["bytes"] or digest(destination) != expected["sha256"]:
                raise ValueError(f"Archive checksum or size mismatch: {entry.name}")
    return manifest


def restore(staging, records):
    installed, identical, conflicts = 0, 0, []
    for row in records:
        name = row["path"]
        relative = Path(*safe_path(name).parts[1:])
        target = data_root(PROJECT / "diagnostics") / relative
        status = copy_verified(staging / name, target, row["sha256"])
        if status == "copied":
            installed += 1
        elif status == "identical":
            identical += 1
        else:
            conflicts.append(str(target))
    return installed, identical, conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--apply", action="store_true", help="Restore verified files into this checkout")
    args = parser.parse_args()
    staging = Path(tempfile.mkdtemp(prefix="voronoi-restoration-"))
    keep = False
    try:
        manifest = extract_verified(args.archive, staging)
        records = manifest["files"]
        print(f"Verified {len(records)} files for {manifest['git']['commit']}.")
        if args.apply:
            keep = True
            installed, identical, conflicts = restore(staging, records)
            keep = bool(conflicts)
            print(f"Installed {installed}; identical {identical}; conflicts {len(conflicts)}.")
            for name in conflicts:
                print(f"Conflict: {name}")
            if conflicts:
                print(f"Verified incoming copies preserved in {staging}")
                return 2
    finally:
        if not keep:
            shutil.rmtree(staging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
