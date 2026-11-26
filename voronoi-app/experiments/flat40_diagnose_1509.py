"""Exact deletion diagnosis of candidate 1509 in frozen Flat 40 C-H."""
import argparse
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from statistics import mean

import networkx as nx
from shapely import from_wkb

from experiments.cross_terrain_axial import DEST
from experiments.cross_terrain_axial_routes import evaluate_active_union
from experiments.flat40_axial_optimisation import verified_previous
from experiments.flat40_exchange_atlas import Atlas, page, plot_pdf, polygon, serial_faces, winding
from experiments.near_collinear_consolidation import continuation, verified_study
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _exact_point, _intersections
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes, positive_interior
from voronoi_app.research_data import sha256_file


def exact_graph(study, ids):
    graph=nx.Graph()
    graph.add_nodes_from(ids)
    contacts={}
    for a,b in combinations(sorted(ids),2):
        left,right=study.lines[a],study.lines[b]
        points=sorted(_intersections(left.start,left.end,right.start,right.end))
        if bool(points)!=(b in study.neighbors[a]):
            raise ValueError(f"Frozen intersection graph mismatch for {a}/{b}.")
        if points:
            graph.add_edge(a,b)
            contacts[a,b]=points
    return graph,contacts


def lost_constraints(study, selected, removed):
    ids=set(selected)-set(removed)
    graph,_=exact_graph(study,ids)
    proof=winding(study,ids,witnesses=True)
    groups={}
    for block, column in zip(proof["circulation_cycle_block_order"],
                             zip(*proof["circulation_cycle_winding_vectors"])):
        groups.setdefault(column,[]).append(block)
    return {"ids":sorted(ids), "components":sorted(map(sorted,nx.connected_components(graph))),
            "edges":graph.number_of_edges(),
            "uncovered_regions":[r for r,g in study.regions.items() if ids.isdisjoint(g)],
            "unserved_doorways":[i for i,g in enumerate(study.doors) if ids.isdisjoint(g)],
            "winding":{k:v for k,v in proof.items() if k!="witness_faces"},
            "exact_witness_faces":serial_faces(proof),
            "indistinguishable_winding_columns":[ids for column,ids in groups.items() if len(ids)>1 and any(column)]}


def movement(study, cases, archived):
    maps={name:{"maps":{"final":r["ids"]}} for name,r in cases.items()}
    output=evaluate_active_union(study.inputs,study.lines,study.clearance,study.reference,maps)
    paired={}
    base=output["methods"]["CH"]["final"]
    for mode in ("angular","metric"):
        key=mode+"_routes"
        if max(abs(a-b) for a,b in zip(base[key],archived["methods"]["C-H"][key],strict=True))>1e-8:
            raise ValueError("Archived movement replay differs.")
    for name,result in output["methods"].items():
        paired[name]={}
        for mode in ("angular","metric"):
            key=mode+"_routes"
            values=result["final"][key]
            valid=[(i,v-b) for i,(v,b) in enumerate(zip(values,base[key],strict=True))
                   if v is not None and b is not None]
            low,high=min(valid,key=lambda p:p[1]),max(valid,key=lambda p:p[1])
            pairs=study.inputs["analysis"]["pairs"]
            paired[name][mode]={"reachable":len(valid),"unreachable":len(values)-len(valid),
                "improved":sum(v < -1e-9 for _,v in valid),"worsened":sum(v > 1e-9 for _,v in valid),
                "unchanged":sum(abs(v)<=1e-9 for _,v in valid),"mean_change":mean(v for _,v in valid),
                "largest_decrease":[pairs[low[0]],low[1]],"largest_increase":[pairs[high[0]],high[1]]}
    return output|{"paired_vs_CH":paired,"doorway_pair_order":study.inputs["analysis"]["pairs"]}


def region_geometry(study, region_ids, ch):
    evidence={}
    for i in region_ids:
        polygon=from_wkb(study.inputs["candidates"]["regions_wkb"][str(i)])
        ring=list(map(_exact_point,polygon.exterior.coords))
        planes=halfplanes(ring)
        inside=[]
        boundary={}
        for j in ch:
            line=study.lines[j]
            if positive_interior(line.start,line.end,planes):
                inside.append(j)
            intersections={p for a,b in zip(ring,ring[1:])
                           for p in _intersections(line.start,line.end,a,b)}
            if intersections:
                boundary[str(j)]=[list(map(str,p)) for p in sorted(intersections)]
        if set(inside) != study.regions[i].intersection(ch):
            raise ValueError(f"Exact half-plane replay differs for strict region {i}.")
        evidence[str(i)]={"ring":[list(map(str,p)) for p in ring],"strict_hits":inside,
                          "boundary_intersections":boundary}
    return evidence


def hop_control(graph):
    retained=sorted(set(graph)-{1509})
    before=dict(nx.all_pairs_shortest_path_length(graph))
    after=dict(nx.all_pairs_shortest_path_length(graph.subgraph(retained)))
    return {"pairs":len(retained)*(len(retained)-1)//2,
            "changed":[[a,b,before[a][b],after[a][b]] for a,b in combinations(retained,2)
                       if before[a][b]!=after[a][b]]}


def draw(study,ch,cases,output):
    atlas=Atlas(study,ch)
    fig, axes=page("Flat 40  |  What candidate 1509 contributes",
                   "Exact intervals, strict region incidence and independent winding witnesses",3)
    lost=cases["without_1509"]
    blocks=set(lost["winding"]["missing_axial_rings"]).union(*lost["indistinguishable_winding_columns"])
    regions=set(lost["uncovered_regions"])
    for ax,name,title in zip(axes,("CH","without_1509","without_1435"),
                             ("Archived C-H","Remove 1509 only","Remove 1435 only")):
        case=cases[name]
        atlas.base(ax)
        atlas.network(ax,set(case["ids"])-{1509,1435})
        for r in regions:
            polygon(ax,atlas.regions[r],"#ffc674","#bc7c29",.5,z=2,alpha=.56)
        for face in case["winding"]["circulation_cycles"]:
            if blocks.intersection(face["enclosed_blocks"]):
                coords=[tuple(float(Fraction(v)) for v in p)
                        for p in case["exact_witness_faces"][str(face["face_index"])]]
                ax.plot(*zip(*coords),color="#245cb0",lw=1.5,zorder=5)
        for i,c in ((1435,"#0d764d"),(1509,"#b82832")):
            atlas.line(ax,i,c,width=1.9 if i in case["ids"] else .85,
                       style="solid" if i in case["ids"] else "dashed",tag=(.68,(2,5)))
        ax.set_title(f"{title} · winding {case['winding']['independent_circulation_rank']}/24",loc="left")
    fig.text(.04,.044,"Red 1509   ·   Green 1435   ·   Dashed deleted reference   ·   Amber uniquely lost with 1509   ·   Blue affected winding faces",fontsize=9)
    plot_pdf(output,[fig])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("manifest","previous","optimisation","atlas","output"):
        p.add_argument("--"+key,type=Path,required=True)
    args=p.parse_args()
    study,ch,d,provenance=verified_study(args.manifest)
    verified_previous(args.previous,study,ch,d,provenance)
    opt,index=read(args.optimisation),read(args.atlas)
    if (opt["maps"]["C-H"]!=ch or opt["provenance"]["lineage"]!=study.source
            or index["provenance"]["optimisation_sha256"]!=sha256_file(args.optimisation)
            or opt["provenance"]["prior_experiment_sha256"]!=sha256_file(args.previous)
            or index["provenance"]["lineage"]!=study.source):
        raise ValueError("Flat 40 derived inventories or hashes disagree.")
    archive=DEST / "flat-40" / "movement.json"
    manifest_key="strict-generalisation/cross-terrain-constructive-1/flat-40/movement.json"
    if sha256_file(archive)!=read(args.manifest)[manifest_key]:
        raise ValueError("Archived movement checksum mismatch.")
    graph,contacts=exact_graph(study,ch)
    common=set(graph[1435])&set(graph[1509])
    neighbors={str(i): sorted(set(graph[i])-{1435,1509}) for i in (1435,1509)}
    cases={name:lost_constraints(study,ch,removed) for name,removed in
           (("CH",()),("without_1509",(1509,)),("without_1435",(1435,)),("without_both",(1435,1509)))}
    if (len(cases["CH"]["components"])!=1 or cases["CH"]["uncovered_regions"]
            or cases["CH"]["unserved_doorways"] or cases["CH"]["winding"]["independent_circulation_rank"]!=24):
        raise ValueError("Baseline verification failed.")
    incidence={}
    for i in (1435,1509):
        line=study.lines[i]
        incidence[str(i)]={"regions":[r for r,g in study.regions.items() if i in g],
                          "doorways":[j for j,g in enumerate(study.doors) if i in g],
                          "interval":[list(map(str,p)) for p in (line.start,line.end)],
                          "provenance":study.inputs["candidates"]["pool"]["candidates"][i]["provenance"]}
    args.output.mkdir(parents=True,exist_ok=False)
    with (args.output/"structural.json").open("xb") as stream:
        stream.write(encode({"provenance":provenance|{k:sha256_file(p) for k,p in
             (("previous_sha256",args.previous),("optimisation_sha256",args.optimisation),
              ("atlas_index_sha256",args.atlas),("movement_archive_sha256",archive))},
             "continuation":continuation(study.lines[1435],study.lines[1509]),
             "neighbors_excluding_pair":neighbors,"shared_neighbors":sorted(common),
             "exclusive_1509_neighbors":sorted(set(neighbors["1509"])-common),
             "exclusive_1435_neighbors":sorted(set(neighbors["1435"])-common),
             "exact_contacts":{f"{a}/{b}":[list(map(str,p)) for p in pts]
                 for (a,b),pts in contacts.items() if {a,b}&{1435,1509}},
             "cases":cases,"incidence":incidence,"retained_unweighted_hops":hop_control(graph),
             "unique_region_geometry":region_geometry(study,cases["without_1509"]["uncovered_regions"],ch)}))
    draw(study,ch,cases,args.output/"diagnosis.pdf")
    with (args.output/"movement.json").open("xb") as stream:
        stream.write(encode(movement(study,{key:cases[key] for key in ("CH","without_1509","without_1435")},
                                     read(archive))))


if __name__=="__main__":
    main()
