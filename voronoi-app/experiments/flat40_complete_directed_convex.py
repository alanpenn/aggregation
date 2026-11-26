"""Systematic, versioned checkpoint of external-wall committed Flat 40 walks."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys

from experiments.external_committed_crawler import ExternalCommittedCrawler
from experiments.flat40_face_extension import load_inputs
from experiments.flat40_oriented_crawler import Replay
from experiments.flat40_region257_inspection import packed
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.research_data import sha256_file


HANDS = ((1, "right"), (-1, "left"))


def checkpoint(path, data):
    atomic_write(path, gzip.compress(encode(data), mtime=0))


def advance(replay, hand, initial, directory, budget):
    directory.mkdir(parents=True, exist_ok=True)
    batches = sorted(directory.glob("*.json.gz"))
    after = {"stack": None, "prefixes": 0, "closures": 0, "complete": False}
    if batches:
        with gzip.open(batches[-1], "rb") as stream:
            after = json.load(stream)["after"]
    if after["complete"] or not budget:
        return after
    stack = replay.load_stack(after["stack"]) if after["stack"] else None
    rows = []
    pending = []
    for route, options, closed, rejections, pending in replay.crawler.traverse(
            initial, hand, replay.occupied, stack):
        records = []
        for polygon, path in closed:
            vertices = packed(polygon)
            records.append({
                "id": sha256(encode(vertices)).hexdigest(), "vertices": vertices,
                "points": path["points"],
                "turns_at_extensions": sum(t[2] == "turn_towards_originating_face"
                                           for t in path["transitions"]),
                "transitions": [[replay.ids[a], replay.ids[b], action, replay.encode_options(opts)]
                                for a, b, action, opts in path["transitions"]],
            })
        rows.append({"path": [replay.ids[t] for t in route],
                     "outgoing": replay.encode_options(options), "closed": records,
                     "rejections": dict(rejections)})
        if len(rows) == budget:
            break
    result = {"stack": replay.save_stack(pending), "complete": not pending,
              "prefixes": after["prefixes"] + len(rows),
              "closures": after["closures"] + sum(len(row["closed"]) for row in rows)}
    checkpoint(directory / f"{len(batches):06d}.json.gz", {"after": result, "records": rows})
    return result


def frame(face):
    return any(face.a[i] == face.b[i] == edge for i in (0, 1) for edge in (0, 100))


def setup(manifest, out):
    study, ch, _, provenance, occupied, domain, blocks = load_inputs(manifest)
    crawler = ExternalCommittedCrawler(domain, blocks, external_boundary=frame)
    replay = Replay(crawler, occupied, out)
    faces = [f.record() | {"source": "external" if f.identifier in crawler.external else "building",
                           "accessible_normal": packed(((-(f.b[1]-f.a[1]), f.b[0]-f.a[0]),))[0]}
             for f in crawler.faces]
    schedule = {side: [s for h, s in crawler.starts() if h == sign] for sign, side in HANDS}
    network = {"inputs": provenance, "faces": faces,
               "code": {name: sha256_file(Path(__file__).with_name(name)) for name in
                        ("flat40_complete_directed_convex.py", "external_committed_crawler.py",
                         "committed_extension_turns.py", "oriented_extension_turns.py",
                         "directed_boundary_cover.py", "flat40_oriented_crawler.py")},
               "tracks": [{"face": t.face, "physical": t.wall, "segment": packed((t.a, t.b)),
                           "away_sign": t.away_sign} for t in crawler.tracks],
               "directed_edges": [{"track": t, "segment": packed((a, b)),
                                   "phase": crawler.phase((t, a, b))}
                                  for t, a, b in replay.states],
               "starts": {side: [replay.ids[t] for t in ss] for side, ss in schedule.items()}}
    geometry = out / "geometry.json"
    if geometry.exists():
        if geometry.read_bytes() != encode(network):
            raise ValueError("Exact geometry, state inventory or code differs from this checkpoint.")
    else:
        out.mkdir(parents=True, exist_ok=False)
        atomic_write(geometry, encode(network))
    return study, ch, domain, replay, schedule


def run(replay, schedule, budget):
    summary = {}
    for hand, side in HANDS:
        by_face = {}
        for ordinal, origin in enumerate(schedule[side]):
            result = advance(replay, hand, origin, replay.out / side / f"{ordinal:05d}", budget)
            face = replay.crawler.tracks[origin[0]].face
            by_face.setdefault(face, []).append(result)
        origins = [s for group in by_face.values() for s in group]
        summary[side] = {
            "physical_faces": len(by_face),
            "completed_faces": sorted(f for f, rows in by_face.items() if all(r["complete"] for r in rows)),
            "faces_without_closure": sorted(f for f, rows in by_face.items()
                                            if all(r["complete"] and not r["closures"] for r in rows)),
            "pending_faces": sorted(f for f, rows in by_face.items() if any(not r["complete"] for r in rows)),
            "origin_count": len(origins), "started_origins": sum(s["prefixes"] > 0 for s in origins),
            "completed_origins": sum(s["complete"] for s in origins),
            "pending_stack_entries": sum(len(s["stack"] or []) for s in origins),
            "prefixes": sum(s["prefixes"] for s in origins),
            "origins_without_closure": sum(s["complete"] and not s["closures"] for s in origins),
        }
    atomic_write(replay.out / "progress.json", encode(summary))
    print({hand: {k: len(v) if isinstance(v, list) else v for k, v in row.items()}
           for hand, row in summary.items()}, flush=True)


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefixes-per-origin", type=int, required=True)
    args = parser.parse_args()
    if args.prefixes_per_origin < 1:
        parser.error("Use a positive explicit per-origin checkpoint budget.")
    _, _, _, replay, schedule = setup(args.manifest, args.output)
    print(len(replay.crawler.faces), len(replay.crawler.external), len(replay.states),
          {k: len(v) for k, v in schedule.items()}, flush=True)
    run(replay, schedule, args.prefixes_per_origin)


if __name__ == "__main__":
    main()
