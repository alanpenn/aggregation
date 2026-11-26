"""Direction-invariant physical support for the experimental face-extension cover."""
from collections import Counter, defaultdict
from fractions import Fraction as F
from itertools import pairwise

from shapely.strtree import STRtree

from experiments.face_extension_cover import bounds, edge, hull, rings
from experiments.flat40_face_extension import points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, ring
from experiments.flat40_oriented_face_audit import coordinates, side
from voronoi_app.region_incidence_angular import halfplanes


def classify_support(face, vertices, *, physical):
    low,high=side(face,vertices)
    if physical:
        return "valid_physical_support" if low>=0 and high>0 else "invalid_physical_support"
    return "backward_extension_context" if low<0 else "forward_extension_context"


def checked_cover(component, audit, accessible, occupied):
    """Revalidate every candidate and retain only semantically valid supports.

    Artificial edges stay in the arrangement. Their parent normals neither
    become constraints nor veto accessible convex space on the other side.
    """
    atoms=[points(a) for a in component["atoms"]]
    areas=[exact_area(p) for p in atoms]
    membership=defaultdict(set)
    for i,p in enumerate(atoms):
        for a,b in pairwise(p+p[:1]):
            membership[edge(a,b)].add(i)
    for row in component["edges"]:
        segment=edge(*coordinates(row["edge"]))
        expected=1 if any(s.startswith("domain-edge:") for s in row["sources"]) else 2
        if len(membership[segment])!=expected:
            raise ValueError("Independent atom-edge partition check failed.")
    domain=rings(accessible)
    total=exact_area(domain[0])-sum(exact_area(p) for p in domain[1:])
    if total!=sum(areas) or not component["partition_certified"]:
        raise ValueError("Independent exact atom-area partition check failed.")
    adjoining=[set() for _ in atoms]
    for members in membership.values():
        for i in members:
            adjoining[i].update(members-{i})
    ids=list(occupied)
    obstacle_tree=STRtree([occupied[i] for i in ids])
    occupied_rings={i:ring(occupied[i]) for i in ids}
    retained={}
    rejected={}
    multiplicity=[0]*len(atoms)
    reasons=Counter()
    for key,record in component["regions"].items():
        p=points(record)
        members=set(record["atoms"])
        area=exact_area(p)
        if tuple(p)!=hull(p) or area<=0 or area!=sum(areas[i] for i in members):
            raise ValueError(f"Invalid convex-union certificate for {key}.")
        if any(hull((*p,*atoms[i]))!=tuple(p) for i in members):
            raise ValueError(f"Member atom outside region {key}.")
        exterior=set().union(*(adjoining[i] for i in members))-members
        for i in exterior:
            if exact_area(list(hull((*p,*atoms[i]))))==area+areas[i]:
                raise ValueError(f"Region {key} admits a convex single-atom enlargement.")
        planes=halfplanes(p+p[:1])
        box=tuple(map(min,zip(*p))),tuple(map(max,zip(*p)))
        blockers=[ids[j] for j in obstacle_tree.query(bounds(box))
                  if exact_area(convex_intersection(occupied_rings[ids[j]],planes))]
        rows=[]
        for original in audit["region_supports"][key]:
            row=original|{"classification":classify_support(audit["faces"][original["face"]],p,
                                  physical=original["physical_contact"])}
            if row["originating_face"] and (not row["physical_contact"] or F(row["min_signed"])<0):
                blockers.append(f"bad originating support {row['face']}")
            if row["classification"]=="invalid_physical_support":
                blockers.append(f"inward physical support {row['face']}")
            reasons[row["classification"]]+=1
            rows.append(row)
        if blockers:
            rejected[key]=blockers
            continue
        retained[key]=record|{
            "physical_supports":[r for r in rows if r["classification"]=="valid_physical_support"],
            "artificial_boundary_context":[r for r in rows if r["classification"]!="valid_physical_support"]}
        for i in members:
            multiplicity[i]+=1
    bins=defaultdict(F)
    for count,area in zip(multiplicity,areas):
        bins[count]+=area
    return {"regions":retained,"rejected":rejected,"support_classification_counts":dict(reasons),
            "exact_covered_area":str(total-bins[0]),"exact_uncovered_area":str(bins[0]),
            "overlap_area_bands":{str(k):str(v) for k,v in bins.items()},
            "atoms":[r|{"multiplicity":count} for r,count in zip(component["atoms"],multiplicity)],
            "partition_certified":True}
