"""Analyze exact winding supports and paired corridor differences."""
from statistics import median, quantiles

from experiments.frozen_preselection import CASES, DEST, Study, save
from experiments.occupied_vertex_pruning import OUTPUT, read
from voronoi_app.angular import _on_segment
from voronoi_app.sheaf_experiment import DEFAULTS, interval, overlap, similarity

TARGETS = (957,1244,1355,865,1189,1190,1208,1354)


def distribution(values):
    return {"min":min(values),"max":max(values),"median":median(values),
            "quartiles":quantiles(values,n=4,method="inclusive")}


def main():
    study=Study()
    threshold=read(OUTPUT/"flat-40.json")["long_threshold"]
    degree=[len(n) for n in study.neighbors]
    upper_degree=sorted(degree,reverse=True)[len(degree)//4-1]
    rows={}
    for case in CASES:
        for phase in ("direct","exchange"):
            row=read(DEST/f"{case}-{phase}.json")
            ids=set(row["ids"])
            geometry=study.full(ids,faces=True)
            witnesses=[]
            for cycle in geometry["circulation_cycles"]:
                ring=geometry["witness_faces"][cycle["face_index"]]
                supporting=set()
                for first,last in zip(ring,ring[1:]):
                    supporting.update(i for i in ids if _on_segment(first,*interval(study.lines[i]))
                                      and _on_segment(last,*interval(study.lines[i])))
                witnesses.append({"blocks":cycle["enclosed_blocks"],"supporting_lines":sorted(supporting),
                                  "ring":[list(map(str,p)) for p in ring]})
            rows[f"{case}-{phase}"]={"lengths":distribution([study.length[i] for i in ids]),
                                   "transverse_degree":distribution([len(study.transverse[i]&ids) for i in ids]),
                                   "long_lines":sorted(i for i in ids if study.length[i]>=threshold),
                                   "high_full_degree":sorted(i for i in ids if degree[i]>=upper_degree),
                                   "targets":dict.fromkeys(TARGETS,False)|{i:True for i in ids.intersection(TARGETS)},
                                   "winding_faces":witnesses}
    comparisons=[]
    for order in ("S","H"):
        for phase in ("direct","exchange"):
            f,c=(set(read(DEST/f"{pool}-{order}-{phase}.json")["ids"]) for pool in ("F","C"))
            f_unique,c_unique=f-c,c-f
            matched=[]
            for i in sorted(f_unique):
                for j in sorted(c_unique):
                    angle,fraction,gap=overlap(study.segments[i],study.segments[j])
                    coverage=similarity(study.cover[i],study.cover[j])
                    if (angle<=DEFAULTS["maximum_angle"] and fraction>=DEFAULTS["minimum_overlap"]
                            and gap<=DEFAULTS["maximum_gap"] and coverage>=DEFAULTS["minimum_coverage_similarity"]):
                        matched.append({"F":i,"C":j,"angle":angle,"overlap":fraction,
                                        "gap":gap,"region_jaccard":coverage})
            f_coverage=set().union(*(study.cover[i] for i in f))
            c_coverage=set().union(*(study.cover[i] for i in c))
            f_support={i for face in rows[f"F-{order}-{phase}"]["winding_faces"] for i in face["supporting_lines"]}
            c_support={i for face in rows[f"C-{order}-{phase}"]["winding_faces"] for i in face["supporting_lines"]}
            comparisons.append({"order":order,"phase":phase,"shared":sorted(f&c),"F_only":sorted(f_unique),
                                "C_only":sorted(c_unique),"geometry_matches":matched,
                                "common_regions":sorted(f_coverage&c_coverage),
                                "region_jaccard":similarity(f_coverage,c_coverage),
                                "winding_support_shared":sorted(f_support&c_support),
                                "winding_support_F_only":sorted(f_support-c_support),
                                "winding_support_C_only":sorted(c_support-f_support)})
    save("inventory",{"source":study.source,"certified_pool":study.inputs["candidates"]["pool"],
                       "starts":{p:read(DEST/f"{p}-start.json")["ids"] for p in ("F","C")}})
    save("geometry",{"maps":rows,"comparisons":comparisons,"long_threshold":threshold,
                     "full_degree_upper_quartile_threshold":upper_degree})


if __name__=="__main__":
    main()
