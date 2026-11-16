"""Compare saved, fully validated candidate subsets at each tolerance."""

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--inputs", type=Path, nargs="+", required=True)
args = parser.parse_args()
alternatives = []
for name in args.inputs:
    for result in json.loads((args.data_dir / name).read_text()):
        for candidate in result["alternatives"]:
            alternatives.append({**candidate, "source_file": str(name),
                                 "source_epsilon": result["epsilon"]})
output = []
for epsilon in (0, .02, .05, .1, .2, .5):
    eligible = [candidate for candidate in alternatives
                if candidate["max_increase"] <= epsilon + 1e-10]
    if not eligible:
        raise ValueError(f"No recorded feasible subset for epsilon {epsilon}")
    best = min(eligible, key=lambda x: (len(x["selected"]), x["length"], x["selected"]))
    output.append({"epsilon": epsilon, "best": best})
(args.data_dir / "angular-hill-final-results.json").write_text(json.dumps(output, allow_nan=False))
