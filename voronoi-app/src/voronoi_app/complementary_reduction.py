"""Reusable structural deletion and bounded exchange over exact candidates."""

from collections import Counter
from itertools import combinations, islice
from time import monotonic

from .sheaf_experiment import overlap

BUDGET = 160
ROUNDS = 2


class StructuralReduction:
    def clear(self, identifier):
        return identifier in self.safe_ids

    def exchange_key(self, ids):
        crossings = {tuple(point) for i in ids for j, point in self.measures[i]["transverse"].items()
                     if int(j) in ids and i < int(j)}
        return len(ids), sum(self.length[i] for i in sorted(ids)), -len(crossings)

    def counts_for(self,ids):
        return Counter(r for i in ids for r in self.by_line[i])

    def connected(self, ids):
        if not ids:
            return False
        first = min(ids)
        unseen = ids - {first}
        queue = [first]
        for i in queue:
            reached = self.neighbors[i] & unseen
            unseen -= reached
            queue.extend(reached)
            if not unseen:
                return True
        return False

    def validate(self, current, removed, added, counts):
        self.counts["proposals"] += 1
        if self.counts["proposals"] % 128 == 0:
            self.progress(self.stage, f"{self.counts['proposals']:,} structural proposals checked")
        delta = Counter(r for i in added for r in self.by_line[i])
        delta.subtract(r for i in removed for r in self.by_line[i])
        missing = [r for r, change in delta.items() if counts[r] + change <= 0]
        if missing:
            return ("region" if min(missing) < len(self.regions) else "doorway"), None
        if any(not self.clear(i) for i in added):
            return "clearance", None
        trial = (current - removed) | added
        if not self.connected(trial):
            return "connectivity", None
        started = monotonic()
        rank = self.winding.rank(trial)
        self.counts["dynamic_validator"] += 1
        self.timings["dynamic_validator"] += monotonic() - started
        if rank is None:
            started = monotonic()
            result = self.geometry.geometry(frozenset(trial))
            self.counts["fallback_validator"] += 1
            self.timings["fallback_validator"] += monotonic() - started
            if not result["circulation_constraints_satisfied"] or result["lines_crossing_effective_occupied_space"]:
                return "winding", None
        elif rank != self.winding.required:
            return "winding", None
        return "valid", delta
    def priority(self, i, current, counts, order):
        key = (self.length[i], i)
        return (-len(self.sheaf[i] & current), *key) if order == "sheaf" else key

    def reduce(self,current,order,trace):
        counts=self.counts_for(current)
        while True:
            blocked={}
            for i in sorted(current,key=lambda j:self.priority(j,current,counts,order)):
                status,changes=self.validate(current,{i},set(),counts)
                if status=="valid":
                    current.remove(i)
                    counts.update(changes)
                    trace.append(i)
                    break
                blocked[i]=status
            else:
                return blocked

    def corridor_replacements(self,i):
        if i in self.corridor_cache:
            return self.corridor_cache[i]
        # Geometric affinity and contact count order a bounded proposal list.
        options=[]
        for j,b in enumerate(self.segments):
            if j==i:
                continue
            angle,fraction,gap=overlap(self.segments[i],b)
            if angle<=27 and fraction>=.35 and gap<=4.5:
                options.append((-len(self.cover[i]&self.cover[j]),-fraction,
                                -len(self.neighbors[j]),-self.length[j],j))
        self.corridor_cache[i] = [row[-1] for row in sorted(options)[:18]]
        return self.corridor_cache[i]

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
                    if (self.historical_exchange and removes==adds
                            and sum(self.length[j] for j in new)<=sum(self.length[j] for j in old)):
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
                        trial = (current - set(old)) | set(new)
                        deletions=[]
                        self.reduce(trial,order,deletions)
                        if not self.historical_exchange and self.exchange_key(trial) >= self.exchange_key(current):
                            tested["no geometric improvement"] += 1
                            continue
                        current.clear()
                        current.update(trial)
                        accepted={"removed":old,"added":new,"subsequent_deletions":deletions}
                        progress=True
                        break
                trace.append({"round":round_no+1,"type":kind,"tested":dict(tested),"accepted":accepted})
            if not progress:
                break
        return trace
