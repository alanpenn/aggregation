"""Matched-budget Flat 40 replay with committed extension approaches."""
import argparse
from pathlib import Path

from experiments.committed_extension_turns import CommittedCrawler
from experiments.directed_boundary_reference import LOW, UP
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_face_extension import load_inputs
from experiments.flat40_oriented_crawler import Replay
from experiments.flat40_crawler_atlas import read
from experiments.flat40_region257_inspection import packed
from experiments.oriented_extension_reference import BLOCKS, DOMAIN, L_ROOM, TARGET, at_junction
from shapely.geometry import box
from shapely.ops import unary_union
from voronoi_app.batch_store import encode
from voronoi_app.research_data import sha256_file

NEW_BLOCKS=BLOCKS|{"E":box(7.75,4,8,4.5)}
FRAME=box(0,0,8,8)
NEW_DOMAIN=FRAME.difference(unary_union(list(NEW_BLOCKS.values())))
PREMATURE=((0,3),(7,3),(7,6),(0,6))
EXTENDED=((0,3),(7.75,3),(7.75,6),(0,6))


def fixtures():
    room=CommittedCrawler(L_ROOM).construct()[0]
    c=CommittedCrawler(DOMAIN,list(BLOCKS.items()))
    three=c.construct(BLOCKS)[0]
    n=CommittedCrawler(NEW_DOMAIN,list(NEW_BLOCKS.items()))
    four,reject=n.construct(NEW_BLOCKS)
    if (set(room)!={LOW,UP} or not exact_coverage(L_ROOM,room)["full_coverage"]
            or not exact_coverage(DOMAIN,three)["full_coverage"]
            or {p["sign"] for p in three[TARGET] if at_junction(p)}!={1,-1}
            or PREMATURE in four or EXTENDED not in four
            or not reject.get("turn_prohibited_during_commitment")
            or not exact_coverage(NEW_DOMAIN,four)["full_coverage"]):
        raise ValueError("Committed fixture validation failed.")
    return n,four,reject


def replay(manifest,previous,out):
    fixtures()
    s,_,_,_,occupied,domain,blocks=load_inputs(manifest)
    before=read(previous/"geometry.json")
    if before["input_lineage"]!=s.source:
        raise ValueError("Prior checkpoint belongs to another source.")
    crawler=CommittedCrawler(domain,blocks)
    job=Replay(crawler,occupied,out)
    if ([{"track":i,"interval":packed((a,b))} for i,a,b in job.states]!=before["directed_edges"]
        or {str(h):[job.ids[t] for k,t in crawler.starts() if h==k] for h in (1,-1)}!=before["start_ids"]):
        raise ValueError("Directed geometry or global starts differ from the earlier replay.")
    local_before=previous/"local-257-schedule"/"start-schedule.json"
    local_order=read(local_before)
    out.mkdir(parents=True,exist_ok=False)
    (out/"geometry.json").write_bytes((previous/"geometry.json").read_bytes())
    (out/"commitment-metadata.json").write_bytes(encode({
        "source_geometry_sha256":sha256_file(previous/"geometry.json"),
        "local_start_schedule_sha256":sha256_file(local_before),
        "commitment_code_sha256":sha256_file(Path(__file__).with_name("committed_extension_turns.py")),
        "global_budget_per_hand":12000,"local_budget_per_hand":6000,
        "state_phases":[{"phase":p,"destination_face":f} for p,f in map(crawler.phase,job.states)]}))
    for _ in range(12):
        for hand in (1,-1):
            v=job.batch(hand,1000)
            print("global",hand,v["origin"],v["popped"],flush=True)
    local=out/"local-257-schedule"
    local.mkdir()
    (local/"start-schedule.json").write_bytes(local_before.read_bytes())
    crawler.starts=lambda:[(h,job.states[i]) for h in (1,-1) for i in local_order[str(h)]]
    work=Replay(crawler,occupied,local)
    for _ in range(6):
        for hand in (1,-1):
            v=work.batch(hand,1000)
            print("local",hand,v["origin"],v["popped"],flush=True)


if __name__=="__main__":
    import sys
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","previous","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    replay(a.manifest,a.previous,a.output)
