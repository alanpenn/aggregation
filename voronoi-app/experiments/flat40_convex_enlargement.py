"""Exact non-maximality witnesses for the independent Flat 40 convex cover."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction as F
from itertools import combinations, pairwise
from pathlib import Path
import sys

from shapely.strtree import STRtree

from experiments.face_extension_cover import bounds, edge, hull, rings
from experiments.flat40_exchange_atlas import Atlas, combine, foot, label, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, lines, load_inputs, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed, shared_parts
from experiments.flat40_oriented_face_audit import coordinates
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _cross, _direction, _inside_prepared, _intersections, _prepare_polygon
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes, positive_interior
from voronoi_app.research_data import sha256_file

PAGES = {3:"21a7aa91ea9375bf",9:"6810e25061ad27b9",14:"880286b22d381950",18:"c99826db684d98fa"}


def edges(p):
    return pairwise(p+p[:1])


def box_of(p):
    return bounds((tuple(map(min,zip(*p))),tuple(map(max,zip(*p)))))


class Checker:
    def __init__(self, domain, occupied):
        self.domain=_prepare_polygon(domain)
        self.boundaries=[(a,b) for ring in rings(domain) for a,b in pairwise(ring)]
        self.boundary_tree=STRtree([bounds(s) for s in self.boundaries])
        self.occupied=[(i,rings(p)[0]) for i,p in occupied.items()]
        self.occupied_tree=STRtree([box_of(p) for _,p in self.occupied])

    def witness(self, old, proposed, *, independent=False):
        if len(proposed)<3 or tuple(proposed)!=hull(proposed):
            return None
        area=exact_area(list(proposed))
        old_area=exact_area(list(old))
        if area<=old_area or hull((*old,*proposed))!=tuple(proposed):
            return None
        centre=tuple(sum(v)/len(proposed) for v in zip(*proposed))
        footprint=box_of(proposed)
        planes=halfplanes(list(proposed)+[proposed[0]])
        # A convex polygon with an interior point in the domain and no
        # domain boundary in its strict interior cannot leave the domain.
        if any(positive_interior(*self.boundaries[i],planes)
               for i in self.boundary_tree.query(footprint)) or not _inside_prepared(centre,self.domain):
            return None
        if independent:
            for j in self.occupied_tree.query(footprint):
                if exact_area(convex_intersection(self.occupied[j][1],planes)):
                    return None
        return {"vertices":packed(proposed),"old_area":str(old_area),"new_area":str(area),
                "added_area":str(area-old_area),"contains_original":True,
                "interior_sample":list(map(str,centre)),"domain_boundary_in_interior":False,
                "positive_occupied_intersection":False if independent else None}


def edge_attempts(old,a,b,checker,*,exhaustive=False):
    dx,dy=_direction(a,b)
    length=max(abs(dx),abs(dy))
    normal=(dy/length,-dx/length)
    accepted=[]
    alternatives=((F(1,2),F(1,4),F(3,4)) if exhaustive else (F(1,2),))
    steps=(F(4),F(1),F(1,4),F(1,16),F(1,256),F(1,4096))
    for t in alternatives:
        for step in steps:
            point=tuple(u+t*d+step*n for u,d,n in zip(a,(dx,dy),normal))
            enlarged=hull((*old,point))
            item=checker.witness(old,enlarged)
            if item:
                accepted.append(item|{"edge":packed((a,b)),"added_point":list(map(str,point)),
                                      "step_in_max_coordinate_norm":str(step)})
                break
    return max(accepted,key=lambda r:F(r["added_area"])) if accepted else None


def provenance(component, audit, study, key):
    record=component["regions"][key]
    p=points(record)
    rows=[]
    for a,b in edges(p):
        segments=[]
        for k in record["atoms"]:
            atom=points(component["atoms"][k])
            segments.extend(edge(*s) for s in shared_parts(a,b,edges(atom)))
        counts=Counter(segments)
        boundary={s for s,count in counts.items() if count==1}
        sources=sorted({tag for s in boundary for tag in component["_edge_sources"][s]})
        physical=[tag for tag in sources if tag in audit["faces"]]
        artificial=[tag for tag in sources if tag in audit["extensions"]]
        domain=[tag for tag in sources if tag.startswith("domain-edge:")]
        desc=[]
        if physical:
            desc.append("physical occupied-face portions")
        if a[0]==b[0] in (0,100) or a[1]==b[1] in (0,100):
            desc.append("external analysis frame")
        elif domain and not physical:
            desc.append("other accessible-domain boundary")
        if artificial:
            desc.append("occupied-face extension")
        if not desc:
            desc.append("other arrangement edge")
        matching=[l.line_id for l in study.lines if
                 _cross(_direction(a,b),_direction(a,l.start))==0 and
                 _cross(_direction(a,b),_direction(a,l.end))==0 and
                 len(_intersections(a,b,l.start,l.end))==2]
        inventory=study.inputs["candidates"]["pool"]["candidates"]
        rows.append({"edge":packed((a,b)),"classifications":desc,
                     "physical_sources":physical,"extension_sources":artificial,
                     "domain_sources":domain,"collinear_overlapping_axial_ids":matching,
                     "collinear_candidate_supports":{str(i):inventory[i]["provenance"] for i in matching},
                     "physical_origin_faces":{f:audit["faces"][f] for f in
                         sorted(set(physical)|{audit["extensions"][s]["face"] for s in artificial})},
                     "positive_physical_face_contact_blocks_crossing":bool(physical),
                     "independent_vertex_tangent_used_by_generator":False,
                     "exact_arrangement_subedges":packed([]) if not boundary else [packed(s) for s in sorted(boundary)]})
    return rows


def local_atlas(out,atlas,records,audit):
    sources=[]
    for number,(page_no,record) in enumerate(records.items(),1):
        old=record["original"]
        new=record["largest_witness"]
        fig,axes=page(f"Atlas page {page_no}  |  {record['region']}",
                       "Matched extent · actual occupied polygons and rational convex witness",2)
        xy_points=[xy(v) for v in (new or old)["vertices"]]
        x,y=map(min,zip(*xy_points))
        X,Y=map(max,zip(*xy_points))
        view=(x-2.5,X+2.5,y-2.5,Y+2.5)
        for ax in axes:
            atlas.base(ax,view)
        if new:
            draw_polygons(axes[1],[new],facecolors="#9ed6a4",edgecolors="#267646",linewidths=1.9,alpha=.48,zorder=5)
        for ax in axes:
            draw_polygons(ax,[old],facecolors="none",edgecolors="#166795",linewidths=1.6,zorder=7)
            for j,r in enumerate(record["boundaries"],1):
                a,b=map(xy,r["edge"])
                if r["enlargement"]:
                    ax.plot(*zip(a,b),color="#bc4d26",ls="dashed",lw=1.45,zorder=8)
                label(ax,tuple((u+v)/2 for u,v in zip(a,b)),f"E{j}","#8d4026",size=7)
            # Marks are exact endpoints of physical faces generating the polygon's edges.
            faces={f for r in record["boundaries"] for f in r["physical_sources"]}
            for f in faces:
                lines(ax,[audit["faces"][f]["face"]],colors="#303a39",linewidths=1.7,zorder=9)
        axes[0].set_title("Original convex polygon",loc="left")
        axes[1].set_title("Exact clearance-certified enlargement" if new else "Search did not prove an enlargement",loc="left")
        foot(fig,"Blue original · Green larger convex set · Dashed orange edges crossed by verified trial enlargements" +
             (f" · Added area {float(F(new['added_area'])):.6f}" if new else ""))
        path=out/f"{number:02d}_page_{page_no}.pdf"
        plot_pdf(path,[fig])
        sources.append((f"Prior atlas page {page_no}",path))
    combine(out/"flat40_nonmaximality_local_atlas.pdf",sources)


def run(manifest,source,audit_path,oriented,out):
    study,ch,_,prov,occupied,domain,_=load_inputs(manifest)
    previous=read(source)
    audit=read(audit_path)
    cover=read(oriented)
    if (previous["provenance"]["lineage"]!=study.source or
            audit["arrangement_sha256"]!=sha256_file(source)):
        raise ValueError("Frozen cover lineage mismatch.")
    component=previous["components"][0]
    component["_edge_sources"]={edge(*coordinates(x["edge"])):x["sources"] for x in component["edges"]}
    checker=Checker(domain,occupied)
    records={}
    for page_no,key in PAGES.items():
        original=cover["regions"][key]
        p=points(original)
        rows=provenance(component,audit,study,key)
        found=[]
        for row,(a,b) in zip(rows,edges(p)):
            result=edge_attempts(p,a,b,checker,exhaustive=True)
            if result:
                result|=checker.witness(p,points(result),independent=True)
                found.append(result)
            row["enlargement"]=result
        # Test simultaneous atom additions separately from free-coordinate
        # witnesses, retaining any successful two-atom witness.
        member=set(original["atoms"])
        full_atoms=[points(x) for x in component["atoms"]]
        atom_edges=defaultdict(set)
        for i,item in enumerate(full_atoms):
            for ab in edges(item):
                atom_edges[edge(*ab)].add(i)
        shared=set().union(*(atom_edges[edge(*ab)] for i in member for ab in edges(full_atoms[i])))-member
        merged=[]
        for a,b in combinations(sorted(shared),2):
            joined=hull((*p,*full_atoms[a],*full_atoms[b]))
            if exact_area(list(joined))==exact_area(p)+exact_area(full_atoms[a])+exact_area(full_atoms[b]):
                cert=checker.witness(p,joined,independent=True)
                if cert:
                    merged.append(cert|{"added_atom_ids":[a,b]})
        records[str(page_no)]={"region":key,"original":original,"boundaries":rows,
             "largest_witness":max(found+merged,key=lambda x:F(x["added_area"]),default=None),
             "two_atom_witnesses":merged,"two_atom_trials":len(shared)*(len(shared)-1)//2,
             "traversal_paths":audit["local"][key]["walks"],"starting_states":audit["local"][key]["starts"]}
    out.mkdir(parents=True,exist_ok=False)
    (out/"local-witnesses.json").write_bytes(encode({"records":records,"lineage":prov["lineage"],
        "source_sha256":sha256_file(source),"oriented_sha256":sha256_file(oriented)}))
    local_atlas(out,Atlas(study,ch),records,audit)
    print({k:(v["region"],float(F(v["largest_witness"]["added_area"])) if v["largest_witness"] else None,
              len(v["two_atom_witnesses"])) for k,v in records.items()},flush=True)


if __name__=="__main__":
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    for field in ("manifest","source","audit","oriented","output"):
        p.add_argument("--"+field,type=Path,required=True)
    args=p.parse_args()
    run(args.manifest,args.source,args.audit,args.oriented,args.output)
