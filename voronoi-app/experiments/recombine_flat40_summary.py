"""Export the movement and structural comparison of every saved outcome."""
from csv import DictWriter
from io import StringIO

from experiments.occupied_vertex_pruning import read
from experiments.recombine_flat40_extended import DEST, ORDERS
from voronoi_app.batch_store import atomic_write


def main():
    movement=read(DEST/"movement.json")
    union_data=read(DEST/"unions.json")
    reference=movement["full_pool_reference"]
    records={f"{u}-{o}":read(DEST/f"{u}-{o}.json") for u in union_data["unions"] for o in ORDERS}
    for mode in ("union","full"):
        records.update({f"{mode} from {r['start']}":r for r in read(DEST/f"{mode}-exchanges.json")["outcomes"]})
    sources={name:row["final"] for name,row in movement["methods"].items()}
    sources["Strict backward"]=movement["baseline"]
    rows=[]
    for name,route in sources.items():
        if not route["valid"] or any(route[k]["reachable"]!=4950 for k in ("angular","metric")):
            raise ValueError(f"Incomplete certified doorway costs in {name}.")
        record=records.get(name,{})
        counts=record.get("counts",{})
        row={"map":name,"count":route["count"],"total_length":route["length"],
             "starting_count":record.get("starting_count",len(record.get("start_ids",())) or None),
             "deletions":len(record["deletions"]) if "deletions" in record else None,
             "proposals":counts.get("proposals"),"dynamic_winding_checks":counts.get("dynamic_validator"),
             "full_winding_checks":counts.get("full_validator",0)+counts.get("fallback_validator",0) if counts else None,
             "seconds":record.get("seconds"),"peak_rss_mib":record.get("peak_rss_mib"),
             "parent_identity":"/".join(record.get("parent_identity",())),
             "outside_U3":",".join(map(str,record.get("outside_U3",())))}
        for cost in ("angular","metric"):
            for stat in ("mean","median","p95","max"):
                row[f"{cost}_{stat}"]=route[cost][stat]
            row[f"{cost}_mean_excess"]=route[cost]["mean"]-reference[cost]
            worst=route[f"{cost}_worst_excess"]
            row[f"{cost}_worst_increase"]=worst[0]["increase"] if worst else 0
            row[f"{cost}_worst_buildings"]="/".join(map(str,worst[0]["buildings"])) if worst else ""
        rows.append(row)
    stream=StringIO(newline="")
    csv=DictWriter(stream,fieldnames=list(rows[0]))
    csv.writeheader()
    csv.writerows(rows)
    atomic_write(DEST/"comparison.csv",stream.getvalue().encode())


if __name__=="__main__":
    main()
