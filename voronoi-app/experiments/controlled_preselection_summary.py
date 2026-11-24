"""Export the matched Flat 40 structural and movement comparisons."""
from csv import DictWriter
from io import StringIO
from statistics import mean

from experiments.controlled_preselection import DEST, ORDERS
from experiments.occupied_vertex_pruning import read
from voronoi_app.batch_store import atomic_write, encode


def main():
    route = read(DEST/"movement.json")
    starts = {p: read(DEST/f"{p}-start.json") for p in ("F","C","N")}
    runs = {f"{p}-{o}": read(DEST/f"{p}-{o}.json") for p in ("F","C") for o in ORDERS}
    runs["N-shortest"] = read(DEST/"N-shortest.json")
    records=[]
    matches=[]
    for name, row in runs.items():
        for phase, structure in (("direct","direct"),("exchange","final")):
            movement=route["methods"][name][phase]
            if (not movement["valid"] or movement["angular"]["reachable"]!=4950
                    or movement["metric"]["reachable"]!=4950
                    or row[f"{structure}_winding"]["independent_circulation_rank"]!=24):
                raise ValueError(f"Failed movement or structural validation in {name}/{phase}.")
            item={"pool":row["pool"],"order":row["order"],"stage":phase,
                  **row[structure],"winding_rank":24,
                  "angular_mean":movement["angular"]["mean"],"angular_p95":movement["angular"]["p95"],
                  "metric_mean":movement["metric"]["mean"],"metric_p95":movement["metric"]["p95"],
                  "angular_excess":movement["angular"]["mean"]-route["full_pool_reference"]["angular"],
                  "metric_excess":movement["metric"]["mean"]-route["full_pool_reference"]["metric"],
                  "elapsed_seconds":row["elapsed_seconds"],"deletion_seconds":row["deletion_seconds"],
                  "outside_start":len(set(row[f"{structure}_ids"])-set(starts[row["pool"]]["ids"]))}
            records.append(item)
    for order in ORDERS:
        for phase,key in (("direct","direct"),("exchange","final")):
            f,c=(runs[f"{p}-{order}"] for p in ("F","C"))
            first,second=(set(r[f"{key}_ids"]) for r in (f,c))
            measurement={}
            for cost in ("angular","metric"):
                a,b=(route["methods"][f"{p}-{order}"][phase][f"{cost}_routes"] for p in ("F","C"))
                delta=[y-x for x,y in zip(a,b,strict=True)]
                measurement[cost]={"mean_delta_C_minus_F":mean(delta),
                                   "pairs_cheaper_C":sum(v < -1e-9 for v in delta),
                                   "pairs_cheaper_F":sum(v > 1e-9 for v in delta),
                                   "pairs_tied":sum(abs(v)<=1e-9 for v in delta)}
            matches.append({"order":order,"stage":phase,"shared":sorted(first&second),
                            "F_only":sorted(first-second),"C_only":sorted(second-first),
                            "F_outside_complementary_start":sorted(first-set(starts["C"]["ids"])),
                            "doorway_cost_comparison":measurement})
    stream=StringIO(newline="")
    writer=DictWriter(stream,fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)
    atomic_write(DEST/"comparison.csv",stream.getvalue().encode())
    atomic_write(DEST/"matched-results.json",encode({"runs":records,"matches":matches,
                "baseline_metrics":{p:starts[p]["metrics"] for p in starts},
                "full_pool_reference":route["full_pool_reference"]}))


if __name__=="__main__":
    main()
