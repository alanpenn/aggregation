"""Read-only audit of archived slope-preference dyad growth."""
import argparse
import json
from pathlib import Path
import sys

import networkx as nx
import numpy as np
from scipy.spatial import Voronoi
from shapely import from_wkb
from shapely.geometry import LineString, box

from voronoi_app.research_data import data_path
from voronoi_app.batch_store import BatchStore
from voronoi_app.core import ExperimentPipeline, UrbanFormComposition
from voronoi_app.experimental_circulation_topology import _edge_graph
from voronoi_app.orchestrator import ExperimentOrchestrator
from voronoi_app.registry import get_registry


def replay(data):
    config=data["configuration"]
    p=ExperimentPipeline.from_dict(dict(config))
    p.urban_form=UrbanFormComposition.from_dict(config["urban_form"])
    r=get_registry()
    terrain=r.get_terrain(p.terrain_provider,p.terrain_params)
    gen=r.get_grid(p.grid_generator,p.grid_params)
    strategy=r.get_aggregation(p.aggregation_strategy,p.aggregation_params)
    extent=tuple(data["grid"]["extent"])
    grid=gen.generate(terrain=terrain,extent=extent,seed=p.seed)
    grid.metadata["extent"]=extent
    if np.asarray(grid.nodes).tolist()!=data["grid"]["nodes"]:
        raise ValueError("Generated sites differ from archived sites.")
    result,parents=trace_aggregation(strategy,terrain,grid,p.urban_form,p.seed)
    if ([list(map(int,pair)) for pair in result.doors]!=data["doors"]
            or {str(i):label for i,label in result.building_labels.items()}!=data["building_labels"]):
        raise ValueError("Replay differs from archived placement identity.")
    polygons=ExperimentOrchestrator(p)._space_polygons(grid)
    if {str(i):polygon.wkb_hex for i,polygon in polygons.items()}!=data["polygons_wkb"]:
        raise ValueError("Reconstructed polygon bytes differ.")
    return parents


def trace_aggregation(strategy,terrain,grid,form,seed):
    target=strategy.aggregate.__func__.__code__
    parents=[]
    def trace(frame,event,arg):
        if event=="return" and frame.f_code==target:
            local=frame.f_locals
            if len(local["doors"])!=len(parents):
                parents.append(int(local["open_idx"]))
        if event=="call" and frame.f_code==target:
            parents.append(None)
        if event=="line" and frame.f_code==target:
            local=frame.f_locals
            if len(local.get("doors",[]))>len(parents):
                parents.append(int(local["open_idx"]))
        return trace if frame.f_code==target else None
    prior=sys.gettrace()
    try:
        sys.settrace(trace)
        result=strategy.aggregate(terrain=terrain,grid=grid,form=form,seed=seed)
    finally:
        sys.settrace(prior)
    return result,parents


def prefix_audit(doors,labels,parents,polygons):
    graph=nx.Graph(_edge_graph(polygons,polygons))
    opens=set()
    rows=[]
    seed_open=doors[0][0] if doors else None
    for (open_cell,building),parent in zip(doors,parents,strict=True):
        prior=set(opens)
        opens.add(open_cell)
        parents_touch=sorted(prior & set(graph[open_cell]))
        def edge(other):
            if other is None:
                return None,None
            contact=polygons[open_cell].boundary.intersection(polygons[other].boundary)
            return contact.length,contact.geom_type if not contact.is_empty else "empty"
        growth,contact=edge(parent)
        face,pair_contact=edge(building)
        rows.append({"building":labels[str(building)],"building_cell":building,"open_cell":open_cell,
                     "parent_open_cell":parent,"parent_face_length":growth,"parent_contact":contact,
                     "pair_face_length":face,"pair_contact":pair_contact,
                     "earlier_face_neighbors":parents_touch,
                     "joins_prior_open":bool(parents_touch) if prior else None,
                     "joins_seed_component":open_cell in nx.node_connected_component(graph.subgraph(opens),seed_open),
                     "components":nx.number_connected_components(graph.subgraph(opens))})
    return rows


def ridge_length(v,left,right,ridge,canvas):
    a,b=ridge
    if a>=0 and b>=0:
        segment=v.vertices[[a,b]]
    else:
        finite=v.vertices[max(a,b)]
        direction=v.points[right]-v.points[left]
        direction/=np.linalg.norm(direction)
        normal=np.array([-direction[1],direction[0]])
        sign=np.sign(np.dot(v.points[[left,right]].mean(axis=0)-v.points.mean(axis=0),normal))
        direction=sign*normal
        lower,upper=0.,float("inf")
        bounds=canvas.bounds
        for i in range(2):
            if direction[i]==0:
                if not bounds[i]<=finite[i]<=bounds[i+2]:
                    return 0.
                continue
            entry,exit=sorted(((bounds[i]-finite[i])/direction[i],
                               (bounds[i+2]-finite[i])/direction[i]))
            lower,upper=max(lower,entry),min(upper,exit)
        return max(0.,upper-lower)
    return LineString(segment).intersection(canvas).length


def audit(root,case,out):
    store=BatchStore(root)
    journal=json.loads((root/"cases"/f"{case}.json").read_text())
    source=journal["stages"]["settlement"]["record"]
    _,d,stamp=store.load(source)
    polys={int(i):from_wkb(w) for i,w in d["polygons_wkb"].items()}
    parents=replay(d)
    rows=prefix_audit(d["doors"],d["building_labels"],parents,polys)
    v=Voronoi(d["grid"]["nodes"])
    canvas=box(*d["grid"]["extent"])
    graph=_edge_graph(polys,polys)
    discrepancy=[]
    for (a,b),ridge in zip(v.ridge_points,v.ridge_vertices,strict=True):
        if int(b) in graph[int(a)]:
            continue
        left,right=polys[int(a)],polys[int(b)]
        boundary=left.boundary.intersection(right.boundary)
        discrepancy.append({"cells":[int(a),int(b)],"ridge_length_inside_canvas":ridge_length(v,a,b,ridge,canvas),
                            "boundary_intersection":boundary.wkt,"polygon_distance":left.distance(right),
                            "overlap_area":left.intersection(right).area})
    out.mkdir(parents=True,exist_ok=True)
    with (out/f"{case}.json").open("x") as f:
        json.dump({"settlement":source,"manifest_sha256":stamp,"placements":rows,
                   "ridge_without_face":discrepancy},f,indent=2)
    print(case,"first disconnect",next((r for r in rows if r["components"]>1),None),
          "first bad edge",next((r for r in rows if r["parent_face_length"]==0 or r["pair_face_length"]==0),None),
          "bad parents",sum(r["parent_face_length"]==0 for r in rows),"bad dyad faces",
          sum(r["pair_face_length"]==0 for r in rows),"final components",rows[-1]["components"],
          "discrepancies",len(discrepancy),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case",nargs="+")
    parser.add_argument("--root",type=Path,default=data_path('strict-generalisation/pilot-1'))
    parser.add_argument("--output",type=Path,default=data_path('facewise-growth-audit'))
    args=parser.parse_args()
    for case in args.case:
        audit(args.root,case,args.output)
