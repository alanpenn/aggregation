"""Exact reference experiments and vector diagrams for oriented open-space turns."""
import argparse
from fractions import Fraction as F
from pathlib import Path

from matplotlib.collections import PolyCollection
from matplotlib.colors import BoundaryNorm
import pymupdf
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from experiments.directed_boundary_reference import L_ROOM, LOW, UP
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_exchange_atlas import combine, foot, label, page, plot_pdf, polygon, xy
from experiments.flat40_region257_inspection import packed
from experiments.oriented_extension_turns import ADMISSIBLE, ExtensionCrawler
from voronoi_app.angular import _cross, _direction, _inside_prepared
from voronoi_app.batch_store import encode
from voronoi_app.research_data import sha256_file

FRAME=box(0,0,8,8)
BLOCKS={"B":box(6,0,8,3),"C":box(0,6,4,8),"D":box(7,7,8,8)}
DOMAIN=FRAME.difference(unary_union(list(BLOCKS.values())))
TARGET=((0,0),(6,0),(6,6),(0,6))
JUNCTION=tuple(map(F,(6,6)))
ORANGE="#aa501d"


def at_junction(path):
    return [t for t in path["transitions"]
            if t[0][2]==JUNCTION and t[2]=="turn_towards_originating_face"]


def check_references():
    l=ExtensionCrawler(L_ROOM)
    room,room_rejections=l.construct()
    if set(room)!={LOW,UP}:
        raise ValueError("New turning rule changed the L-room rectangles.")
    lc=exact_coverage(L_ROOM,room)
    if lc["area_by_count"]!={"1":"16","2":"4","0":"0"}:
        raise ValueError("Incorrect L-room multiplicity.")
    crawler=ExtensionCrawler(DOMAIN,list(BLOCKS.items()))
    regions,rejections=crawler.construct(BLOCKS)
    paths=regions[TARGET]
    if {p["sign"] for p in paths}!={1,-1} or any(not at_junction(p) for p in paths):
        raise ValueError("Target did not require the mirrored open-space turns.")
    if not _inside_prepared(JUNCTION,crawler.walls.prepared):
        raise ValueError("Junction is not in open interior.")
    exemplars={sign:next(p for p in paths if p["sign"]==sign
                         and any(status=="straight" for _,status in at_junction(p)[0][3]))
               for sign in (1,-1)}
    for sign,path in exemplars.items():
        incoming,chosen,status,options=at_junction(path)[0]
        current,nxt=(crawler.tracks[s[0]] for s in (incoming,chosen))
        if current.wall or nxt.wall or nxt.direction(*chosen[1:])!=-1 or nxt.away_sign!=-sign:
            raise ValueError("Turn did not approach the physical source with the proper hand.")
        if not any(c[0]==nxt.id and s=="away_from_originating_face" for c,s in options):
            raise ValueError("Away-going direction was not explicitly rejected.")
        if not any(event=="follow_physical_face" and b[1]==nxt.a
                   and crawler.tracks[b[0]].face==nxt.face
                   for a,b,event,_ in path["transitions"] if a[0]==nxt.id):
            raise ValueError("The chosen extension did not reach its originating physical face.")
    cover=exact_coverage(DOMAIN,regions)
    if cover["domain_area"]!="49" or not cover["full_coverage"]:
        raise ValueError("The completed three-block paths do not cover the required space.")
    return l,room,room_rejections,lc,crawler,regions,rejections,cover,exemplars


def arrow(ax,a,b,color,*,dashed=False):
    line,=ax.plot(*zip(a,b),color=color,lw=2.,linestyle="dashed" if dashed else "solid",zorder=7)
    start=tuple(x+.36*(y-x) for x,y in zip(a,b))
    end=tuple(x+.71*(y-x) for x,y in zip(a,b))
    ax.annotate("",xy=end,xytext=start,arrowprops={"arrowstyle":"-|>","lw":1.65,"color":color},zorder=8)
    return line


def base(ax):
    polygon(ax,DOMAIN,"#f1f4ee","#32534c",.8)
    for name,shape in BLOCKS.items():
        polygon(ax,shape,"#303740","#22282c",.9)
        label(ax,shape.representative_point().coords[0],name,"#2a3934",size=10)
    ax.set(xlim=(-.5,8.55),ylim=(-.5,8.55),aspect="equal")
    ax.set_axis_off()


def draw(output,crawler,regions,cover,exemplars):
    fig,axes=page("An oriented turn in open space","Three occupied blocks · same 6 × 6 circuit, opposite directions",2)
    for sign,ax in zip((1,-1),axes):
        base(ax)
        polygon(ax,Polygon(TARGET),"#a5d5b3","none",z=2,alpha=.38)
        path=exemplars[sign]
        incoming,chosen,_,options=at_junction(path)[0]
        for movement,track_id in zip(zip(path["points"],path["points"][1:]),path["tracks"]):
            track=crawler.tracks[track_id]
            arrow(ax,*map(xy,movement),"#225b86" if track.wall else ORANGE,dashed=not track.wall)
        for j,state in enumerate((incoming,chosen)):
            track=crawler.tracks[state[0]]
            face=crawler.faces[track.face]
            a,b=map(xy,(face.a,face.b))
            mid=tuple((p+q)/2 for p,q in zip(a,b))
            nx,ny=map(float,(-float(face.b[1]-face.a[1]),float(face.b[0]-face.a[0])))
            mag=(nx*nx+ny*ny)**.5
            target=(mid[0]+.78*nx/mag,mid[1]+.78*ny/mag)
            arrow(ax,mid,target,"#0b6844")
            label(ax,target,face.blocks[0]+" normal","#0b6844",offset=(-25,4),size=7)
        wrong=next(s for s,status in options if s[0]==chosen[0] and status=="away_from_originating_face")
        arrow(ax,*map(xy,wrong[1:]),"#a33142",dashed=True)
        ax.scatter(6,6,c="#f1b26c",edgecolors="#854317",s=45,zorder=10)
        label(ax,(6,6),"J (6,6)","#783711",offset=(5,-11))
        ax.set_title("Right hand · left turn" if sign==1 else "Left hand · right turn",loc="left")
    foot(fig,"Blue physical travel · Orange extensions · Green outward normals · Dashed red rejected outgoing direction")
    p1=output/"01_mirrored_open_space_turns.pdf"
    plot_pdf(p1,[fig])

    fig,(a,b)=page("Exact three-block coverage","Closed polygons and their validation-only overlap overlay",2)
    for ax in (a,b):
        base(ax)
    for shape in regions:
        polygon(a,Polygon([xy(p) for p in shape]),"#2d9366","#1c6b52",.55,z=2,alpha=.19)
    maximum=max(f["multiplicity"] for f in cover["faces"])
    coll=PolyCollection([list(map(xy,f["vertices"])) for f in cover["faces"]],cmap="Blues",
                        norm=BoundaryNorm([n-.5 for n in range(maximum+2)],256),zorder=2,edgecolors="none")
    coll.set_array([f["multiplicity"] for f in cover["faces"]])
    b.add_collection(coll)
    fig.colorbar(coll,ax=b,fraction=.035,pad=.02,ticks=range(1,maximum+1),label="Exact overlap count")
    a.set_title(f"{len(regions)} distinct closed convex polygons",loc="left")
    b.set_title("Exact area 49/49 · zero uncovered",loc="left")
    foot(fig,"All vertices and junction events in the companion JSON")
    p2=output/"02_full_coverage.pdf"
    plot_pdf(p2,[fig])
    atlas=output/"oriented_extension_turns_atlas.pdf"
    combine(atlas,[("Open-space turns",p1),("Coverage",p2)])
    with pymupdf.open(atlas) as pdf:
        if len(pdf)!=2 or any(p.get_images() for p in pdf):
            raise ValueError("Atlas is not a two-page vector PDF.")


def serialize(crawler, regions, rejects, cover):
    def track_event(s):
        i,a,b=s
        t=crawler.tracks[i]
        return {"track":i,"segment":packed((a,b)),"face":t.face,"wall":t.wall,
                "towards_origin":None if t.wall else t.direction(a,b)<0}
    def transition(item,sign):
        incoming,chosen,status,options=item
        return {"incoming":track_event(incoming),"chosen":track_event(chosen),"status":status,
                "outgoing":[track_event(c)|{"status":reason,"handed_cross":str(sign*_cross(
                         _direction(*incoming[1:]),_direction(*c[1:]))),
                         "arrives_with_correct_hand":None if crawler.tracks[c[0]].wall
                         else crawler.tracks[c[0]].away_sign==-sign}
                         for c,reason in options]}
    summary=[]
    for v,paths in regions.items():
        summary.append({"vertices":packed(v),"paths":[p|{
            "transitions":[transition(t,p["sign"]) for t in p["transitions"]]} for p in paths]})
    return {"faces":[f.record() for f in crawler.faces],"tracks":[{"id":t.id,"face":t.face,
        "endpoints":packed((t.a,t.b)),"wall":t.wall,
        "towards_physical_origin":packed((t.b,t.a)) if not t.wall else None,
        "towards_admissible_hand":("right" if t.away_sign==-1 else "left") if not t.wall else None}
        for t in crawler.tracks],"regions":summary,"rejections":rejects,"coverage":cover,
        "branch_junctions":[{"sign":sign,"path_prefix":[track_event(t) for t in route],
                            "alternatives":[track_event(t)|{"status":status,"admissible":status in ADMISSIBLE}
                                            for t,status in options]}
                            for sign,route,options in crawler.branch_log]}


def main(output):
    l,room,room_rejections,lc,crawler,regions,rejections,cover,ex=check_references()
    output.mkdir(parents=True,exist_ok=False)
    draw(output,crawler,regions,cover,ex)
    (output/"exact-fixtures.json").write_bytes(encode({
        "room":serialize(l,room,room_rejections,lc),
        "three_blocks":serialize(crawler,regions,rejections,cover),
        "open_space_junction":packed([JUNCTION])[0],
        "crawler_sha256":sha256_file(Path(__file__).with_name("oriented_extension_turns.py"))}))
    print(f"L room {len(room)} rectangles; three-block fixture {len(regions)} convex polygons, "
          f"cover {cover['covered_area']}/{cover['domain_area']}.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    main(p.parse_args().output)
