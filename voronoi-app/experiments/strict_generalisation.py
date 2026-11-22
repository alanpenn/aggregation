"""Run the paired 40–45 strict axial generalisation experiment."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import resource
import sys
from time import monotonic, sleep

from voronoi_app.batch import run_stage
from voronoi_app.batch_store import BatchStore, atomic_write, encode

ROOT = Path("diagnostics/strict-generalisation/pilot-1")
PRESERVED = Path("diagnostics/preserved-axial-benchmark")
TERRAINS = {"hill":"7ed1bddef0af4543ac332ea44f79ce52",
            "converging_valleys":"a8a2376c11174ca8a74e5189216bdaa1"}
CASES = [(terrain,seed) for seed in range(40,46) for terrain in TERRAINS]


def case_path(root, terrain, seed):
    return root/"cases"/f"{terrain}-{seed}.json"


def rss_mib():
    size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return size/(1024**2 if sys.platform=="darwin" else 1024)


def prepare(root, terrain, seed):
    path = case_path(root,terrain,seed)
    if path.exists():
        raise FileExistsError(path)
    original = BatchStore(PRESERVED)
    reference, data, checksum = original.load(TERRAINS[terrain])
    configuration = data["configuration"] | {"seed":seed}
    journal = {"case":path.stem,"terrain":terrain,"seed":seed,"configuration":configuration,
               "configuration_source":reference["id"],"configuration_sha256":checksum,"stages":{}}
    path.parent.mkdir(parents=True,exist_ok=True)
    store = BatchStore(root)
    parent = None
    for stage, method in (("settlement","generate-settlement"),("topology","main-open-topology"),
                          ("candidates","fresh-exact")):
        started = monotonic()
        rec = run_stage(store,stage,method,configuration if stage=="settlement" else {},parent)
        parent = rec["id"]
        journal["stages"][stage] = {"record":parent,"status":rec["status"],"seconds":monotonic()-started,
                                    "peak_rss_mib":rss_mib(),"error":rec.get("error")}
        atomic_write(path,encode(journal))
        print(path.stem,stage,rec["status"],flush=True)
        if rec["status"]!="successful":
            break


def analyze(root, terrain, seed):
    path=case_path(root,terrain,seed)
    marker=root/"analysis-workers"/path.stem
    marker.parent.mkdir(parents=True,exist_ok=True)
    while True:
        try:
            marker.mkdir()
            break
        except FileExistsError:
            sleep(5)
    try:
        analyze_case(root,terrain,seed)
    finally:
        marker.rmdir()


def analyze_case(root, terrain, seed):
    path = case_path(root,terrain,seed)
    while True:
        if path.exists():
            journal=json.loads(path.read_text())
            stages=journal["stages"]
            if "candidates" in stages or any(x["status"]!="successful" for x in stages.values()):
                break
        sleep(5)
    if "analysis" in journal["stages"]:
        previous=journal["stages"]["analysis"]
        manifest=BatchStore(root).load(previous["record"])[0]
        if manifest["method"]["version"]=="2":
            return
        journal.setdefault("earlier_analysis_attempts",[]).append(journal["stages"].pop("analysis"))
    parent = journal["stages"].get("candidates")
    if parent is None or parent["status"]!="successful":
        return
    store = BatchStore(root)
    started = monotonic()
    for stage, method in (("selection","full-pool"),
                          ("validation","voronoi_app.strict_generalisation:analyze")):
        if stage=="selection" and stage in journal["stages"]:
            parent=journal["stages"][stage]
            continue
        rec = run_stage(store,stage,method,{},parent["record"],None if stage=="selection" else "2")
        parent = {"record":rec["id"],"status":rec["status"],"seconds":monotonic()-started,
                  "peak_rss_mib":rss_mib(),"error":rec.get("error")}
        journal["stages"]["analysis" if stage=="validation" else stage] = parent
        atomic_write(path,encode(journal))
        print(path.stem,stage,rec["status"],flush=True)
        if rec["status"]!="successful":
            break


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=["prepare","analyze","export"])
    parser.add_argument("--output",type=Path,default=ROOT)
    parser.add_argument("--workers",type=int,default=3)
    parser.add_argument("--case",choices=[f"{t}-{s}" for t,s in CASES])
    args=parser.parse_args()
    if args.phase=="export":
        from .strict_generalisation_export import export
        return export(args.output)
    method=prepare if args.phase=="prepare" else analyze
    cases=[(t,s) for t,s in CASES if not args.case or args.case==f"{t}-{s}"]
    if len(cases)==1:
        return method(args.output,*cases[0])
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        futures=[pool.submit(method,args.output,t,s) for t,s in cases]
        for future in futures:
            future.result()


if __name__=="__main__":
    main()
