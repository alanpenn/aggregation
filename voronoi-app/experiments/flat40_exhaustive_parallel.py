"""Checkpoint one generation across disjoint Flat 40 origins in local processes."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import resource
import sys
from time import monotonic

from experiments import flat40_exhaustive_resume
from experiments.flat40_complete_directed_convex import HANDS, advance, run, setup
from voronoi_app.batch_store import atomic_write, encode


def work(manifest, out, generation, limit, slot, worker_count):
    sys.set_int_max_str_digits(0)
    start = monotonic()
    _, _, _, replay, schedule = setup(manifest, out)
    written = []
    with flat40_exhaustive_resume.exact_caches() as caches:
        for index, (hand, side) in enumerate(HANDS):
            for ordinal, origin in enumerate(schedule[side]):
                if (index*len(schedule[side])+ordinal) % worker_count != slot:
                    continue
                directory = out/side/f"{ordinal:05d}"
                target = directory/f"{generation:06d}.json.gz"
                if target.exists():
                    continue
                previous = sorted(directory.glob("*.json.gz"))
                if len(previous) != generation:
                    # Earlier completion is allowed; no extra generation will be written.
                    import gzip
                    with gzip.open(previous[-1], "rb") as stream:
                        if json.load(stream)["after"]["complete"]:
                            continue
                    raise ValueError(f"Missing predecessor batch for {side} origin {ordinal}.")
                advance(replay, hand, origin, directory, limit)
                if target.exists():
                    written.append(str(target.relative_to(out)))
        return {"worker": slot,"seconds":monotonic()-start,
                "peak_rss_macos_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "written": written,"cache":flat40_exhaustive_resume.cache_stats(caches)}


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","output","metrics"):
        parser.add_argument("--"+name,type=Path,required=True)
    for name in ("generation","workers","prefixes-per-origin"):
        parser.add_argument("--"+name,type=int,required=True)
    args = parser.parse_args()
    if min(args.generation,args.workers,args.prefixes_per_origin) < 1 or args.metrics.exists():
        parser.error("Use positive values and a new metrics path.")
    verified = json.loads((args.output/"cache-benchmark-bounds.json").read_bytes())
    cache_sha = sha256(Path(flat40_exhaustive_resume.__file__).read_bytes()).hexdigest()
    if not verified["exact_journal_byte_equality"] or verified["implementation_sha256"] != cache_sha:
        raise ValueError("The predicate cache study does not match the current implementation.")

    start = monotonic()
    _, _, _, replay, schedule = setup(args.manifest,args.output)
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context("spawn")) as executor:
        tasks = [executor.submit(work,args.manifest,args.output,args.generation,args.prefixes_per_origin,
                                slot,args.workers) for slot in range(args.workers)]
        metrics = [task.result() for task in tasks]
    run(replay,schedule,0)
    files = [p for m in metrics for p in m["written"]]
    if len(files) != len(set(files)):
        raise ValueError("Overlapping journal ownership.")
    atomic_write(args.metrics,encode({"seconds":monotonic()-start, "workers":metrics,
                "generation":args.generation,"prefixes_per_origin_budget":args.prefixes_per_origin,
                "exact_cache_code_sha256":cache_sha,"scheduler_sha256":sha256(Path(__file__).read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
