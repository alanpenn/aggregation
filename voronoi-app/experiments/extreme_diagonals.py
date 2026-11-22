"""Run the extreme-diagonal corridor comparison."""
import argparse
import json
import os
from pathlib import Path

from voronoi_app.batch_store import BatchStore, encode


ROOT = Path("diagnostics/preserved-axial-benchmark")
PILOT = ROOT / "route-sparse" / "pilot-2"
OUT = Path(os.environ.get("EXTREME_DIAGONAL_OUTPUT", ROOT / "extreme-diagonals" / "pilot-1"))
LIMITS = {"corridor_limit": 3, "pair_shortlist": 8, "repair_shortlist": 10, "repair_limit": 2}


def run(case):
    store = BatchStore(ROOT)
    if case in ("Hill-42", "Y-42"):
        prior = json.loads((PILOT / f"{case}-sparse_routes.json").read_text())["record"]
        record, _, stamp = store.load(prior)
        if record["status"] != "successful":
            raise ValueError("Expected successful sparse-routing record.")
        params = {**record["parameters"], **LIMITS, "sparse_record": prior, "sparse_sha256": stamp}
        stage, parent = "validation", record["parent"]["id"]
        method = "voronoi_app.extreme_diagonal_experiment:preserved"
    else:
        params = {"fixture": case, **LIMITS}
        stage, parent = "settlement", None
        method = "voronoi_app.extreme_diagonal_synthetic:synthetic"
    OUT.mkdir(exist_ok=True, parents=True)
    journal = OUT/f"{case}.json"
    if journal.exists():
        raise FileExistsError(journal)
    result = store.run(stage, method, "1", params, parent)
    with journal.open("xb") as stream:
        stream.write(encode({"record": result["id"], "status": result["status"],
                             "error": result.get("error")}))
    print(case, result["status"], result.get("error"), flush=True)
    return int(result["status"] != "successful")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    return run(parser.parse_args().case)


if __name__ == "__main__":
    raise SystemExit(main())
