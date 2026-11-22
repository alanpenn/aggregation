"""Tabular and numbered-map exports for the paired strict pilot."""
import csv
import json
from collections import Counter
from time import monotonic

from voronoi_app.batch_routing_reference import interval
from voronoi_app.batch_store import BatchStore, atomic_write, encode
from voronoi_app.strict_coverage_experiment import compare_pairs, incidence_sets

from .strict_generalisation import CASES, case_path, rss_mib

METHODS=("full_pool","strict_entrance_guided","strict_backward","geometric_extreme","route_ranked")


def numbered_map(path, settlement, candidates, case, methods):
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from shapely import from_wkb

    polygons=settlement["polygons_wkb"]
    buildings=[(label,from_wkb(polygons[key])) for key,label in settlement["building_labels"].items()]
    segments=[interval(line) for line in candidates]
    figure,axes=plt.subplots(1,5,figsize=(17,4),layout="constrained")
    figure.suptitle(case.replace("_"," ").title())
    for ax,name in zip(axes,METHODS,strict=True):
        row=methods.get(name,{})
        for label,p in buildings:
            ax.fill(*p.exterior.xy,color="#38414b",zorder=1)
            center=p.representative_point()
            ax.text(center.x,center.y,str(label),color="white",fontsize=3.4,
                    ha="center",va="center",zorder=3)
        if "line_ids" in row:
            lines=[segments[i] for i in row["line_ids"]]
            ax.add_collection(LineCollection(lines,colors="#2583ad",
                                             alpha=.18 if name=="full_pool" else .9,
                                             linewidths=.8,zorder=2))
        ax.autoscale()
        ax.axis("off")
        x0,y0,x1,y1=settlement["grid"]["extent"]
        ax.set(xlim=(x0,x1),ylim=(y0,y1))
        status=f"{row['line_count']} lines" if row.get("status")=="valid" else row.get("status","unavailable")
        ax.set(aspect="equal",title=name.replace("_"," ").capitalize()+"\n"+status)
    with path.open("xb") as stream:
        figure.savefig(stream,format="png",dpi=200)
    plt.close(figure)


def table(path, rows):
    if not rows:
        return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=keys)
        writer.writeheader()
        writer.writerows({k:"null" if v is None else v for k,v in row.items()} for row in rows)


def screened_methods(store, path, case, analysis, checksum, data):
    bands=data.get("corridors",[])
    if not bands:
        return data.get("maps",{}),[],None
    stages=case["stages"]
    kinds=(("geometric_extreme","extreme"),("route_ranked","best_ranked"))
    if "physical_screen" not in stages:
        started=monotonic()
        options={}
        for method,key in kinds:
            options[method]=[[r["line_count"],r["routing"]["angular"]["cost"]["mean"],r["length"],r["pair"]]
                             if r and r["status"]=="valid" else None for r in (b[key] for b in bands)]
        rec=store.run("validation","voronoi_app.strict_generalisation:screen_physical_bands","1",
                      {"analysis_record":analysis["record"],"analysis_sha256":checksum,
                       "axes":[b["axis"] for b in bands],"options":options},stages["selection"]["record"])
        stages["physical_screen"]={"record":rec["id"],"status":rec["status"],
                                   "seconds":monotonic()-started,"peak_rss_mib":rss_mib(),
                                   "error":rec.get("error")}
        atomic_write(path,encode(case))
    record,result,_=store.load(stages["physical_screen"]["record"])
    if record["status"]!="successful":
        raise ValueError(record)
    screen=result["bands"]
    maps=dict(data["maps"])
    for method,key in kinds:
        admissible=[band for band,s in zip(bands,screen,strict=True) if s["accepted"]]
        winner=result["winners"][method]
        if winner is not None:
            maps[method]=bands[winner-1][key]
        else:
            has_pairs=any(b["qualifying_pairs"] for b in admissible)
            maps[method]={"status":"invalid" if has_pairs else "unsupported",
                          "reason":"no feasible pair in screened bands" if has_pairs else
                          "no qualifying pair in screened bands"}
    return maps,screen,record["id"]


def export(root):
    store=BatchStore(root)
    rows,paired,bands=[],[],[]
    maps_dir=root/"numbered-maps"
    maps_dir.mkdir(exist_ok=True)
    geometry_dir=root/"selected-geometry"
    geometry_dir.mkdir(exist_ok=True)
    for terrain,seed in CASES:
        path=case_path(root,terrain,seed)
        case=json.loads(path.read_text())
        stages=case["stages"]
        analysis=stages.get("analysis")
        _,d,checksum=store.load(analysis["record"]) if analysis else (None,None,None)
        d=d or {}
        methods,screen,screen_id=screened_methods(store,path,case,analysis,checksum,d)
        prior=stages.get("topology")
        prepared=store.load(prior["record"])[1] if prior and prior["status"]=="successful" else {}
        topology=prepared.get("topology",{})
        region_sets,door_sets=incidence_sets(d["incidence"]) if "incidence" in d else ({},[])
        forced={next(iter(group)) for group in [*region_sets.values(), *door_sets] if len(group)==1}
        common={"case":case["case"],"terrain":terrain,"seed":seed,
                "settlement_record":stages.get("settlement",{}).get("record"),
                "topology_record":prior["record"] if prior else None,
                "candidate_record":stages.get("candidates",{}).get("record"),
                "analysis_record":analysis["record"] if analysis else None,
                "physical_screen_record":screen_id,
                "internal_blocks":sum(v["kind"]!="boundary" for v in topology.get("occupied_blocks", [])) if topology else None,
                "accessible_holes":len(topology.get("circulation_holes",[])) if topology else None,
                "internal_associated_holes":len(topology["internal_circulation_holes"]) if topology else None,
                "excluded_open":len(topology["excluded_open_cells"]) if topology else None,
                "doorways":len(d["doorways"]) if "doorways" in d else None,
                "excluded_doorways":len(d["excluded_doors"]) if "excluded_doors" in d else None,
                "required_regions":d.get("regions"),
                "forced_region_or_door_lines":len(forced) if "incidence" in d else None,
                "corridors":sum(row["accepted"] for row in screen) if "corridors" in d else None,
                "proposed_bands":len(screen) if "corridors" in d else None,
                "metric_connector_geometry_failures":len(d["metric_connector_rejections"])
                if "metric_connector_rejections" in d else None,
                "generation_seconds":sum(x["seconds"] for k,x in stages.items() if k in ("settlement","topology","candidates")),
                "analysis_seconds":analysis["seconds"] if analysis else None,
                "peak_worker_rss_mib":max(x["peak_rss_mib"] for k,x in stages.items() if k!="physical_screen"),
                "configuration":json.dumps(case["configuration"],sort_keys=True)}
        failed=[{"stage":key,"status":x["status"],"error":x.get("error")} for key,x in stages.items()
                if x["status"]!="successful"]
        for name in METHODS:
            method=methods.get(name,{})
            constraint=method.get("constraints",{})
            row=common | {"method":name,"status":method.get("status",failed[-1]["status"] if failed else "unsupported"),
                          "reason":method.get("reason") or json.dumps(d.get("failure_reasons",failed)),
                          "lines":method.get("line_count"),"length":method.get("length"),
                          "covered_regions":d["regions"]-len(constraint["missing_regions"])
                          if "regions" in d and "missing_regions" in constraint else None,
                          "rank":constraint.get("rank"),"missing_regions":json.dumps(constraint.get("missing_regions")),
                          "metric_unattached_doors":json.dumps(method.get("metric_unattached_doors"))}
            for measure in ("angular","metric"):
                for category in ("cost","absolute","proportional"):
                    stats=method.get("routing",{}).get(measure,{}).get(category,{})
                    for key in ("mean","median","p95","max","reachable","unreachable"):
                        row[f"{measure}_{category}_{key}"]=stats.get(key)
                proportional=method.get("routing",{}).get(measure,{}).get("proportional",{})
                row[f"{measure}_undefined_proportions"]=len(d["pairs"])-proportional["reachable"] if proportional else None
            rows.append(row)
        pairs=(("strict_entrance_guided","strict_backward"),
               ("strict_backward","geometric_extreme"),("strict_backward","route_ranked"),
               ("geometric_extreme","route_ranked"))
        for before,after in pairs:
            a,b=methods.get(before,{}),methods.get(after,{})
            if a.get("status")!="valid" or b.get("status")!="valid":
                continue
            compare={"case":case["case"],"from":before,"to":after,"from_lines":a["line_count"],
                     "to_lines":b["line_count"],"matched_count":a["line_count"]==b["line_count"]}
            for measure in ("metric","angular"):
                stats=compare_pairs(a["routes"][measure],b["routes"][measure])
                compare |= {f"{measure}_{k}":v for k,v in stats.items()}
            paired.append(compare)
        settlement=store.load(common["settlement_record"])[1] if common["settlement_record"] else None
        for i,band in enumerate(d.get("corridors",[]),1):
            a,b=band["extreme"] or {},band["best_ranked"] or {}
            summary={"case":case["case"],"corridor":i,"ratio":band["length_to_width"],
                     "length":band["length"],"width":band["width"],"banked_sections":band["profile"]["two_banks"],
                     "candidate_members":len(band["members"]),"selected_members":len(band["selected_members"]),
                     "opposed_pairs":band["qualifying_pairs"],"tested_pairs":len(band["trials"]),
                     "extreme_pair":json.dumps(a.get("pair")),"ranked_pair":json.dumps(b.get("pair")),
                     "extreme_status":a.get("status","unsupported"),
                     "ranked_status":b.get("status","invalid" if band["qualifying_pairs"] else "unsupported")}
            summary |= screen[i-1]
            summary["backward_lines"]=methods.get("strict_backward",{}).get("line_count")
            for prefix,item in (("extreme",a),("ranked",b)):
                summary[f"{prefix}_lines"]=item.get("line_count")
                for k in ("metric","angular"):
                    summary[f"{prefix}_{k}"]=item.get("routing",{}).get(k,{}).get("cost",{}).get("mean")
            for k in ("angular","metric"):
                baseline=methods.get("strict_backward",{}).get("routing",{}).get(k,{}).get("cost",{}).get("mean")
                summary[f"backward_{k}"]=baseline
            bands.append(summary)
        if settlement is not None:
            candidates=store.load(common["candidate_record"])[1] if common["candidate_record"] else None
            records=candidates["pool"]["candidates"] if candidates else []
            numbered_map(maps_dir/(case["case"]+".png"),settlement,
                         records,case["case"],methods)
            snapshot={"case":case["case"],"settlement_record":common["settlement_record"],
                      "candidate_record":common["candidate_record"],"analysis_record":common["analysis_record"],
                      "physical_screen_record":screen_id,
                      "maps":{name:{"status":row["status"],"lines":[
                          {k:records[i][k] for k in ("id","start","end")}
                          for i in row.get("line_ids",[])]} for name,row in methods.items()}}
            with (geometry_dir/(case["case"]+".json")).open("xb") as stream:
                stream.write(encode(snapshot))
    table(root/"comparison.csv",rows)
    table(root/"paired-comparisons.csv",paired)
    table(root/"corridors.csv",bands)
    print("Rows",len(rows),Counter(row["status"] for row in rows),flush=True)
