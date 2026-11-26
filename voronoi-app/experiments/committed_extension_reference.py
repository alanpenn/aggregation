"""Exact premature-turn and committed-approach fixtures."""
import argparse
from fractions import Fraction as F
from pathlib import Path

from shapely.affinity import scale
from shapely.geometry import Polygon
from shapely.ops import unary_union

from experiments.committed_extension_turns import CommittedCrawler
from experiments.face_extension_cover import hull
from experiments.flat40_committed_replay import FRAME, NEW_BLOCKS, PREMATURE, fixtures
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_exchange_atlas import combine, foot, label, page, plot_pdf, polygon, xy
from experiments.flat40_region257_inspection import packed
from experiments.oriented_extension_reference import arrow, serialize
from experiments.oriented_extension_turns import ExtensionCrawler
from voronoi_app.batch_store import encode


def example(sign):
    blocks=NEW_BLOCKS if sign==1 else {k:scale(v,xfact=-1,origin=(4,4)) for k,v in NEW_BLOCKS.items()}
    domain=FRAME.difference(unary_union(list(blocks.values())))
    small=PREMATURE if sign==1 else hull([(F(8-x),F(y)) for x,y in PREMATURE])
    baseline=ExtensionCrawler(domain,list(blocks.items()))
    old,reject_old=baseline.construct(blocks)
    crawler=CommittedCrawler(domain,list(blocks.items()))
    new,reject_new=crawler.construct(blocks)
    if small not in old or small in new:
        raise ValueError("Premature circuit was not removed.")
    for path in old[small]:
        if path["sign"]!=sign:
            continue
        for index,(a,b,event,_) in enumerate(path["transitions"]):
            prefix=[tuple(map(F,v)) for v in path["points"][:index+2]]
            if crawler.decision(a,b,sign,prefix)!="turn_prohibited_during_commitment":
                continue
            destination=crawler.tracks[a[0]].face
            previous=[t for t in path["transitions"][:index] if
                      t[2]=="turn_towards_originating_face" and t[1][0]==a[0]]
            if not previous:
                continue
            for shape,paths in new.items():
                for candidate in paths:
                    if candidate["sign"]!=sign:
                        continue
                    states=candidate["transitions"]
                    if (not any(k==a and status=="straight" for k,_,status,_ in states)
                        or not any(k==previous[-1][0] and j==previous[-1][1] and status==previous[-1][2]
                                   for k,j,status,_ in states)
                        or not any(crawler.tracks[k[0]].id==a[0] and k[2]==crawler.tracks[a[0]].a
                                   and status=="follow_physical_face" and crawler.tracks[j[0]].face==destination
                                   for k,j,status,_ in states)):
                        continue
                    return {"sign":sign,"blocks":blocks,"domain":domain,"small":small,"large":shape,
                            "old":path,"new":candidate,"incoming":a,"prohibited":b,
                            "accepted_turn":previous[-1],"destination":destination,
                            "crawler":crawler,"regions":new,"rejections":reject_new}
    raise ValueError("No matched successful committed suffix.")


def publish(out):
    fixtures()
    examples=[example(sign) for sign in (1,-1)]
    out.mkdir(parents=True,exist_ok=False)
    sources=[]
    for n,record in enumerate(examples,1):
        sign=record["sign"]
        crawler=record["crawler"]
        fig,axes=page("Commitment to an originating occupied face",
                      "Right-hand example" if sign==1 else "Mirrored left-hand example",2)
        for ax,shape,path in zip(axes,(record["small"],record["large"]),(record["old"],record["new"])):
            polygon(ax,record["domain"],"#f1f4ef","#52665b")
            for k,g in record["blocks"].items():
                polygon(ax,g,"#303840","#25313b")
                label(ax,g.representative_point().coords[0],k,"#29363c",size=9)
            polygon(ax,Polygon([xy(p) for p in shape]),"#88bfa1","#327c56",.9,z=2,alpha=.36)
            for a,b,i in zip(path["points"],path["points"][1:],path["tracks"]):
                t=crawler.tracks[i]
                arrow(ax,xy(a),xy(b),"#287095" if t.wall else "#ad5c2b",dashed=not t.wall)
            f=crawler.faces[record["destination"]]
            a,b=xy(f.a),xy(f.b)
            ax.plot(*zip(a,b),c="#08754e",lw=3,zorder=9)
            point=xy(record["incoming"][2])
            ax.scatter(*point,s=30,c="#bd2e44",zorder=10)
            label(ax,point,"Prohibited turn" if ax is axes[0] else "Continue straight",
                  "#9d2540",offset=(5,-12),size=7)
            ax.set(xlim=(-.4,8.5),ylim=(-.4,8.4),aspect="equal")
            ax.set_axis_off()
        axes[0].set_title("Earlier rule · premature closure",loc="left")
        axes[1].set_title("Committed rule · contact the generating face",loc="left")
        foot(fig,"Solid blue physical travel · Dashed orange extension · Green destination face")
        path=out/f"{n:02d}.pdf"
        plot_pdf(path,[fig])
        sources.append(("Right-hand witness" if sign==1 else "Left-hand witness",path))
    combine(out/"committed_reference_atlas.pdf",sources)
    records=[]
    for r in examples:
        c=r["crawler"]
        validation=exact_coverage(r["domain"],r["regions"])
        data=serialize(c,r["regions"],r["rejections"],validation)
        path=r["old"]
        data.update(sign=r["sign"],premature=packed(r["small"]),result=packed(r["large"]),
                    destination_face=r["destination"],prohibited_at=packed([r["incoming"][2]])[0],
                    old_premature_walk={"points":path["points"],"tracks":path["tracks"]})
        records.append(data)
    (out/"exact-fixtures.json").write_bytes(encode({"examples":records}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    publish(p.parse_args().output)
