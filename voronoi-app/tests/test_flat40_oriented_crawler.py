import gzip
import json
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.flat40_oriented_crawler import Replay
from experiments.oriented_extension_reference import BLOCKS, DOMAIN
from experiments.oriented_extension_turns import ExtensionCrawler
from voronoi_app.batch_store import encode


def journal(path, side):
    rows=[]
    last=None
    for f in sorted((path/side).glob("*.gz")):
        with gzip.open(f,"rb") as stream:
            batch=json.load(stream)
        rows.extend(batch["records"])
        last=batch["after"]
    return rows,last


def test_checkpoint_inside_a_start_replays_the_same_branches(tmp_path):
    one,two=tmp_path/"one",tmp_path/"two"
    one.mkdir()
    two.mkdir()
    a=Replay(ExtensionCrawler(DOMAIN,list(BLOCKS.items())),BLOCKS,one)
    b=Replay(ExtensionCrawler(DOMAIN,list(BLOCKS.items())),BLOCKS,two)
    for sign in (1,-1):
        a.batch(sign,260)
        b.batch(sign,73)
        b.batch(sign,187)
    assert journal(one,"right")==journal(two,"right")
    assert journal(one,"left")==journal(two,"left")


def test_flat40_saved_checkpoint_geometry_and_paths():
    root=Path("diagnostics/strict-generalisation/directed-face-convex-flat40-1")
    if not (root/"regions.json").is_file():
        pytest.skip("Run the Flat 40 replay before checking its saved artifacts.")
    a=json.loads((root/"geometry.json").read_bytes())
    r=json.loads((root/"regions.json").read_bytes())
    c=json.loads((root/"coverage.json").read_bytes())
    assert a["start_ids"]["1"] and a["start_ids"]["-1"]
    assert len(a["faces"])==496
    for face in a["faces"]:
        x,y=tuple(map(F,face["endpoints"][0]))
        X,Y=tuple(map(F,face["endpoints"][1]))
        assert tuple(map(F,face["outward_normal"]))==(y-Y,X-x)
    for key,p in r["regions"].items():
        assert sha256(encode(p["vertices"])).hexdigest()[:16]==key
        assert p["paths"] and p["physical_support_faces"]
        assert p["validation"]["convex"] and p["validation"]["contained"]
        assert not p["validation"]["occupied_interior_or_island"]
    assert any(path["turns_at_extensions"] for p in r["regions"].values() for path in p["paths"])
    assert F(c["covered_area"])+F(c["uncovered_area"])==F(c["domain_area"])
    assert sum(F(v) for v in c["area_by_count"].values())==F(c["domain_area"])
