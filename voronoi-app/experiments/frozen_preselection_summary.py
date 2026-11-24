"""Export count, timing, and movement comparisons without changing maps."""
from csv import DictWriter
from io import StringIO
from statistics import mean

from experiments.frozen_preselection import CASES, DEST, save
from experiments.occupied_vertex_pruning import read
from voronoi_app.batch_store import atomic_write


def main():
    movement=read(DEST/"movement.json")
    profile=read(DEST/"preselection-profile.json")
    rows=[]
    matches=[]
    for case in CASES:
        direct=read(DEST/f"{case}-direct.json")
        for phase in ("direct","exchange"):
            row=read(DEST/f"{case}-{phase}.json")
            route=movement["methods"][case][phase]
            if not route["valid"] or any(route[k]["reachable"]!=4950 for k in ("angular","metric")):
                raise ValueError(f"Missing certified route for {case}/{phase}")
            cumulative=row["construction_seconds"]+(direct["construction_seconds"] if phase=="exchange" else 0)
            result={"case":case,"phase":phase,"starting_count":row["starting_count"],**row["metrics"],
                    "winding_rank":row["winding"]["independent_circulation_rank"],
                    "proposals":row["counts"].get("proposals",0),"accepted_single_deletions":
                    len(row["deletions"])+sum(len(t["accepted"]["subsequent_deletions"])
                                             for t in row["exchanges"] if t["accepted"]),
                    "dynamic_winding_calls":row["counts"].get("dynamic_validator",0),
                    "full_winding_calls":row["counts"].get("full_validator",0)+row["counts"].get("fallback_validator",0),
                    "search_seconds":row["search_seconds"],"construction_seconds":row["construction_seconds"],
                    "cumulative_seconds_from_saved_inputs":cumulative,
                    "cumulative_seconds_with_reconstruction":cumulative+(profile["reconstruct_seconds"] if case[0]=="C" else 0),
                    "retrieval_seconds":row["retrieval_seconds"],"peak_rss_mib":row["peak_rss_mib"]}
            for cost in ("angular","metric"):
                for stat in ("mean","median","p95","max"):
                    result[f"{cost}_{stat}"]=route[cost][stat]
                result[f"{cost}_mean_excess"]=route[cost]["mean"]-movement["full_pool_reference"][cost]
                result[f"{cost}_max_pair_deterioration"]=max(
                    (p["increase"] for p in route[f"{cost}_worst_excess"]),default=0)
            rows.append(result)
    for order in ("S","H"):
        for phase in ("direct","exchange"):
            f,c=(movement["methods"][f"{p}-{order}"][phase] for p in ("F","C"))
            costs={}
            for name in ("angular","metric"):
                differences=[b-a for a,b in zip(f[f"{name}_routes"],c[f"{name}_routes"],strict=True)]
                costs[name]={"mean_delta_C_minus_F":mean(differences),
                             "C_cheaper":sum(d<-1e-9 for d in differences),
                             "F_cheaper":sum(d>1e-9 for d in differences),
                             "ties":sum(abs(d)<=1e-9 for d in differences)}
            matches.append({"order":order,"phase":phase,"costs":costs})
    stream=StringIO(newline="")
    csv=DictWriter(stream,fieldnames=list(rows[0]))
    csv.writeheader()
    csv.writerows(rows)
    atomic_write(DEST/"comparisons.csv",stream.getvalue().encode())
    save("matched-movement",{"rows":rows,"paired":matches,"full_pool_reference":movement["full_pool_reference"]})


if __name__=="__main__":
    main()
