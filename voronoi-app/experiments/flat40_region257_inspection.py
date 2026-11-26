"""Exact geometric inspection and vector atlas of frozen Flat 40 region 257."""
import argparse
from fractions import Fraction as F
from itertools import combinations
from math import atan2, degrees, sqrt
from pathlib import Path

import pymupdf
from shapely import constrained_delaunay_triangles
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import MultiPoint
from shapely.ops import unary_union

from experiments.flat40_axial_optimisation import verified_previous
from experiments.flat40_exchange_atlas import (
    Atlas, BLUE, RED, FRAME, combine, foot, label, page, plot_pdf, pngs, polygon, xy,
)
from experiments.near_collinear_consolidation import dot, verified_study
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _cross, _direction, _exact_point, _intersections
from voronoi_app.batch_methods import _domain
from voronoi_app.batch_store import encode
from voronoi_app.region_incidence_angular import halfplanes, positive_interior
from voronoi_app.research_data import sha256_file

REGION = 257
GOLD = "#fbbf62"
INK = "#8a4817"


def ring(p):
    return list(map(_exact_point,p.exterior.coords))


def edges(r):
    return zip(r,r[1:])


def exact_area(vertices):
    if not vertices:
        return F(0)
    return abs(sum((_cross(a,b) for a,b in zip(vertices,vertices[1:]+vertices[:1])),F(0)))/2


def interpolate(a,b,t):
    return tuple(x+t*d for x,d in zip(a,_direction(a,b)))


def convex_intersection(vertices, planes):
    """Rational Sutherland-Hodgman intersection with a convex polygon."""
    points = vertices[:-1] if vertices and vertices[0]==vertices[-1] else vertices
    for a,d in planes:
        clipped=[]
        for p,q in zip(points,points[1:]+points[:1]):
            f,g=(_cross(d,_direction(a,x)) for x in (p,q))
            if f>=0:
                clipped.append(p)
            if (f>=0)!=(g>=0):
                clipped.append(interpolate(p,q,f/(f-g)))
        points=clipped
        if not points:
            break
    return points


def interval(line, planes):
    a,b=line.start,line.end
    low,high=F(0),F(1)
    for p,normal in planes:
        value,rate=_cross(normal,_direction(p,a)),_cross(normal,_direction(a,b))
        if not rate:
            if value<0:
                return None
        elif rate>0:
            low=max(low,-value/rate)
        else:
            high=min(high,-value/rate)
        if low>high:
            return None
    return interpolate(a,b,low),interpolate(a,b,high)


def length2(a,b):
    d=_direction(a,b)
    return dot(d,d)


def packed(points):
    return [list(map(str,p)) for p in points]


def shared_parts(a,b, other):
    segments=[]
    for c,d in other:
        hits=sorted(_intersections(a,b,c,d))
        if len(hits)==2:
            segments.append(hits)
    return segments


def extent(poly, margin):
    a,b,c,d=poly.bounds
    return a-margin,c+margin,b-margin,d+margin


def local_base(atlas, ax, view, *, cells=(), neighbours=(), region=True, network=True):
    atlas.base(ax,view)
    if network:
        atlas.network(ax,atlas.ch-{1435,1509})
    for i in neighbours:
        polygon(ax,atlas.regions[i],"#bbd9e7","#3a788f",.8,2,.20)
    if region:
        polygon(ax,atlas.regions[257],GOLD,INK,2.0,3,.58)
    for i,poly in cells:
        polygon(ax,poly,"none","#7f4086",1.0,5)
        label(ax,poly.representative_point().coords[0],f"cell {i}","#7f4086",offset=(4,5),size=8)


def line_pair(atlas,ax,tag=True):
    for i,c,position in ((1509,RED,.32),(1435,BLUE,.32)):
        atlas.line(ax,i,c,width=1.85,z=7,tag=(position,(3,-10 if i==1509 else 5)) if tag else None)


def mark(ax, coords, text, color, offset=(4,5)):
    p=xy(coords)
    ax.scatter(*p,s=26,color=color,edgecolors="white",linewidths=.6,zorder=11)
    label(ax,p,text,color,offset=offset)


def separated_labels(ax, items, color):
    ax.figure.canvas.draw()
    renderer=ax.figure.canvas.get_renderer()
    occupied=[item.get_window_extent(renderer).expanded(1.14,1.30) for item in ax.texts]
    for i,point in items:
        for offset in ((5,5),(5,-12),(-17,6),(-17,-12),(12,12),(12,-20),(-25,15),(-25,-20)):
            artist=label(ax,point,i,color,offset=offset,size=8)
            box=artist.get_window_extent(renderer).expanded(1.13,1.25)
            if (ax.bbox.contains(box.x0,box.y0) and ax.bbox.contains(box.x1,box.y1)
                    and not any(box.overlaps(other) for other in occupied)):
                occupied.append(box)
                break
            artist.remove()
        else:
            raise ValueError(f"No space for region label {i}.")


def seed_replay(domain, target):
    # A triangle that seeded this hull must already lie inside it.
    simple=domain.simplify(0,preserve_topology=True)
    anchors=sorted({tuple(p) for r in (simple.exterior,*simple.interiors) for p in r.coords[:-1]})
    matches=[]
    for triangle in constrained_delaunay_triangles(simple).geoms:
        if not target.covers(triangle):
            continue
        hull=triangle
        for point in anchors:
            expanded=MultiPoint([*list(hull.exterior.coords)[:-1],point]).convex_hull
            if simple.covers(expanded):
                hull=expanded
        if hull.equals(target):
            matches.append(packed(ring(triangle)))
    return matches


def evidence(atlas,study,raw,repaired,exchanges):
    region=atlas.regions[257]
    vertices=ring(region)
    planes=halfplanes(vertices)
    target_area=exact_area(vertices)
    covers={i for i,l in enumerate(study.lines) if positive_interior(l.start,l.end,planes)}
    if covers!=study.regions[257] or covers&atlas.ch!={1509} or len(study.regions)!=292:
        raise ValueError("Independent region 257 incidence disagrees with the archive.")
    areas={}
    neighbors={}
    for i,p in atlas.regions.items():
        if i==257 or not p.envelope.intersects(region.envelope):
            continue
        other=ring(p)
        overlap=exact_area(convex_intersection(vertices,halfplanes(other)))
        contacts=[s for a,b in edges(vertices) for s in shared_parts(a,b,edges(other))]
        point_contacts=sorted({p for a,b in edges(vertices) for c,d in edges(other)
                               for p in _intersections(a,b,c,d)})
        if point_contacts or overlap:
            areas[i]=overlap
            neighbors[i]={"overlap_area":str(overlap),"shared_segments":[packed(s) for s in contacts],
                          "boundary_intersections":packed(point_contacts),"convex_exact_union":False}
    for i in neighbors:
        other=ring(atlas.regions[i])
        hull=unary_union([region,atlas.regions[i]]).convex_hull
        equal=exact_area(ring(hull))==target_area+exact_area(other)-areas[i]
        neighbors[i]["convex_exact_union"]=equal
    opened,occupied,accessible,_=_domain(study.inputs)
    cells={}
    for i,p in opened.items():
        if region.envelope.intersects(p.envelope):
            if not p.equals(p.convex_hull):
                raise ValueError(f"Archived source cell {i} is not convex.")
            area=exact_area(convex_intersection(vertices,halfplanes(ring(p))))
            if area:
                cells[i]={"area":str(area),"area_approx":float(area)}
    physical=[]
    domain_edges=[edge for boundary in (accessible.exterior,*accessible.interiors)
                  for edge in edges(list(map(_exact_point,boundary.coords)))]
    for a,b in edges(vertices):
        rows=[]
        for i,p in occupied.items():
            for part in getattr(p,"geoms",[p]):
                for s in shared_parts(a,b,edges(ring(part))):
                    rows.append({"cell":i,"building_label":atlas.labels.get(i),"segment":packed(s)})
        full=any({a,b}=={tuple(map(F,x)) for x in row["segment"]} for row in rows)
        physical.append({"edge":packed((a,b)),"building_faces":rows,"full_physical_edge":full,
                         "accessible_boundary_contacts":[packed(s) for s in shared_parts(a,b,domain_edges)]})
    clips={}
    for i in (1435,1509):
        l=study.lines[i]
        ab=interval(l,planes)
        clips[i]={"closed_interval":packed(ab),"squared_length":str(length2(*ab)),
                  "length_approx":sqrt(float(length2(*ab))),"strict_interior":i in covers}
    substitute=None
    options=[i for i,v in areas.items() if v]
    for a,b in combinations(options,2):
        p=convex_intersection(vertices,halfplanes(ring(atlas.regions[a])))
        if not p:
            continue
        joint=exact_area(convex_intersection(p,halfplanes(ring(atlas.regions[b]))))
        if areas[a]+areas[b]-joint==target_area:
            substitute={"ids":[a,b],"intersection_inside_257_area":str(joint),
                        "individual_overlap_areas":[str(areas[a]),str(areas[b])],
                        "1435_hits":[i for i in (a,b) if 1435 in study.regions[i]]}
            break
    candidates={}
    for i in sorted(covers):
        l=study.lines[i]
        dx,dy=_direction(l.start,l.end)
        candidates[i]={"bearing_mod_180":degrees(atan2(float(dy),float(dx)))%180,
            "exact_interval":packed((l.start,l.end)),
            "clip_to_257":packed(interval(l,planes)),
            "supports":study.inputs["candidates"]["pool"]["candidates"][i]["provenance"],
            "complementary_raw":i in raw,"complementary_repaired":i in repaired,
            "CH":i in atlas.ch,"in_certified_exchange_replacements":i in exchanges,
            "in_certified_exchange_maps":sorted(k for k,value in exchanges.items() if i in value)}
    widths=[max(_cross(_direction(a,b),_direction(a,p)) for p in vertices)-
            min(_cross(_direction(a,b),_direction(a,p)) for p in vertices) for a,b in edges(vertices)]
    width2=min(w*w/length2(a,b) for w,(a,b) in zip(widths,edges(vertices)))
    return {"vertices":packed(vertices),"area":str(target_area),"area_approx":float(target_area),
            "perimeter_approx":region.length,"minimum_width_squared":str(width2),
            "minimum_width_approx":sqrt(float(width2)),"contacts":clips,"1435_minimum_distance":"0",
            "source_cell_overlaps":cells,"source_cell_area_total":str(sum(F(x["area"]) for x in cells.values())),
            "replayed_matching_seed_triangles":seed_replay(accessible,region),
            "physical_edges":physical,"neighbours":neighbors,"coverage_union_witness":substitute,
            "strict_covering_candidates":candidates}


def draw(atlas, evidence, out):
    r=atlas.regions[257]
    local=extent(r,3.6)
    small=extent(r,1.2)
    neighbours=[int(i) for i,row in evidence["neighbours"].items()
                if F(row["overlap_area"]) or row["shared_segments"]]
    named_order=[]
    files=[]
    def save(number, stem, title, fig):
        path=out/f"{number:02d}_{stem}.pdf"
        plot_pdf(path,[fig])
        named_order.append((title,path))
        files.append({"page":number,"purpose":title,"pdf":path.name,"png":pngs(path,out/"png")[0]})

    fig,(a,b)=page("Region 257  |  Corrected Flat 40",
                   "Original building labels and archived C-H intervals",2)
    for ax,view in ((a,FRAME),(b,extent(r,9))):
        local_base(atlas,ax,view)
        line_pair(atlas,ax)
        label(ax,r.representative_point().coords[0],257,INK)
    a.set_title("Full settlement")
    b.set_title("East-side context")
    foot(fig,"Red 1509 · Blue 1435 · Gold region 257 · Grey other retained C-H")
    save(1,"settlement_context","Complete Flat 40 context",fig)

    fig,(a,b)=page("Region 257  |  Enlarged geometry",
                   "The coverage regions are an overlapping convex cover",2)
    local_base(atlas,a,local)
    local_base(atlas,b,local,neighbours=neighbours)
    for ax in (a,b):
        line_pair(atlas,ax,False)
        label(ax,r.representative_point().coords[0],257,INK,offset=(3,-6))
    for j,p in enumerate(ring(r)[:-1],1):
        mark(a,p,f"V{j}",INK,offset=((-15,5) if j==3 else (4,5)))
    anchors=[]
    for i in neighbours:
        q=atlas.regions[i].intersection(r.buffer(2.8)).representative_point()
        if not q.is_empty:
            anchors.append((i,q.coords[0]))
    separated_labels(b,anchors,"#2b657e")
    a.set_title("Archived polygon vertices V1–V5")
    b.set_title("Direct edge or interior-overlap neighbours")
    foot(fig,"Red 1509 · Blue 1435 · Gold region 257 · Pale blue neighbouring regions")
    save(2,"enlarged_geometry","Enlarged geometry",fig)

    fig,(a,b)=page("Region 257  |  Strict coverage",
                   "Same scale and extent in both panels",2)
    for ax in (a,b):
        local_base(atlas,ax,small,network=False)
    for ax,i,c in ((a,1509,RED),(b,1435,BLUE)):
        atlas.line(ax,i,c,width=1.0,z=7)
        p,q=evidence["contacts"][i]["closed_interval"]
        ax.plot(*zip(xy(p),xy(q)),color=c,lw=3.2,zorder=9,
                linestyle="solid" if i==1509 else "dashed")
        mark(ax,p,"Entry" if i==1509 else "Contact start",c,offset=(4,7))
        mark(ax,q,"Exit" if i==1509 else "Contact end",c,offset=(4,-13))
        length=evidence["contacts"][i]["length_approx"]
        ax.set_title(f"{i} · {length:.3f} units " + ("inside polygon" if i==1509 else "along boundary"))
    foot(fig,"1435 has exact minimum distance 0 and zero interior traversal. Entry and exit labels follow archived endpoint order.")
    save(3,"strict_coverage","Exact strict coverage",fig)

    fig,(a,b)=page("Region 257  |  Physical faces and constructed edges",
                   "Archived source cells and coverage hull shown at a common scale",2)
    local_base(atlas,a,local,cells=[(i,atlas.polygons[i]) for i in evidence["source_cell_overlaps"]],network=False)
    local_base(atlas,b,local,network=False)
    for ax in (a,b):
        label(ax,r.representative_point().coords[0],257,INK)
    for j,row in enumerate(evidence["physical_edges"],1):
        ends=tuple(map(xy,row["edge"]))
        b.plot(*zip(*ends),color="#bb7722",lw=2.25,ls="dashed",zorder=7)
        for face in row["building_faces"]:
            b.plot(*zip(*map(xy,face["segment"])),color="#00584f",lw=3.2,zorder=8)
        label(b,tuple((u+v)/2 for u,v in zip(*ends)),f"E{j}",INK,offset=(3,6))
    a.set_title("Purple  Original clipped Voronoi cell boundaries")
    b.set_title("Green  Exact occupied-face contact · Amber  Other hull edge")
    foot(fig,"V1–V5 follow the archived ring order. E1 starts at V1. The original convex coverage used expanded hulls, not a disjoint partition.")
    save(4,"subdivision","Convex cover and source cells",fig)

    variants=[i for i in evidence["strict_covering_candidates"] if i!=1509]
    fig,axes=plt.subplots(2,3,figsize=(15.5,10.2))
    fig.subplots_adjust(top=.89,bottom=.08,left=.035,right=.97,hspace=.30,wspace=.16)
    fig.text(.04,.96,"Region 257  |  Alternatives in the full certified pool",fontsize=22,weight="bold")
    colors=("#8e2a79","#13698b","#517b13","#be551e","#33338b","#147b69")
    groups=[variants[j:j+6] for j in range(0,len(variants),6)]
    for k,(ax,ids) in enumerate(zip(axes.flat,groups)):
        local_base(atlas,ax,small,network=False)
        handles=[]
        for j,i in enumerate(ids):
            style=("solid",(0,(3,1)),(0,(2,1,1,1)))[j%3]
            atlas.line(ax,i,colors[j],width=1.35,style=style)
            handles.append(Line2D([],[],color=colors[j],ls=style,lw=1.6,label=str(i)))
        ax.legend(handles=handles,loc="upper center",bbox_to_anchor=(.5,-.015),
                  ncol=3,frameon=False,fontsize=7,columnspacing=.9)
        ax.set_title(f"Candidates {ids[0]}–{ids[-1]} in ID order",fontsize=9)
    foot(fig,"Each panel uses the same viewport. All 34 alternatives shown cross the interior in the exact predicate.")
    save(5,"alternatives","Alternative certified candidates",fig)

    fig,(a,b)=page("Region 257  |  Neighbouring open-space union",
                   "Neighbour criteria are exact positive-area overlap or a positive-length shared boundary",2)
    union=unary_union([r,*[atlas.regions[i] for i in neighbours]])
    frame=extent(union,1.6)
    hinges=evidence["coverage_union_witness"]
    for ax in (a,b):
        local_base(atlas,ax,frame,region=False,network=False)
    polygon(a,union,"#b8d9e0","#267181",1.3,z=2,alpha=.56)
    for i in neighbours:
        polygon(a,atlas.regions[i],"none","#3a788f",.75,z=4)
    polygon(b,union,"#dceaf0","#739eae",1.,z=2,alpha=.5)
    if hinges:
        for i in hinges["ids"]:
            polygon(b,atlas.regions[i],"#bfdab9","#4e8052",1.15,z=3,alpha=.38)
            label(b,atlas.regions[i].representative_point().coords[0],i,"#3f6946",size=7)
    for ax in (a,b):
        polygon(ax,r,GOLD,INK,1.8,z=5,alpha=.54)
        label(ax,r.representative_point().coords[0],257,INK)
        line_pair(atlas,ax)
    separated_labels(a,[(i,atlas.regions[i].representative_point().coords[0]) for i in neighbours],"#21637a")
    a.set_title("Union and individual convex hull outlines")
    b.set_title("Coverage-equivalent neighbours highlighted" if hinges else "Original intervals across the union")
    foot(fig,"A convex union requires an exact convexity check. Interior overlap or edge contact alone does not establish it.")
    save(6,"neighbour_union","Neighbouring region union",fig)
    combined=out/"flat40_region_257_atlas.pdf"
    combine(combined,named_order)
    with pymupdf.open(combined) as pdf:
        if len(pdf)!=6 or any(p.get_images() for p in pdf):
            raise ValueError("Expected six vector pages.")
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ("manifest","prior","optimisation","atlas_index","diagnosis","output"):
        parser.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    args=parser.parse_args()
    study,ch,d,prov=verified_study(args.manifest)
    verified_previous(args.prior,study,ch,d,prov)
    diagnostic,opt,index=map(read,(args.diagnosis,args.optimisation,args.atlas_index))
    if (opt["maps"]["C-H"]!=ch or diagnostic["cases"]["CH"]["ids"]!=ch
            or diagnostic["provenance"]["atlas_index_sha256"]!=sha256_file(args.atlas_index)
            or diagnostic["provenance"]["optimisation_sha256"]!=sha256_file(args.optimisation)
            or index["provenance"]["optimisation_sha256"]!=sha256_file(args.optimisation)):
        raise ValueError("Derived source provenance differs.")
    parent=Path(args.manifest).parent
    archive=parent/"strict-generalisation/cross-terrain-constructive-1/flat-40/structural.json"
    hold=read(archive)
    atl=Atlas(study,ch)
    data=evidence(atl,study,set(hold["complementary_raw"]),set(hold["complementary_repaired"]),
                  {row["replacement"]:row["certificate"]["ids"] for row in index["exchanges"]})
    sources={k:sha256_file(getattr(args,k)) for k in ("prior","optimisation","atlas_index","diagnosis")}
    data.update({"provenance":prov|{"derived_sources_sha256":sources,"renderer_sha256":sha256_file(__file__)},
                 "region_id":257,"exact_selected_ids":ch,
                 "1435_neighbour_hits":[i for i in data["neighbours"] if 1435 in study.regions[i]],
                 "1509_neighbour_hits":[i for i in data["neighbours"] if 1509 in study.regions[i]],
                 "accessible_area_approx":atl.domain.area,
                 "archived_regions_still_covered_without_1509":292-len(diagnostic["cases"]["without_1509"]["uncovered_regions"]),
                 "deletion_control":{k:diagnostic["cases"]["without_1509"][k] for k in
                                     ("uncovered_regions","components","unserved_doorways","winding")}})
    # Compare the replayed closed contacts with the separately archived result.
    previous_contacts=diagnostic["unique_region_geometry"]["257"]["boundary_intersections"]
    if any(sorted(row["closed_interval"])!=sorted(previous_contacts[str(i)]) for i,row in data["contacts"].items()):
        raise ValueError("Exact interval endpoints differ from the earlier diagnostic.")
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/"png").mkdir()
    (args.output/"geometry-incidence.json").write_bytes(encode(data))
    pages=draw(atl,data,args.output)
    (args.output/"visual-index.json").write_bytes(encode({"geometry_record":"geometry-incidence.json",
        "source_lineage":prov["lineage"],"derived_sources_sha256":sources,
        "atlas":"flat40_region_257_atlas.pdf","pages":pages}))


if __name__=="__main__":
    main()
