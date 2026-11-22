"""Build an experimental all-line map from projected building-block faces and corners."""

import argparse
import json
from pathlib import Path

from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.exact_enumeration import exact_pool_to_dict
from voronoi_app.experimental_projected_faces import (
    block_rings as block_rings,
    generate_projected_face_all_lines,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    opened, buildings, _, _, _ = load_axial_snapshot(json.loads(args.snapshot.read_text()))
    pool, audit = generate_projected_face_all_lines(opened, buildings)
    with args.output.open("x") as stream:
        json.dump({"pool": exact_pool_to_dict(pool), "audit": audit}, stream, indent=2)
        stream.write("\n")
    print({key: value for key, value in audit.items()
           if key not in {"projections", "uncovered_convex_regions"}})


if __name__ == "__main__":
    main()
