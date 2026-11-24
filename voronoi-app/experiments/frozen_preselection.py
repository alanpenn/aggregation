"""Controlled Flat 40 benchmark with frozen shortest and sheaf priorities."""
import argparse
from hashlib import sha256
from itertools import combinations
from fractions import Fraction
from statistics import mean
from time import monotonic

from experiments.constructive_axial import evaluate
from experiments.controlled_preselection import Study, DEST as PREVIOUS, check, inputs, metrics
from experiments.occupied_vertex_pruning import OUTPUT, boundary_index, read
from experiments.unrestricted_axial_reduction import BUDGET, ROUNDS, DEST as UNRESTRICTED
from experiments.vertex_connectivity_complements import axial_angle
from voronoi_app.batch_methods import _settlement
from voronoi_app.batch_store import atomic_write, encode
from experiments.strict_generalisation import rss_mib

DEST = OUTPUT.parent / "frozen-preselection-1"
CASES = ("F-S", "C-S", "F-H", "C-H")
ORDERS = {"S": "shortest", "H": "sheaf"}


def save(name, data):
    atomic_write(DEST / f"{name}.json", encode(data))


def hash_data(value):
    return sha256(encode(value)).hexdigest()


def blockers(study, selected, rejected):
    if set(rejected) != selected or "valid" in rejected.values():
        raise ValueError("The final deletion sweep did not cover every line.")
    rows = {}
    for i, reason in rejected.items():
        others = selected-{i}
        rows[i] = {"reason": reason,
                   "regions": [r for r, ids in study.regions.items() if others.isdisjoint(ids)],
                   "doorways": [d for d, ids in enumerate(study.doors) if others.isdisjoint(ids)],
                   "connected": study.connected(others),
                   "winding_rank": study.winding.rank(others) if reason == "winding" else None}
    return rows


def profile_preselection(study):
    started = monotonic()
    polygons, _, _ = _settlement(study.inputs)
    labels = {int(i): v for i,v in study.inputs["settlement"]["building_labels"].items()}
    vertices, support, _ = boundary_index(study.inputs["topology"],polygons,labels,study.lines)
    directions = [(line.end[0]-line.start[0],line.end[1]-line.start[1]) for line in study.lines]
    lengths = [sum(v*v for v in d) for d in directions]
    def score(pair):
        i,j=pair
        a,b=study.neighbors[i],study.neighbors[j]
        distance=Fraction(len(a^b),len(a|b)) if a|b else Fraction(0)
        return (min(len(a),len(b))*(1+distance)/2,axial_angle(directions[i],directions[j]),
                len(a)+len(b),lengths[i]+lengths[j],-i,-j)
    reconstructed=set(study.graph)-support.keys()
    for vertex in vertices:
        candidates=vertex["supported"]
        reconstructed.update(max(combinations(sorted(candidates),2),key=score)
                             if len(candidates)>1 else candidates)
    profiles = read(OUTPUT/"flat-40-connectivity-complements.json")
    if reconstructed!=set(profiles["retained"]):
        raise ValueError("Complementary preselection failed the timed reconstruction check.")
    repaired=reconstructed|{1212}
    if repaired!=inputs(study,"C"):
        raise ValueError("Reconstructed repair does not match C.")
    save("preselection-profile",{"ids_sha256":hash_data(sorted(repaired)),
         "reconstruct_seconds":monotonic()-started,"peak_rss_mib":rss_mib()})


def run(case, phase):
    if (DEST/f"{case}-{phase}.json").exists():
        return
    overall=monotonic()
    study=Study()
    start_clock=monotonic()
    initial=inputs(study,case[0])
    retrieve=monotonic()-start_clock
    baseline=read(PREVIOUS/f"{case[0]}-start.json")
    if baseline["source"]!=study.source or baseline["ids"]!=sorted(initial):
        raise ValueError("Independent archived start certificate differs from frozen inputs.")
    order=ORDERS[case[2]]
    configuration={"order":order,"start_sha256":hash_data(sorted(initial)),
                   "frozen_sheaf_sha256":hash_data(study.previous["sheaves"]),
                   "exchange_budget":BUDGET,"exchange_rounds":ROUNDS,
                   "algorithm_sha256":{module:sha256((__import__("pathlib").Path(__file__).with_name(module)).read_bytes()).hexdigest()
                                       for module in ("frozen_preselection.py","controlled_preselection.py","unrestricted_axial_reduction.py","dynamic_winding.py")}}
    start_path=DEST/f"{case[0]}-start.json"
    if not start_path.exists():
        save(f"{case[0]}-start",baseline)
    if phase=="direct":
        current=set(initial)
    else:
        if not all((DEST/f"{key}-direct.json").exists() for key in CASES):
            raise ValueError("Complete every direct map before exchanging any map.")
        prior=read(DEST/f"{case}-direct.json")
        current=set(prior["ids"])
    if any(not study.clear(i) for i in sorted(current)):
        raise ValueError("Starting exact clearance failed.")
    if study.winding.rank(current) not in (24,None):
        raise ValueError("Starting dynamic winding rank failed.")
    warmed=monotonic()
    study.counts.clear()
    study.timings.clear()
    trace=[]
    if phase=="direct":
        rejected=study.reduce(current,order,trace)
        exchanges=[]
    else:
        exchanges=study.exchange(current,order)
        rejected=study.reduce(current,order,trace)
    search_time=monotonic()-warmed
    certificate=check(study,current)
    construction=monotonic()-overall
    if case.startswith("C"):
        archived=read(UNRESTRICTED/f"{order}.json")
        expected=archived["direct_ids" if phase=="direct" else "final_ids"]
        if sorted(current)!=expected:
            raise ValueError(f"{case} {phase} differs from the archived result.")
        if phase=="direct" and trace!=archived["deletions"]:
            raise ValueError(f"{case} direct trace differs from the archived result.")
    save(f"{case}-{phase}",{"name":case,"phase":phase,"source":study.source,"configuration":configuration,
         "configuration_sha256":hash_data(configuration),"starting_count":len(initial),
         "ids":sorted(current),"metrics":metrics(study,current),"deletions":trace,"exchanges":exchanges,
         "strict_regions":sorted(study.regions),"doorway_building_labels":[
             study.inputs["settlement"]["building_labels"][str(door["building_cell"])]
             for door in study.inputs["analysis"]["doorways"]],
         "components":1,"winding":certificate,"blockers":blockers(study,current,rejected),
         "counts":dict(study.counts),"validator_seconds":dict(study.timings),
         "retrieval_seconds":retrieve,"search_seconds":search_time,"construction_seconds":construction,
         "peak_rss_mib":rss_mib()})
    print(case,phase,len(current),round(search_time,2),flush=True)


def routes():
    study=Study()
    maps={case:{"maps":{phase:read(DEST/f"{case}-{phase}.json")["ids"]
                       for phase in ("direct","exchange")}} for case in CASES}
    result=evaluate(study.inputs,study.lines,study.clearance,study.reference,maps)
    result["full_pool_reference"]={name:mean(study.reference[name]) for name in ("angular","metric")}
    save("movement",result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("direct","exchange","profile","routes"))
    parser.add_argument("--case",choices=CASES)
    args=parser.parse_args()
    DEST.mkdir(exist_ok=True)
    if args.phase=="routes":
        routes()
    elif args.phase=="profile":
        profile_preselection(Study())
    else:
        run(args.case,args.phase)


if __name__=="__main__":
    main()
