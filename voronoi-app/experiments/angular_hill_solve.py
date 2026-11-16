import argparse
import json
import math
import time
from fractions import Fraction
from pathlib import Path

from voronoi_app.angular import SampleAttachment
from voronoi_app.exact_axial import ExactCandidate, closed_routes
from voronoi_app.experimental_angular_selection import AngularResult, optimise_fidelity


parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--attempts", type=int, default=2)
parser.add_argument("--heuristic", action="store_true",
                    help="Seed with penalised shortest-path witnesses, then validate unpenalised costs")
parser.add_argument("--heuristic-input", type=Path, default=Path("angular-hill-heuristic.json"))
parser.add_argument("--output", type=Path, help="Override the result filename within the data directory")
parser.add_argument("--epsilon", type=float, nargs="*",
                    default=[0, 0.02, 0.05, 0.10, 0.20, 0.50])
args = parser.parse_args()
state = args.data_dir
prepared = json.loads((state / "angular-hill-prepared.json").read_text())
raw_reference = json.loads((state / "angular-hill-reference.json").read_text())
lines = []
for i, record in enumerate(prepared["records"]):
    source = record["baseline"] or record["boundary"][0]
    start = tuple(map(Fraction, source["start"]))
    end = tuple(map(Fraction, source["end"]))
    lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
attachments = [SampleAttachment(tuple(map(Fraction, item["sample"])),
                                tuple(map(Fraction, item["point"])), item["line_id"])
               for item in prepared["attachments"]]
sample_components = [item["component"] for item in prepared["attachments"]]
groups = [{i for i, value in enumerate(prepared["components"]) if value == component}
          for component in range(len(set(prepared["components"])))]
covers = [set(values) for values in prepared["covers"]]
targets = set(range(prepared["regions"]))
obstacles = prepared["obstacles"]
reference = AngularResult({(a, b): d for a, b, d in raw_reference["depths"]},
                          frozenset(raw_reference["witness_lines"]))
heuristic = (json.loads((state / args.heuristic_input).read_text())
             if args.heuristic else None)
seed_witnesses = (set(heuristic["witness_lines"]) if heuristic is not None
                  else set(reference.witness_lines))
ring_seed = set(prepared["old_selected_in_pool"])
initial = ring_seed | seed_witnesses
started = time.monotonic()
ring_count = len(closed_routes([lines[i] for i in sorted(initial)], obstacles))
print("witness and historical seed", len(initial), "rings", ring_count,
      "seconds", round(time.monotonic() - started, 1), flush=True)
if ring_count != len(obstacles):
    ring_seed.update(prepared["ring_candidates"])
    print("added full boundary seed", len(ring_seed), flush=True)
results = []
for epsilon in args.epsilon:
    alternatives = []
    for reverse in (False, True):
        begin = time.monotonic()
        answer = optimise_fidelity(
            lines, covers, targets, groups, obstacles, attachments, sample_components,
            reference, epsilon, ring_seed, attempt_limit=args.attempts, reverse_order=reverse,
            seed_witnesses=seed_witnesses,
        )
        elapsed = time.monotonic() - begin
        differences = {pair: answer.depths[pair] - depth
                       for pair, depth in reference.depths.items() if math.isfinite(depth)}
        alternatives.append({
            "reverse": reverse, "selected": sorted(answer.selected),
            "attempted": answer.attempted, "accepted": answer.accepted,
            "seconds": elapsed,
            "mean_increase": sum(differences.values()) / len(differences),
            "max_increase": max(differences.values()),
            "increased_pairs": sum(value > 1e-10 for value in differences.values()),
            "differences": [[*pair, value] for pair, value in sorted(differences.items())],
            "length": sum(lines[i].length for i in answer.selected),
            "corridor_555": 555 in answer.selected,
            "candidate_592": 592 in answer.selected,
        })
        print("epsilon", epsilon, "reverse", reverse, "lines", len(answer.selected),
              "accepted", answer.accepted, "/", answer.attempted,
              "max_delta", alternatives[-1]["max_increase"], "seconds",
              round(elapsed, 2), flush=True)
    best = min(alternatives, key=lambda x: (len(x["selected"]), x["length"], x["selected"]))
    results.append({"epsilon": epsilon, "best": best, "alternatives": alternatives})
    filename = (args.output if args.output is not None else
                Path("angular-hill-heuristic-results.json" if args.heuristic
                     else "angular-hill-solve-results.json"))
    (state / filename).write_text(json.dumps(results, allow_nan=False))
