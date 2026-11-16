import argparse
import json
import time
from fractions import Fraction
from pathlib import Path

from voronoi_app.angular import SampleAttachment
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_angular_selection import angular_reference


parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--witness-turn-penalty", type=float, default=0.0)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
state = args.data_dir
prepared = json.loads((state / "angular-hill-prepared.json").read_text())
lines = []
for i, record in enumerate(prepared["records"]):
    source = record["baseline"] or record["boundary"][0]
    start = tuple(map(Fraction, source["start"]))
    end = tuple(map(Fraction, source["end"]))
    lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
attachments = [
    SampleAttachment(tuple(map(Fraction, item["sample"])),
                     tuple(map(Fraction, item["point"])), item["line_id"])
    for item in prepared["attachments"]
]
components = [item["component"] for item in prepared["attachments"]]
print("begin full routing", len(lines), len(attachments), flush=True)
started = time.monotonic()
result = angular_reference(lines, attachments, components,
                           witness_turn_penalty=args.witness_turn_penalty)
output = {
    "depths": [[a, b, depth] for (a, b), depth in sorted(result.depths.items())],
    "witness_lines": sorted(result.witness_lines),
    "seconds": time.monotonic() - started,
    "witness_turn_penalty": args.witness_turn_penalty,
}
filename = (args.output if args.output is not None else
            Path("angular-hill-heuristic.json" if args.witness_turn_penalty
                 else "angular-hill-reference.json"))
(state / filename).write_text(json.dumps(output, allow_nan=False))
print("finished", "pairs", len(result.depths), "witnesses", len(result.witness_lines),
      "seconds", round(output["seconds"], 2), flush=True)
