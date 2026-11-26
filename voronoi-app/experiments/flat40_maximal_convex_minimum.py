"""Bounded exact cardinality search on the frozen Flat 40 maximal-cover maps."""
import argparse
from collections import Counter
from fractions import Fraction
from itertools import combinations
from pathlib import Path
import sys
from time import monotonic

import networkx as nx
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csc_matrix

from experiments.flat40_maximal_convex_axial import exact_incidence, load_experiment, save, variant
from experiments.near_collinear_consolidation import certificate
from experiments.occupied_vertex_pruning import read
from voronoi_app.research_data import sha256_file


class Search:
    def __init__(self, study, matrix):
        self.study = study
        self.keys = matrix["region_order"] + [f"door:{i}" for i in range(len(study.doors))]
        self.groups = list(study.incidence)
        self.masks = [sum(1 << i for i in group) for group in self.groups]
        self.all = (1 << len(study.lines)) - 1
        self.certificates = {}

    @staticmethod
    def bits(mask):
        while mask:
            bit = mask & -mask
            yield bit.bit_length()-1
            mask ^= bit

    def missing(self, rest):
        return [i for i,g in enumerate(self.groups) if rest.isdisjoint(g)]

    def independent(self, ids):
        ids = frozenset(ids)
        if ids not in self.certificates:
            self.certificates[ids] = certificate(self.study,ids)
        return self.certificates[ids]

    def assess(self, ids):
        if not self.study.connected(ids):
            return "connectivity"
        rank = self.study.winding.rank(ids)
        if rank is not None and rank != self.study.winding.required:
            return "winding"
        w = self.study.geometry.geometry(frozenset(ids))
        if not w["circulation_constraints_satisfied"]:
            return "winding"
        if w["lines_crossing_effective_occupied_space"]:
            return "clearance"
        self.independent(ids)
        return "accepted"

    def direct(self, ids):
        rows = []
        for i in sorted(ids):
            rest = ids-{i}
            gaps = self.missing(rest)
            components = nx.number_connected_components(self.study.graph.subgraph(rest))
            w = self.study.geometry.geometry(frozenset(rest))
            failures = []
            if any(k<len(self.study.regions) for k in gaps): failures.append("convex")
            if any(k>=len(self.study.regions) for k in gaps): failures.append("doorway")
            if components!=1: failures.append("connectivity")
            if not w["circulation_constraints_satisfied"]: failures.append("winding")
            if w["lines_crossing_effective_occupied_space"]: failures.append("clearance")
            rows.append({"removed":i,"missing":[self.keys[k] for k in gaps],"components":components,
                         "rank":w["independent_circulation_rank"],"failures":failures,"winding":w})
            if not failures:
                self.independent(rest)
        return rows

    def one(self, ids, remove_count, pool=None, extra_groups=()):
        extra = [(name,frozenset(group),sum(1 << i for i in group))
                 for name,group in extra_groups]
        pool = self.all if pool is None else pool
        available = pool & ~sum(1 << i for i in ids)
        rows = []
        for removed in combinations(sorted(ids),remove_count):
            rest = ids-set(removed)
            gaps = self.missing(rest)
            viable = available
            category = Counter()
            for r in gaps:
                before = viable.bit_count()
                viable &= self.masks[r]
                category["convex" if r<len(self.study.regions) else "doorway"] += before-viable.bit_count()
                if not viable: break
            missing_rays = []
            for name,group,mask in extra:
                if viable and rest.isdisjoint(group):
                    missing_rays.append(name)
                    before = viable.bit_count()
                    viable &= mask
                    category["winding_ray"] += before-viable.bit_count()
            trials = []
            for added in self.bits(viable):
                status = self.assess(rest|{added})
                trials.append({"added":[added],"status":status})
                category[status]+=1
            rows.append({"removed":removed,"missing":[self.keys[k] for k in gaps],
                         "counts":dict(category),"trials":trials,"screening_rays":missing_rays})
        return rows

    def two(self, ids, structure_budget, extra_groups=()):
        extra = [frozenset(g) for _,g in extra_groups]
        extra_masks = [sum(1 << i for i in g) for g in extra]
        masks = self.masks + extra_masks
        requirements = self.groups + extra
        available = self.all & ~sum(1 << i for i in ids)
        rows = []
        accepted = []
        checked = 0
        for removed in combinations(sorted(ids),3):
            rest = ids-set(removed)
            gaps = [i for i,g in enumerate(requirements) if rest.isdisjoint(g)]
            pivot = min(gaps,key=lambda i:(available & masks[i]).bit_count()) if gaps else None
            sides = available if pivot is None else available & masks[pivot]
            category = Counter()
            trials = []
            for a in self.bits(sides):
                options = available & ~(1 << a)
                # Pairs with both ends covering the pivot are counted once.
                options &= ~(sides & ((1 << a)-1))
                for r in gaps:
                    if not masks[r] & (1 << a):
                        options &= masks[r]
                        if not options: break
                for b in self.bits(options):
                    if checked >= structure_budget:
                        return {"rows":rows,"partial": {"removed":removed,"next":[a,b],"trials":trials},
                                "complete":False,"checked":checked}, accepted
                    checked += 1
                    status = self.assess(rest|{a,b})
                    trials.append({"added":sorted((a,b)),"status":status})
                    category[status]+=1
                    if status=="accepted":
                        accepted.append((removed,tuple(sorted((a,b)))))
            rows.append({"removed":removed,"counts":dict(category),"trials":trials})
        return {"rows":rows,"complete":True,"checked":checked}, accepted


def lower_bound(search):
    row,col = zip(*((i,j) for i,g in enumerate(search.groups) for j in sorted(g)))
    incidence = csc_matrix((np.ones(len(row)),(row,col)),shape=(len(search.groups),len(search.study.lines)))
    result = linprog(np.ones(incidence.shape[1]),A_ub=-incidence,b_ub=-np.ones(incidence.shape[0]),
                     bounds=(0,None),method="highs")
    if not result.success:
        raise RuntimeError(result.message)
    denominator = 10**8
    weights = [max(0,int(-x*denominator)) for x in result.ineqlin.marginals]
    totals = [sum(weights[i] for i in g) for g in search.study.by_line]
    denominator = max(denominator,max(totals))
    total = sum(weights)
    return {"bound":(total+denominator-1)//denominator,"denominator":denominator,
            "weight_sum":total,"maximum_weight_covered_by_a_line":max(totals),
            "integer_weights":dict(zip(search.keys,weights)),
            "rational_objective":str(Fraction(total,denominator)),
            "proof":"Summing weighted required incidences forces weight at least weight_sum. Each line supplies at most denominator."}


def valid_exchanges(base, rows):
    for r in rows:
        for trial in r["trials"]:
            if trial["status"]=="accepted":
                yield frozenset(base-set(r["removed"])|set(trial["added"])),r["removed"],trial["added"]


def main():
    sys.set_int_max_str_digits(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ("manifest","source","reference","output"):
        parser.add_argument("--"+n,type=Path,required=True)
    a=parser.parse_args()
    started=monotonic()
    frozen,atlas,_,new,provenance=load_experiment(a.manifest,a.source)
    a.output.mkdir(parents=True,exist_ok=False)
    names=("B-C-H","B-C-S")
    files=("incidence-B.json", *(f"{n}.json" for n in names),"comparison.json","movement.json","provenance.json")
    hashes={f:sha256_file(a.reference/f) for f in files}
    previous=read(a.reference/"provenance.json")
    for k in ("lineage","candidate_pool_sha256","cover_files","archived_convex_regions_sha256"):
        if provenance[k]!=previous[k]:
            raise ValueError(f"Frozen input changed: {k}")
    matrix=read(a.reference/"incidence-B.json")
    if exact_incidence(frozen.lines,new)["by_region"]!=matrix["by_region"]:
        raise ValueError("Exact frozen incidence differs.")
    study=variant(frozen,matrix)
    search=Search(study,matrix)
    controls={n:frozenset(read(a.reference/f"{n}.json")["ids"]) for n in names}
    if tuple(sorted(controls[names[0]]-controls[names[1]]))!=(1278,) or tuple(sorted(controls[names[1]]-controls[names[0]]))!=(1422,):
        raise ValueError("Frozen maps differ from reference.")
    compared=read(a.reference/"comparison.json")["maps"]
    for name,ids in controls.items():
        if search.independent(ids)!=compared[name]["certificate"]:
            raise ValueError(f"Structural certificate mismatch: {name}")
    save(a.output,"provenance",provenance|{"reference_sha256":hashes,"search_sha256":sha256_file(__file__)})
    save(a.output,"lower-bound",lower_bound(search))
    discovered = {}
    def register(name, ids, removed, added):
        discovered.setdefault(ids,[]).append({"origin":name,"removed":removed,"added":added})

    for name, ids in controls.items():
        direct=search.direct(ids)
        save(a.output,f"{name}-direct",direct)
        for row in direct:
            if not row["failures"]:
                register(name,ids-{row["removed"]},[row["removed"]],[])
        pairs=search.one(ids,2)
        save(a.output,f"{name}-two-for-one",pairs)
        for new_ids,removed,added in valid_exchanges(ids,pairs):
            register(name,new_ids,removed,added)
        print(name,"pair successes",sum(r["counts"].get("accepted",0) for r in pairs),flush=True)

    if not discovered:
        for name,ids in controls.items():
            results,hits=search.two(ids,20000)
            save(a.output,f"{name}-three-for-two",results)
            for removed,added in hits:
                register(name,ids-set(removed)|set(added),removed,added)
            print(name,"triple results",results["complete"],results["checked"],len(hits),flush=True)

    plateaus={ids:[] for ids in controls.values()}
    for name,ids in controls.items():
        rows=search.one(ids,1)
        save(a.output,f"{name}-one-for-one",rows)
        for trial,removed,added in valid_exchanges(ids,rows):
            plateaus.setdefault(trial,[]).append({"origin":name,"removed":removed,"added":added})
    alternatives=sorted(set(plateaus)-set(controls.values()),key=lambda ids:tuple(sorted(ids)))
    for ordinal,ids in enumerate(alternatives[:8],1):
        name=f"plateau-{ordinal:02d}"
        rows=search.one(ids,2)
        save(a.output,f"{name}-two-for-one",rows)
        for trial,removed,added in valid_exchanges(ids,rows):
            register(name,trial,removed,added)

    items=sorted(discovered,key=lambda ids:(len(ids),tuple(sorted(ids))))
    save(a.output,"results",{"controls":{k:sorted(v) for k,v in controls.items()},
          "common":sorted(set.intersection(*(set(v) for v in controls.values()))),
          "union":sorted(set.union(*(set(v) for v in controls.values()))),
          "alternatives":[{"ids":sorted(ids),"paths":plateaus[ids]} for ids in alternatives],
          "tested_plateau_maps":[sorted(ids) for ids in alternatives[:8]],
          "in_all_31_neighbourhood_maps":sorted(set.intersection(*(set(v) for v in plateaus))),
          "smaller":[{"ids":sorted(ids),"origins":discovered[ids],"certificate":search.certificates[ids]}
                     for ids in items],"seconds":monotonic()-started})
    print("Finished",len(alternatives),"alternative 31 maps;",len(items),"smaller maps",flush=True)


if __name__=="__main__":
    main()
