"""Audit semantic outward face orientation independently of directed walks."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
from itertools import pairwise
from pathlib import Path
import sys

from experiments.face_extension_cover import edge, rings
from experiments.flat40_face_extension import load_inputs, points
from experiments.flat40_exchange_atlas import Atlas
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed, ring
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _cross, _direction, _on_segment
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes
from voronoi_app.research_data import sha256_file


def coordinates(values):
    return [tuple(map(F,p)) for p in values]


def semantic_faces(blocks, records):
    faces=defaultdict(list)
    for name,poly in blocks:
        i=0
        for number,r in enumerate(rings(poly)):
            ccw=sum(_cross(x,y) for x,y in pairwise(r))>0
            occupied_left=ccw != (number>0)
            for a,b in pairwise(r):
                dx,dy=_direction(a,b)
                normal=(dy,-dx) if occupied_left else (-dy,dx)
                faces[name,i].append((a,b,normal,ccw,number))
                i+=1
    result={}
    for key,record in records.items():
        block,i,_=key.rsplit(":",2)
        p,q=coordinates(record["face"])
        options=[row for row in faces[block,int(i)]
                 if _on_segment(p,*row[:2]) and _on_segment(q,*row[:2])]
        if len(options)!=1:
            raise ValueError(f"Cannot recover unique physical source for {key}.")
        a,b,normal,ccw,number=options[0]
        result[key]=record|{"occupied_ring_orientation":"CCW" if ccw else "CW","ring_number":number,
                            "directed_ring_face":packed([a,b]),"outward_normal":list(map(str,normal))}
    return result


def side(face, vertices):
    base=coordinates(face["face"])[0]
    nx,ny=map(F,face["outward_normal"])
    values=[nx*(x-base[0])+ny*(y-base[1]) for x,y in vertices]
    return min(values),max(values)


def audit(component, blocks, region):
    faces=semantic_faces(blocks,component["faces"])
    edges={edge(*coordinates(r["edge"])):r["sources"] for r in component["edges"]}
    atom_edges=[[edge(a,b) for a,b in pairwise(p+[p[0]])] for r in component["atoms"]
                for p in [points(r)]]
    near=halfplanes(ring(region))
    reports={}
    tested=Counter()
    all_supports={}
    walks=component["walks"]
    atom_walks=defaultdict(list)
    for name,walk in walks.items():
        if walk["atom"] is not None:
            atom_walks[walk["atom"]].append(name)
    orders={tuple(map(F,r["point"])):coordinates(r["incident_ccw"]) for r in component["angles"]}
    for key,r in component["regions"].items():
        p=points(r)
        local=bool(exact_area(convex_intersection(p,near)))
        outline=[s for s,n in Counter(s for i in r["atoms"] for s in atom_edges[i]).items() if n==1]
        physical={tag for s in outline for tag in edges[s] if tag in faces}
        extension={tag for s in outline for tag in edges[s] if tag in component["extensions"]}
        origin={state[0] for start in r["starts"] for state in start["face_states"]}
        tested["regions"]+=1
        states=[state for start in r["starts"] for state in start["face_states"]]
        support_rows=[]
        for face_id in sorted(physical|origin|{component["extensions"][tag]["face"] for tag in extension}):
            f=faces[face_id]
            low,high=side(f,p)
            support_rows.append({"face":face_id,"physical_contact":face_id in physical,
                "originating_face":face_id in origin,"min_signed":str(low),"max_signed":str(high),
                "extension_boundary_segments":[tag for tag in sorted(extension) if
                        component["extensions"][tag]["face"]==face_id],
                "origin_states":[state for state in states if state[0]==face_id]})
            if low<0:
                if face_id in physical or face_id in origin:
                    tested["physical_or_origin_inward_pairs"]+=1
                else:
                    tested["extension_only_inward_pairs"]+=1
        all_supports[key]=support_rows
        if local:
            tested["local_regions"]+=1
            revised=[]
            walk_ids=sorted({k for start in r["starts"] for k in atom_walks[start["seed"]]})
            for index in walk_ids:
                w=walks[index]
                hand=w["hand"]
                path=coordinates(w["path"])
                step=-1 if hand=="right" else 1
                revised.extend(orders[v][(orders[v].index(u)+step)%len(orders[v])]==z
                               for u,v,z in zip(path,path[1:]+path[:1],path[2:]+path[:2]))
            if not all(revised):
                raise ValueError(f"Archived junction turning disagrees for region {key}.")
            reports[key]={"vertices":r["vertices"],"starts":r["starts"],"supports":support_rows,
                          "walks":{index:walks[index] for index in walk_ids},
                          "junction_decisions_checked":len(revised)}
    return {"faces":faces,"extensions":component["extensions"],"counts":dict(tested),"local":reports,"region_supports":all_supports}


def main():
    sys.set_int_max_str_digits(0)
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ("manifest","arrangement","output"):
        parser.add_argument("--"+arg,type=Path,required=True)
    args=parser.parse_args()
    s,ch,_,prov,_,_,blocks=load_inputs(args.manifest)
    archived=read(args.arrangement)
    if archived["provenance"]["lineage"]!=s.source:
        raise ValueError("Arrangement provenance mismatch.")
    result=audit(archived["components"][0],blocks,Atlas(s,ch).regions[257])
    with args.output.open("xb") as stream:
        stream.write(encode(result|{"arrangement_sha256":sha256_file(args.arrangement),"lineage":prov["lineage"]}))
    print(result["counts"])


if __name__=="__main__":
    main()
