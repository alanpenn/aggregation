"""Flat 40 experimental structural reduction, bounded exchanges and routing."""
from collections import Counter
from functools import cache
from hashlib import sha256
from itertools import combinations, islice
import argparse
from time import monotonic

import networkx as nx
from shapely.geometry import LineString

from experiments.constructive_axial import ROOT, evaluate, load
from experiments.dynamic_winding import CycleSignatures
from experiments.occupied_vertex_pruning import OUTPUT, read
from voronoi_app.angular import LineClearance
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.sheaf_experiment import overlap
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import Geometry

DEST = OUTPUT.parent / "unrestricted-structural-reduction-1"
ORDERS = ("shortest", "geometry", "region-overlap", "transverse", "sheaf", "sheaf-restricted")
BUDGET = 160
ROUNDS = 2


class Study:
    def __init__(self):
        self.inputs,self.source,self.reference=load("flat-40")
        self.previous=read(OUTPUT.parent/"complementary-sheaf-reduction-1/flat-40.json")
        if self.source!=self.previous["source"]:
            raise ValueError("The conservative result has different certified inputs.")
        self.lines=exact_pool_from_dict(self.inputs["candidates"]["pool"]).candidates
        data=read(ROOT/"flat-40/geometry.json")["candidates"]
        self.graph=nx.Graph()
        self.graph.add_nodes_from(range(len(self.lines)))
        self.graph.add_edges_from((row["id"],j) for row in data for j in row["intersections"])
        self.neighbors=[set(self.graph[i]) for i in self.graph]
        self.transverse=[set(map(int,row["transverse"])) for row in data]
        self.length=[line.length for line in self.lines]
        self.segments=[LineString([line.start,line.end]) for line in self.lines]
        self.regions,self.doors=incidence_sets(self.inputs["analysis"]["incidence"])
        self.incidence=list(self.regions.values())+self.doors
        self.cover=[set(row["regions"]) for row in data]
        self.by_line=[set() for _ in self.lines]
        for requirement,ids in enumerate(self.incidence):
            for i in ids:
                self.by_line[i].add(requirement)
        self.sheaf=[set() for _ in self.lines]
        for group in self.previous["sheaves"]:
            for i in group["ids"]:
                self.sheaf[i].update(set(group["ids"])-{i})
        self.geometric=[{} for _ in self.lines]
        for i, rows in self.previous["cross_vertex_matches"].items():
            for row in rows:
                a,f,g,_,_=row["diagnostics"]
                self.geometric[int(i)][row["line"]]=f/(1+a/21+g/3)
        _,occupied,accessible,obstacles=_domain(self.inputs)
        self.clearance=IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
        self.geometry=Geometry(self.inputs,self.lines,self.graph,self.clearance)
        polygons,_,_=_settlement(self.inputs)
        self.winding=CycleSignatures(self.lines,self.graph,polygons,self.geometry.blocks)
        self.counts=Counter()
        self.timings=Counter()

    @cache
    def clear(self,i):
        line=self.lines[i]
        return self.clearance.permits(line.start,line.end)

    def full(self,ids, *, faces=False):
        started=monotonic()
        result=self.geometry.geometry(frozenset(ids),witness=faces)
        self.counts["full_validator"]+=1
        self.timings["full_validator"]+=monotonic()-started
        if (not result["circulation_constraints_satisfied"]
            or result["lines_crossing_effective_occupied_space"]):
            raise ValueError("Independent full exact winding or clearance check failed.")
        return result

    def counts_for(self,ids):
        return Counter(r for i in ids for r in self.by_line[i])

    def validate(self,current,removed,added,counts):
        self.counts["proposals"]+=1
        changes=Counter(r for i in added for r in self.by_line[i])
        changes.subtract(r for i in removed for r in self.by_line[i])
        if any(counts[r]+n<=0 for r,n in changes.items()):
            missing=[r for r,n in changes.items() if counts[r]+n<=0]
            return ("region" if min(missing)<len(self.regions) else "doorway"),None
        if any(not self.clear(i) for i in added):
            return "clearance",None
        trial=(current-removed)|added
        if not trial or not nx.is_connected(self.graph.subgraph(trial)):
            return "connectivity",None
        started=monotonic()
        rank=self.winding.rank(trial)
        self.counts["dynamic_validator"]+=1
        self.timings["dynamic_validator"]+=monotonic()-started
        if rank is None:
            started=monotonic()
            exact=self.geometry.geometry(frozenset(trial))
            self.counts["fallback_validator"]+=1
            self.timings["fallback_validator"]+=monotonic()-started
            if not exact["circulation_constraints_satisfied"] or exact["lines_crossing_effective_occupied_space"]:
                return "winding",None
        elif rank!=self.winding.required:
            return "winding",None
        return "valid",changes

    def priority(self,i,current,counts,order):
        tie=(self.length[i],i)
        if order=="geometry":
            return (-max((w for j,w in self.geometric[i].items() if j in current),default=0),*tie)
        if order=="region-overlap":
            redundancy=sum(counts[r]-1 for r in self.by_line[i] if r<len(self.regions))
            return (-redundancy,*tie)
        if order=="transverse":
            return (len(self.transverse[i]&current),*tie)
        if order.startswith("sheaf"):
            return (-len(self.sheaf[i]&current),*tie)
        return tie

    def reduce(self,current,order,trace):
        counts=self.counts_for(current)
        while True:
            blocked={}
            for i in sorted(current,key=lambda j:self.priority(j,current,counts,order)):
                if order=="sheaf-restricted" and not self.sheaf[i]&current:
                    blocked[i]="same-sheaf restriction"
                    continue
                status,changes=self.validate(current,{i},set(),counts)
                if status=="valid":
                    current.remove(i)
                    counts.update(changes)
                    trace.append(i)
                    break
                blocked[i]=status
            else:
                return blocked

    @cache
    def corridor_replacements(self,i):
        # Geometric affinity and contact count order a bounded proposal list.
        options=[]
        for j,b in enumerate(self.segments):
            if j==i:
                continue
            angle,fraction,gap=overlap(self.segments[i],b)
            if angle<=27 and fraction>=.35 and gap<=4.5:
                options.append((-len(self.cover[i]&self.cover[j]),-fraction,
                                -len(self.neighbors[j]),-self.length[j],j))
        return [row[-1] for row in sorted(options)[:18]]

    def proposals(self,current,kind):
        removes,adds=kind
        global_alts=sorted(set(self.graph)-current,key=lambda j:(-len(self.neighbors[j]),-self.length[j],j))[:16]
        proposals=set()
        for i in sorted(current):
            peers=sorted((self.sheaf[i]|set(self.geometric[i])|self.neighbors[i])&current-{i},
                         key=lambda j:(-len(self.cover[i]&self.cover[j]),j))[:4]
            alternatives=list(dict.fromkeys([j for j in self.corridor_replacements(i) if j not in current]+global_alts))[:9]
            for rest in combinations(peers,removes-1):
                old=tuple(sorted((i,*rest)))
                for new in islice(combinations(alternatives,adds),15):
                    new=tuple(sorted(new))
                    if removes==adds and sum(self.length[j] for j in new)<=sum(self.length[j] for j in old):
                        continue
                    proposals.add((old,new))
        counts=self.counts_for(current)
        def priority(proposal):
            old,new=proposal
            supplied=set().union(*(self.by_line[i] for i in new))
            losses=Counter(r for i in old for r in self.by_line[i])
            missing=sum(counts[r]==lost and r not in supplied for r,lost in losses.items())
            affinity=sum(len(self.cover[i]&self.cover[j]) for i in old for j in new)
            return (missing,-affinity,-sum(self.length[j] for j in new),old,new)
        return sorted(proposals,key=priority)[:BUDGET]

    def exchange(self,current,order):
        trace=[]
        for round_no in range(ROUNDS):
            progress=False
            for kind in ((2,1),(3,2),(1,1)):
                counts=self.counts_for(current)
                tested=Counter()
                accepted=None
                for old,new in self.proposals(current,kind):
                    status,_=self.validate(current,set(old),set(new),counts)
                    tested[status]+=1
                    if status=="valid":
                        current.difference_update(old)
                        current.update(new)
                        deletions=[]
                        self.reduce(current,order,deletions)
                        accepted={"removed":old,"added":new,"subsequent_deletions":deletions}
                        progress=True
                        break
                trace.append({"round":round_no+1,"type":kind,"tested":dict(tested),"accepted":accepted})
            if not progress:
                break
        return trace


def run(orders):
    DEST.mkdir(exist_ok=True)
    study=Study()
    started=monotonic()
    initial=set(study.previous["repaired_ids"])
    if any(not study.clear(i) for i in initial):
        raise ValueError("Repaired certified input contains an unsafe line.")
    baseline=study.full(initial)
    if study.winding.rank(initial)!=baseline["independent_circulation_rank"]:
        raise ValueError("Dynamic winding did not match the exact start certificate.")
    atomic_write(DEST/"inputs.json",encode({"source":study.source,"starting_ids":sorted(initial),
                                          "startup_seconds":monotonic()-started,"winding":baseline}))
    for order in orders:
        started=monotonic()
        study.counts.clear()
        study.timings.clear()
        current=set(initial)
        trace=[]
        blocked=study.reduce(current,order,trace)
        direct=study.full(current)
        direct_ids=sorted(current)
        print(order,"direct",len(current),flush=True)
        exchanges=[] if order=="sheaf-restricted" else study.exchange(current,order)
        final_blocked=study.reduce(current,order,[])
        final=direct if sorted(current)==direct_ids else study.full(current)
        result={"order":order,"source":study.source,"deletions":trace,"direct_ids":direct_ids,
                "direct_winding":direct,"direct_blockers":blocked,
                "exchanges":exchanges,"final_ids":sorted(current),"final_winding":final,
                "final_blockers":final_blocked,"seconds":monotonic()-started,
                "validation_counts":dict(study.counts),"validation_seconds":dict(study.timings),
                "exchange_budget_per_type":BUDGET,"exchange_round_limit":ROUNDS}
        atomic_write(DEST/f"{order}.json",encode(result))
        print(order,"final",len(current),result["validation_counts"],flush=True)


def routes():
    study=Study()
    cases={o:read(DEST/f"{o}.json") for o in ORDERS}
    methods={o:{"maps":{"direct":r["direct_ids"],"exchange":r["final_ids"]}} for o,r in cases.items()}
    methods["controls"]={"maps":{"repaired":study.previous["repaired_ids"],"conservative":study.previous["retained"],
                                "algorithm_d":read(ROOT/"flat-40/D.json")["maps"]["exchanged"]}}
    atomic_write(DEST/"movement.json",encode(evaluate(study.inputs,study.lines,study.clearance,study.reference,methods)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--order",choices=ORDERS,action="append")
    parser.add_argument("--routes",action="store_true")
    args=parser.parse_args()
    if args.routes:
        routes()
    else:
        run(args.order or ORDERS)


if __name__=="__main__":
    main()
