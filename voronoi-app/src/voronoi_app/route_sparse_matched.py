"""Fixed-line-count exchange control for the route-efficient reduction pilot."""

from time import monotonic

from .batch_store import StageResult
from .route_sparse_experiment import MEASURES, SparseSearch


def matched_exchanges(inputs, parameters):
    started = monotonic()
    search = SparseSearch(inputs, parameters)
    original = search.archived["B"]
    if not search.structural(original):
        raise ValueError("Saved backward map failed structural validation.")
    start_cost = search.mean_excess(original)
    start_sample = search.mean_excess(original, True)
    state = original
    results = []

    def score(chosen, sampled):
        means = search.mean_excess(chosen, sampled)
        base = start_sample if sampled else start_cost
        return sum(x / a for x, a in zip(means, base, strict=True)), sorted(chosen)

    for round_number in range(parameters["exchange_rounds"]):
        added_maps = [state | {line} for line in sorted(search.start - state)]
        additions = sorted(added_maps, key=lambda chosen: score(chosen, True))[:parameters["addition_limit"]]
        candidates = set()
        for expanded in additions:
            new_line = next(iter(expanded - state))
            # Preserve length as a secondary economy measure when geometric ties arise.
            order = sorted(state, key=lambda i: (
                i in search.start, -search.network.lines[i].length, i,
            ))
            valid = 0
            for removed in order:
                trial = expanded - {removed}
                if search.structural(trial):
                    candidates.add(trial)
                    valid += 1
                    if valid >= parameters["removal_limit"]:
                        break
        ranked = sorted(candidates, key=lambda chosen: score(chosen, True))
        complete = ranked[:parameters["complete_shortlist"]]
        frontier = []
        previous = search.mean_excess(state)
        for chosen in complete:
            means = search.mean_excess(chosen)
            metrics = search.evaluate(chosen)
            if all(value <= old + 1e-9 for value, old in zip(means, previous, strict=True)) and any(
                value < old - 1e-9 for value, old in zip(means, previous, strict=True)
            ) and all(metrics[k]["cost"]["unreachable"] == 0 for k in MEASURES):
                frontier.append(chosen)
        if not frontier:
            break
        state = min(frontier, key=lambda chosen: score(chosen, False))
        print(parameters["case"], "matched-count exchange", round_number + 1,
              search.mean_excess(state), flush=True)
        results.append(search.report(state))
    return StageResult({"baseline": search.report(original), "improvements": results,
                        "complete_route_evaluations": len(search.complete),
                        "sampled_route_evaluations": len(search.sampled),
                        "seconds": monotonic() - started})
