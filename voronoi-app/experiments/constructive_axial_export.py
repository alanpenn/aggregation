"""Render numbered constructive maps and report geometric and route outcomes."""
import argparse
from collections import Counter
import csv
from fcntl import LOCK_EX, flock
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median
from time import sleep

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from PIL import Image
from scipy.stats import spearmanr

from experiments.constructive_axial import CASES, PARAMETERS, ROOT, TANGENT_AUDIT, evaluate, load
from experiments.extended_terrain_export import TERRAIN_LABELS
from experiments.plot_facewise_matched import draw_map
from voronoi_app.angular import LineClearance
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance

METHODS = ("A", "B", "B-coverage", "D")
TARGETS = (957, 1244, 1355, 865, 1189, 1354)
LOCATIONS = {(15,25):(957,865),(6,5):(1244,1189),(41,43):(1355,1354)}
COLORS = {"backbone":"#236398","coverage":"#148271","connectivity":"#946f19",
          "circulation":"#c65b2b","exchanges":"#972386","baseline":"#36455a"}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def table(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def route_row(case, method, variant, route, validation, seconds=None, memory=None):
    row = {"case":case,"method":method,"variant":variant,"status":"valid" if route["valid"] else "invalid",
           "lines":route["count"],"length":route["length"],"rank":validation.get("rank"),
           "required_rank":validation.get("required_rank"),"construction_seconds":seconds,
           "routing_seconds":route["routing_seconds"],"peak_rss_mib":memory}
    for kind in ("angular","metric"):
        row.update({f"{kind}_{key}":value for key,value in route[kind].items()})
        row[f"{kind}_absolute_excess"] = route[f"{kind}_absolute_excess"]
    return row


def stages(result):
    memberships = {}
    for event in result["trace"]:
        stage = event["stage"]
        if stage == "singleton":
            stage = "coverage"
        for i in event.get("add",[]):
            memberships[i] = stage
    completed = result.get("completed",result.get("partial",[]))
    yield "backbone", result["backbone"], memberships
    yield "coverage", [i for i in completed if memberships[i] in ("backbone","coverage")], memberships
    yield "completion", completed, memberships
    if "error" in result:
        yield "failed", completed, memberships
    else:
        final = set(result["maps"]["constructive"])
        for variant, ids in result["maps"].items():
            tags = memberships | {i:"exchanges" for i in ids if i not in final}
            yield variant, ids, tags


def draw(ax, settlement, polygons, lines, ids, tags, *, extent=None, size=6):
    draw_map(ax,polygons,settlement,extent=extent,label_size=size)
    for category,color in COLORS.items():
        segments = [(lines[i].start,lines[i].end) for i in sorted(ids) if tags.get(i,"baseline")==category]
        collection = LineCollection(segments,colors=color,linewidths=1.05,zorder=5)
        ax.add_collection(collection)
        if [segment.tolist() for segment in collection.get_segments()] != [
           [[float(value) for value in point] for point in segment] for segment in segments]:
            raise ValueError("A plotted interval differs from its certified candidate.")


def save(root, stem, fig, atlas):
    index = {}
    for extension in ("pdf","png"):
        path = root/"numbered-maps"/f"{stem}.{extension}"
        fig.savefig(path,dpi=310,bbox_inches="tight",facecolor="white")
        if extension == "pdf" and b"/Subtype /Image" in path.read_bytes():
            raise ValueError(f"Rasterized map {path}.")
        if extension == "png":
            with Image.open(path) as raster:
                if min(raster.size) < 1850:
                    raise ValueError(f"Low resolution map {path}.")
        index[extension] = str(path.relative_to(root))
    atlas.savefig(fig,bbox_inches="tight")
    plt.close(fig)
    return index


def page(root, atlas, case, stage, polygons, settlement, lines, ids, tags, title, record, metric=None):
    if len(ids) != len(set(ids)) or any(lines[i].line_id != i for i in ids):
        raise ValueError("Map has invalid line identities.")
    fig, ax = plt.subplots(figsize=(8.4,9.2),layout="constrained")
    draw(ax,settlement,polygons,lines,ids,tags)
    fig.suptitle(title,fontsize=15)
    fig.legend(handles=[Line2D([],[],color=color,label=key.capitalize()) for key,color in COLORS.items()
                        if key in {tags.get(i,"baseline") for i in ids}],loc="outside lower center",ncols=3)
    if metric:
        ax.set_title(f"{len(ids)} lines · rank {metric['rank']}/{metric['required_rank']} · {metric['status']}\n"
                     f"Mean angular {metric['angular_mean']:.4f} · metric {metric['metric_mean']:.3f}")
    elif ids:
        ax.set_title(f"{len(ids)} lines")
    return {"case":case,"stage":stage,"ids":sorted(ids),"record":record,
            "metrics":metric,"files":save(root,f"{case}-{stage}",fig,atlas)}


def highlights(root, atlas, settlement, polygons, lines, methods, baseline, source):
    labels = {n:int(cell) for cell,n in settlement["building_labels"].items()}
    output=[]
    for (a,b),target in LOCATIONS.items():
        bounds = [polygons[labels[n]].bounds for n in (a,b)]
        extent = (max(0,min(v[0] for v in bounds)-8),max(0,min(v[1] for v in bounds)-8),
                  min(100,max(v[2] for v in bounds)+8),min(100,max(v[3] for v in bounds)+8))
        fig,axes=plt.subplots(2,3,figsize=(15,10),layout="constrained")
        fig.suptitle(f"Flat 40 · Buildings {a} and {b} · Tangent audit candidates {target[0]} and {target[1]}")
        inventories = {"Strict backward":baseline,**{f"{key} exchanged":result.get("maps",{}).get("exchanged",result.get("partial",[]))
                                                     for key,result in methods.items()}}
        for (label,ids),ax in zip(inventories.items(),axes.flat):
            draw(ax,settlement,polygons,lines,ids,{i:"exchanges" for i in set(ids)&set(target)},
                 extent=extent,size=7)
            ax.set_title(label+" · "+str(len(set(ids)&set(target)))+" highlighted")
        draw(axes.flat[-1],settlement,polygons,lines,target,{i:"exchanges" for i in target},extent=extent,size=7)
        axes.flat[-1].set_title("Certified tangent-audit reference intervals")
        stage=f"closeup-{a}-{b}"
        output.append({"case":"flat-40","stage":stage,"panels":inventories | {"audit targets":list(target)},
                       "record":{"candidate_record":source["candidates"],"methods":{name:digest(root/"flat-40"/f"{name}.json") for name in methods}},
                       "files":save(root,"flat-40-"+stage,fig,atlas)})
    return output


def export_case(root, case, atlas):
    path = root/case
    inputs,source,reference = load(case)
    polygons,_,_ = _settlement(inputs)
    settlement = inputs["settlement"]
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    geometry=json.loads((path/"geometry.json").read_bytes())
    movement=json.loads((path/"movement.json").read_bytes())
    methods={key:json.loads((path/f"{key}.json").read_bytes()) for key in METHODS}
    decisions(root,case,methods,geometry)
    base=movement["baseline"]
    required=inputs["analysis"]["holes"]
    venue, seed = case.rsplit("-",1)
    name=f"{TERRAIN_LABELS[venue]} · seed {seed}"
    records=[page(root,atlas,case,"settlement",polygons,settlement,lines,[],{},name+" · Numbered settlement",
                  source["settlement"])]
    rows=[]
    for method,variant,route,validation in [
        ("strict-backward","baseline",base,{"rank":required,"required_rank":required}),
        ("full-pool","reference",{"valid":True,"count":len(lines),"length":sum(l.length for l in lines),
                                 "angular":inputs["analysis"]["maps"]["full_pool"]["routing"]["angular"]["cost"],
                                 "metric":inputs["analysis"]["maps"]["full_pool"]["routing"]["metric"]["cost"],
                                 "routing_seconds":None,"angular_absolute_excess":0,"metric_absolute_excess":0},
         {"rank":required,"required_rank":required})]:
        rows.append(route_row(case,method,variant,route,validation))
    records.append(page(root,atlas,case,"strict-backward",polygons,settlement,lines,base["ids"],{},
                        name+" · Archived strict backward",source["analysis"],rows[0]))
    discoveries=[]
    for method,result in methods.items():
        checkpoint=path/f"{method}.json"
        evidence={"file":str(checkpoint.relative_to(root)),"sha256":digest(checkpoint),"candidate_record":source["candidates"]}
        for stage,ids,tags in stages(result):
            row=None
            if stage in result.get("maps",{}):
                validation=result["validation"][stage]
                route=movement["methods"][method][stage]
                if not validation["valid"]:
                    raise ValueError(f"An uncertified geometry escaped into routing for {case}/{method}/{stage}.")
                row=route_row(case,method,stage,route,validation,result["seconds"],result["peak_rss_mib"])
                if not route["valid"]:
                    row["reason"] = "Incomplete certified doorway reachability."
                row["backbone_retained"]=len(set(ids)&set(result["backbone"]))
                row["coverage_added"]=sum(len(event.get("add",[])) for event in result["trace"]
                                          if event["stage"] in ("singleton","coverage"))
                row["circulation_added"]=sum(len(event.get("add",[])) for event in result["trace"]
                                             if event["stage"]=="circulation")
                row["connectivity_added"]=sum(len(event.get("add",[])) for event in result["trace"]
                                              if event["stage"]=="connectivity")
                row["geometry_seconds"]=geometry["seconds"]
                for category in ("coverage","connectivity","circulation","exchanges"):
                    row[f"retained_{category}"] = sum(tags.get(i)==category for i in ids)
                rows.append(row)
            title=f"{name} · {method} · {stage.replace('_',' ')}"
            if stage=="failed":
                validation = result["validation"]
                rank = validation.get("rank")
                title += f"\nRank {rank}/{required} · {result['error']}"
                rows.append({"case":case,"method":method,"variant":"failed","status":"invalid",
                             "reason":result["error"],"lines":len(ids),"rank":rank,"required_rank":required,
                             "construction_seconds":result["seconds"]})
            records.append(page(root,atlas,case,f"{method}-{stage}",polygons,settlement,lines,ids,tags,title,evidence,row))
        if case=="flat-40":
            rank=geometry["rankings"][method]
            direct = set(result.get("maps",{}).get("constructive",[]))
            exchanged = set(result.get("maps",{}).get("exchanged",[]))
            transitions = result["trace"] + [{"stage":"exchange","add":sorted(exchanged-direct),
                                               "remove":sorted(direct-exchanged)}]
            for target in TARGETS:
                measure=geometry["candidates"][target]
                duplicates=set(measure["redundant"])
                retained=set(result.get("maps",{}).get("exchanged",[]))
                discoveries.append({"method":method,"candidate":target,"static_rank":rank.index(target)+1,
                                    "in_backbone":target in result["backbone"],"in_exchanged":target in retained,
                                    "similar_final_candidates":sorted(retained&duplicates),
                                    "events":[event for event in transitions if target in event.get("add",[])+event.get("remove",[])]})
    if case=="flat-40":
        controls=json.loads((root/"flat40-audit-controls.json").read_bytes())
        for method,inventory in controls["methods"].items():
            ids=inventory["maps"]["control"]
            row=route_row(case,method,"control",controls["movement"]["methods"][method]["control"],
                          {"rank":required,"required_rank":required})
            rows.append(row)
            records.append(page(root,atlas,case,method,polygons,settlement,lines,ids,{},
                                name+" · Tangent exchange control "+method.split("-")[1],
                                {"file":"flat40-audit-controls.json","sha256":digest(root/"flat40-audit-controls.json")},row))
        records.extend(highlights(root,atlas,settlement,polygons,lines,methods,base["ids"],source))
    for method,result in methods.items():
        ids=result.get("maps",{}).get("constructive",[])
        if ids:
            vectors = [geometry["candidates"][i]["normalized"] for i in ids]
            row=next(row for row in rows if row["method"]==method and row["variant"]=="constructive")
            for feature,values in zip(("length","diversity","distribution","coverage","redundancy"),zip(*vectors),strict=True):
                row[f"geometry_{feature}"]=mean(values)
    return records,rows,discoveries


def report(root, cases, rows, discoveries):
    by_case = {row["case"]:row for row in rows if row["method"]=="strict-backward"}
    natural = [row for row in rows if row["variant"]=="constructive" and row["status"]=="valid"]
    exchanged = [row for row in rows if row["variant"]=="exchanged" and row["status"]=="valid"]
    matching = [row for row in rows if row["method"] in METHODS and row["status"]=="valid"
                and row["lines"]==by_case[row["case"]]["lines"]]
    fewer = [row for row in exchanged if row["lines"]<by_case[row["case"]]["lines"]]
    better = [row for row in matching if all(row[f"{cost}_mean"]<by_case[row["case"]][f"{cost}_mean"]-1e-9
                                            for cost in ("angular","metric"))]
    outcomes = Counter((row["case"],row["method"]) for row in better)
    lines = ["# Constructive axial map selection from local geometry", "",
             f"The experiment covers {len(cases)} corrected settlements. {len(natural)} constructive maps and "
             f"{len(exchanged)} exchange-stage maps passed structural and movement checks. "
             f"{len(fewer)} exchange-stage maps use fewer lines than the corresponding archived strict backward map. "
             f"{len(outcomes)} case–method pairs have a matched-count result with lower means for both movement measures.", "",
             "## Flat 40 target recovery", "",
             "| Method | Candidate | Geometric rank | Backbone | Final exchange map | Geometrically similar final IDs | Entered or left at |",
             "|---|---:|---:|---|---|---|---|"]
    for row in discoveries:
        events = ", ".join(event["stage"] + (" add" if event.get("add") else " remove") for event in row["events"])
        lines.append(f"| {row['method']} | {row['candidate']} | {row['static_rank']} | "
                     f"{'yes' if row['in_backbone'] else '—'} | {'yes' if row['in_exchanged'] else '—'} | "
                     f"{', '.join(map(str,row['similar_final_candidates'])) or '—'} | {events or '—'} |")
    completed = {row["method"] for row in exchanged if row["case"]=="flat-40"}
    recovered = [row for row in discoveries if row["method"] in completed and row["in_exchanged"]]
    comparable = [row for row in discoveries if row["method"] in completed and row["similar_final_candidates"]]
    lines += ["", f"Across {len(completed)} valid Flat 40 exchange maps, exact recovery occurred in "
              f"{len(recovered)} of {len(TARGETS)*len(completed)} target–method combinations. "
              f"The similarity rule identified retained alternatives in {len(comparable)} combinations."]
    lines += ["", "D's geometric rank column uses the static B order for marginal-score ties. "
               "The D checkpoint contains the actual marginal contributions and exact winding gains at each step. "
               "Similarity uses the same overlap, orientation and separation rules as suppression. "
               "A similar interval may have different movement consequences.", "",
               "## Flat 40 comparisons", "",
               "| Method | Map | Lines | Total length | Angular mean | Angular p95 | Metric mean | Metric p95 |",
               "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        if row["case"]=="flat-40" and row["status"]=="valid":
            lines.append(f"| {row['method']} | {row['variant']} | {row['lines']} | {row['length']:.2f} | "
                         f"{row['angular_mean']:.4f} | {row['angular_p95']:.4f} | "
                         f"{row['metric_mean']:.3f} | {row['metric_p95']:.3f} |")
    archived = by_case.get("flat-40")
    matched_d = next((row for row in rows if row["case"]=="flat-40" and row["method"]=="D"
                      and row["variant"]=="archived_count" and row["status"]=="valid"),None)
    if matched_d:
        lines.extend(["", f"At {matched_d['lines']} lines, the D control uses {matched_d['length']:.2f} total axial length "
                      f"compared with {archived['length']:.2f} in the archived map. "
                      "The equal-count movement comparison therefore allows different total lengths."])
    lines += ["", "## Economy and generality", "",
               "| Method | Fewer lines after exchanges | Median line difference | Matched-count cases improving both means | Median construction seconds | Median backbone retained | Median coverage retained | Median circulation retained |",
               "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for method in METHODS:
        group=[row for row in exchanged if row["method"]==method]
        if not group:
            continue
        delta=[row["lines"]-by_case[row["case"]]["lines"] for row in group]
        wins=sum(key[1]==method for key in outcomes)
        lines.append(f"| {method} | {sum(d<0 for d in delta)}/{len(group)} | {median(delta):g} | {wins} | "
                     f"{median(row['construction_seconds'] for row in group):.2f} | "
                     f"{median(row['backbone_retained'] for row in group):g} | "
                     f"{median(row['retained_coverage'] for row in group):g} | "
                     f"{median(row['retained_circulation'] for row in group):g} |")
    lines.extend(["", "| Settlement | Archived backward | A exchanged | B exchanged | B-coverage exchanged | D exchanged |",
                  "|---|---:|---:|---:|---:|---:|"])
    lines_by_map = {(row["case"],row["method"]):row["lines"] for row in exchanged}
    for case in cases:
        fields = [case,str(by_case[case]["lines"])]
        fields.extend(str(lines_by_map.get((case,method),"—")) for method in METHODS)
        lines.append("| "+" | ".join(fields)+" |")
    if exchanged:
        economy = {method:[row for row in exchanged if row["method"]==method] for method in METHODS}
        available = [method for method in METHODS if economy[method]]
        def score(method):
            group = economy[method]
            wins = sum(key[1]==method for key in outcomes)
            return (-len(group),median(row["lines"]-by_case[row["case"]]["lines"] for row in group),
                    -wins,median(row["construction_seconds"] for row in group),method)
        leader=min(available,key=score)
        lines.extend(["", f"**{leader}** leads the reported comparison when methods are ordered by number of valid "
                      "cases, median line-count difference, cases improving both matched-count means, and median "
                      "construction time, in that order. The order makes explicit how economy and computation are "
                      "traded off against movement in this summary."])
    lines.extend(["", "Backbone retention counts measure how much of the original 12-line selection survives. "
                  "The statistics count retained additions by stage and the additions made before reduction. "
                  "Timings are wall-clock measurements from a mixture of sequential and parallel runs. Memory is "
                  "the worker's high-water mark.", "",
                  "Matched comparisons use the frozen geometric exchange criterion. When a feasible map was already "
                  "smaller than the archive, the archived-count variant adds the highest-ranked candidates that preserve "
                  "the certificate until the count matches. These controls compare route performance at the same count. "
                  "Their outcome also reflects the effect of those extra lines."])
    lines += ["", "## Local geometry and subsequent movement", ""]
    tests=[]
    for feature in ("length","diversity","distribution","coverage","redundancy"):
        for measure in ("angular","metric"):
            # Within-case differences reduce the effect of different terrains and scales.
            obs=[]
            for case in cases:
                group=[r for r in natural if r["case"]==case]
                if len(group)<2:
                    continue
                x=[row[f"geometry_{feature}"] for row in group]
                y=[row[f"{measure}_absolute_excess"] for row in group]
                obs.extend((a-mean(x),b-mean(y)) for a,b in zip(x,y,strict=True))
            if len(obs)>2 and all(len(set(col))>1 for col in zip(*obs)):
                x,y=zip(*obs)
                tests.append((measure,feature,float(spearmanr(x,y).statistic),len(x)))
    for measure in ("angular","metric"):
        ranked=sorted((row for row in tests if row[0]==measure),key=lambda row:-abs(row[2]))
        if ranked:
            lines.append(f"- {measure.capitalize()} excess · " + ", ".join(
                f"{feature} ρ={rho:.3f}" for _,feature,rho,_ in ranked) + f" ({ranked[0][3]} map observations).")
    lines.extend(["", "The correlations use within-settlement variation across methods. They describe this sample, "
                  "which shares candidate pools and cases, and do not establish independent predictive performance. "
                  "Differences in count, coverage repair and winding completion can also change route costs."])
    failures=[row for row in rows if row["status"]!="valid"]
    if failures:
        lines.extend(["", "## Unresolved selections", ""])
        lines.extend(f"- {row['case']} · {row['method']} · rank {row.get('rank')}/{row.get('required_rank')} · {row.get('reason','incomplete movement reachability')}"
                     for row in failures)
    diagnostics = root/"repair-diagnostics.json"
    if diagnostics.exists():
        detail = json.loads(diagnostics.read_bytes())
        lines.extend(["", "The repair audit counted the additional certified supports in the available archived "
                      "face bundles for each unenclosed block. Under the frozen 18-line cap, none of the audited "
                      "bundles enclosing the missing blocks in Y 40, Ridge 40 and Shoulder 40 was eligible. "
                      "These are sizes of particular witness bundles. A different arrangement of certified lines "
                      "can provide a smaller enclosure, as the archived strict maps demonstrate. In the two Flat 40 "
                      "B attempts, every occupied block was already enclosed, while some enclosures contributed "
                      "the same winding class. Those attempts stalled on independence.", "",
                      "[Repair diagnostics](repair-diagnostics.json)"])
    lines += ["", "## Frozen design and reproduction", "",
              "A ranks by exact maximal length. B and B-coverage blend min-max scaled length, transverse family count, "
              "the span of family centres along the interval, positive-interior coverage and a redundancy penalty. "
              "D recomputes marginal region, doorway, transverse and component gains at each step, and evaluates exact "
              "winding gain for its four best local proposals. D gives weights 1 to each new region and doorway, "
              "2 to each new transverse connection, 5 to each component merge, −5 to each redundant selected "
              "neighbour and 12 to each unit of exact winding gain, with a unit cost per accepted line. "
              "Each method starts with a 12-line backbone. "
              "Two transverse intervals belong to the same family if linked by the recorded similarity relation. "
              "Grouping is transitive. The similarity threshold is 10 degrees, two units at both projected overlap ends, "
              "65% overlap of the shorter interval and 55% convex-coverage Jaccard similarity. "
              "Projected overlap and separation at both overlap ends preserve crossing diagonals "
              "that fan apart.", "",
              "Completion adds forced singletons, repairs region and doorway coverage, connects components, and uses "
              "geometry to propose separating lines where distinct occupied blocks are enclosed together. The exact winding "
              "validator checks every accepted split and any small face-support bundle used as a fallback. "
              "The preliminary bundle-only Flat 40 pilot stalled below full rank. This repair was frozen before "
              "the cross-terrain runs. Backward cleanup removes redundant selected lines "
              "subject to the exact certificate. Exchanges minimize count, then favor higher aggregate geometric ranks. "
              "The saved trials include one-for-one, one-for-two and two-for-three proposals. "
              "Angular and metric routes are evaluated after selection and omitted from all rankings and exchange decisions.", "",
              "Run `PYTHONPATH=src:. python -m experiments.constructive_axial --workers 6` from the application directory. "
              "The runner resumes certified geometry, selection and movement checkpoints. "
              "Render the completed run with `PYTHONPATH=src:. python -m experiments.constructive_axial_export`.", "",
              "The finite metric graph uses certified regional stops and connectors. Angular entry and exit use "
              "the certified convex-incidence terminal sets. Exact candidate IDs in the atlas use the archived pool coordinates.", "",
              "[Geometric design](design.json) · [Runtime source hashes](runtime-source.json) · [Candidate measures](candidate-measures.csv) · [Statistics](statistics.csv) · [Target recovery](flat40-targets.json) · "
              "[Map index](visual-index.json) · [Numbered vector atlas](numbered-axial-atlas.pdf)", ""]
    (root/"report.md").write_text("\n".join(lines))


def decisions(root, case, methods, geometry):
    """Reconstruct the fixed backbone cutoff and the recorded D shortlist outcomes."""
    output = {}
    for method, result in methods.items():
        if method == "D":
            output[method] = [{"chosen":event["add"][0],"assessed":event["shortlist"],
                               "reason_for_other_candidates":"outside exact geometry shortlist"}
                              for event in result["trace"] if event["stage"]=="backbone"]
            continue
        selected, trace = set(), []
        for i in geometry["rankings"][method]:
            blockers = selected.intersection(geometry["candidates"][i]["redundant"])
            if len(selected) == PARAMETERS["backbone_lines"]:
                state = "outside backbone budget"
            elif blockers:
                state = "suppressed geometric overlap"
            else:
                state = "selected"
                selected.add(i)
            trace.append({"id":i,"decision":state,"redundant_with":sorted(blockers)})
        if selected != set(result["backbone"]):
            raise ValueError(f"Cannot replay backbone ranking for {case}/{method}.")
        output[method] = trace
    atomic_write(root/case/"backbone-decisions.json",encode(output))


def candidate_csv(root, cases):
    rows = []
    for case in cases:
        data = json.loads((root/case/"geometry.json").read_bytes())
        ranks = {method:{i:r for r,i in enumerate(ids,1)}
                 for method,ids in data["rankings"].items()}
        for item in data["candidates"]:
            i = item["id"]
            rows.append({"case":case,"candidate_id":i,"length":item["length"],
                         "region_count":len(item["regions"]),"doorway_count":len(item["doorways"]),
                         "raw_intersections":len(item["intersections"]),"transverse_count":len(item["transverse"]),
                         "transverse_family_count":len(item["families"]),"family_span":item["family_span"],
                         "redundancy_count":len(item["redundant"]),
                         **{f"{method}_rank":ranking[i] for method,ranking in ranks.items()}})
    table(root/"candidate-measures.csv",rows)


def ensure_controls(root):
    """Route the independent Flat 40 controls defined by the tangent audit."""
    source = TANGENT_AUDIT/"audit.json"
    output = root/"flat40-audit-controls.json"
    checksum = digest(source)
    if output.exists():
        if json.loads(output.read_bytes())["audit_sha256"] != checksum:
            raise ValueError("The source tangent audit changed.")
        return
    audit = json.loads(source.read_bytes())
    trials = [row for group in audit["exchanges"].values() for row in group] + audit["combinations"]
    baseline = set(audit["baseline_ids"])
    methods = {}
    for count in (43,44):
        row = min((r for r in trials if r["valid"] and r["line_count"]==count),
                  key=lambda r:(r["angular"]["mean"],r["metric"]["mean"],r["length"],r["add"],r["remove"]))
        ids = sorted((baseline | set(row["add"])) - set(row["remove"]))
        methods[f"audit-{count}"] = {"maps":{"control":ids}}
    inputs, _, reference = load("flat-40")
    _,occupied,accessible,obstacles = _domain(inputs)
    clearance = IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    movement = evaluate(inputs,lines,clearance,reference,methods)
    atomic_write(output,encode({"methods":methods,"movement":movement,"audit_sha256":checksum}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT)
    parser.add_argument("--flat-only",action="store_true")
    parser.add_argument("--wait",action="store_true",help="Render ready cases and wait for pending movement checkpoints.")
    args=parser.parse_args()
    cases=CASES[:1] if args.flat_only else CASES
    with (args.output/"export.lock").open("a") as claim:
        flock(claim,LOCK_EX)
        index_path=args.output/"visual-index.json"
        if ((args.output/"export-checksums.json").exists() and index_path.exists()
                and tuple(json.loads(index_path.read_bytes())["cases"])==cases):
            print("The complete requested atlas is already exported.",flush=True)
            return
        publish(args.output,cases,args.wait)


def publish(root, cases, wait):
    missing=[case for case in cases if not (root/case/"movement.json").exists()]
    if missing and not wait:
        raise ValueError("Missing movement checkpoints for "+", ".join(missing))
    ensure_controls(root)
    (root/"numbered-maps").mkdir(exist_ok=True)
    atlas_path=root/"numbered-axial-atlas.pdf"
    records,rows,discoveries=[],[],[]
    remaining=[case for case in cases if case not in missing]+missing
    with PdfPages(atlas_path.with_suffix(".tmp")) as atlas:
        for case in remaining:
            while not (root/case/"movement.json").exists():
                sleep(10)
            index,stats,targets=export_case(root,case,atlas)
            records.extend(index)
            rows.extend(stats)
            discoveries.extend(targets)
            print(case,len(index),"numbered maps exported",flush=True)
    atlas_path.with_suffix(".tmp").replace(atlas_path)

    report(root,cases,rows,discoveries)
    table(root/"statistics.csv",rows)
    candidate_csv(root,cases)
    atomic_write(root/"flat40-targets.json",encode(discoveries))
    atomic_write(root/"visual-index.json",encode({"atlas":atlas_path.name,"cases":list(cases),"maps":records}))
    artifacts=[*root.glob("numbered-maps/*"),*root.glob("*.pdf"),*root.glob("*.csv"),
               *root.glob("*.md"),*(p for p in root.glob("*.json") if p.name!="export-checksums.json"),
               *(path for case in cases for path in (root/case).glob("*.json"))]
    atomic_write(root/"export-checksums.json",encode({str(p.relative_to(root)):digest(p) for p in artifacts}))


if __name__=="__main__":
    main()
