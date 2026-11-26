"""Settlement-keyed adapter for the exact face-committed crawler."""
from fractions import Fraction
import fcntl
import gzip
from hashlib import sha256
import json
from pathlib import Path

from shapely import from_wkb

from experiments.external_committed_crawler import ExternalCommittedCrawler
from experiments.flat40_convex_enlargement import Checker, edge_attempts, edges
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_enlarged_cover import blocked_facets
from experiments.flat40_face_extension import points
from experiments.flat40_oriented_crawler import Replay
from experiments.flat40_region257_inspection import packed
from voronoi_app import angular, batch_methods, experimental_circulation_topology
from voronoi_app.batch_methods import _domain, derive_topology
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.complementary_axial import settlement_key
from voronoi_app.research_data import sha256_file

METHOD = "Maximal overlapping convex regions (directed face-extension crawler)"
LEGACY = "Convex regions (experimental)"
CELLS = "Voronoi cells"


def cover_key(snapshot):
    root = Path(__file__).resolve().parent
    files = ("live_maximal_cover.py", "external_committed_crawler.py", "committed_extension_turns.py",
             "oriented_extension_turns.py", "directed_boundary_cover.py", "flat40_oriented_crawler.py",
             "flat40_directed_boundary.py", "face_extension_cover.py", "flat40_enlarged_cover.py",
             "flat40_convex_enlargement.py")
    dependencies = [root / name for name in files]
    dependencies.extend(Path(module.__file__) for module in
                        (angular, batch_methods, experimental_circulation_topology))
    return settlement_key(snapshot, ":".join(sha256_file(path) for path in dependencies))


def checkpoint_path(snapshot, directory):
    return directory / cover_key(snapshot)


def read_checkpoint(snapshot, directory):
    path = checkpoint_path(snapshot, directory) / "cover.json"
    if path.is_file():
        record = json.loads(path.read_bytes())
        if record["key"] != path.parent.name:
            raise ValueError("Checkpoint belongs to another settlement or crawler version.")
        return record
    return None


def census(replay):
    polygons = set()
    progress = []
    rejected = 0
    for sign, hand in ((1, "right"), (-1, "left")):
        count = sum(h == sign for h, _ in replay.crawler.starts())
        latest = {"origin": 0, "total_origins": count, "complete": count == 0, "popped": 0}
        for path in sorted((replay.out / hand).glob("*.json.gz")):
            with gzip.open(path, "rb") as stream:
                batch = json.load(stream)
            latest = batch["after"]
            for row in batch["records"]:
                rejected += sum(row["rejections"].values())
                polygons.update(tuple(tuple(map(Fraction, p)) for p in r["vertices"]) for r in row["closed"])
        progress.append(latest)
    return polygons, progress, rejected


def advance_cover(snapshot, directory, budget):
    if budget < 1:
        raise ValueError("The checkpoint budget must be positive.")
    target = checkpoint_path(snapshot, directory)
    target.mkdir(parents=True, exist_ok=True)
    with (target / "writer.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another local session is advancing this checkpoint.") from error
        return advance_locked(snapshot, target, budget)


def advance_locked(snapshot, target, budget):
    saved = read_checkpoint(snapshot, target.parent)
    if saved and saved["enumeration_complete"]:
        return saved
    inputs = {"settlement": snapshot}
    inputs["topology"] = derive_topology(inputs, {}).output
    _, occupied, domain, _ = _domain(inputs)
    if domain.geom_type != "Polygon" or domain.is_empty:
        raise ValueError("The directed crawler requires one connected polygonal accessible domain.")
    blocks = []
    for name, wkb in sorted(inputs["topology"]["blocks_wkb"].items()):
        block = from_wkb(wkb)
        blocks.extend((name, part) for part in getattr(block, "geoms", [block]) if part.geom_type == "Polygon")
    replay = Replay(ExternalCommittedCrawler(domain, blocks), occupied, target)
    replay.batch(1, budget)
    replay.batch(-1, budget)
    polygons, progress, rejected = census(replay)
    complete = all(p["complete"] for p in progress)
    record = {"key": target.name, "enumeration_complete": complete, "ready": False,
              "progress": progress, "distinct": len(polygons), "rejected_transitions": rejected}
    if complete:
        checker = Checker(domain, occupied)
        certified = {}
        unresolved = 0
        nonmaximal = 0
        for polygon in sorted(polygons):
            if not checker.witness([], polygon, independent=True):
                raise ValueError("An accepted circuit failed independent geometry validation.")
            proof = blocked_facets(checker, polygon)
            vertices = packed(polygon)
            if proof:
                certified[sha256(encode(vertices)).hexdigest()] = {"vertices": vertices, "proof": proof}
            elif any((probe := edge_attempts(polygon, a, b, checker))
                     and checker.witness(polygon, points(probe), independent=True) for a, b in edges(polygon)):
                nonmaximal += 1
            else:
                unresolved += 1
        overlay = exact_coverage(domain, [points(row) for row in certified.values()])
        record.update(regions=certified, unresolved=unresolved, nonmaximal=nonmaximal,
                      maximum_overlap=max(map(int, overlay["area_by_count"])),
                      coverage=overlay["covered_percent"], uncovered_area=overlay["uncovered_area"],
                      ready=overlay["full_coverage"] and not unresolved)
    atomic_write(target / "cover.json", encode(record))
    return record
