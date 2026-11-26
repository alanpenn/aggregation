"""Extend frozen convex polygons across artificial edges and replay C-H."""
import argparse
from collections import Counter, defaultdict, deque
from fractions import Fraction as F
from hashlib import sha256
from itertools import pairwise
from math import fsum
from pathlib import Path
import sys

from shapely.geometry.polygon import orient

from experiments.face_extension_cover import arrangement, bounds, crawl, edge, rings
from experiments.flat40_convex_enlargement import Checker, edge_attempts, edges
from experiments.flat40_exchange_atlas import Atlas, page, foot, plot_pdf
from experiments.flat40_face_extension import draw_polygons, incidence, load_inputs, points, select
from experiments.flat40_oriented_face_audit import coordinates
from experiments.flat40_region257_inspection import exact_area, packed, ring, convex_intersection
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _cross, _direction, _intersections
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes
from voronoi_app.research_data import sha256_file


def coalesce_collinear(segments):
    groups=defaultdict(lambda:defaultdict(Counter))
    for (a,b),tags in segments.items():
        dx,dy=_direction(a,b)
        slope=dy/dx if dx else None
        key=(slope,a[1]-slope*a[0]) if dx else (None,a[0])
        groups[key][a].update(tags)
        groups[key][b].subtract(tags)
    result={}
    for events in groups.values():
        active=Counter()
        ordered=sorted(events)
        for a,b in pairwise(ordered):
            active.update(events[a])
            if tags:=set(+active):
                result[a,b]=tags
    return result


def balanced_sum(values):
    values=list(values)
    while len(values)>1:
        grouped=[values[i]+values[i+1] for i in range(0,len(values)-1,2)]
        if len(values)%2:
            grouped.append(values[-1])
        values=grouped
    return values[0] if values else F(0)


def exact_overlap(domain, scaffolding, regions, *, progress=lambda *a: None, compressed=False):
    """Propagate oriented boundary jumps between exact noded planar faces."""
    segments=defaultdict(set)
    signs={}
    domain_spans={}
    for row in scaffolding:
        segments[edge(*coordinates(row["edge"]))].add("scaffold")
    for name,boundaries in [(key,[points(record)]) for key,record in regions.items()]+[
            ("domain", [r[:-1] for r in rings(orient(domain))])]:
        for k,p in enumerate(boundaries):
            for j,(a,b) in enumerate(edges(p)):
                tag=f"{name}:{k}:{j}"
                segments[edge(a,b)].add(tag)
                signs[tag]=(0 if name=="domain" else 1,1 if a<b else -1)
                if name=="domain":
                    domain_spans[tag]=edge(a,b)
    merged=coalesce_collinear(segments)
    progress("Overlay source segments",len(segments),"after collinear span consolidation",len(merged))
    graph=arrangement(merged)
    progress("Overlay noded",graph.number_of_edges(),"segments")
    walks,index,_=crawl(graph)
    right=index["right"]
    area={i:sum((_cross(a,b) for a,b in path),F(0))/2
          for i,(hand,path,closed) in walks.items() if hand=="right" and closed}
    outer=[i for i,value in area.items() if value<0]
    if len(outer)!=1:
        raise ValueError("Expected one exterior orbit on the connected overlay.")
    arcs=defaultdict(list)
    pieces=defaultdict(list)
    for a,b,row in graph.edges(data=True):
        u,v=edge(a,b)
        left,right_face=right[u,v],right[v,u]
        delta=[0,0]
        for tag in row["sources"]-{"scaffold"}:
            axis,sign=signs[tag]
            delta[axis]+=sign
            if axis==0:
                pieces[tag].append((u,v))
        arcs[right_face].append((left,*delta))
        arcs[left].append((right_face,-delta[0],-delta[1]))
    known={outer[0]:(0,0)}
    pending=deque(outer)
    while pending:
        i=pending.popleft()
        for j,dd,dm in arcs[i]:
            pair=known[i][0]+dd,known[i][1]+dm
            if j in known:
                if pair!=known[j]:
                    raise ValueError("Inconsistent oriented overlap counts.")
            else:
                known[j]=pair
                pending.append(j)
    if (set(known)!=set(area) or any(d not in (0,1) or m<0 or (not d and m)
                                     for d,m in known.values())):
        raise ValueError("Overlay fails domain/multiplicity consistency.")
    for tag,(a,b) in domain_spans.items():
        spans=sorted(pieces[tag])
        if (not spans or spans[0][0]!=a or spans[-1][1]!=b
                or any(u[1]!=v[0] for u,v in pairwise(spans))):
            raise ValueError("Exact subdivided domain boundary does not telescope.")
    band_values=defaultdict(list)
    atoms=[]
    for i,(d,m) in known.items():
        if d:
            if area[i]<=0 or not m:
                raise ValueError("Degenerate or uncovered accessible overlay face.")
            band_values[m].append(area[i])
            atoms.append({"vertices":packed([a for a,b in walks[i][1]]),
                          "area":str(area[i]),"multiplicity":m})
    original=rings(domain)
    domain_area=exact_area(original[0])-sum(exact_area(p) for p in original[1:])
    if compressed:
        # Domain-area terms telescope across the verified original directed
        # boundary. Each density bin is stored as an exact sum via its atoms.
        # Only the display decimal is summed here, avoiding giant denominators.
        return atoms, {"exact_domain_area":str(domain_area), "areas_approx":{
            "0":0., **{str(m):fsum(float(a) for a in values) for m,values in band_values.items()}}}
    bands={m:balanced_sum(values) for m,values in band_values.items()}
    bands.setdefault(0,F(0))
    if balanced_sum(bands.values())!=domain_area or bands[0]:
        raise ValueError("Overlay coverage is incomplete.")
    return atoms,bands


def expand(cover, checker, local):
    regions={}
    results={}
    for key,original in sorted(cover["regions"].items()):
        p=points(original)
        found=[trial for a,b in edges(p) if (trial:=edge_attempts(p,a,b,checker))]
        if key in local and local[key]:
            found.append(local[key])
        winner=max(found,key=lambda r:F(r["added_area"]),default=None)
        if winner is not None:
            certificate=checker.witness(p,points(winner),independent=True)
            if certificate is None:
                raise ValueError(f"Independent enlargement recheck failed for {key}.")
            result=original|{"vertices":certificate["vertices"],"area":certificate["new_area"],
                             "physical_supports":[],
                             "predecessor_artificial_context":original["artificial_boundary_context"]}
            result.pop("artificial_boundary_context")
            # The old face still constrains the larger region only if it
            # remains a physical supporting half-plane after growth.
            from experiments.flat40_oriented_face_audit import side
            result["physical_supports"]=[row for row in original["physical_supports"]
                                         if side(cover["_faces"][row["face"]],points(result))[0]>=0]
            results[key]=certificate|{k:v for k,v in winner.items() if k not in certificate}
        else:
            result=original
            results[key]=None
        shape=sha256(encode(result["vertices"])).hexdigest()[:16]
        if shape in regions:
            regions[shape]["parent_ids"].append(key)
        else:
            regions[shape]=result|{"parent_ids":[key]}
    return regions,results


def blocked_facets(checker, polygon):
    """A positive-length domain-boundary contact on every facet proves maximality."""
    proof=[]
    for a,b in edges(polygon):
        contacts=[sorted(meets) for j in checker.boundary_tree.query(bounds((a,b)))
                  if len(meets:=_intersections(a,b,*checker.boundaries[j]))==2]
        if not contacts:
            return None
        proof.append({"facet":packed((a,b)),"boundary_contacts":[packed(s) for s in contacts]})
    return proof


def plot_change(out, atlas, regions, atoms, bands):
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import BoundaryNorm
    fig,axes=page("Flat 40  |  Enlarged convex cover",
                  "Transparent polygon overlay and exact integer multiplicity",2)
    for ax in axes:
        atlas.base(ax)
    draw_polygons(axes[0],regions.values(),facecolors="#2279ae",edgecolors="none",alpha=.10,zorder=2)
    maximum=max(bands)
    # Keep one integer bin for every actual multiplicity.
    collection=PolyCollection([[(float(F(x)),float(F(y))) for x,y in a["vertices"]] for a in atoms],
        cmap="Blues",norm=BoundaryNorm([i-.5 for i in range(maximum+2)],256),edgecolors="none",zorder=2)
    collection.set_array([r["multiplicity"] for r in atoms])
    axes[1].add_collection(collection)
    bar=fig.colorbar(collection,ax=axes[1],fraction=.025,pad=.025,ticks=range(maximum+1))
    bar.set_label("Number of overlapping convex regions")
    axes[0].set_title("Equal-opacity overlay",loc="left")
    axes[1].set_title("Exact overlap multiplicity",loc="left")
    foot(fig,"The integer map is derived from oriented edge jumps. Polygon boundaries have zero area.")
    plot_pdf(out/"full_overlap.pdf",[fig])


def run(manifest, old, audit, oriented, output, *, resume=False):
    study,ch,_,prov,occupied,domain,_=load_inputs(manifest)
    source=read(old)
    if source["provenance"]["lineage"]!=study.source:
        raise ValueError("Frozen arrangement lineage mismatch.")
    orientation=read(audit)
    if orientation["arrangement_sha256"]!=sha256_file(old):
        raise ValueError("Frozen orientation and arrangement differ.")
    component=source["components"][0]
    cover=read(oriented)
    cover["_faces"]=orientation["faces"]
    local_path=output/"local-witnesses.json"
    local={row["region"]:row["largest_witness"] for row in read(local_path)["records"].values()}
    enlargement_path=output/"enlargements.json"
    if resume:
        previous=read(enlargement_path)
        if previous["lineage"]!=prov["lineage"] or previous["oriented_sha256"]!=sha256_file(oriented):
            raise ValueError("Enlargement checkpoint differs from frozen inputs.")
        regions=previous["regions"]
    else:
        regions,witnesses=expand(cover,Checker(domain,occupied),local)
        count=sum(w is not None for w in witnesses.values())
        print("Original regions proved non-maximal",count,"distinct revised polygons",len(regions),flush=True)
        with enlargement_path.open("xb") as f:
            f.write(encode({"witnesses":witnesses,"regions":regions,
                "original_proved_nonmaximal":count,"original_unresolved":len(witnesses)-count,
                "revised_maximality_unresolved":len(regions),"lineage":prov["lineage"],
                "oriented_sha256":sha256_file(oriented)}))
    proof_path=output/"facet-maximality.json"
    if not proof_path.exists():
        checker=Checker(domain,occupied)
        proof={key:{"parent_ids":r["parent_ids"],"facets":v} for key,r in regions.items()
               if (v:=blocked_facets(checker,points(r)))}
        with proof_path.open("xb") as f:
            f.write(encode({"proved":proof,"unresolved_count":len(regions)-len(proof),
                            "cover_sha256":sha256_file(enlargement_path)}))
    atoms,density=exact_overlap(domain,component["edges"],regions,
                              progress=lambda *a:print(*a,flush=True),compressed=True)
    with (output/"exact-overlap.json").open("xb") as f:
        f.write(encode({"atoms":atoms,**density,
                         "exact_area_by_count":"Sum the rational atom areas grouped by multiplicity.",
                         "uncovered_area":"0","occupied_island_violations":0}))
    atlas=Atlas(study,ch)
    plot_change(output,atlas,regions,atoms,{int(k):v for k,v in density["areas_approx"].items()})
    print("Exact overlay and full domain coverage certified",len(atoms),"faces",flush=True)
    coverage=incidence(study,regions)
    target=ring(atlas.regions[257])
    near=[k for k,r in regions.items() if exact_area(convex_intersection(target,
          halfplanes(points(r)+points(r)[:1])))]
    only=[k for k,r in coverage.items() if set(r["line_ids"]).intersection(ch)=={1509}]
    with (output/"coverage.json").open("xb") as f:
        f.write(encode({"incidence":coverage,"overlapping_257":near,"only_1509_in_archived_CH":sorted(only),
                         "only_1509_local":sorted(set(near).intersection(only))}))
    result=select(study,regions,coverage,ch)
    with (output/"selection.json").open("xb") as f:
        f.write(encode(result))
    print("Selection",result["status"],len(result["C-H"]["ids"]) if result.get("C-H") else None,flush=True)


if __name__=="__main__":
    sys.set_int_max_str_digits(0)
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("manifest","arrangement","audit","oriented","output"):
        p.add_argument("--"+k,required=True,type=Path)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    run(a.manifest,a.arrangement,a.audit,a.oriented,a.output,resume=a.resume)
