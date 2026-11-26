"""Plan, copy, verify and isolate runs in a shared research-data directory."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

from voronoi_app.research_data import ENV, copy_verified, data_root, sha256_file

PROJECT = Path(__file__).resolve().parents[1]
SHARED = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/ResearchArchives/aggregation-data"
SKIP = {".DS_Store", "__pycache__", ".pytest_cache", ".venv", "claims", "analysis-workers",
        "runs", "secrets.toml", "credentials"}
SKIP_SUFFIXES = {".tmp", ".lock", ".pid", ".pyc", ".eml", ".zip", ".gz"}


def scientific_files(root):
    for directory, folders, names in os.walk(root, followlinks=False):
        folder = Path(directory)
        folders[:] = sorted(d for d in folders if d not in SKIP and not d.startswith((".", "work-computer-transfer-"))
                            and not (folder / d).is_symlink())
        for name in sorted(names):
            path = folder / name
            # Gzipped JSON snapshots are scientific inputs, unlike transfer bundles.
            if (not name.startswith(".") and name not in SKIP and not path.is_symlink()
                    and (path.suffix not in SKIP_SUFFIXES or name.endswith(".json.gz"))):
                yield path


def inventory(extracted):
    local = PROJECT / "diagnostics"
    tracked = set(subprocess.check_output(
        ["git", "ls-files", "-z", "--", "diagnostics"], cwd=PROJECT
    ).decode().split("\0"))
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "diagnostics/probe"],
                             cwd=PROJECT, capture_output=True).returncode == 0
    items = [(f.relative_to(local), f, None,
              "tracked" if str(f.relative_to(PROJECT)) in tracked else "ignored" if ignored else "untracked")
             for f in scientific_files(local)]
    if extracted:
        rows = json.loads((extracted / "research-handover-manifest.json").read_bytes())["files"]
        for row in rows:
            src = Path(row["path"])
            if src.is_absolute() or ".." in src.parts or src.parts[0] != "diagnostics":
                raise ValueError(f"Unexpected archive path {src}")
            items.append((Path(*src.parts[1:]), extracted / src, row["sha256"], "verified archive"))
    return items


def migrate(destination, extracted, apply):
    results = []
    for relative, source, expected, kind in inventory(extracted):
        target = destination / relative
        checksum = expected or sha256_file(source)
        error_text = None
        try:
            status = copy_verified(source, target, checksum) if apply else "planned"
        except (OSError, ValueError) as error:
            status, error_text = "error", str(error)
        results.append({"source": str(source), "destination": str(target), "relative": str(relative),
                        "sha256": checksum, "origin": kind, "status": status, "error": error_text})
    return results


def run_isolated(root, module, arguments, previous=None, fresh=()):
    if not root.is_dir():
        raise FileNotFoundError(root)
    omitted = tuple(Path(name) for name in fresh)
    if any(path.is_absolute() or ".." in path.parts or not path.parts for path in omitted):
        raise ValueError("Fresh paths must be relative to the diagnostics root.")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="aggregation-run-") as temp:
        scratch = Path(temp) / "diagnostics"
        scratch.mkdir()
        before = {}
        # Scripts may overwrite their fixed legacy filenames in this temporary
        # copy. The shared originals never enter the writable workspace.
        for source in scientific_files(root):
            relative = source.relative_to(root)
            if any(relative == path or path in relative.parents for path in omitted):
                continue
            before[relative] = sha256_file(source)
            local = scratch / relative
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, local)
            if sha256_file(local) != before[relative]:
                raise ValueError(f"Shared input changed during staging: {source}")
        if previous:
            if Path(previous).name != previous or previous in (".", ".."):
                raise ValueError("Expected a single run ID.")
            parent = root / "runs" / previous
            prior = json.loads((parent / "run.json").read_bytes())
            for name, expected in prior["files"].items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError(f"Unsafe run member: {name}")
                if any(relative == path or path in relative.parents for path in omitted):
                    continue
                local = scratch / relative
                local.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(parent / relative, local)
                if sha256_file(local) != expected:
                    raise ValueError(f"Parent run has not been downloaded or its checksum differs: {name}")
        if any(Path(arg.split("=", 1)[-1]).is_absolute() or ".." in Path(arg.split("=", 1)[-1]).parts for arg in arguments):
            raise ValueError("Use run-relative CLI paths inside the isolated workspace.")
        git_dir = subprocess.check_output(["git","rev-parse","--absolute-git-dir"], cwd=PROJECT, text=True).strip()
        process = subprocess.run([sys.executable, "-m", module, *arguments], cwd=temp,
                                 env=os.environ | {ENV: str(scratch), "GIT_DIR": git_dir, "GIT_WORK_TREE": str(PROJECT),
                                                   "PYTHONPATH": os.pathsep.join((str(PROJECT/"src"),str(PROJECT)))})
        output = root / "runs" / run_id
        output.mkdir(parents=True, exist_ok=False)
        files = {}
        for source in scientific_files(scratch):
            relative = source.relative_to(scratch)
            checksum = sha256_file(source)
            if before.get(relative) != checksum:
                if copy_verified(source, output / relative, checksum) != "copied":
                    raise ValueError(f"Publication conflict in {output}: {relative}")
                files[str(relative)] = checksum
        manifest = Path(temp) / "run.json"
        manifest.write_text(json.dumps({"command":[module,*arguments],"exit_code":process.returncode,"parent_run":previous,"fresh":list(fresh),
                                        "git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=PROJECT,text=True).strip(),
                                        "inputs":{str(p):h for p,h in before.items()},"files":files},indent=2))
        copy_verified(manifest, output / "run.json")
        print(f"Isolated run published to {output}", flush=True)
    return process.returncode


def verify(root, manifest, *, run=False):
    entries = json.loads(manifest.read_bytes())
    if run:
        root = manifest.parent
        exit_code = entries["exit_code"]
        entries = entries["files"]
        if exit_code:
            print(f"Run exited with status {exit_code}.")
    errors = []
    for relative, expected in entries.items():
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe manifest path: {relative}")
        file = root / rel
        try:
            if sha256_file(file) != expected:
                errors.append(f"checksum mismatch: {relative}")
        except OSError as error:
            errors.append(f"unavailable: {relative} ({error.strerror})")
    print(f"Verified {len(entries)-len(errors)}/{len(entries)} files in {root}.")
    for error in errors:
        print(error)
    return bool(errors) or (run and bool(exit_code))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=data_root(SHARED))
    commands = parser.add_subparsers(dest="command", required=True)
    copy = commands.add_parser("migrate")
    copy.add_argument("--extracted", type=Path)
    copy.add_argument("--apply", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("manifest", type=Path)
    check.add_argument("--run", action="store_true", help="Verify a run.json and its published outputs.")
    run = commands.add_parser("run")
    run.add_argument("--from-run")
    run.add_argument("--fresh", action="append", default=[], help="Omit a legacy output folder from the private workspace.")
    run.add_argument("module")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    if args.command == "verify":
        return verify(destination, args.manifest, run=args.run)
    if args.command == "run":
        return run_isolated(destination, args.module, args.arguments, args.from_run, args.fresh)
    local = (PROJECT / "diagnostics").resolve()
    if destination == local or local in destination.parents or destination in local.parents:
        parser.error("Choose a destination outside the local diagnostics tree.")
    results = migrate(destination, args.extracted, args.apply)
    print(json.dumps(results, indent=2))
    return int(any(row["status"] in ("conflict", "error") for row in results))


if __name__ == "__main__":
    raise SystemExit(main())
