"""Benchmark exact predicate caching and advance the original checkpoint engine."""
import argparse
from contextlib import contextmanager
from functools import lru_cache
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from unittest.mock import patch

from experiments import oriented_extension_turns
from experiments.directed_boundary_cover import Face
from experiments.flat40_complete_directed_convex import HANDS, advance, run, setup
from voronoi_app.batch_store import atomic_write, encode


@contextmanager
def exact_caches():
    """Cache complete inputs to pure predicates, preserving every path check."""
    signed = lru_cache(maxsize=65536)(Face.signed)
    intersect = oriented_extension_turns._intersections

    @lru_cache(maxsize=8192)
    def extents(a, b):
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    @lru_cache(maxsize=65536)
    def intersections(a, b, c, d):
        x,y,X,Y = extents(a,b)
        u,v,U,V = extents(c,d)
        if X < u or U < x or Y < v or V < y:
            return frozenset()
        return frozenset(intersect(a, b, c, d))

    with patch.object(Face, "signed", signed), patch.object(
            oriented_extension_turns, "_intersections", intersections):
        yield {"signed": signed, "intersections": intersections, "extents": extents}


def cache_stats(caches):
    return {name: operation.cache_info()._asdict() for name, operation in caches.items()}


def benchmark(replay, schedule):
    origins = (0, 41, 132, 310, 313, 488, 683, 684, 804, 807, 944, 1063)
    with TemporaryDirectory() as temp:
        root = Path(temp)
        for _, side in HANDS:
            for ordinal in origins:
                for mode in ("reference", "cached"):
                    shutil.copytree(replay.out / side / f"{ordinal:05d}", root/mode/side/f"{ordinal:05d}")

        def measure(mode):
            start = monotonic()
            for hand, side in HANDS:
                for ordinal in origins:
                    advance(replay, hand, schedule[side][ordinal], root/mode/side/f"{ordinal:05d}", 96)
            return monotonic() - start

        reference = measure("reference")
        with exact_caches() as caches:
            cached = measure("cached")
            counters = cache_stats(caches)
        files = sorted((root/"reference").glob("*/*/*.json.gz"))
        if any(f.read_bytes() != (root/"cached"/f.relative_to(root/"reference")).read_bytes() for f in files):
            raise ValueError("Cached and reference checkpoint bytes differ.")
        return {"reference_seconds": reference, "cached_seconds": cached,
                "exact_journal_byte_equality": True, "origins_per_hand": origins,
                "prefix_limit_per_origin": 96, "cache": counters}


def triangle_discovery(out, source):
    fixture = json.loads(source.read_text())
    target = fixture["triangle_id"]
    expected = {(r["hand"], r["checkpoint"]["ordinal"]): r["face"] for r in fixture["paths"]}
    events = []
    for order, (_, side) in enumerate(HANDS):
        for directory in sorted((out/side).iterdir()):
            ordinal = int(directory.name)
            for f in sorted(directory.glob("*.json.gz")):
                with gzip.open(f, "rb") as stream:
                    batch = json.load(stream)
                offset = batch["after"]["prefixes"] - len(batch["records"])
                for j, row in enumerate(batch["records"], 1):
                    if any(r["id"] == target for r in row["closed"]):
                        events.append((int(f.stem.split(".")[0]), order, ordinal, j, {
                            "batch": str(f.relative_to(out)), "hand": side, "origin": ordinal,
                            "start_edge": row["path"][0], "prefix_number_within_origin": offset+j,
                            "journal_row": j, "path": row["path"],
                            "expected_face_endpoint": expected.get((side, ordinal)),
                        }))
    events.sort(key=lambda r:r[:4])
    hits = [x[-1] for x in events]
    # Reconcile the fixed per-round hand/origin processing order against the
    # journal sequence. A finished origin receives no later batches.
    return {"polygon_id": target, "first_discovery": next(iter(hits), None), "paths": hits,
            "expected_origins_observed": [list(k) for k in sorted(expected)
                                         if any((p["hand"],p["origin"]) == k for p in hits)],
            "expected_origins_pending_discovery": [list(k) for k in sorted(expected)
                                                  if not any((p["hand"],p["origin"]) == k for p in hits)]}


def run_generation(replay, schedule, budget, generation):
    for hand, side in HANDS:
        for ordinal, start in enumerate(schedule[side]):
            directory = replay.out / side / f"{ordinal:05d}"
            if not (directory / f"{generation:06d}.json.gz").exists():
                advance(replay, hand, start, directory, budget)
    run(replay, schedule, 0)


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--prefixes-per-origin", type=int)
    parser.add_argument("--generation", type=int)
    parser.add_argument("--verification-file", default="cache-benchmark.json")
    parser.add_argument("--metrics", type=Path, required=True)
    args = parser.parse_args()
    if not args.benchmark and (args.prefixes_per_origin is None or args.prefixes_per_origin < 1):
        parser.error("Pass --benchmark or a positive additional per-origin budget.")
    if args.metrics.exists():
        parser.error("The requested metrics file already exists.")
    _, _, _, replay, schedule = setup(args.manifest, args.output)
    implementation = sha256(Path(__file__).read_bytes()).hexdigest()
    if args.benchmark:
        result = benchmark(replay,schedule)
    else:
        verified = json.loads((args.output/args.verification_file).read_text())
        if not verified["exact_journal_byte_equality"] or verified["implementation_sha256"] != implementation:
            raise ValueError("Use the reference runner until exact journal equality is verified.")
        start = monotonic()
        with exact_caches() as caches:
            if args.generation is None:
                run(replay,schedule,args.prefixes_per_origin)
            else:
                run_generation(replay,schedule,args.prefixes_per_origin,args.generation)
            result = {"seconds": monotonic() - start, "cache": cache_stats(caches),
                      "prefixes_per_origin_budget": args.prefixes_per_origin}
    result["implementation_sha256"] = implementation
    atomic_write(args.metrics, encode(result))
    print(result, flush=True)


if __name__ == "__main__":
    main()
