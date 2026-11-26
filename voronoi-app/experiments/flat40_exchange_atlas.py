"""Vector atlas from frozen Flat 40 geometry and saved structural certificates."""
import argparse
from fractions import Fraction
from itertools import combinations
from math import atan2, degrees
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as effects
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch
import networkx as nx
import pymupdf
from shapely import from_wkb
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from experiments.flat40_axial_optimisation import verified_previous
from experiments.near_collinear_consolidation import continuation, verified_study
from experiments.occupied_vertex_pruning import read
from voronoi_app.angular import _intersections
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import encode
from voronoi_app.experimental_circulation_topology import evaluate_circulation_lines
from voronoi_app.research_data import sha256_file

CASES = {
    "A": ((1435, 1509), (323, 1365, 1436)),
    "B": ((1470, 1509), (377, 1387, 1443, 1444, 1445, 1460, 1466, 1469, 1475)),
    "C": ((957, 1519), (364, 367, 1389, 1391, 1425, 1427, 1481, 1501, 1502, 1503, 1504)),
}
RED, GREEN, BLUE, GREY = "#ba252e", "#087448", "#245cb0", "#9ba3ab"
FRAME = (0, 100, 0, 100)
styles = ("solid", (0,(5,2)), (0,(1,1.5)), (0,(4,1,1,1)))


def parts(geometry):
    if isinstance(geometry, Polygon):
        if not geometry.is_empty:
            yield geometry
    else:
        for part in getattr(geometry, "geoms", ()):
            yield from parts(part)


def xy(p):
    return tuple(float(Fraction(v)) for v in p)


def polygon(ax, geometry, face, edge, width=.4, z=1, alpha=1):
    for p in parts(geometry):
        p = orient(p)
        vertices, codes = [], []
        for ring in (p.exterior, *p.interiors):
            vertices.extend(ring.coords)
            codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(ring.coords)-2)+[PlotPath.CLOSEPOLY])
        ax.add_patch(PathPatch(PlotPath(vertices, codes), facecolor=face, edgecolor=edge,
                               linewidth=width, zorder=z, alpha=alpha))


def label(ax, p, text, color, offset=(3, 3), size=8):
    return ax.annotate(str(text), p, xytext=offset, textcoords="offset points", color=color,
                fontsize=size, weight="bold", annotation_clip=True, zorder=12,
                path_effects=[effects.withStroke(linewidth=2.2, foreground="white")])


class Atlas:
    def __init__(self, study, ch):
        self.study = study
        self.ch = set(ch)
        self.lines = study.lines
        self.polygons, _, _ = _settlement(study.inputs)
        self.labels = {int(i): label for i, label in study.inputs["settlement"]["building_labels"].items()}
        self.domain = _domain(study.inputs)[2]
        self.regions = {int(i): from_wkb(wkb) for i,wkb in study.inputs["candidates"]["regions_wkb"].items()}
        self.building_points = {i: p.representative_point().coords[0] for i,p in self.polygons.items()
                                if i in self.labels}
        expected = (min(p.bounds[0] for p in self.polygons.values()), max(p.bounds[2] for p in self.polygons.values()),
                    min(p.bounds[1] for p in self.polygons.values()), max(p.bounds[3] for p in self.polygons.values()))
        if expected != FRAME:
            raise ValueError("Archived settlement frame differs.")

    def base(self, ax, viewport=FRAME):
        polygon(ax, self.domain, "#f0f4ef", "#98ab9d", z=0)
        ax.plot([0,100,100,0,0],[0,0,100,100,0],color="#46505a",lw=.65,zorder=2)
        for i, point in self.building_points.items():
            polygon(ax, self.polygons[i], "#303941", "#0e1419", .25, 3)
            if viewport[0] < point[0] < viewport[1] and viewport[2] < point[1] < viewport[3]:
                ax.text(*point, str(self.labels[i]), color="white", fontsize=4.5,
                        ha="center", va="center", clip_on=True, zorder=5)
        ax.set(xlim=viewport[:2], ylim=viewport[2:], aspect="equal")
        ax.set_axis_off()

    def line(self, ax, i, color, *, width=1, style="solid", z=6, tag=None):
        line = self.lines[i]
        a,b = xy(line.start),xy(line.end)
        artist, = ax.plot(*zip(a,b), color=color, lw=width, linestyle=style, zorder=z,
                          solid_capstyle="round", dash_capstyle="butt")
        if tuple(zip(*artist.get_data())) != (a,b):
            raise ValueError(f"Plotted coordinates changed for candidate {i}.")
        if tag:
            fraction, offset = tag
            label(ax, tuple(x+fraction*(y-x) for x,y in zip(a,b)), i, color, offset)
        return artist

    def network(self, ax, ids):
        for i in sorted(ids):
            self.line(ax,i,GREY,width=.75,z=4)

    def intersections(self, ax, ids):
        points = {xy(p) for a,b in self.study.graph.subgraph(ids).edges
                  for p in _intersections(self.lines[a].start,self.lines[a].end,
                                          self.lines[b].start,self.lines[b].end)}
        if points:
            ax.scatter(*zip(*points),s=4,c="#707982",zorder=5,linewidths=0)

    def numbered_network(self, ax, ids):
        # Place each ID on the line at the first free position. Test the actual
        # rendered text boxes in display coordinates, leaving a small halo.
        ax.figure.canvas.draw()
        renderer = ax.figure.canvas.get_renderer()
        placed = [item.get_window_extent(renderer).expanded(1.12,1.25) for item in ax.texts]
        positions = (.5,.42,.58,.34,.66,.26,.74,.18,.82,.12,.88)
        for i in ids:
            line = self.lines[i]
            a,b = xy(line.start),xy(line.end)
            for fraction in positions:
                for offset in ((3,3),(3,-8),(-13,3),(-13,-8)):
                    point = tuple(x+fraction*(y-x) for x,y in zip(a,b))
                    artist = label(ax,point,i,"#65717c",offset,size=7)
                    box = artist.get_window_extent(renderer).expanded(1.20,1.27)
                    if (ax.bbox.contains(box.x0,box.y0) and ax.bbox.contains(box.x1,box.y1)
                            and not any(box.overlaps(other) for other in placed)):
                        placed.append(box)
                        break
                    artist.remove()
                else:
                    continue
                break
            else:
                raise ValueError(f"Cannot fit archived candidate label {i}.")

    def junction(self, ax, row):
        ax.scatter(*xy(row["junction"]),s=38,facecolors="white",edgecolors=RED,
                   linewidths=1.35,zorder=10)

    def local(self, pair, candidate, contacts):
        focus = [xy(p) for i in (*pair,candidate) for p in (self.lines[i].start,self.lines[i].end)]
        focus.extend(xy(p) for p in contacts)
        xmin,ymin = map(min,zip(*focus))
        xmax,ymax = map(max,zip(*focus))
        for i in self.labels:
            a,b,c,d = self.polygons[i].bounds
            if c >= xmin-2 and a <= xmax+2 and d >= ymin-2 and b <= ymax+2:
                focus.extend(((a,b),(c,d)))
        xmin,ymin = map(min,zip(*focus))
        xmax,ymax = map(max,zip(*focus))
        margin = 3.5
        return xmin-margin,xmax+margin,ymin-margin,ymax+margin

    def exchange(self, name, row, candidate, selected, viewport, *, detail):
        pair = row["pair"]
        retained = self.ch-set(pair)
        fig, axes = page(f"Case {name}  |  Remove {pair[0]} and {pair[1]}, add {candidate}",
                         f"{row['delta']:.3f}° departure from straight  ·  " +
                         ("Matched local detail" if detail else "Matched full settlement"), 2)
        for ax in axes:
            self.base(ax,viewport)
        self.network(axes[0],retained)
        self.intersections(axes[0],self.ch)
        self.network(axes[1],retained)
        self.intersections(axes[1],selected)
        axes[0].set_title("Before  ·  Archived C-H  ·  34 lines",loc="left")
        axes[1].set_title("After  ·  Independently certified  ·  33 lines",loc="left")
        self.line(axes[1],candidate,GREEN,width=3.0,z=7,tag=(.56,(4,-13)))
        for j,i in enumerate(pair):
            for k,ax in enumerate(axes):
                self.line(ax,i,RED,width=2.05 if k==0 else 1.25,style="dashed" if k else "solid",
                          z=9,tag=((.26,.76)[j],(4,7 if j==0 else -11)))
        for ax in axes:
            self.junction(ax,row)
        if detail:
            line = self.lines[candidate]
            supports = {xy(p) for s in line.provenance for p in (s.start,s.end)}
            contacts = {xy(p) for i in self.study.neighbors[candidate] & retained
                        for p in _intersections(line.start,line.end,self.lines[i].start,self.lines[i].end)}
            if supports:
                axes[1].scatter(*zip(*supports),c=BLUE,s=16,marker="D",zorder=10,edgecolors="white",linewidths=.45)
            if contacts:
                axes[1].scatter(*zip(*contacts),c=GREEN,s=24,zorder=11,edgecolors="white",linewidths=.55)
        foot(fig,"Red  Removed pair and junction   ·   Green  Replacement and retained contacts   ·   Blue  Saved support points (local view)")
        return fig

    def overview(self, name, row, candidates):
        pair = row["pair"]
        fig, (ax, inset) = page(f"Case {name}  |  {pair[0]} and {pair[1]}",
                                f"{row['delta']:.3f}° departure from straight  ·  {len(candidates)} independently certified alternatives",2)
        focus = [xy(p) for i in (*pair,*candidates) for p in (self.lines[i].start,self.lines[i].end)]
        lx, ly = map(min,zip(*focus))
        hx, hy = map(max,zip(*focus))
        colors = ["#087448","#28934e","#4a8118","#008375","#006436","#469c31"]
        handles = []
        for k,i in enumerate(candidates):
            handles.append(Line2D([],[],color=colors[k%len(colors)],linestyle=styles[k//len(colors)],
                                  lw=2,label=str(i)))
        for slot, viewport in ((ax,FRAME),(inset,(lx-3,hx+3,ly-3,hy+3))):
            self.base(slot,viewport)
            self.network(slot,self.ch-set(pair))
            for k,i in enumerate(candidates):
                self.line(slot,i,colors[k%len(colors)],width=1.35,style=styles[k//len(colors)],z=7)
            for j,i in enumerate(pair):
                self.line(slot,i,RED,width=2.1,z=9,tag=((.25,.77)[j],(4,7 if j==0 else -11)))
            self.junction(slot,row)
        ax.set_title("Full settlement",loc="left")
        inset.set_title("Exchange area",loc="left")
        fig.legend(handles=handles,loc="lower center",ncol=min(6,len(handles)),frameon=False,
                   title="Certified replacement candidate IDs",bbox_to_anchor=(.5,.018))
        return fig

    def coverage(self, name, row, candidates, unique, shared):
        pair = row["pair"]
        fig, axes = page(f"Case {name}  |  Strict convex coverage",
                         "Region sets come from frozen positive-interior incidence",2)
        view = self.local(pair,candidates[0],set())
        for ax in axes:
            self.base(ax,view)
        for i in sorted(shared):
            polygon(axes[0],self.regions[i],"#c9def1","#6291b5",.6,z=2,alpha=.40)
        for ax in axes:
            for i in sorted(unique):
                region = self.regions[i]
                polygon(ax,region,"#ffd386","#a65c13",.9,z=2,alpha=.53)
                label(ax,region.representative_point().coords[0],i,"#8d4307",size=7)
        for j,i in enumerate(pair):
            self.line(axes[0],i,RED,width=2,tag=((.25,.75)[j],(3,5)))
        self.line(axes[1],candidates[0],GREEN,width=2.6,tag=(.6,(3,-12)))
        axes[0].set_title("Blue  Also covered by retained C-H\nAmber  Uncovered after deletion",loc="left")
        axes[1].set_title(f"Candidate {candidates[0]} shown\nEvery certified alternative covers each amber region",loc="left")
        foot(fig,"Amber region IDs  " + ", ".join(map(str,sorted(unique))) +
             f"    ·    {len(shared)} shared regions    ·    {len(candidates)} alternatives verified")
        return fig


def page(title, subtitle, panels=1):
    fig, axes = plt.subplots(1,panels,figsize=(15.5,8.5),squeeze=False)
    fig.subplots_adjust(left=.035,right=.965,bottom=.105,top=.845,wspace=.12)
    fig.text(.04,.955,title,fontsize=22,weight="bold",color="#202c36",va="top")
    fig.text(.041,.907,subtitle,fontsize=11,color="#546371",va="top")
    return fig, axes.ravel()


def foot(fig, text):
    fig.text(.042,.042,text,fontsize=9,color="#43515d")


def plot_pdf(path, figures):
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        for fig in figures:
            pdf.savefig(fig)
            plt.close(fig)


def combine(path, sources):
    toc = []
    with pymupdf.open() as output:
        for title, source in sources:
            toc.append([1,title,len(output)+1])
            with pymupdf.open(source) as pdf:
                output.insert_pdf(pdf)
        output.set_toc(toc)
        output.save(path,garbage=3,deflate=True)
    return toc


def pngs(path, directory):
    names = []
    with pymupdf.open(path) as pdf:
        for number,p in enumerate(pdf,1):
            name = f"{path.stem}_{number:02d}.png"
            pix = p.get_pixmap(dpi=240,alpha=False)
            if min(pix.width,pix.height) < 1800:
                raise ValueError("Export resolution is too small.")
            pix.save(directory/name)
            names.append(f"png/{name}")
    return names


def winding(study, ids, *, witnesses=False):
    return evaluate_circulation_lines(study.polygons,[study.lines[i] for i in sorted(ids)],
                                      study.geometry.blocks,study.geometry.domain_clearance,
                                      include_witness_faces=witnesses)


def serial_faces(witness):
    return {str(i): [list(map(str,p)) for p in face] for i,face in witness["witness_faces"].items()}


def circuit_page(atlas, name, pair, candidate, before, removed, after, affected):
    fig, axes = page(f"Case {name}  |  Exact winding witness faces",
                     "Blue outlines are exact bounded faces from the independent winding validator",3)
    retained = atlas.ch-set(pair)
    stages = (
        (atlas.ch, before, "Archived C-H"),
        (retained, removed, "After deleting the pair"),
        (retained|{candidate}, after, f"After inserting {candidate}"),
    )
    for ax, (ids, cert, title) in zip(axes,stages):
        atlas.base(ax)
        atlas.network(ax,ids)
        for cycle in cert["circulation_cycles"]:
            if affected.intersection(cycle["enclosed_blocks"]):
                points = cert["witness_faces"][cycle["face_index"]]
                ax.plot(*zip(*(xy(p) for p in points)),lw=1.75,color=BLUE,zorder=8)
        ax.set_title(f"{title} · rank {cert['independent_circulation_rank']}/24",loc="left")
    for j,i in enumerate(pair):
        atlas.line(axes[0],i,RED,width=2.1,z=9,tag=((.25,.75)[j],(3,5)))
    atlas.line(axes[2],candidate,GREEN,width=2.3,z=9,tag=(.63,(3,-10)))
    foot(fig,"Affected occupied blocks  " + ", ".join(map(str,sorted(affected))) +
         "  ·  Validated witness faces do not define a unique circuit basis")
    return fig


def validate_inputs(study, ch, pairs_path, old_path, provenance, d):
    previous_maps = verified_previous(old_path,study,ch,d,provenance)
    data = read(pairs_path)
    recorded = data["provenance"]
    if (recorded["lineage"] != study.source or
            any(recorded["verified_inputs"].get(f) != digest for f,digest in provenance["verified_inputs"].items())
            or data["maps"]["C-H"] != ch
            or recorded["prior_experiment_sha256"] != sha256_file(old_path)
            or recorded["manifest_sha256"] != provenance["manifest_sha256"]):
        raise ValueError("Optimisation output has different archive provenance.")
    accepted = {tuple(row["pair"]):row for row in data["rows"] if row["counts"].get("accepted")}
    if set(accepted) != {pair for pair,_ in CASES.values()}:
        raise ValueError("Unexpected set of certified pairs.")
    cases = {}
    for name,(pair, expected) in CASES.items():
        row = accepted[pair]
        actual = continuation(*(study.lines[i] for i in pair))
        if any(row[key] != value for key,value in actual.items()):
            raise ValueError(f"Exact junction differs for {pair}.")
        trials = {entry["replacement"]:entry["certificate"] for entry in row["incidence_survivors"]
                  if entry["status"]=="accepted"}
        if set(trials) != set(expected) or not set(pair) <= set(ch):
            raise ValueError(f"Candidate inventory differs for {pair}.")
        for candidate,cert in trials.items():
            ids = (set(ch)-set(pair))|{candidate}
            if (cert["ids"] != sorted(ids) or len(ids)!=33 or candidate in ch
                    or (cert["coverage"],cert["doorways"],cert["components"])!=(292,100,1)
                    or not cert["winding"]["circulation_constraints_satisfied"]
                    or cert["winding"]["independent_circulation_rank"] != 24
                    or cert["winding"]["effective_clearance_line_count"] != 33
                    or not study.clear(candidate)):
                raise ValueError(f"Unexpected independent certificate for {candidate}.")
            if name=="A" and cert["ids"] != previous_maps[f"C-H+{candidate}"]:
                raise ValueError("Previous near-collinear inventory differs.")
        cases[name] = row,trials
    return cases


def pair_geometry(study, candidates):
    result = {}
    for i in candidates:
        line = study.lines[i]
        a,b = xy(line.start),xy(line.end)
        result[str(i)] = {"endpoints":[list(map(str,line.start)),list(map(str,line.end))],
                          "bearing_mod_180":degrees(atan2(b[1]-a[1],b[0]-a[0]))%180,
                          "start_float":a,"end_float":b}
    return result


def connectivity(study, retained, candidate):
    groups = sorted(map(sorted,nx.connected_components(study.graph.subgraph(retained))))
    neighbors = study.neighbors[candidate] & retained
    line = study.lines[candidate]
    return groups, {str(i):[list(map(str,p)) for p in sorted(_intersections(
            line.start,line.end,study.lines[i].start,study.lines[i].end))]
            for i in sorted(neighbors)}


def publication(study, ch, cases, output, provenance):
    atlas = Atlas(study,ch)
    output.mkdir(parents=True,exist_ok=False)
    png = output/"png"
    png.mkdir()
    baseline = output/"flat40_full_settlement.pdf"
    fig,(ax, bx)=page("Corrected Flat 40  |  Full settlement",
                     "Original numbered footprints, accessible space and archived C-H candidate IDs",2)
    for axis in (ax,bx):
        atlas.base(axis)
    ax.set_title("Original building plan",loc="left")
    bx.set_title("Archived C-H · 34 exact maximal intervals",loc="left")
    atlas.network(bx,atlas.ch)
    atlas.intersections(bx,atlas.ch)
    atlas.numbered_network(bx,ch)
    foot(fig,"C-H IDs  " + " · ".join(map(str,ch)))
    plot_pdf(baseline,[fig])
    documents = [("1 · Full settlement",baseline)]
    pngs(baseline,png)
    report = {"provenance":provenance,"full_settlement":baseline.name,"cases":{},"exchanges":[]}
    baseline_wind = winding(study,atlas.ch,witnesses=True)
    if baseline_wind["independent_circulation_rank"]!=24:
        raise ValueError("Baseline independent winding witness replay failed.")
    for name, (row,trials) in cases.items():
        pair = tuple(row["pair"])
        candidates = tuple(trials)
        stem=f"flat40_pair_{pair[0]}_{pair[1]}"
        case_sources=[]
        case_record={"pair":pair,"delta":row["delta"],"junction":row["junction"],
                     "alternatives":pair_geometry(study,candidates)}
        report["cases"][name]=case_record
        retained=atlas.ch-set(pair)
        pair_regions={i for i,group in study.regions.items() if not group.isdisjoint(pair)}
        unique={i for i in pair_regions if retained.isdisjoint(study.regions[i])}
        if sorted(unique)!=row["uncovered_regions"] or (name=="A" and unique!={255,256,257,270}):
            raise ValueError("Saved required regions differ from strict incidence.")
        shared=pair_regions-unique
        removal=winding(study,retained,witnesses=True)
        merged = [cycle["enclosed_blocks"] for cycle in removal["circulation_cycles"]
                  if len(cycle["enclosed_blocks"]) > 1]
        affected = set(removal["missing_axial_rings"]).union(*merged)
        exemplar=candidates[0]
        example_wind=winding(study,retained|{exemplar},witnesses=True)
        if example_wind["independent_circulation_rank"]!=24:
            raise ValueError("Independent representative winding witness replay failed.")
        overview,coverage,circuits=[output/f"{stem}_{suffix}.pdf" for suffix in ("overview","coverage","winding")]
        case_record.update({"combined_regions":sorted(pair_regions),"shared_regions":sorted(shared),
                            "required_regions":sorted(unique),
                            "removal_winding":{k:v for k,v in removal.items() if k!="witness_faces"},
                            "removal_exact_witness_faces":serial_faces(removal),
                            "affected_blocks":sorted(affected),"merged_block_witnesses_after_deletion":merged,
                            "representative_witness_replacement":exemplar,
                            "baseline_exact_witness_faces":serial_faces(baseline_wind),
                            "representative_exact_witness_faces":serial_faces(example_wind),
                            "overview":overview.name,"coverage":coverage.name,"winding":circuits.name})
        plot_pdf(overview,[atlas.overview(name,row,candidates)])
        plot_pdf(coverage,[atlas.coverage(name,row,candidates,unique,shared)])
        plot_pdf(circuits,[circuit_page(atlas,name,pair,exemplar,baseline_wind,removal,example_wind,affected)])
        for title, source in (("Group overview",overview),("Strict convex coverage",coverage),("Winding witness faces",circuits)):
            case_sources.append((f"Case {name} · {title}",source))
            pngs(source,png)
        for i in candidates:
            ids=set(trials[i]["ids"])
            groups, contacts=connectivity(study,retained,i)
            if not all(i in study.regions[r] for r in unique):
                raise ValueError("Replacement fails an exact required-region incidence.")
            if any(set(group).isdisjoint(map(int,contacts)) for group in groups):
                raise ValueError("Replacement misses a retained graph component.")
            view=atlas.local(pair,i,[p for points in contacts.values() for p in points])
            path=output/f"{stem}_replace_{i}.pdf"
            plot_pdf(path,[atlas.exchange(name,row,i,ids,FRAME,detail=False),
                           atlas.exchange(name,row,i,ids,view,detail=True)])
            case_sources.append((f"Case {name} · replacement {i}",path))
            report["exchanges"].append({"case":name,"removed":pair,"replacement":i,
                "pdf":path.name,"png":pngs(path,png),"local_viewport":view,
                "retained_components":groups,"replacement_contacts":contacts,
                "required_regions_covered":sorted(unique),"certificate":trials[i]})
        pair_pdf=output/f"{stem}_atlas.pdf"
        case_record["atlas"]=pair_pdf.name
        case_toc=combine(pair_pdf,case_sources)
        for exchange,(_,_,page_no) in zip([e for e in report["exchanges"] if e["case"]==name],case_toc[3:]):
            exchange["pair_atlas_pages"]=[page_no,page_no+1]
        documents.extend(case_sources)
        print(f"Case {name} exported {len(candidates)} exchanges",flush=True)
    overview=output/"flat40_comparative_overview.pdf"
    fig,axes=page("Comparative overview  |  The three removed pairs",
                  "Same settlement frame in all panels",3)
    for (name,(row,_)),ax in zip(cases.items(),axes):
        atlas.base(ax)
        atlas.network(ax,atlas.ch-set(row["pair"]))
        for j,i in enumerate(row["pair"]):
            atlas.line(ax,i,RED,width=2,z=8,tag=((.25,.75)[j],(3,5)))
        atlas.junction(ax,row)
        ax.set_title(f"Case {name} · {row['delta']:.3f}°",loc="left")
    plot_pdf(overview,[fig])
    pngs(overview,png)
    documents.append(("5 · Comparative overview",overview))
    index_page=output/"flat40_visual_index.pdf"
    fig,axes=page("Visual index  |  Certified candidate substitutions",
                  "Select a replacement ID in the consolidated atlas to jump to its matched views",3)
    for axis,(name,(row,trials)) in zip(axes,cases.items()):
        axis.set_axis_off()
        axis.text(.04,.98,f"Case {name} · remove {row['pair'][0]} and {row['pair'][1]}",
                  transform=axis.transAxes,fontsize=12,weight="bold",va="top")
        for k,i in enumerate(trials):
            axis.text(.04,.87-k*.068,f"Replacement {i}",transform=axis.transAxes,
                      fontsize=11,color=GREEN,va="top")
    foot(fig,"Each certificate is embedded in visual-index.json under exchanges, keyed in the order listed.")
    plot_pdf(index_page,[fig])
    pngs(index_page,png)
    documents.append(("Visual index",index_page))
    consolidated=output/"flat40_axial_exchange_atlas.pdf"
    toc=combine(consolidated,documents)
    report["consolidated_atlas"]=consolidated.name
    page_by_title={title:number for _,title,number in toc}
    with pymupdf.open(consolidated) as pdf:
        index=pdf[-1]
        for n,e in enumerate(report["exchanges"]):
            number=page_by_title[f"Case {e['case']} · replacement {e['replacement']}"]
            e["atlas_pages"]=[number,number+1]
            e["certificate_pointer"]=f"/exchanges/{n}/certificate"
            rectangles=index.search_for(f"Replacement {e['replacement']}")
            if len(rectangles)!=1:
                raise ValueError(f"Cannot resolve index link for {e['replacement']}.")
            index.insert_link({"kind":pymupdf.LINK_GOTO,"from":rectangles[0],"page":number-1})
        pdf.saveIncr()
    with (output/"visual-index.json").open("xb") as stream:
        stream.write(encode(report))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ("manifest","pairs","previous","output"):
        parser.add_argument(f"--{arg}",required=True,type=Path)
    args=parser.parse_args()
    study,ch,d,provenance=verified_study(args.manifest)
    cases=validate_inputs(study,ch,args.pairs,args.previous,provenance,d)
    publication(study,ch,cases,args.output,provenance|{
        "optimisation_sha256":sha256_file(args.pairs),
        "previous_experiment_sha256":sha256_file(args.previous),
        "renderer_sha256":sha256_file(__file__)})


if __name__=="__main__":
    main()
