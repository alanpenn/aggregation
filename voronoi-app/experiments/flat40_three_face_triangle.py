"""Exact three-face triangle diagnosis against the saved Flat 40 checkpoint."""
import argparse
from fractions import Fraction as F
import gzip
from hashlib import sha256
from itertools import pairwise, product
import json
from pathlib import Path
import sys

import pymupdf

from experiments.face_extension_cover import hull
from experiments.flat40_complete_directed_atlas import normal
from experiments.flat40_complete_directed_convex import HANDS, setup
from experiments.flat40_convex_enlargement import Checker
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_enlarged_cover import blocked_facets
from experiments.flat40_exchange_atlas import Atlas, combine, foot, label, page, plot_pdf, xy
from experiments.flat40_face_extension import draw_polygons, lines, points
from experiments.flat40_region257_inspection import convex_intersection, exact_area, packed, ring
from voronoi_app.angular import _cross, _direction, _inside_prepared, _intersections, _on_segment
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.region_incidence_angular import halfplanes

LABELS = (30, 32, 33)
COLORS = ("#98375a", "#246797", "#207548")


def intersection(f, g):
    u, v = _direction(f.a, f.b), _direction(g.a, g.b)
    determinant = _cross(u, v)
    if determinant:
        t = _cross(_direction(f.a, g.a), v) / determinant
        return tuple(a + t*b for a,b in zip(f.a,u))


def candidates(groups, checker):
    """Check every combination of exposed physical faces of the three buildings."""
    audit = []
    for faces in product(*groups):
        vertices = [intersection(faces[i-1], faces[i]) for i in range(3)]
        if None in vertices or len(set(vertices)) != 3:
            continue
        if not all(all(min(a,b) < p < max(a,b) for p in (f.a,f.b))
                   for f,a,b in zip(faces,vertices,vertices[1:]+vertices[:1])):
            continue
        triangle = hull(vertices)
        signed = [[str(f.signed(v)) for v in triangle] for f in faces]
        oriented = all(F(v) >= 0 for row in signed for v in row)
        certificate = checker.witness([], triangle, independent=True) if oriented else None
        audit.append((faces, vertices, {"faces": [f.identifier for f in faces], "vertices": packed(triangle),
                                       "signed_halfplane_values": signed, "geometry_certificate": certificate}))
    return audit


def face_path(replay, face, start, end):
    """Return the exact approach, physical and departure chains on one side."""
    tracks = replay.crawler.tracks
    first, second = sorted((face.a,face.b), reverse=start>end)
    stages = ((start,first,False),(first,second,True),(second,end,False))
    result = []
    for a,b,wall in stages:
        relevant = [state for state in replay.states
                    if tracks[state[0]].face == face.identifier and tracks[state[0]].wall == wall
                    and (state[1] < state[2]) == (a < b)
                    and all(_on_segment(p,a,b) for p in state[1:])]
        steps = sorted(relevant, key=lambda s:s[1], reverse=a>b)
        if (not steps or steps[0][1] != a or steps[-1][2] != b
                or any(s[2] != t[1] for s,t in pairwise(steps))):
            raise ValueError(f"Missing directed chain on face {face.identifier}: {a}, {b}")
        result.append(steps)
    return result


def expected_walks(replay, faces, triangle, hand):
    ring_vertices = list(triangle if hand == 1 else reversed(triangle))
    sides = []
    for a,b in pairwise(ring_vertices+ring_vertices[:1]):
        f = next(f for f in faces if not f.signed(a) and not f.signed(b))
        approach, physical, departure = face_path(replay, f, a, b)
        sides.append((f, approach, physical, departure))
    for i,(face, _, _, _) in enumerate(sides):
        walk = [state for _,a,b,c in sides[i:]+sides[:i] for state in (*a,*b,*c)]
        pivot = len(sides[i][1])
        yield face, walk[pivot:]+walk[:pivot]


def targeted(replay, walk, hand):
    """Use the original search step at every junction, retaining its exact decisions."""
    stack = None
    trace = []
    for planned in walk[1:] + walk[:1]:
        route, options, closed, rejects, pending = next(
            replay.crawler.traverse(walk[0], hand, replay.occupied, stack))
        i = replay.ids
        decision = dict(options).get(planned, "missing_outgoing_edge")
        trace.append({"prefix": [i[t] for t in route], "next": i[planned], "decision": decision,
                      "incoming_phase": replay.crawler.phase(route[-1]),
                      "outgoing_phase": replay.crawler.phase(planned),
                      "options": replay.encode_options(options), "rejected": dict(rejects)})
        if planned == walk[0]:
            return trace, [packed(p) for p,_ in closed]
        stack = [s for s in pending if s[0][-1] == planned and len(s[0]) == len(route)+1]
        if not stack:
            return trace, []


def journal(replay, schedule, side, walk, triangle_id):
    ordinal = schedule[side].index(walk[0])
    i = replay.ids
    path = [i[t] for t in walk]
    history = {}
    sample = None
    actual_length = -1
    for file in sorted((replay.out/side/f"{ordinal:05d}").glob("*.json.gz")):
        with gzip.open(file,"rb") as f:
            batch = json.load(f)
        history = batch["after"]
        for row in batch["records"]:
            length = next((k for k,(a,b) in enumerate(zip(row["path"],path)) if a != b),
                          min(len(row["path"]),len(path)))
            if length > actual_length or (length == actual_length and row["path"] == path[:length]):
                actual_length = length
                sample = row
    matched_exact = sample is not None and sample["path"] == path
    stack_prefixes = [s["route"] for s in history.get("stack", []) if s["route"] == path[:len(s["route"])]]
    if sample is None:
        status = "not_started"
    elif matched_exact:
        status = "closed_in_checkpoint" if any(row["id"] == triangle_id for row in sample["closed"]) else "closure_absent"
    elif stack_prefixes:
        status = "triangle_branch_pending"
    else:
        status = "target_path_not_saved_or_pending"
    return {"status": status, "ordinal": ordinal, "start_edge": path[0],
            "origin_complete": history.get("complete", False), "prefixes_explored": history.get("prefixes",0),
            "longest_common_prefix": actual_length, "last_matching_or_diverging_row": sample,
            "pending_matching_prefixes": stack_prefixes}


def face_data(face, label_number, settlement_id, vertices):
    a,b = face.a,face.b
    dx,dy = _direction(a,b)
    n = (-dy,dx)
    ends = [v for v in vertices if not face.signed(v)]
    length_squared = dx*dx+dy*dy
    return face.record() | {"building_label":label_number,"settlement_polygon_id":settlement_id,
                            "length_squared":str(length_squared),"length_approx":float(length_squared)**.5,
                            "extension_directions":packed(((-dx,-dy),(dx,dy))),
                            "line_coefficients_Ax_plus_By_plus_C": [str(n[0]),str(n[1]),str(-n[0]*a[0]-n[1]*a[1])],
                            "triangle_side_vertices":packed(ends)}


def render(out, atlas, replay, faces, triangle, paths, before, data):
    extent = [xy(p) for i in (r["settlement_polygon_id"] for r in data["faces"])
              for p in atlas.polygons[i].exterior.coords]
    view = (min(p[0] for p in extent)-1.0,max(p[0] for p in extent)+1.0,
            min(p[1] for p in extent)-1.0,max(p[1] for p in extent)+1.0)
    sources = []
    triangle_shape = {"vertices": packed(triangle)}
    gaps = [r for r in before["faces"] if not r["multiplicity"]]
    def figure(title, subtitle):
        fig, (ax,) = page(title, subtitle)
        atlas.base(ax,view)
        return fig,ax

    def save(fig,title):
        path = out / f"{len(sources)+1:02d}.pdf"
        plot_pdf(path,[fig])
        sources.append((title,path))

    def fill(ax, shapes, color, alpha, z=4):
        draw_polygons(ax, shapes, facecolors=color, edgecolors="none", alpha=alpha, zorder=z)

    def draw_triangle(ax):
        fill(ax,[triangle_shape],"#6cba90",.25)
        lines(ax,pairwise(triangle+triangle[:1]),colors="#265a4c",linewidths=1.,zorder=6)

    def supports(ax, extend=False, normals=False):
        for f,c,d in zip(faces,COLORS,data["faces"]):
            if extend:
                a,b = sorted(tuple(map(F,v)) for v in d["triangle_side_vertices"])
                p,q = sorted((f.a,f.b))
                lines(ax,[(a,p),(q,b)],colors=c,linestyles="dashed",linewidths=2.0,zorder=8)
            lines(ax,[(f.a,f.b)],colors=c,linewidths=3.0,zorder=9)
            if normals:
                normal(ax,f,.9,c)

    def arrow(ax,a,b,color,at=.60):
        x,y = xy(a)
        X,Y = xy(b)
        pivot = (x+at*(X-x),y+at*(Y-y))
        tail = (x+(at-.13)*(X-x),y+(at-.13)*(Y-y))
        ax.annotate("",pivot,tail,arrowprops={"arrowstyle":"-|>","color":color,"lw":1.6},zorder=12)

    fig,ax = figure("Physical geometry around buildings 30, 32 and 33",
                    "Orange marks accessible space uncovered in the saved Flat 40 checkpoint")
    fill(ax,gaps,"#ed934d",.70,z=2)
    save(fig,"Physical geometry and uncovered space")

    fig,ax = figure("Three complete physical supporting faces",
                    "30 · face 136     32 · face 305     33 · face 367")
    supports(ax,normals=True)
    save(fig,"Physical faces and outward normals")

    fig,ax = figure("Each physical face extends at both endpoints",
                    "Solid segments are physical faces · Dashes show the two arms required by the triangle")
    supports(ax,extend=True)
    save(fig,"Both extension directions")

    fig,ax = figure("Exact three-face triangle","Each corner is a pairwise supporting-line intersection in open space")
    draw_triangle(ax)
    supports(ax,extend=True)
    for k,p in enumerate(triangle,1):
        label(ax,xy(p),f"V{k}","#143d35",(4,4),size=9)
    foot(fig,"   ·   ".join(f"V{k} = ({float(x):.6f}, {float(y):.6f})" for k,(x,y) in enumerate(triangle,1)))
    save(fig,"Exact triangle and intersection vertices")

    fig,ax = figure("Intersection of three oriented half-planes",
                    "Each translucent tint shows the accessible side of one supporting line")
    xmin,xmax,ymin,ymax = map(F,view)
    box = [(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)]
    for f,c in zip(faces,COLORS):
        clipped = convex_intersection(box,[(f.a,_direction(f.a,f.b))])
        fill(ax,[{"vertices":packed(clipped)}],c,.10)
    draw_triangle(ax)
    supports(ax,extend=True,normals=True)
    save(fig,"Outward-facing half-plane construction")

    for side in ("right","left"):
        sample = next(r for r in paths if r["hand"] == side and r["face"] == faces[0].identifier)
        fig,ax = figure(f"{side.capitalize()}-hand traversal",
                        "The target branch replay closed from each of the three physical starts")
        draw_triangle(ax)
        supports(ax,extend=True)
        for i,edge in enumerate(sample["expected_edges"]):
            t,a,b = replay.states[edge]
            if i % 4 == 0:
                arrow(ax,a,b,"#172b3b")
            row = sample["targeted_steps"][i]
            if row["decision"] in ("straight_extension_from_wall","turn_towards_originating_face") or (
                    row["incoming_phase"][0] == "committed" and row["outgoing_phase"][0] == "physical"):
                label(ax,xy(b),i+1,"#202c36",(4,4),size=7)
        foot(fig,"Numbered events mark departures, extension turns and arrivals at the physical face.")
        save(fig,f"{side.capitalize()}-hand complete circuit")

    fig,ax = figure("Saved search prefixes and pending continuations",
                    "All six target paths are pending · Solid green shows the saved prefix · Ochre arrows show its queued continuation")
    draw_triangle(ax)
    for row in paths:
        status = row["checkpoint"]
        count = status["longest_common_prefix"]
        for edge in row["expected_edges"][:count]:
            _,a,b = replay.states[edge]
            lines(ax,[(a,b)],colors="#24775b",linewidths=2.3,zorder=8)
        if count < len(row["expected_edges"]):
            _,a,b = replay.states[row["expected_edges"][count]]
            arrow(ax,a,b,"#af6a14")
            ax.scatter(*xy(a),color="#af6a14",s=14,zorder=10)
    foot(fig,"Targeted replay follows the queued branch through to closure; the saved checkpoint is unchanged.")
    save(fig,"Checkpoint prefixes and first pending edges")

    fig,ax = figure("Each facet is blocked by physical contact",
                    "A convex superset crossing any side would enter occupied interior at its supporting face")
    draw_triangle(ax)
    supports(ax,extend=True,normals=True)
    for f,c,d in zip(faces,COLORS,data["faces"]):
        midpoint = tuple((a+b)/2 for a,b in zip(f.a,f.b))
        label(ax,xy(midpoint),f'{d["length_approx"]:.3f}',c,(4,-9),size=8)
    save(fig,"Global maximality certificate")

    fig,ax = figure("Exact contribution to the saved cover",
                    "Orange shows the pre-existing gap · Teal marks previously uncovered area inside the triangle")
    fill(ax,gaps,"#e88d45",.60,z=2)
    draw_triangle(ax)
    planes = halfplanes(triangle+triangle[:1])
    for g in gaps:
        clipped = convex_intersection(points(g),planes)
        if exact_area(clipped):
            fill(ax,[{"vertices":packed(clipped)}],"#067c74",.67,z=5)
    foot(fig,f'{data["gap_area_filled_approx"]:.6f} square units of previously uncovered accessible space')
    save(fig,"Exact coverage contribution")

    consolidated = out/"flat40-three-face-triangle-atlas.pdf"
    combine(consolidated,sources)
    with pymupdf.open(consolidated) as pdf:
        if len(pdf) != 10 or any(p.get_images() for p in pdf):
            raise ValueError("The ten atlas views must be vector pages.")


def main():
    sys.set_int_max_str_digits(0)
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","checkpoint","output"):
        cli.add_argument("--"+name,type=Path,required=True)
    cli.add_argument("--render-only",action="store_true")
    args = cli.parse_args()
    study,ch,domain,replay,schedule = setup(args.manifest,args.checkpoint)
    atlas = Atlas(study,ch)
    ids = [next(i for i,label in atlas.labels.items() if int(label)==n) for n in LABELS]
    groups = [[f for f in replay.crawler.faces if any(
        len(_intersections(f.a,f.b,a,b)) == 2 for a,b in pairwise(ring(atlas.polygons[i])))] for i in ids]
    checker = Checker(domain,replay.occupied)
    audit = candidates(groups,checker)
    [(faces, _, evidence)] = [r for r in audit if r[2]["geometry_certificate"]]
    triangle = hull(points(evidence))
    if not all(_inside_prepared(p,checker.domain) for p in triangle):
        raise ValueError("Triangle vertex outside accessible open space.")
    for face, building in zip(faces, ids):
        if not any({a,b} == {face.a,face.b} for a,b in pairwise(ring(atlas.polygons[building]))):
            raise ValueError(f"Face {face.identifier} does not span a complete original building edge.")
    certificate = blocked_facets(checker, triangle)
    if len(certificate) != 3:
        raise ValueError("Expected independent maximality evidence for each triangle facet.")
    triangle_id = sha256(encode(packed(triangle))).hexdigest()
    paths = []
    for hand,side in HANDS:
        for face, walk in expected_walks(replay,faces,triangle,hand):
            trace, closures = targeted(replay,walk,hand)
            paths.append({"face":face.identifier,"hand":side,"expected_edges":[replay.ids[t] for t in walk],
                          "targeted_steps":trace,"closures":closures,
                          "checkpoint":journal(replay,schedule,side,walk,triangle_id)})
    print([(r["hand"],r["face"],len(r["expected_edges"]),len(r["targeted_steps"]),
            r["targeted_steps"][-1]["decision"],bool(r["closures"]),r["checkpoint"]["status"],
            r["checkpoint"]["longest_common_prefix"]) for r in paths],flush=True)
    before = json.loads((args.checkpoint/"coverage-maximal.json").read_text())
    if args.render_only:
        data = json.loads((args.output/"triangle-diagnosis.json").read_text())
        render(args.output,atlas,replay,faces,triangle,paths,before,data)
        return
    prior_regions = json.loads((args.checkpoint/"regions.json").read_text())["regions"]
    after = exact_coverage(domain,[points(r) for r in prior_regions.values()]+[triangle])
    extra = F(before["uncovered_area"])-F(after["uncovered_area"])
    planes = halfplanes(triangle+triangle[:1])
    clipped_gap = sum(exact_area(convex_intersection(points(g),planes))
                      for g in before["faces"] if not g["multiplicity"])
    if clipped_gap != extra:
        raise ValueError("The clipped gap area differs from the exact cover-area delta.")
    data = evidence | {"triangle_id":triangle_id,"vertices_in_accessible_interior":True,
        "area":str(exact_area(triangle)),"maximality_certificate":certificate,
        "faces":[face_data(f,n,i,triangle) for f,n,i in zip(faces,LABELS,ids)],
        "exposed_faces_checked": [[f.identifier for f in group] for group in groups],
        "other_full_face_combinations":[r for _,_,r in audit if r is not evidence],
        "paths":paths,"present_in_checkpoint_registry":triangle_id in prior_regions,
        "gap_area_filled":str(extra),"gap_area_filled_approx":float(extra),
        "after_covered_percent":after["covered_percent"],
        "input_network_sha256":sha256((args.checkpoint/"geometry.json").read_bytes()).hexdigest(),
        "checkpoint_coverage_sha256":sha256((args.checkpoint/"coverage-maximal.json").read_bytes()).hexdigest()}
    args.output.mkdir(parents=True,exist_ok=False)
    atomic_write(args.output/"triangle-diagnosis.json",encode(data))
    render(args.output,atlas,replay,faces,triangle,paths,before,data)
    print("Area of triangle",float(exact_area(triangle)),"gap filled",float(extra),flush=True)


if __name__ == "__main__":
    main()
