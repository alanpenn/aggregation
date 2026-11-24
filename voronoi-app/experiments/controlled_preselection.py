"""Matched Flat 40 reductions with and without complementary preselection."""
import argparse
from collections import Counter

from hashlib import sha256
from random import Random
from statistics import mean
from time import monotonic, sleep
from types import SimpleNamespace

from experiments.constructive_axial import ROOT, evaluate
from experiments.dynamic_winding import CycleSignatures
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.unrestricted_axial_reduction import BUDGET, ROUNDS, Study as BaseStudy
from voronoi_app.batch_store import atomic_write, encode

DEST = OUTPUT.parent / "controlled-preselection-1"
ORDERS = ("shortest", "region-overlap", "transverse")


class MatchedWinding(CycleSignatures):
    def __init__(self, previous):
        self.__dict__.update(previous.__dict__)
        self.neighbors = {i: set(self.graph[i]) for i in self.graph}
        self.uniform_roots = []

    def rank(self, selected):
        if not selected:
            return 0
        uniform = any(selected <= root for root in self.uniform_roots)
        origin = min(selected)
        potentials = {origin: 0}
        pending = [origin]
        basis = {}
        for i in pending:
            for j in self.neighbors[i] & selected:
                value = potentials[i] ^ self.edge(i, j)
                if j not in potentials:
                    potentials[j] = value
                    pending.append(j)
                    continue
                value ^= potentials[j]
                while value:
                    pivot = value.bit_length()
                    if pivot in basis:
                        value ^= basis[pivot]
                        continue
                    basis[pivot] = value
                    if uniform:
                        if len(basis) == self.required:
                            return len(basis)
                    elif any(value & mask not in (0, mask) for mask in self.masks):
                        return None
                    break
        if not uniform and len(basis) == self.required:
            self.uniform_roots.append(frozenset(selected))
        return len(basis)


class Study(BaseStudy):
    def __init__(self):
        super().__init__()
        self.winding = MatchedWinding(self.winding)

    def connected(self, ids):
        if not ids:
            return False
        first = min(ids)
        unseen = ids - {first}
        queue = [first]
        for i in queue:
            reached = self.neighbors[i] & unseen
            unseen -= reached
            queue.extend(reached)
            if not unseen:
                return True
        return False

    def validate(self, current, removed, added, counts):
        self.counts["proposals"] += 1
        delta = Counter(r for i in added for r in self.by_line[i])
        delta.subtract(r for i in removed for r in self.by_line[i])
        missing = [r for r, change in delta.items() if counts[r] + change <= 0]
        if missing:
            return ("region" if min(missing) < len(self.regions) else "doorway"), None
        if any(not self.clear(i) for i in added):
            return "clearance", None
        trial = (current - removed) | added
        if not self.connected(trial):
            return "connectivity", None
        started = monotonic()
        rank = self.winding.rank(trial)
        self.counts["dynamic_validator"] += 1
        self.timings["dynamic_validator"] += monotonic() - started
        if rank is None:
            started = monotonic()
            result = self.geometry.geometry(frozenset(trial))
            self.counts["fallback_validator"] += 1
            self.timings["fallback_validator"] += monotonic() - started
            if not result["circulation_constraints_satisfied"] or result["lines_crossing_effective_occupied_space"]:
                return "winding", None
        elif rank != self.winding.required:
            return "winding", None
        return "valid", delta


class MemoizedStudy(Study):
    def reduce(self, current, order, trace):
        counts = self.counts_for(current)
        permanent = {}
        while True:
            blocked = {}
            for i in sorted(current, key=lambda j: self.priority(j, current, counts, order)):
                if i in permanent:
                    self.counts["cached_rejections"] += 1
                    blocked[i] = permanent[i]
                    continue
                status, delta = self.validate(current, {i}, set(), counts)
                if status == "valid":
                    current.remove(i)
                    counts.update(delta)
                    trace.append(i)
                    break
                if status in ("region", "doorway") or (
                        status == "winding" and any(current <= root for root in self.winding.uniform_roots)):
                    # Deletion cannot create incidence or a new cycle in a
                    # uniform arrangement. Connectivity rejections can change.
                    permanent[i] = status
                blocked[i] = status
            else:
                return blocked


def inputs(study, pool):
    full = set(study.graph)
    complements = read(OUTPUT / "flat-40-connectivity-complements.json")
    if complements["source"] != study.source or study.previous["source"] != study.source:
        raise ValueError("Mismatched Flat 40 lineage.")
    selected = set(complements["retained"])
    if (len(full) != 1534 or len(selected) != 628 or len(study.previous["repaired_ids"]) != 629
            or selected != set(study.previous["baseline_ids"])
            or set(study.previous["repaired_ids"]) != selected | {1212}
            or selected & study.regions[233] or 1212 not in study.regions[233]):
        raise ValueError("Unexpected certified starting pools.")
    return full if pool == "F" else selected | {1212}


def metrics(study, ids):
    ids = set(ids)
    return {"count": len(ids), "length": sum(study.length[i] for i in sorted(ids)),
            "intersection_pairs": sum(len(study.neighbors[i] & ids) for i in ids) // 2,
            "transverse_pairs": sum(len(study.transverse[i] & ids) for i in ids) // 2}


def check(study, ids):
    if not study.connected(ids) or any(ids.isdisjoint(group) for group in study.incidence):
        raise ValueError("Required strict region, doorway or graph connectivity is missing.")
    if any(not study.clear(i) for i in ids):
        raise ValueError("An exact line clearance check failed.")
    return study.full(ids)


def neutral_start(study):
    """Reach 629 lines by seeded deletion without using vertex or corridor scores."""
    initial = inputs(study, "F")
    if any(not study.clear(i) for i in initial):
        raise ValueError("Full-pool clearance failed during neutral thinning.")
    study.winding.rank(initial)
    order = sorted(initial)
    Random(40).shuffle(order)
    current = set(initial)
    counts = study.counts_for(current)
    trace = []
    for i in order:
        status, changes = study.validate(current, {i}, set(), counts)
        if status == "valid":
            current.remove(i)
            counts.update(changes)
            trace.append(i)
            if len(current) == 629:
                return current, trace
    raise ValueError("The neutral order did not reach a 629-line valid pool.")


def run(pool, orders=None, *, memoize=False):
    DEST.mkdir(exist_ok=True)
    for order in orders or (("shortest",) if pool == "N" else ORDERS):
        study = MemoizedStudy() if memoize else Study()
        start_path = DEST / f"{pool}-start.json"
        start_clock = monotonic()
        if pool == "N":
            initial, thinning = neutral_start(study)
        else:
            initial, thinning = inputs(study, pool), []
        if not start_path.exists():
            started = monotonic()
            winding = check(study, initial)
            start = {"pool": pool, "source": study.source, "ids": sorted(initial),
                     "ids_sha256": sha256(encode(sorted(initial))).hexdigest(),
                     "regions": len(study.regions), "doorways": len(study.doors),
                     "components": 1, "metrics": metrics(study, initial),
                     "winding": winding, "validation_seconds": monotonic() - started,
                     "neutral_thinning_deletions": thinning, "preparation_seconds": started-start_clock}
            atomic_write(start_path, encode(start))
            print(pool, "start verified", start["metrics"], flush=True)
        else:
            start = read(start_path)
            if start["ids"] != sorted(initial) or start["source"] != study.source:
                raise ValueError("The start certificate does not match the archived pool.")
        started = monotonic()
        for i in sorted(initial):
            if not study.clear(i):
                raise ValueError("An exact starting line clearance check failed.")
        dynamic = study.winding.rank(initial)
        if dynamic is not None and dynamic != study.winding.required:
            raise ValueError("Exact dynamic and full start winding disagree.")
        warmup = monotonic() - started
        study.counts.clear()
        study.timings.clear()
        current = set(initial)
        trace = []
        started = monotonic()
        blocked = study.reduce(current, order, trace)
        direct_time = monotonic() - started
        direct_ids = sorted(current)
        direct_winding = check(study, current)
        print(pool, order, "direct", len(current), round(direct_time, 2), flush=True)
        exchange_started = monotonic()
        exchanges = study.exchange(current, order)
        final_blocked = study.reduce(current, order, [])
        exchange_time = monotonic() - exchange_started
        final_winding = direct_winding if sorted(current) == direct_ids else check(study, current)
        atomic_write(DEST / f"{pool}-{order}.json", encode({
            "pool": pool, "order": order, "source": study.source, "deletions": trace,
            "direct_ids": direct_ids, "direct": metrics(study, direct_ids),
            "direct_winding": direct_winding, "direct_blockers": blocked,
            "proposals": dict(study.counts), "validator_seconds": dict(study.timings),
            "warmup_seconds": warmup, "deletion_seconds": direct_time,
            "exchange_seconds": exchange_time, "elapsed_seconds": monotonic()-started,
            "exchange_budget_per_type": BUDGET, "exchange_round_limit": ROUNDS, "memoized_rejections": memoize,
            "exchanges": exchanges, "final_ids": sorted(current), "final": metrics(study, current),
            "final_winding": final_winding, "final_blockers": final_blocked,
            "outside_start_final": sorted(current - initial),
        }))
        print(pool, order, "exchange", len(current), round(exchange_time, 2), flush=True)


def routes():
    study = Study()
    def map_items():
        # The established evaluator constructs its shared exact network before
        # requesting the maps, so this can overlap independent structural runs.
        names = [f"{p}-{o}" for p in ("F", "C") for o in ORDERS] + ["N-shortest"]
        deadline = monotonic() + 480
        while not all((DEST / f"{name}.json").is_file() for name in names):
            if monotonic() >= deadline:
                raise TimeoutError("The matched structural runs have not finished.")
            sleep(3)
        methods = {}
        for name in names:
            record = read(DEST / f"{name}.json")
            methods[name] = {"maps": {"direct": record["direct_ids"], "exchange": record["final_ids"]}}
        methods["controls"] = {"maps": {
            "algorithm_d": read(ROOT / "flat-40/D.json")["maps"]["exchanged"],
            "complementary_start": sorted(inputs(study, "C")),
        }}
        return methods.items()

    raw = evaluate(study.inputs, study.lines, study.clearance, study.reference,
                   SimpleNamespace(items=map_items))
    raw["full_pool_reference"] = {k: mean(study.reference[k]) for k in ("angular", "metric")}
    atomic_write(DEST / "movement.json", encode(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("F", "C", "N", "routes"))
    parser.add_argument("--order", choices=ORDERS, action="append")
    parser.add_argument("--memoize", action="store_true")
    args = parser.parse_args()
    routes() if args.phase == "routes" else run(args.phase, args.order, memoize=args.memoize)


if __name__ == "__main__":
    main()
