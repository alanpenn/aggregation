"""Compare strict-incidence corridor replacements using preserved batch records."""

import argparse
import csv
import json
from pathlib import Path

from voronoi_app.batch_store import BatchStore, encode

from .region_incidence_angular import DEFAULT_OUT as INCIDENCE
from .strict_coverage import OUT as STRICT, ROOT, read


DEFAULT_OUT = ROOT / "strict-corridors" / "pilot-1"
MAPS = {
    "Hill-42": {"angular": ("A", "backward-3"), "metric": ("Bmetric", "shortest")},
    "Y-42": {"angular": ("B", "backward-1"), "metric": ("Bmetric", "shortest")},
}


def run(case, output):
    output.mkdir(parents=True, exist_ok=True)
    journal = output / f"{case}.json"
    if journal.exists():
        raise FileExistsError(journal)
    store = BatchStore(ROOT)
    reference_id = read(INCIDENCE / f"{case}.json")["record"]
    reference, incidence, checksum = store.load(reference_id)
    parent = reference["parent"]["id"]
    sources = {reference_id:checksum}

    def load(path):
        record, payload, stamp = store.load(read(path)["record"])
        if record["status"] != "successful" or record["parent"]["id"] != parent:
            raise ValueError(f"Invalid or incompatible reference: {path}")
        sources[record["id"]] = stamp
        return record, payload

    _, old_corridors = load(ROOT / "extreme-diagonals" / "pilot-3" / f"{case}.json")
    maps = {}
    for name, (stage, variant) in MAPS[case].items():
        record, data = load(STRICT / f"{case}-{stage}.json")
        result = data["results"][variant]
        maps[name] = {k:result[k] for k in ("line_ids","angular","metric")} | {
            "source_record":record["id"],"source_variant":variant}
    parameters = {"case":case,"incidence":incidence,"reference":reference["parameters"]["reference"],
                  "sources":sources,"strict_maps":maps,"corridors":old_corridors["corridors"],
                  "repair_candidates":10,"repair_depth":3}
    result = store.run("validation","voronoi_app.strict_corridor_experiment:reassess","2",parameters,parent)
    with journal.open("xb") as stream:
        stream.write(encode({"record":result["id"],"status":result["status"],"error":result.get("error")}))
    print(case,result["status"],result.get("error"),flush=True)
    return result["status"] != "successful"


def export(output):
    store = BatchStore(ROOT)
    rows = []
    for case in MAPS:
        journal = read(output / f"{case}.json")
        if journal["status"] != "successful":
            raise ValueError(journal)
        _,data,_ = store.load(journal["record"])
        for selection, corridors in data["references"].items():
            for n, corridor in enumerate(corridors,1):
                for method, row in corridor["variants"].items():
                    check = row.get("constraints",{})
                    metric = row.get("metric",{})
                    result = {
                        "case":case,"reference":selection,"corridor":n,
                        "physical_profile":corridor["physical_profile"]["classification"],
                        "banked_samples":corridor["physical_profile"]["two_banks"],
                        "median_banked_width":corridor["physical_profile"]["median_banked_width"],
                        "opposed_pairs":corridor["opposed_pairs"],
                        "extreme_pair":json.dumps(corridor.get("extreme_pair")),
                        "valid_opposed_pairs":corridor.get("valid_pairs",0),
                        "combined_opposed_pairs":corridor.get("metric_complete_pairs",0),
                        "repair_trials":corridor.get("repair_trials",0),
                        "method":method,"status":row["status"],
                        "lines":row.get("line_count"),"length":row.get("length"),
                        "members":json.dumps(row.get("members")),
                        "missing_regions":json.dumps(check.get("missing_regions")),
                        "unattached_angular_doors":json.dumps(check.get("unattached_doors")),
                        "components":check.get("components"),"rank":check.get("winding_rank"),
                        "required_rank":check.get("required_rank"),
                        "clearance_rejections":json.dumps(check.get("clearance_rejections")),
                        "missing_rings":json.dumps(check.get("missing_rings")),
                        "lost_transverse":json.dumps(row.get("lost_transverse_contacts")),
                        "gained_transverse":json.dumps(row.get("gained_transverse_contacts")),
                        "worst_angular_pairs":json.dumps(row.get("worst_angular_pairs")),
                        "angular_excess_mean":row.get("angular_excess",{}).get("mean"),
                        "angular_change_mean":row.get("angular_change",{}).get("mean"),
                        "metric_unattached":len(metric["unattached_doors"]) if metric else None,
                        "metric_certified_witnesses":sum(w["certified_visible_interior_witness"] is not None
                                                         for w in metric["alternative_witnesses"]) if metric else None,
                        "metric_newly_unreachable":row.get("newly_unreachable_metric"),
                        "metric_change_mean":row.get("metric_change",{}).get("mean"),
                    }
                    for prefix, stats in (("angular",row.get("angular_statistics",{})),
                                          ("metric",metric.get("statistics",{}))):
                        for stat in ("mean","median","p95","max","reachable","unreachable"):
                            result[f"{prefix}_{stat}"] = stats.get(stat)
                    rows.append(result)
    with (output/"comparison.csv").open("x",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k:"null" if v is None else v for k,v in row.items()} for row in rows)


def protocol(case, output):
    store = BatchStore(ROOT)
    journal = output / f"{case}-metric-protocol.json"
    if journal.exists():
        raise FileExistsError(journal)
    record,data,stamp = store.load(read(output/f"{case}.json")["record"])
    if record["status"] != "successful":
        raise ValueError("The corridor analysis must be successful.")
    variants = []
    for selection, corridors in data["references"].items():
        for n, corridor in enumerate(corridors,1):
            for method, row in corridor["variants"].items():
                failures = row.get("metric",{}).get("alternative_witnesses")
                if failures:
                    variants.append({"map":f"{selection}/{n}/{method}", "line_ids":row["line_ids"],
                                     "failures":failures})
    parameters = {"corridor_record":record["id"],"corridor_sha256":stamp,
                  "doorways":record["parameters"]["incidence"]["doorways"], "selections":variants}
    result = store.run("validation","voronoi_app.strict_corridor_experiment:audit_metric_protocol",
                       "1",parameters,record["parent"]["id"])
    with journal.open("xb") as stream:
        stream.write(encode({"record":result["id"],"status":result["status"],"error":result.get("error")}))
    return result["status"] != "successful"


def export_protocol(output):
    store = BatchStore(ROOT)
    with (output/"metric-protocol.csv").open("x",newline="") as stream:
        fields = ("case","map","door","building","classification","uncapped_nearest","interior_witness")
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for case in MAPS:
            journal = read(output/f"{case}-metric-protocol.json")
            if journal["status"] != "successful":
                raise ValueError(journal)
            _, data, _ = store.load(journal["record"])
            for failure in data["failures"]:
                writer.writerow({"case":case,**failure,
                                 "uncapped_nearest":json.dumps(failure["uncapped_nearest"]),
                                 "interior_witness":json.dumps(failure["interior_witness"])})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case",choices=[*MAPS,"export"])
    parser.add_argument("--output",type=Path,default=DEFAULT_OUT)
    parser.add_argument("--metric-protocol",action="store_true")
    args=parser.parse_args()
    if args.case=="export":
        return export_protocol(args.output) if args.metric_protocol else export(args.output)
    return protocol(args.case,args.output) if args.metric_protocol else run(args.case,args.output)


if __name__=="__main__":
    raise SystemExit(main())
