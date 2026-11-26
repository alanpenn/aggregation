"""Checkpointed Flat 40 replay of the reference oriented-extension crawler."""
import argparse
from collections import Counter
from fractions import Fraction as F
import gzip
from hashlib import sha256
from itertools import pairwise
from math import hypot
from pathlib import Path
import sys

from experiments.flat40_face_extension import load_inputs
from experiments.flat40_region257_inspection import packed
from experiments.oriented_extension_reference import check_references
from experiments.oriented_extension_turns import ADMISSIBLE, ExtensionCrawler
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.research_data import sha256_file


class Replay:
    def __init__(self,crawler,occupied,out):
        self.crawler=crawler
        self.occupied=occupied
        self.out=out
        self.states=sorted({x for group in crawler.outgoing.values() for x in group})
        self.ids={t:i for i,t in enumerate(self.states)}

    def encode_options(self,options):
        return [[self.ids[t],reason] for t,reason in options]

    def save_stack(self,stack):
        return [{"route":[self.ids[x] for x in route],"supports":sorted(supports),
                 "history":[[self.ids[a],self.ids[b],action,self.encode_options(opts)]
                            for a,b,action,opts in history]}
                for route,_,supports,history in stack]

    def load_stack(self,saved):
        result=[]
        for item in saved:
            route=tuple(self.states[x] for x in item["route"])
            history=tuple((self.states[a],self.states[b],action,
                           tuple((self.states[c],reason) for c,reason in opts))
                          for a,b,action,opts in item["history"])
            vertices=(route[0][1],*(s[2] for s in route))
            result.append((route,vertices,frozenset(item["supports"]),history))
        return result

    def batch(self,sign,budget):
        starts=[t for h,t in self.crawler.starts() if h==sign]
        directory=self.out/("right" if sign==1 else "left")
        directory.mkdir(exist_ok=True)
        previous=sorted(directory.glob("*.json.gz"))
        if previous:
            import json
            with gzip.open(previous[-1],"rb") as f:
                saved=json.load(f)["after"]
        else:
            saved={"origin":0,"stack":None,"popped":0}
        i=saved["origin"]
        todo=self.load_stack(saved["stack"]) if saved["stack"] is not None else None
        count=0
        records=[]
        while i<len(starts) and count<budget:
            for route,options,closed,rejections,pending in self.crawler.traverse(
                    starts[i],sign,self.occupied,todo):
                outputs=[]
                for polygon,path in closed:
                    vertices=packed(polygon)
                    outputs.append({"id":sha256(encode(vertices)).hexdigest()[:16],
                                    "vertices":vertices,"points":path["points"],
                                    "turns_at_extensions":sum(t[2]=="turn_towards_originating_face"
                                                               for t in path["transitions"]),
                                    "transitions":[[self.ids[a],self.ids[b],action,self.encode_options(opts)]
                                                   for a,b,action,opts in path["transitions"]]})
                records.append({"origin":i,"path":[self.ids[t] for t in route],
                                "outgoing":self.encode_options(options),"closed":outputs,
                                "rejections":dict(rejections)})
                count+=1
                if count>=budget:
                    todo=pending
                    break
            else:
                i+=1
                todo=None
                continue
            if not todo:
                i+=1
                todo=None
            break
        result={"origin":i,"total_origins":len(starts),"stack":self.save_stack(todo) if todo is not None else None,
                "popped":saved["popped"]+count,"complete":i==len(starts)}
        if records:
            atomic_write(directory/f"{len(previous):06d}.json.gz",
                         gzip.compress(encode({"after":result,"records":records}),mtime=0))
        return result


def geometry(manifest,out):
    study,ch,d,provenance,occupied,domain,blocks=load_inputs(manifest)
    ref=check_references()
    if not ref[3]["full_coverage"] or not ref[7]["full_coverage"]:
        raise ValueError("Reference fixture failed.")
    crawler=ExtensionCrawler(domain,blocks)
    replay=Replay(crawler,occupied,out)
    direction_data={"input_lineage":provenance["lineage"],"inputs":provenance["verified_inputs"],
                    "crawler_sha256":sha256_file(Path(__file__).with_name("oriented_extension_turns.py")),
                    "checkpoint_code_sha256":sha256_file(__file__),
                    "faces":[f.record() for f in crawler.faces],
                    "tracks":[{"id":t.id,"face":t.face,"interval":packed((t.a,t.b)),"physical":t.wall,
                              "towards_admissible_sign":-t.away_sign if not t.wall else None}
                              for t in crawler.tracks],
                    "directed_edges":[{"track":i,"interval":packed((a,b))} for i,a,b in replay.states],
                    "start_ids":{str(h):[replay.ids[t] for k,t in crawler.starts() if h==k] for h in (1,-1)},
                    "intersection_vertices":sum(len({t[0] for t in group})>1 for group in crawler.outgoing.values())}
    path=out/"geometry.json"
    if path.exists():
        if path.read_bytes()!=encode(direction_data):
            raise ValueError("Checkpoint and exact geometry or algorithm versions differ.")
    else:
        out.mkdir(parents=True,exist_ok=False)
        atomic_write(path,encode(direction_data))
    return study,ch,occupied,domain,replay


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--states-per-hand",type=int,default=10000)
    parser.add_argument("--batch",type=int,default=500)
    args=parser.parse_args()
    if min(args.batch,args.states_per_hand)<1:
        parser.error("Batch and per-hand budget must be positive.")
    _,_,_,_,r=geometry(args.manifest,args.output)
    print(len(r.crawler.faces),"boundary faces",len(r.crawler.tracks)-len(r.crawler.faces),
          "extensions",len(r.states),"directed subedges",flush=True)
    for first in range(0,args.states_per_hand,args.batch):
        budget=min(args.batch,args.states_per_hand-first)
        for hand in (1,-1):
            result=r.batch(hand,budget)
            print(hand,{k:v for k,v in result.items() if k!="stack"},
                  "pending prefixes",len(result["stack"] or []),flush=True)


if __name__=="__main__":
    sys.set_int_max_str_digits(0)
    main()
