from fractions import Fraction as F

from shapely.geometry import box

from experiments.committed_extension_reference import example
from experiments.committed_extension_turns import CommittedCrawler
from experiments.flat40_committed_replay import fixtures
from experiments.oriented_extension_turns import Track


def test_reference_geometries_still_cover():
    crawler,regions,rejections=fixtures()
    assert len(regions)==8
    assert rejections["turn_prohibited_during_commitment"]>0
    assert crawler.faces


def test_premature_closure_is_rejected_and_mirrored_approaches_arrive():
    for sign in (1,-1):
        r=example(sign)
        c=r["crawler"]
        assert c.phase(r["incoming"])==("committed",r["destination"])
        assert c.phase(r["accepted_turn"][1])==("committed",r["destination"])
        assert r["small"] not in r["regions"] and r["large"] in r["regions"]


def test_blocked_approach_records_exact_boundary_failure():
    block=box(2,2,4,4)
    domain=box(0,0,6,6).difference(block)
    c=CommittedCrawler(domain,[("block",block)])
    face=next(f for f in c.faces if f.blocks)
    track_id=len(c.tracks)
    c.tracks.append(Track(track_id,face.identifier,(F(2),F(3)),(F(5),F(3)),False,1))
    assert c.approach_failure(track_id,(F(5),F(3)))=="blocked_approach_intervening_physical_boundary"


def test_saved_flat40_arrivals_obey_the_exact_destination_when_available():
    import json
    from pathlib import Path
    import pytest

    root=Path("diagnostics/strict-generalisation/flat40-committed-extension-1")
    if not (root/"regions.json").is_file():
        pytest.skip("Run the matched Flat 40 experiment before checking its outputs.")
    def read(name):
        return json.loads((root/name).read_bytes())

    geometry=read("geometry.json")
    metadata=read("commitment-metadata.json")
    paths=read("regions.json")["regions"]
    tracks={t["id"]:t for t in geometry["tracks"]}
    edges=geometry["directed_edges"]
    phases=metadata["state_phases"]
    count=0
    for shape in paths.values():
        for route in shape["paths"]:
            for before,after,action,_ in route["transitions"]:
                phase=phases[before]
                if phase["phase"]!="committed":
                    continue
                count+=1
                current=edges[before]
                track=tracks[current["track"]]
                assert action!="turn_towards_originating_face"
                if current["interval"][1]==track["interval"][0]:
                    assert action=="follow_physical_face"
                    assert tracks[edges[after]["track"]]["face"]==phase["destination_face"]
                else:
                    assert action=="straight"
                    assert current["track"]==edges[after]["track"]
                    assert phases[after]==phase
    assert count>0
