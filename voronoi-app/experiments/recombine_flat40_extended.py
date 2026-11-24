"""Run the complete Flat 40 recombination protocol on certified intervals."""
from collections import Counter
from functools import cache
from hashlib import sha256
from itertools import combinations
from time import monotonic
import argparse

import networkx as nx

from experiments.constructive_axial import ROOT, evaluate
from experiments.controlled_preselection import Study as BaseStudy, check, metrics
from experiments.occupied_vertex_pruning import OUTPUT, read
from experiments.recombine_flat40 import DEST as EXACT
from experiments.strict_generalisation import rss_mib
from voronoi_app.angular import _on_segment
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.sheaf_experiment import interval, overlap, similarity

DEST = OUTPUT.parent / "recombined-axial-maps-2"
ORDERS = ("shortest", "longest", "sheaf", "transverse", "geometry")
KINDS = ((1,1),(2,1),(3,2),(4,2))
LIMIT = 96
ROUNDS = 2


def save(name, data):
    atomic_write(DEST / f"{name}.json",encode(data))


class Study(BaseStudy):
    def priority(self, i, current, counts, order):
        if order=="longest":
            return (-self.length[i],i)
        return super().priority(i,current,counts,order)

    @cache
    def certificate(self, ids):
        return check(self,set(ids))

    def winding_support(self, ids):
        topology=self.full(set(ids),faces=True)
        rows=[]
        for cycle in topology["circulation_cycles"]:
            ring=topology["witness_faces"][cycle["face_index"]]
            owners={i for a,b in zip(ring,ring[1:]) for i in ids
                    if _on_segment(a,*interval(self.lines[i])) and _on_segment(b,*interval(self.lines[i]))}
            rows.append({"blocks":cycle["enclosed_blocks"],"support":sorted(owners),
                         "ring":[list(map(str,p)) for p in ring]})
        return rows

    @cache
    def near(self, i, j):
        return overlap(self.segments[i],self.segments[j])

    @cache
    def quality(self, chosen):
        current=set(chosen)
        all_sites={tuple(p) for i in current for j,p in self.transverse_points[i].items()
                   if j in current and j>i}
        return (len(current),sum(self.length[i] for i in sorted(current)),-len(all_sites))

    def setup(self):
        self.transverse_points=[{int(j):p for j,p in row["transverse"].items()}
            for row in read(ROOT/"flat-40/geometry.json")["candidates"]]

    def alternatives(self, current, allowed, kind, union):
        remove_count,add_count=kind
        available=allowed-current
        counts=self.counts_for(current)
        high=sorted(available,key=lambda j:(-len(self.transverse[j]&current),
                    -len(self.neighbors[j]&current),-self.length[j],j))[:6]
        proposals={}
        for first in sorted(current):
            local=[j for j in self.corridor_replacements(first) if j in available][:9]
            # All union alternatives can be proposed. Full-pool alternatives
            # add a bounded corridor list and the strongest transverse options.
            additions=sorted(available) if allowed==union else list(dict.fromkeys(local+high+sorted(available&union)))
            peers=sorted(current-{first},key=lambda j:(-len(self.cover[first]&self.cover[j]),
                        j not in self.neighbors[first],j))[:5]
            drops=combinations(peers,remove_count-1)
            for rest in drops:
                old=tuple(sorted((first,*rest)))
                losses=Counter(r for i in old for r in self.by_line[i])
                required={r for r,n in losses.items() if counts[r]==n}
                for new in combinations(additions,add_count):
                    new=tuple(sorted(new))
                    supplied=set().union(*(self.by_line[j] for j in new))
                    if required-supplied:
                        continue
                    trial=(current-set(old))|set(new)
                    trial_key=self.quality(frozenset(trial))
                    if trial_key>=self.quality(frozenset(current)):
                        continue
                    affine=sum(len(self.cover[i]&self.cover[j]) for i in old for j in new)
                    pair=(old,new)
                    proposals[pair]=(trial_key,-affine,old,new)
        return sorted(proposals,key=proposals.__getitem__)[:LIMIT]

    def shuffle_down(self, current, allowed, order, union):
        trace=[]
        for round_number in range(1,ROUNDS+1):
            changed=False
            for kind in KINDS:
                counts=self.counts_for(current)
                record={"round":round_number,"remove_add":list(kind),"start_ids":sorted(current),
                        "tested":[],"accepted":None}
                for old,new in self.alternatives(current,allowed,kind,union):
                    status,_=self.validate(current,set(old),set(new),counts)
                    record["tested"].append({"remove":old,"add":new,"status":status})
                    if status!="valid":
                        continue
                    trial=(current-set(old))|set(new)
                    certificate=self.certificate(frozenset(trial))
                    deletions=[]
                    self.reduce(trial,order,deletions)
                    current=trial
                    record["accepted"]={"removed":old,"added":new,"subsequent_deletions":deletions,
                                        "exchange_winding":certificate,"final_ids":sorted(current)}
                    changed=True
                    break
                trace.append(record)
            if not changed:
                break
        return current,trace


def lineage(study):
    exact=read(EXACT/"results.json")
    detail=read(EXACT/"analysis.json")
    if exact["source"]!=study.source or detail["source"]!=study.source:
        raise ValueError("The union proof uses different exact inputs.")
    if detail["pool_sha256"]!=sha256(encode(study.inputs["candidates"]["pool"])).hexdigest():
        raise ValueError("The full certified interval inventory changed.")
    parents={k:set(v["ids"]) for k,v in exact["parents"].items()}
    if parents["F-S"]!=parents["F-H"]:
        raise ValueError("Full-pool parent maps differ.")
    groups={"U1":("F-S","C-S"),"U2":("F-H","C-H"),"U3":("F-S","C-S","C-H")}
    unions={}
    for k,names in groups.items():
        parts=[parents[n] for n in names]
        ids=set.union(*parts)
        unions[k]={"ids":sorted(ids),"shared":sorted(set.intersection(*parts)),
                   "parents":list(names),"contributions":{i:[n for n in names if i in parents[n]] for i in sorted(ids)},
                   "overlap":[{"parents":[a,b],"intersection":len(parents[a]&parents[b]),
                               "jaccard":similarity(parents[a],parents[b])} for a,b in combinations(names,2)],
                   "metrics":metrics(study,ids),"winding":study.certificate(frozenset(ids))}
    return exact,parents,unions


def finish(study, ids, parents, union):
    ids=set(ids)
    return {"ids":sorted(ids),"metrics":metrics(study,ids),
            "winding":study.certificate(frozenset(ids)),
            "strict_regions":sorted(study.regions),"doorways":len(study.doors),"components":1,
            "parent_identity":[name for name,selected in parents.items() if ids==selected],
            "outside_U3":sorted(ids-union)}


def run():
    DEST.mkdir(exist_ok=True)
    study=Study()
    study.setup()
    exact,parents,unions=lineage(study)
    save("unions",{"source":study.source,"parents":exact["parents"],"unions":unions,
                   "exact_inventory":read(EXACT/"analysis.json")["exact_union_inventory"]})
    union=set(unions["U3"]["ids"])
    if any(not study.clear(i) for i in union) or study.winding.rank(union)!=24:
        raise ValueError("Union dynamic precheck failed.")
    for group,row in unions.items():
        for order in ORDERS:
            name=f"{group}-{order}"
            if (DEST/f"{name}.json").exists():
                continue
            started=monotonic()
            study.counts.clear()
            study.timings.clear()
            ids=set(row["ids"])
            deletions=[]
            blocked=study.reduce(ids,order,deletions)
            if set(blocked)!=ids:
                raise ValueError("Single deletion irreducibility sweep incomplete.")
            record=finish(study,ids,parents,union)
            record.update({"union":group,"order":order,"starting_count":len(row["ids"]),
                           "deletions":deletions,"blockers":blocked,"counts":dict(study.counts),
                           "validation_seconds":dict(study.timings),"seconds":monotonic()-started,
                           "peak_rss_mib":rss_mib()})
            save(name,record)
            print(name,len(ids),flush=True)
    # Begin at each distinct direct map; identical states and the same
    # post-exchange priority share one search. The union minimum remains exact.
    for mode in ("union","full"):
        if (DEST/f"{mode}-exchanges.json").exists():
            continue
        started=monotonic()
        allowed=union if mode=="union" else set(study.graph)
        outcomes=[]
        visited=set()
        for group in unions:
            for order in ORDERS:
                direct=read(DEST/f"{group}-{order}.json")
                key=tuple(direct["ids"])
                if key in visited:
                    continue
                visited.add(key)
                study.counts.clear()
                study.timings.clear()
                before=monotonic()
                retained,trace=study.shuffle_down(set(key),allowed,"shortest",union)
                record=finish(study,retained,parents,union)
                record.update({"start":f"{group}-{order}","start_ids":list(key),"trace":trace,
                               "counts":dict(study.counts),"validation_seconds":dict(study.timings),
                               "seconds":monotonic()-before,"peak_rss_mib":rss_mib()})
                outcomes.append(record)
                print(mode,group,order,len(retained),flush=True)
        best=min(outcomes,key=lambda r:(study.quality(frozenset(r["ids"])),r["ids"]))
        save(f"{mode}-exchanges",{"source":study.source,"mode":mode,"rounds":ROUNDS,
                                  "proposals_per_type":LIMIT,"exchange_types":KINDS,
                                  "outcomes":outcomes,"best":best,"seconds":monotonic()-started})


def analyze():
    study=Study()
    study.setup()
    lineage_data=read(DEST/"unions.json")
    parents={name:set(row["ids"]) for name,row in lineage_data["parents"].items()}
    for name, row in lineage_data["parents"].items():
        parent=OUTPUT.parent/"frozen-preselection-1"/f"{name}-exchange.json"
        if sha256(parent.read_bytes()).hexdigest()!=row["sha256"]:
            raise ValueError(f"Exact parent record changed: {name}.")
    u3=set(lineage_data["unions"]["U3"]["ids"])
    inventory=[]
    for i in sorted(u3):
        row=study.lines[i]
        inventory.append({"id":i,"parent_maps":[n for n,ids in parents.items() if i in ids],
                          "length":row.length,"regions":sorted(study.cover[i]),
                          "doorways":[j for j,ids in enumerate(study.doors) if i in ids],
                          "transverse_neighbors_in_U3":sorted(study.transverse[i]&u3),
                          "transverse_neighbors_full":sorted(study.transverse[i])})
    vertex=read(OUTPUT/"flat-40.json")
    for row in inventory:
        row["convex_vertex_support"]=[vertex["vertices"][v] for v in vertex["lines"][row["id"]]["support"]]
    witness={n:study.winding_support(ids) for n,ids in parents.items() if n!="F-H"}
    # A complete exact face check after each deletion identifies the classes
    # that merge or vanish, separately from the strict-incidence blockers.
    best=set(read(DEST/"union-exchanges.json")["best"]["ids"])
    indispensability={}
    for i in sorted(best):
        remainder=best-{i}
        w=study.geometry.geometry(frozenset(remainder))
        indispensability[i]={"lost_regions":[r for r,ids in study.regions.items() if remainder.isdisjoint(ids)],
            "lost_doors":[j for j,ids in enumerate(study.doors) if remainder.isdisjoint(ids)],
            "components":nx.number_connected_components(study.graph.subgraph(remainder)),
            "winding_rank":w["independent_circulation_rank"],"lost_enclosures":w["missing_axial_rings"],
            "remaining_winding_classes":[c["enclosed_blocks"] for c in w["circulation_cycles"]],
            "merged_winding_classes":[c["enclosed_blocks"] for c in w["circulation_cycles"]
                                      if len(c["enclosed_blocks"])>1],
            "parent_winding_support":[name for name,rows in witness.items()
                                      if any(i in row["support"] for row in rows)]}
    save("line-analysis",{"union_candidates":inventory,"parents_winding":witness,
                          "best_union_winding":study.winding_support(best),
                          "union_best_indispensability":indispensability,
                          "independent_pair_analysis":read(EXACT/"analysis.json")["interchangeable_pairs"]})


def movement():
    study=Study()
    control=read(DEST/"unions.json")
    ids={name:row["ids"] for name,row in control["parents"].items() if name!="F-H"}
    ids["Algorithm D"]=read(ROOT/"flat-40/D.json")["maps"]["exchanged"]
    ids.update({k:read(DEST/f"{k}.json")["ids"] for k in
                (f"{u}-{order}" for u in control["unions"] for order in ORDERS)})
    for mode in ("union","full"):
        rows=read(DEST/f"{mode}-exchanges.json")["outcomes"]
        ids.update({f"{mode} from {r['start']}":r["ids"] for r in rows})
    result=evaluate(study.inputs,study.lines,study.clearance,study.reference,
                    {n:{"maps":{"final":v}} for n,v in ids.items()})
    from statistics import mean
    result["full_pool_reference"]={cost:mean(study.reference[cost]) for cost in ("angular","metric")}
    save("movement",result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("run","analyze","movement"))
    phase=parser.parse_args().phase
    {"run":run,"analyze":analyze,"movement":movement}[phase]()


if __name__=="__main__":
    main()
