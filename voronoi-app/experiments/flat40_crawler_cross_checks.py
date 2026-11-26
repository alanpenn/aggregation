"""Per-facet, reference provenance, and handedness cross-checks for a saved replay."""
import argparse
from pathlib import Path
from fractions import Fraction as F
import sys

from shapely.strtree import STRtree

from experiments.face_extension_cover import bounds, hull
from experiments.flat40_convex_enlargement import box_of, edges
from experiments.flat40_crawler_atlas import read
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_face_extension import load_inputs, points
from experiments.flat40_region257_inspection import packed
from voronoi_app.angular import _inside_prepared, _intersections, _prepare_polygon
from voronoi_app.batch_store import encode
from voronoi_app.research_data import sha256_file


def run(manifest,out):
    _,_,_,_,_,domain,_=load_inputs(manifest)
    record=read(out/"regions.json")
    geometry=read(out/"geometry.json")
    regions=record["regions"]
    supports=[tuple(tuple(map(F,u)) for u in f["endpoints"]) for f in geometry["faces"]]
    s_index=STRtree([bounds(x) for x in supports])
    ids=list(regions)
    polygons={i:tuple(points(r)) for i,r in regions.items()}
    poly_index=STRtree([box_of(polygons[i]) for i in ids])
    details={}
    hands={}
    open_turns={"right":0,"left":0}
    paths_with_open_turn={"right":0,"left":0}
    prepared=_prepare_polygon(domain)
    tracks=geometry["tracks"]
    directed=geometry["directed_edges"]
    for key,p in polygons.items():
        r=regions[key]
        hands[key]={a["hand"] for a in r["paths"]}
        for path in r["paths"]:
            n=0
            for before,after,action,_ in path["transitions"]:
                seg=directed[before]
                if (action=="turn_towards_originating_face"
                        and not tracks[seg["track"]]["physical"]
                        and not tracks[directed[after]["track"]]["physical"]
                        and _inside_prepared(tuple(map(F,seg["interval"][1])),prepared)):
                    n+=1
            open_turns[path["hand"]]+=n
            paths_with_open_turn[path["hand"]]+=bool(n)
        r_facets=[]
        for a,b in edges(p):
            contacts=[]
            for j in s_index.query(bounds((a,b))):
                hit=_intersections(a,b,*supports[j])
                if len(hit)==2:
                    contacts.append({"face":int(j),"exact_shared_segment":packed(sorted(hit))})
            r_facets.append({"edge":packed((a,b)),"positive_physical_boundary_contact":contacts})
        super_regions=[ids[i] for i in poly_index.query(box_of(p))
                       if F(regions[ids[i]]["area"])>F(r["area"])
                       and hull((*p,*polygons[ids[i]]))==polygons[ids[i]]]
        details[key]={"facets":r_facets,"strictly_contained_in_completed_regions":super_regions,
                      "maximal_within_completed_family":not super_regions}
    results={}
    for sign in ("right","left"):
        selected={k for k in ids if sign in hands[k]}
        chosen=[polygons[k] for k in ids if k in selected]
        coverage=exact_coverage(domain,chosen)
        results[sign]={"regions":len(selected),
                       "covered_area":coverage["covered_area"],
                       "covered_percent":coverage["covered_percent"],
                       "only_hand_regions":sum(hands[k]=={sign} for k in ids)}
    total=F(read(out/"coverage.json")["covered_area"])
    for sign,other in (("right","left"),("left","right")):
        results[sign]["exclusive_covered_area_in_explored_family"]=str(total-F(results[other]["covered_area"]))
    with (out/"cross-checks.json").open("xb") as stream:
        stream.write(encode({"facets_and_containment":details,"hands":results,
                             "open_extension_turns":open_turns,"paths_with_open_extension_turn":paths_with_open_turn,
                             "regions_sha256":sha256_file(out/"regions.json")}))
    print("per-hand covers",{k:{a:v for a,v in d.items() if a not in (
        "covered_area","exclusive_covered_area_in_explored_family")} for k,d in results.items()},
          "strictly contained",sum(not r["maximal_within_completed_family"] for r in details.values()),flush=True)


if __name__=="__main__":
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(a.manifest,a.output)
