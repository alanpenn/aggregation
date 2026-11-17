"""Compute fixed-terminal full-network angular depths for the Valley experiment."""

import argparse
import json
import time
from fractions import Fraction
from pathlib import Path

from voronoi_app.angular import SampleAttachment
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_angular_selection import angular_reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--turn-penalty", type=float, default=0.0)
    parser.add_argument("--output", default="reference.json")
    args = parser.parse_args()
    data = json.loads((args.data_dir / "prepared.json").read_text())
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    attachments = [SampleAttachment(tuple(map(Fraction, item["sample"])),
                                    tuple(map(Fraction, item["point"])), item["line_id"])
                   for item in data["attachments"]]
    components = [item["component"] for item in data["attachments"]]
    print("routing", len(lines), "candidates", len(attachments), "fixed samples", flush=True)
    started = time.monotonic()
    result = angular_reference(lines, attachments, components,
                               witness_turn_penalty=args.turn_penalty)
    output = {"depths": [[a, b, d] for (a, b), d in sorted(result.depths.items())],
              "witness_lines": sorted(result.witness_lines),
              "seconds": time.monotonic() - started, "turn_penalty": args.turn_penalty}
    with (args.data_dir / args.output).open("x") as file:
        json.dump(output, file, allow_nan=False)
    print("reference pairs", len(result.depths), "witness lines", len(result.witness_lines),
          "seconds", round(output["seconds"], 2), flush=True)


if __name__ == "__main__":
    main()
