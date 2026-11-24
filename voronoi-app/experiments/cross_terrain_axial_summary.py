"""Produce matched accounting, paired results, and morphology tables."""
from collections import Counter
from csv import DictWriter
from io import StringIO
from hashlib import sha256
from itertools import combinations
from statistics import mean, median

from scipy.stats import spearmanr

from experiments.cross_terrain_axial import CASES, DEST, METHODS, TERRAINS, D_ARCHIVE, read, save
from voronoi_app.batch_store import atomic_write, encode


def stats(x):
    return {"n":len(x),"mean":mean(x),"median":median(x),"min":min(x),"max":max(x),
            "leave_one_out_mean_range":[min(mean(x[:i]+x[i+1:]) for i in range(len(x))),
                                       max(mean(x[:i]+x[i+1:]) for i in range(len(x)))] if len(x)>1 else None} if x else {"n":0}


def csvfile(name,rows):
    stream=StringIO(newline="")
    headings=list(dict.fromkeys(k for row in rows for k in row))
    writer=DictWriter(stream,fieldnames=headings)
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(DEST/f"{name}.csv",stream.getvalue().encode())


def main():
    inputs=read(DEST/"inputs.json")
    evaluation=[]
    morphology=[]
    publications=[]
    lineage={}
    for case in CASES:
        provenance=inputs[case]
        terrain,seed=case.rsplit("-",1)
        folder=DEST/case
        config_hash=sha256(encode(provenance["configuration"])).hexdigest()
        lineage[case]={"configuration_sha256":config_hash,"journal_sha256":provenance["journal_sha256"],
                       "missing":provenance["missing"],"verified_members":provenance["verified_tar_members"]}
        published=provenance["published_strict"]["result"]
        publications.append({"case":case,"terrain":terrain,"seed":int(seed),"status":published["status"],
                "exact_input_available":not provenance["missing"],"count":published["line_count"],
                **{f"{cost}_{stat}":published["routing"][cost]["cost"][stat]
                   for cost in ("angular","metric") for stat in ("mean","median","p95","max")}})
        structure=read(folder/"structural.json") if (folder/"structural.json").exists() else {}
        movement=read(folder/"movement.json") if (folder/"movement.json").exists() else {}
        geometry_path=D_ARCHIVE/case/"geometry.json"
        if not geometry_path.exists():
            geometry_path=folder/"geometry.json"
        geometric=read(geometry_path)["candidates"] if structure else []
        log=(folder/"run.log").read_text() if (folder/"run.log").exists() else ""
        if structure:
            angles=structure["pair_angles_degrees"]
            morphology.append({"case":case,"terrain":terrain,"seed":int(seed),
                **{k:structure.get(k) for k in ("blocks","regions","doorways","full_count","convex_vertices","excluded_open")},
                "complementary_raw":len(structure["complementary_raw"]),
                "complementary_repaired":len(structure["complementary_repaired"]),
                "complementary_pairs":len(angles),"mean_pair_angle":mean(angles) if angles else None,
                "sheaves":len(structure.get("sheaves",()))})
        for method in METHODS:
            result=structure.get("methods",{}).get(method,{})
            costs=movement.get("methods",{}).get(method,{})
            row={"case":case,"terrain":terrain,"seed":int(seed),"method":method,
                 "journal_sha256":provenance["journal_sha256"],"configuration_sha256":config_hash}
            if provenance["missing"]:
                published=provenance["published_strict"]["result"]
                row.update(status="published_archive_only" if method=="strict_backward" else "incomplete_input",
                           reason=f"{len(provenance['missing'])} immutable record files missing")
                if method=="strict_backward":
                    row.update(archived_status=published.get("status"),archived_count=published.get("line_count"))
            elif not result:
                row.update(status="execution_failure",reason=log.splitlines()[-1] if log.strip() else "No completed worker record")
            else:
                row.update(status=result["status"],reason=result.get("reason"),selected=len(result.get("ids",())),
                           start_count=result.get("start_count"),seconds=result.get("seconds"),
                           peak_rss_mib=result.get("peak_rss_mib"),deletion_seconds=result.get("deletion_seconds"),
                           exchange_seconds=result.get("exchange_seconds"),
                           exact_winding_checks=result.get("validation_counts",{}).get("dynamic_validator"))
                row.update(**result.get("metrics",{}))
                if method=="strict_backward":
                    row["seconds"]=provenance["published_strict"]["result"].get("selection_seconds")
                if method.startswith("C-"):
                    row.update(preselection_seconds=structure["preselection_seconds"],
                               completion_seconds=structure["repair_seconds"],
                               catalogue_seconds=structure.get("sheaf_seconds"),
                               independent_validation_seconds=result.get("validation_seconds",{}).get("full_validator"))
                if result.get("ids"):
                    selected=set(result["ids"])
                    row["distinct_transverse_sites"]=len({tuple(point) for i in selected for j,point
                            in geometric[i]["transverse"].items() if int(j) in selected and i<int(j)})
                if row["status"] in ("independent_success","certified_archive"):
                    if not costs or not costs.get("valid"):
                        row.update(status="routing_failed",reason="No complete valid movement record")
                    else:
                        expected=structure["doorways"]*(structure["doorways"]-1)//2
                        if any(costs[k]["reachable"]!=expected for k in ("angular","metric")):
                            raise ValueError(f"Incomplete doorway reachability {case}/{method}")
                        for cost in ("angular","metric"):
                            for stat in ("mean","median","p95","max"):
                                row[f"{cost}_{stat}"]=costs[cost][stat]
                            row[f"{cost}_excess"]=costs[cost]["mean"]-movement["reference_means"][cost]
                        row["reduction_fraction"]=1-row["selected"]/row["start_count"]
                        row["winding_rank"]=result["winding"]["independent_circulation_rank"]
                        row["required_rank"]=result["winding"]["required_circulation_rank"]
            evaluation.append(row)
    successful=[r for r in evaluation if r["status"] in ("independent_success","certified_archive")]
    values=("selected","length","angular_mean","metric_mean","angular_excess","metric_excess","seconds")
    summary={}
    for method in METHODS:
        rows=[r for r in evaluation if r["method"]==method]
        valid=[r for r in successful if r["method"]==method]
        summary[method]={"statuses":dict(Counter(r["status"] for r in rows)),
                         "statistics":{k:stats([r[k] for r in valid if r.get(k) is not None]) for k in values}}
    paired=[]
    for case in CASES:
        rows=[r for r in successful if r["case"]==case]
        for a,b in combinations(rows,2):
            both=[k for k in values if a.get(k) is not None and b.get(k) is not None
                  and (k!="seconds" or (a["method"].startswith("C-") and b["method"].startswith("C-")))]
            paired.append({"case":case,"terrain":a["terrain"],"first":a["method"],"second":b["method"],
                           **{f"delta_{k}":b[k]-a[k] for k in both},
                           **{f"relative_{k}":(b[k]-a[k])/a[k] for k in both if a[k]}})
    matched={}
    for a,b in combinations(METHODS,2):
        group=[r for r in paired if r["first"]==a and r["second"]==b]
        matched[f"{b} minus {a}"]={k:stats([r[f"delta_{k}"] for r in group if f"delta_{k}" in r]) for k in values}
    terrain_stats={}
    for terrain in TERRAINS:
        terrain_stats[terrain]={method:{"statuses":dict(Counter(r["status"] for r in evaluation
                                     if r["terrain"]==terrain and r["method"]==method)),
                 **{k:stats([r[k] for r in successful if r["terrain"]==terrain and r["method"]==method
                             and r.get(k) is not None]) for k in values}} for method in METHODS}
    by_morph={row["case"]:row for row in morphology}
    associations={}
    for method in METHODS:
        rows=[r for r in successful if r["method"]==method and r["case"] in by_morph]
        correlations={}
        for key in ("blocks","regions","full_count","convex_vertices","excluded_open","complementary_pairs","mean_pair_angle","sheaves"):
            available=[(by_morph[r["case"]].get(key),r["selected"]) for r in rows]
            available=[(a,b) for a,b in available if a is not None]
            if len(available)>=4 and len({a for a,_ in available})>1 and len({b for _,b in available})>1:
                rho=float(spearmanr(*zip(*available)).statistic)
                correlations[key]={"rho_descriptive":rho,"n":len(available)}
        associations[method]=correlations
    save(DEST/"statistics.json",{"summaries":summary,"terrain":terrain_stats,
                             "matched_delta":matched,"morphology_associations":associations})
    save(DEST/"evaluation-ledger.json",evaluation)
    csvfile("evaluations",evaluation)
    csvfile("paired-comparisons",paired)
    csvfile("morphology",morphology)
    csvfile("published-backward",publications)
    save(DEST/"lineage.json",lineage)


if __name__=="__main__":
    main()
