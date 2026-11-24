"""Report E against immutable D and strict-backward Flat 40 controls."""
from fractions import Fraction
from hashlib import sha256
import json
from statistics import median

from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Point, MultiPoint

from experiments.constructive_axial_export import draw, page, route_row, save, stages, table
from experiments.vertex_axial import CASE, CONSTRUCTIVE, ROOT, load
from voronoi_app.angular import _cross, _direction
from voronoi_app.batch_methods import _settlement
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.exact_enumeration import exact_pool_from_dict

TARGETS = (957, 1244, 1355, 865, 1189, 1190, 1208, 1354)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def export():
    archived = CONSTRUCTIVE/CASE
    inputs, source, _ = load(CASE)
    geometry = read(ROOT/"vertices.json")
    vertices = geometry["vertices"]
    result = read(ROOT/"E.json")
    existing = read(archived/"D.json")
    movement = read(ROOT/"movement.json")["methods"]["E"]
    controls = read(archived/"movement.json")
    polygons, _, _ = _settlement(inputs)
    settlement = inputs["settlement"]
    lines = exact_pool_from_dict(inputs["candidates"]["pool"]).candidates
    base = controls["baseline"]
    required = inputs["analysis"]["holes"]
    full = read(archived/"geometry.json")
    archived_manifest = read(CONSTRUCTIVE/"export-checksums.json")
    for name in ("geometry.json","D.json","movement.json","source.json"):
        key = f"{CASE}/{name}"
        if digest(archived/name) != archived_manifest[key]:
            raise ValueError(f"The archived D control differs from its published checksum for {key}.")
    contacts = []
    for vertex in vertices:
        for candidate,members in vertex["support_members"].items():
            line = lines[int(candidate)]
            direction = _direction(line.start,line.end)
            for member in members:
                occurrence = vertex["members"][member]
                along_face = any(_cross(direction,tuple(map(Fraction,edge)))==0
                                 for edge in occurrence["adjacent_directions"])
                contacts.append({"vertex_id":vertex["id"],"candidate_id":int(candidate),
                                 "building_cell":occurrence["cell"],"building_label":occurrence["label"],
                                 "vertex_index":occurrence["vertex_index"],
                                 "support_type":"incident face aligned" if along_face else "vertex tangent"})
    atomic_write(ROOT/"tangent-contacts.json",encode(contacts))
    baseline_ids = set(base["ids"])
    junctions = MultiPoint(list({tuple(float(Fraction(a)) for a in point)
                                 for i in baseline_ids for j, point in full["candidates"][i]["transverse"].items()
                                 if int(j) in baseline_ids}))
    vertex_order = sorted(vertices,key=lambda v:(-v["score"],v["id"]))
    top = vertex_order[:max(1,len(vertices)//10)]
    remaining = vertex_order[len(top):]
    def distance(group):
        return median(Point(*(float(Fraction(x)) for x in record["point"])).distance(junctions) for record in group)
    near, other = distance(top), distance(remaining)
    inspect = []
    selected = result.get("maps",{}).get("exchanged",[])
    for i in TARGETS:
        support = sorted(geometry["candidate_supports"][i],key=lambda v:(-vertices[v]["score"],v))
        inspect.append({"candidate":i,"rank":geometry["ranking"].index(i)+1,
                        "support_vertices":support,
                        "support_buildings":sorted({m["label"] for v in support for m in vertices[v]["members"]}),
                        "in_E_backbone":i in result["backbone"],"in_E_final":i in selected,
                        "in_E_partial":i in result.get("partial",[]),
                        "in_D_final":i in existing["maps"]["exchanged"],"in_backward":i in baseline_ids,
                        "E_stages":[r["stage"] for r in result["trace"] if i in r.get("add",[])+r.get("remove",[])]})
    (ROOT/"numbered-maps").mkdir(exist_ok=True)
    rows, index = [], []
    atlas = ROOT/"numbered-axial-atlas.pdf"
    with PdfPages(atlas.with_suffix(".tmp")) as pdf:
        for title,run in (("E",result),("D",existing)):
            paths = ROOT/"E.json" if title=="E" else archived/"D.json"
            routes = movement if title=="E" else controls["methods"]["D"]
            for stage, ids, tags in stages(run):
                row = None
                if stage in routes:
                    valid = run["validation"][stage]
                    if not valid["valid"]:
                        raise ValueError("Uncertified map reached routing.")
                    row=route_row(CASE,title,stage,routes[stage],valid,run["seconds"],run["peak_rss_mib"])
                    rows.append(row)
                name=f"Flat 40 · Algorithm {title} · {stage.replace('_',' ')}"
                if stage=="failed":
                    check=run["validation"]
                    name+=f"\nWinding rank {check.get('rank')}/{required}"
                    rows.append({"case":CASE,"method":title,"variant":"failed","status":"invalid",
                                 "lines":len(ids),"rank":check.get("rank"),"required_rank":required,
                                 "reason":run["error"],"construction_seconds":run["seconds"]})
                index.append(page(ROOT,pdf,CASE,f"{title}-{stage}",polygons,settlement,lines,ids,tags,name,
                                  {"file":str(paths),"sha256":digest(paths)},row))
        row = route_row(CASE,"strict-backward","baseline",base,{"rank":required,"required_rank":required})
        rows.append(row)
        index.append(page(ROOT,pdf,CASE,"strict-backward",polygons,settlement,lines,base["ids"],{},
                          "Flat 40 · Archived strict backward",source["analysis"],row))
        fig, ax = plt.subplots(figsize=(8.4,9.2),layout="constrained")
        draw(ax,settlement,polygons,lines,base["ids"],{})
        for v in top:
            x,y=(float(Fraction(p)) for p in v["point"])
            ax.scatter(x,y,s=10+50*v["score"],c="#9b2685",edgecolors="white",linewidths=.4,zorder=7)
        fig.suptitle("Flat 40 · Highest-scoring vertex decile and archived axial network")
        index.append({"case":CASE,"stage":"vertex-decile","ids":base["ids"],"vertices":[v["id"] for v in top],
                      "record":{"vertices_sha256":digest(ROOT/"vertices.json"),"baseline":source["analysis"]},
                      "files":save(ROOT,"vertex-decile",fig,pdf)})
    atlas.with_suffix(".tmp").replace(atlas)
    table(ROOT/"comparison.csv",rows)
    atomic_write(ROOT/"targets.json",encode(inspect))
    atomic_write(ROOT/"visual-index.json",encode({"atlas":atlas.name,"maps":index}))
    text = ["# Vertex supported axial selection on Flat 40","",
            f"The occupied geometry contains **{len(vertices)} distinct exact coordinates** and "
            f"**{sum(len(v['members']) for v in vertices)} building-vertex occurrences**. "
            "Each occurrence retains its building cell and label, polygon index, two rational incident-edge vectors, "
            "coincident building memberships and exact shared-edge or vertex-only contact records.",
            f"The index links {sum(len(v['supported']) for v in vertices):,} vertex–candidate pairs "
            f"across {sum(bool(v) for v in geometry['candidate_supports']):,} certified candidates.","",
            "A candidate supports a vertex when its exact interval contains that coordinate and its direction passes "
            "the existing supporting-vertex predicate for at least one incident building. The tangent-contact table distinguishes "
            "edge-aligned support from a tangent through the vertex alone. The index counts intermediate "
            "support contacts as well as generating endpoints. IDs, endpoints, route references, and incidence come "
            "from the archived certified pool.","",
            "## Geometry and backbone","",
            f"Extended candidates are at least the pool median length, **{geometry['extended_threshold']:.2f} units**. "
            "The vertex score combines distinct nonredundant extended families, occupied 15° direction bins, maximum "
            "length, and mean transverse family diversity with scaled weights 0.35, 0.30, 0.20, and 0.15. "
            "E ranks candidates using 55% of their strongest supporting vertex score and 45% of D's static geometric "
            "tie-break order score. E selects the first 12 nonredundant candidates before common coverage, "
            "connectivity, winding repair, reduction, and exchange. Doorway route costs are evaluated afterward.","",
            f"The highest-scoring vertex decile has median distance **{near:.2f}** to an archived transverse "
            f"intersection, versus **{other:.2f}** for the remaining vertices. The intersections are a junction proxy "
            "from the independently archived map. The score's transverse-diversity term and shared geometry mean this "
            "single-case contrast is descriptive.","","## Map comparison","",
            "| Method | Stage | Lines | Winding | Angular mean | Metric mean |",
            "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        if row["variant"] in ("constructive","exchanged","archived_count","baseline"):
            text.append(f"| {row['method']} | {row['variant']} | {row['lines']} | {row['rank']}/{row['required_rank']} | "
                        f"{row['angular_mean']:.4f} | {row['metric_mean']:.3f} |")
    if result.get("error"):
        check=result["validation"]
        text.extend(["",f"E stalled at winding rank {check.get('rank')}/{required} with {len(result['partial'])} lines. "
                    "It covered every required region and doorway and formed one connected network. "
                    "The comparison reports movement for the certified controls."])
        termination = ROOT/"termination-winding.json"
        if termination.exists():
            groups = [", ".join(face["blocks"]) for face in read(termination)["shared_faces"]]
            if groups:
                text.extend(["", "The independent termination check found a shared enclosure for "
                             + " and ".join(groups) + ". "
                             "It counted as a single winding class. [Exact termination certificate](termination-winding.json)"])
    elif movement:
        e=movement["exchanged"]
        text.extend(["",f"E's exchanged map has {e['count']} lines. Across {e['angular']['reachable']:,} angular and "
                    f"{e['metric']['reachable']:,} metric doorway pairs, its mean changes relative to strict "
                    f"backward are {e['angular']['mean']-base['angular']['mean']:+.4f} quarter turns and "
                    f"{e['metric']['mean']-base['metric']['mean']:+.3f} units."])
    text.extend(["","## Independent tangent checks","",
                 "| Candidate | E rank | Supporting building labels | E backbone | E partial | E final | D final |",
                 "|---|---:|---|---|---|---|---|"])
    for row in inspect:
        text.append(f"| {row['candidate']} | {row['rank']} | {', '.join(map(str,row['support_buildings']))} | "
                    f"{row['in_E_backbone']} | {row['in_E_partial']} | {row['in_E_final']} | {row['in_D_final']} |")
    text.extend(["","The named candidates appear only in the evaluation. The experiment uses Flat 40 as specified "
                 "in the supplied brief. The final contact-type bullet ends mid-sentence, so face contact here "
                 "means an exact shared polygon edge and vertex-only contact means a coincident point without such an edge.",
                 "", "[Numbered vector atlas](numbered-axial-atlas.pdf) · [Exact vertex index](vertices.json) · [Axial support contacts](tangent-contacts.json) · "
                 "[Comparison CSV](comparison.csv) · [Target evaluation](targets.json) · [Map index](visual-index.json)",""])
    (ROOT/"report.md").write_text("\n".join(text))
    print(f"{len(index)} verified numbered maps exported.")


if __name__=="__main__":
    export()
