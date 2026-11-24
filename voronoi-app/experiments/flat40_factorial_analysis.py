"""Finite-population movement contrasts and geometric explanations for U3."""
from fractions import Fraction
from itertools import combinations
from statistics import mean

import numpy as np
from shapely.geometry import Point

from experiments.constructive_axial import ROOT
from experiments.controlled_preselection import Study
from experiments.flat40_factorial_routes import DEST, save
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.recombine_flat40 import DEST as PRIOR
from voronoi_app.angular import _on_segment
from voronoi_app.sheaf_experiment import interval

METRICS=("angular_mean","angular_p95","metric_mean","metric_p95","length")
GEOMETRIC=("length","transverse","regions","doorways","transverse_families","mandatory_intersections","transverse_span")


def summarize(values):
    q=np.percentile(values,[5,25,50,75,95])
    return {"minimum":float(np.min(values)),"maximum":float(np.max(values)),"mean":float(np.mean(values)),
            "median":float(q[2]),"sd_population":float(np.std(values)),"p05":float(q[0]),
            "q1":float(q[1]),"q3":float(q[3]),"p95":float(q[4]),"iqr":float(q[3]-q[1])}


def factorial(values,bits):
    signs=2*bits-1
    effects=[]
    variance=np.var(values)
    for order in range(1,8):
        for factors in combinations(range(7),order):
            basis=np.prod(signs[:,factors],axis=1)
            coefficient=float(np.mean(values*basis))
            effects.append({"factors":[i+1 for i in factors],"coefficient":coefficient,
                            "contrast":coefficient*2**order,"variance":coefficient**2})
    if not np.isclose(sum(e["variance"] for e in effects),variance,atol=1e-14):
        raise ValueError("Orthogonal effects do not reconstruct cell variance.")
    marginal=[]
    for i in range(7):
        low=np.flatnonzero(bits[:,i]==0)
        high=low+(1<<(6-i))
        differences=values[high]-values[low]
        marginal.append({"factor":i+1,"mean":float(np.mean(differences)),
                         "minimum":float(np.min(differences)),"maximum":float(np.max(differences)),
                         "positive_contexts":int(np.sum(differences>1e-9)),
                         "negative_contexts":int(np.sum(differences<-1e-9))})
    return {"effects":effects,"main_contexts":marginal,"variance":float(variance),
            "variance_fraction_by_order":{i:sum(e["variance"] for e in effects if len(e["factors"])==i)/variance
                                          if variance else 0 for i in range(1,8)}}


def main():
    inventory=read(DEST/"inventory.json")
    routes=read(DEST/"routing-index.json")
    study=Study()
    maps=inventory["maps"]
    bits=np.array([m["bits"] for m in maps],dtype=int)
    geometry=read(ROOT/"flat-40/geometry.json")["candidates"]
    core=set(inventory["core"])
    rows=[]
    arrays={k:[] for k in ("angular","metric")}
    for row in maps:
        result=read(DEST/"routes"/f'{row["id"]}.json')
        ids=set(row["ids"])
        points={tuple(p) for i in ids for j,p in geometry[i]["transverse"].items() if int(j) in ids and i<int(j)}
        rows.append({"id":row["id"],"bits":row["bits"],"ids":row["ids"],"length":row["length"],
                     "intersection_count":row["intersection_count"],"transverse_sites":len(points),
                     **{f"{k}_{metric}":result[k][metric] for k in arrays for metric in ("mean","median","p95","max")},
                     **{f"{k}_{metric}":result[f"{k}_{metric}"] for k in arrays for metric in ("mean_excess","worst_excess")}})
        for k in arrays:
            arrays[k].append(result[f"{k}_routes"])
    values={k:np.array([row[k] for row in rows]) for k in METRICS}
    effects={k:factorial(v,bits) for k,v in values.items()}
    distributions={k:summarize(v) for k,v in values.items()}
    best={k:min(rows,key=lambda r:(r[k],r["id"])) for k in METRICS}
    for row in rows:
        row["balanced"] = mean((row[k]-float(np.min(values[k])))/float(np.ptp(values[k]))
                               if np.ptp(values[k]) else 0 for k in ("angular_mean","metric_mean"))
    best["balanced"]=min(rows,key=lambda r:(r["balanced"],r["id"]))
    pareto=[r for r in rows if not any(q["angular_mean"]<=r["angular_mean"]+1e-12
            and q["metric_mean"]<=r["metric_mean"]+1e-12 and
            (q["angular_mean"]<r["angular_mean"]-1e-12 or q["metric_mean"]<r["metric_mean"]-1e-12) for q in rows)]

    vertex=read(OUTPUT/"flat-40.json")
    archived_pairs=read(PRIOR/"analysis.json")["interchangeable_pairs"]
    fixed=[]
    contextual={}
    for pair in inventory["pairs"]:
        records=[]
        for i in pair:
            g=geometry[i]
            span=g["family_span"]*study.length[i]
            records.append({"id":i,"length":study.length[i],"orientation_degrees":vertex["lines"][i]["angle"],
                "supporting_vertices":[vertex["vertices"][v] for v in vertex["lines"][i]["support"]],
                "region_ids":g["regions"],"regions":len(g["regions"]),
                "doorway_ids":g["doorways"],"doorways":len(g["doorways"]),
                "transverse":len(g["transverse"]),"full_intersections":len(g["intersections"]),
                "full_transverse_families":g["families"],"transverse_families":len(g["families"]),
                "mandatory_intersection_ids":sorted(study.neighbors[i]&core),
                "mandatory_intersections":len(study.neighbors[i]&core),
                "transverse_span":span})
        fixed.append({"pair":pair,"members":records,
                      "differences_second_minus_first":{k:records[1][k]-records[0][k] for k in GEOMETRIC},
                      "similarity":next(r for r in archived_pairs if r["ids"]==pair)})
    for row in maps:
        extras=set(row["alternatives"])
        contextual[row["id"]]=[{"id":i,"other_alternative_intersections":sorted(study.neighbors[i]&extras),
                               "other_alternative_transverse":sorted(study.transverse[i]&extras),
                               "active_transverse_families":[sorted(set(g)&set(row["ids"]))
                                  for g in geometry[i]["families"] if set(g)&set(row["ids"])]}
                              for i in row["alternatives"]]
    predictors={}
    for cost in ("angular_mean","metric_mean"):
        changes=[r["mean"] for r in effects[cost]["main_contexts"]]
        predictors[cost]={}
        for name in GEOMETRIC:
            deltas=[row["differences_second_minus_first"][name] for row in fixed]
            observed=[(d,c) for d,c in zip(deltas,changes) if abs(d)>1e-9 and abs(c)>1e-9]
            predictors[cost][name]={"higher_feature_improved":sum(d*c<0 for d,c in observed),
                                    "higher_feature_worsened":sum(d*c>0 for d,c in observed),
                                    "ties_or_no_effect":len(deltas)-len(observed),
                                    "pearson_descriptive":float(np.corrcoef(deltas,changes)[0,1])
                                    if np.std(deltas)>0 and np.std(changes)>0 else None}

    indices=np.array(routes["pairs"],dtype=int)
    signs_to_costs={k:np.array(v) for k,v in arrays.items()}
    door_points=[Point([float(Fraction(x)) for x in row["point"]]) for row in routes["doorways"]]
    labels=routes["building_labels"]
    door_effects=[]
    for index,pair in enumerate(inventory["pairs"]):
        start=np.flatnonzero(bits[:,index]==0)
        other=start+(1<<(6-index))
        near=np.array([min(study.segments[i].distance(p) for i in pair)<=10 for p in door_points])
        both_remote=~(near[indices[:,0]]|near[indices[:,1]])
        costs={}
        for metric,arr in signs_to_costs.items():
            difference=arr[other]-arr[start]
            affected=np.abs(difference)>1e-9
            ever=affected.any(axis=0)
            per_pair_max=np.max(np.abs(difference),axis=0)
            per_pair_mean=np.mean(difference,axis=0)
            biggest=np.argsort(-per_pair_max,kind="stable")[:10]
            counts=np.bincount(indices[ever].ravel(),minlength=100)
            costs[metric]={"affected_pair_count":int(ever.sum()),"affected_context_pair_count":int(affected.sum()),
                "mean_absolute_change_affected":float(np.mean(np.abs(difference[affected]))) if affected.any() else 0,
                "maximum_absolute_change":float(per_pair_max.max()),
                "remote_affected_pairs":int((ever&both_remote).sum()),"remote_pair_count":int(both_remote.sum()),
                "affected_by_building":{labels[j]:int(n) for j,n in enumerate(counts)},
                "per_pair":[{"index":int(j),"average_change":float(per_pair_mean[j]),
                             "max_absolute_change":float(per_pair_max[j]),
                             "affected_contexts":int(affected[:,j].sum())} for j in np.flatnonzero(ever)],
                "largest":[{"index":int(j),"buildings":[labels[n] for n in indices[j]],
                            "max_absolute_change":float(per_pair_max[j])} for j in biggest if ever[j]]}
        door_effects.append({"pair":pair,"spatial_near_units":10,"costs":costs})

    from experiments.recombine_flat40_extended import DEST as EXTDIR
    if read(EXTDIR/"unions.json")["source"]!=study.source:
        raise ValueError("Archived control lineage differs from the factorial inputs.")
    archive=read(EXTDIR/"movement.json")
    full_best=read(EXTDIR/"full-exchanges.json")["best"]["start"]
    controls={"Algorithm D":archive["methods"]["Algorithm D"]["final"],"Strict backward":archive["baseline"],
              "C-H":archive["methods"]["C-H"]["final"],
              "Best full-pool exchange":archive["methods"][f"full from {full_best}"]["final"]}
    control_ids=read(EXTDIR/"final-inventories.json")["maps"]
    saved_ids={"Algorithm D":control_ids["Algorithm D"],"Strict backward":control_ids["Strict backward"],
               "C-H":control_ids["C-H"],"Best full-pool exchange":control_ids["full-best"]}
    controls={name:{"count":r["count"],"length":r["length"],"ids":saved_ids[name],
                    "factorial_id":next((row["id"] for row in maps if row["ids"]==sorted(saved_ids[name])),None),
                    **{f"{k}_{s}":r[k][s] for k in arrays for s in ("mean","p95")}} for name,r in controls.items()}
    ch=controls["C-H"]["factorial_id"]
    if ch is None:
        raise ValueError("The C-H control was not recovered in the factorial family.")
    ch_result=read(DEST/"routes"/f"{ch}.json")
    for cost in arrays:
        if not np.allclose(ch_result[f"{cost}_routes"], archive["methods"]["C-H"]["final"][f"{cost}_routes"],
                           rtol=0,atol=1e-10):
            raise ValueError(f"C-H comparison disagrees with the established {cost} routing.")
    save("performance",{"rows":rows,"distributions":distributions,"best":best,"pareto":pareto,
                        "controls":controls,"balance":"Equal mean of min–max normalised angular and metric means."})
    save("factorial",{"contrasts":effects,"geometric_predictors":predictors})
    save("candidate-geometry",{"fixed":fixed,"contextual":contextual,
                             "exact_U3_intervals":read(PRIOR/"analysis.json")["exact_union_inventory"]})
    save("doorway-effects",door_effects)


if __name__=="__main__":
    main()
