"""Run regional metric attachments and simultaneous strict corridor exchanges."""
import argparse
import csv
import json
from pathlib import Path

from voronoi_app.batch_store import BatchStore, encode
from voronoi_app.strict_coverage_experiment import incidence_sets, omissions

from .region_incidence_angular import DEFAULT_OUT as INCIDENCE
from .strict_corridors import DEFAULT_OUT as CORRIDORS, MAPS
from .strict_coverage import ROOT, read

OUT = ROOT / "convex-metric" / "pilot-1"


def run(case, out):
    store = BatchStore(ROOT)
    out.mkdir(parents=True,exist_ok=True)
    journal = out/f"{case}.json"
    if journal.exists():
        raise FileExistsError(journal)
    records = {}

    def load(path):
        record,data,digest = store.load(read(path)["record"])
        if record["status"]!="successful":
            raise ValueError(f"Unsuccessful archived stage: {path}")
        records[record["id"]] = digest
        return record,data

    inc_record,incidence = load(INCIDENCE/f"{case}.json")
    corridor_record,corridors = load(CORRIDORS/f"{case}.json")
    audit_record,audit = load(CORRIDORS/f"{case}-metric-protocol.json")
    parent = inc_record["parent"]["id"]
    if any(r["parent"]["id"]!=parent for r in (corridor_record,audit_record)):
        raise ValueError("Archived records use different geometry.")
    benchmark = {k:{"line_ids":v["line_ids"],"angular":v["angular"],
                   "prior_metric_statistics":v["connector_metric_statistics"]}
                 for k,v in incidence["maps"].items()}
    replay = []
    indexed_maps = {}
    for ref,bands in corridors["references"].items():
        for n,band in enumerate(bands,1):
            for method,row in band["variants"].items():
                if row["status"]!="valid":
                    continue
                name = f"{ref}/{n}/{method}"
                indexed_maps[name] = row
                benchmark[name] = {"line_ids":row["line_ids"],"angular":row["angular"],
                                   "prior_metric_statistics":row["metric"]["statistics"]}
    for f in audit["failures"]:
        replay.append(f | {"line_ids":indexed_maps[f["map"]]["line_ids"]})
    parameters = {"case":case,"incidence":incidence,"reference":inc_record["parameters"]["reference"],
                  "strict_maps":corridor_record["parameters"]["strict_maps"],"benchmark":benchmark,
                  "archived_failures":replay,"corridor_results":corridors["references"],
                  "sources":records}
    result = store.run("validation","voronoi_app.convex_metric_experiment:run","2",parameters,parent)
    with journal.open("xb") as stream:
        stream.write(encode({"record":result["id"],"status":result["status"],"error":result.get("error")}))
    print(case,result["status"],result.get("error"),flush=True)
    return result["status"]!="successful"


def export(out):
    store = BatchStore(ROOT)
    results,replay = [],[]
    for case in MAPS:
        state = read(out/f"{case}.json")
        if state["status"]!="successful":
            raise ValueError(state)
        record,data,_ = store.load(state["record"])
        regions,doors = incidence_sets(record["parameters"]["incidence"])
        for ref, entries in [("benchmark",data["benchmark"])] + [(r,d["results"]) for r,d in data["joint"].items()]:
            for name,row in entries.items():
                ids = set(row.get("line_ids", []))
                missing, unattached = omissions(ids,regions,doors) if ids else ([],[])
                fields = {"case":case,"reference":ref,"map":name,
                          "status":row.get("status","evaluated" if ref=="benchmark" else "valid"),
                          "lines":row.get("line_count"),"length":row.get("length"),
                          "line_ids":json.dumps(row.get("line_ids")),
                          "covered_regions":len(regions)-len(missing) if ids else None,
                          "required_regions":len(regions),
                          "unattached_angular_doors":len(unattached) if ids else None,
                          "unattached_metric_doors":len(row["unattached_metric_doors"])
                          if "unattached_metric_doors" in row else None,
                          "winding_rank":row.get("constraints",{}).get("winding_rank"),
                          "constraints":json.dumps(row.get("constraints")),
                          "transverse":json.dumps(row.get("transverse")),
                          "worst_angular_pairs":json.dumps(row.get("worst_angular_pairs")),
                          "worst_metric_pairs":json.dumps(row.get("worst_metric_pairs"))}
                for k in ("angular_statistics","metric_statistics","angular_excess","metric_excess","prior_metric_statistics"):
                    for stat in ("mean","median","p95","max","reachable","unreachable"):
                        fields[f"{k}_{stat}"] = row.get(k,{}).get(stat)
                results.append(fields)
        for row in data["failure_replay"]:
            replay.append({"case":case,**row,"interior_witness":json.dumps(row["interior_witness"]),
                           "uncapped_nearest":json.dumps(row["uncapped_nearest"])})
    for name,rows in (("comparison.csv",results),("failure-replay.csv",replay)):
        with (out/name).open("x",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({k:"null" if v is None else v for k,v in row.items()} for row in rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case",choices=[*MAPS,"export"])
    parser.add_argument("--output",type=Path,default=OUT)
    args=parser.parse_args()
    return export(args.output) if args.case=="export" else run(args.case,args.output)


if __name__=="__main__":
    raise SystemExit(main())
