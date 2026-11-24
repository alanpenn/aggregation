"""Frozen cross-terrain benchmark over recoverable corrected archival records."""
import argparse
from collections import Counter
from functools import cache
from fractions import Fraction
from hashlib import sha256
from itertools import combinations
from pathlib import Path
import platform
import tarfile
from time import monotonic

import networkx as nx
from shapely.geometry import LineString

from experiments.constructive_axial import ROOT as D_ARCHIVE, PARAMETERS, Selection, construct, local_geometry, rankings, load
from experiments.cross_terrain_axial_routes import evaluate_active_union
from experiments.controlled_preselection import Study, MatchedWinding, check, metrics
from experiments.dynamic_winding import CycleSignatures
from experiments.facewise_rerun import ROOT as FACEWISE
from experiments.extended_terrain import ROOT as EXTENDED
from experiments.occupied_vertex_pruning import boundary_index, read
from experiments.strict_generalisation import rss_mib
from experiments.unrestricted_axial_reduction import BUDGET, ROUNDS
from experiments.vertex_connectivity_complements import axial_angle
from voronoi_app.angular import LineClearance, _direction
from voronoi_app.batch_methods import _domain, _settlement
from voronoi_app.batch_store import BatchStore, atomic_write, encode
from voronoi_app.exact_axial import candidate_graph
from voronoi_app.exact_enumeration import exact_pool_from_dict
from voronoi_app.experimental_visibility import IndexedClearance
from voronoi_app.sheaf_experiment import DEFAULTS, detect_sheaves
from voronoi_app.strict_coverage_experiment import incidence_sets
from voronoi_app.strict_generalisation import Geometry

DEST=EXTENDED.parent/"cross-terrain-constructive-1"
TERRAINS=("flat","hill","ridge","shoulder","twin_peaks","converging_valleys")
CASES=tuple(f"{terrain}-{seed}" for seed in range(40,46) for terrain in TERRAINS)
METHODS=("strict_backward","D","C-S","C-H")
SETTINGS=DEFAULTS|{"minimum_line_length":0.0}


def save(path, value):
    atomic_write(path,encode(value))


def origin(case):
    return FACEWISE if case.startswith(("hill-","converging_valleys-")) else EXTENDED


def capture_inputs(archive):
    DEST.mkdir(exist_ok=True)
    entries={}
    if archive.is_file():
        with tarfile.open(archive) as t:
            members={m.name:m for m in t if m.isfile()}
            for case in CASES:
                root=origin(case)
                journal_path=root/"cases"/f"{case}.json"
                journal=read(journal_path)
                restored={}
                checks={}
                source_path=D_ARCHIVE/case/"source.json"
                source=read(source_path) if source_path.exists() else {}
                missing=[]
                for stage,value in journal["stages"].items():
                    identifier=value["record"]
                    for basename,field in (("record.json","sha256"),("output.json","output")):
                        expected=source.get(stage,{}).get(field)
                        path=root/"records"/identifier/basename
                        member=members.get(path.as_posix())
                        if member is not None and expected:
                            data=t.extractfile(member).read()
                            digest=sha256(data).hexdigest()
                            if digest!=expected:
                                raise ValueError(f"Tar checksum mismatch for {path}")
                            checks[str(path)]=digest
                            if not path.exists():
                                path.parent.mkdir(parents=True,exist_ok=True)
                                with path.open("xb") as f:
                                    f.write(data)
                                restored[str(path)]=digest
                            elif sha256(path.read_bytes()).hexdigest()!=digest:
                                raise ValueError(f"Existing record differs from the verified tar: {path}")
                        if not path.is_file():
                            missing.append(str(path))
                publication=next(c for c in read(root/"visual-index.json")["cases"] if c["case"]==case)
                entries[case]={"root":str(root),"journal_sha256":sha256(journal_path.read_bytes()).hexdigest(),
                    "configuration":journal["configuration"],"records":journal["stages"],
                    "verified_tar_members":checks,"restored":restored,"missing":missing,
                    "published_strict":publication["methods"]["strict_backward"],
                    "published_full":publication["methods"]["full_pool"]}
    else:
        raise FileNotFoundError(archive)
    save(DEST/"inputs.json",entries)
    filenames=("constructive_axial.py","vertex_connectivity_complements.py","unrestricted_axial_reduction.py",
               "controlled_preselection.py","dynamic_winding.py","cross_terrain_axial.py")
    save(DEST/"protocol.json",{"cohort":CASES,"methods":METHODS,"D":PARAMETERS,"sheaves":SETTINGS,
        "pair_rule":"min(full degrees) times (1 + Jaccard distance) / 2; angle, degree sum, exact squared-length sum, ID",
        "repair":"For each currently uncovered strict region in ascending order add shortest certified line; then use existing bounded Selection.complete with archived D priorities when necessary",
        "catalog":"complete-link sheaves from the shared repaired complementary start, require different selected anchors, never depend on final maps",
        "exchange_budget":BUDGET,"exchange_rounds":ROUNDS,
        "source_sha256":{f:sha256(Path(__file__).with_name(f).read_bytes()).hexdigest() for f in filenames},
        "machine":platform.platform(),"processor":platform.machine(),
        "execution":"one subprocess per case; two C methods in sequence; compare timings within case, D timings archived"})


class CaseStudy(Study):
    def __init__(self, case):
        self.inputs,self.source,self.reference=load(case)
        original_path=D_ARCHIVE/case/"source.json"
        if original_path.exists() and self.source!=read(original_path):
            raise ValueError("Archived constructive input lineage differs.")
        pool=exact_pool_from_dict(self.inputs["candidates"]["pool"])
        self.lines=pool.candidates
        gpath=D_ARCHIVE/case/"geometry.json"
        if gpath.exists():
            checksum=read(D_ARCHIVE/"export-checksums.json")[f"{case}/geometry.json"]
            if sha256(gpath.read_bytes()).hexdigest()!=checksum:
                raise ValueError("Saved candidate measures changed.")
            self.data=read(gpath)
        else:
            local=DEST/case/"geometry.json"
            if local.exists():
                self.data=read(local)
                if self.data["source"]!=self.source:
                    raise ValueError("Candidate geometry checkpoint has different inputs.")
            else:
                graph=candidate_graph(self.lines)
                started=monotonic()
                measures=local_geometry(self.lines,graph,*incidence_sets(self.inputs["analysis"]["incidence"]))
                self.data={"source":self.source,"candidates":measures,"rankings":rankings(measures),
                           "seconds":monotonic()-started}
                save(local,self.data)
        rows=self.data["candidates"]
        self.graph=nx.Graph()
        self.graph.add_nodes_from(range(len(self.lines)))
        self.graph.add_edges_from((r["id"],j) for r in rows for j in r["intersections"])
        self.neighbors=[set(self.graph[i]) for i in self.graph]
        self.transverse=[set(map(int,r["transverse"])) for r in rows]
        self.length=[line.length for line in self.lines]
        self.segments=[LineString([line.start,line.end]) for line in self.lines]
        self.regions,self.doors=incidence_sets(self.inputs["analysis"]["incidence"])
        self.incidence=list(self.regions.values())+self.doors
        self.cover=pool.covers
        if any(ids!={i for i,v in enumerate(self.cover) if r in v} for r,ids in self.regions.items()):
            raise ValueError("Strict incidence differs from certified pool.")
        self.by_line=[set() for _ in self.lines]
        for k,ids in enumerate(self.incidence):
            for i in ids:
                self.by_line[i].add(k)
        self.geometric=[{} for _ in self.lines]
        self.sheaf=[set() for _ in self.lines]
        _,occupied,accessible,obstacles=_domain(self.inputs)
        self.clearance=IndexedClearance(LineClearance(accessible,obstacles,original_obstacles=occupied.values()))
        self.geometry=Geometry(self.inputs,self.lines,self.graph,self.clearance)
        polygons,_,_=_settlement(self.inputs)
        self.polygons=polygons
        winding=CycleSignatures(self.lines,self.graph,polygons,self.geometry.blocks)
        self.winding=MatchedWinding(winding)
        self.counts=Counter()
        self.timings=Counter()

    @cache
    def confirmed(self, ids):
        return check(self,set(ids))


def preselect(study):
    labels={int(k):v for k,v in study.inputs["settlement"]["building_labels"].items()}
    vertices,support,_=boundary_index(study.inputs["topology"],study.polygons,labels,study.lines)
    directions=[_direction(line.start,line.end) for line in study.lines]
    lengths=[sum(x*x for x in d) for d in directions]
    retained=set(study.graph)-support.keys()
    anchors=[set() for _ in study.lines]
    pairs=[]
    def score(pair):
        i,j=pair
        a,b=study.neighbors[i],study.neighbors[j]
        distance=Fraction(len(a^b),len(a|b)) if a|b else Fraction(0)
        return min(len(a),len(b))*(1+distance)/2,axial_angle(directions[i],directions[j]),len(a)+len(b),lengths[i]+lengths[j],-i,-j
    for v in vertices:
        ids=v["supported"]
        chosen=max(combinations(sorted(ids),2),key=score) if len(ids)>1 else tuple(ids)
        for i in chosen:
            anchors[i].add(v["id"])
        retained.update(chosen)
        if len(chosen)==2:
            pairs.append(axial_angle(*(directions[i] for i in chosen)))
    return retained,anchors,vertices,pairs


def repair(study, selected):
    trace=[]
    for r,ids in sorted(study.regions.items()):
        if selected.isdisjoint(ids):
            candidate=min(ids,key=lambda i:(study.length[i],i))
            selected.add(candidate)
            trace.append({"stage":"strict-region","region":r,"add":[candidate]})
    rank=study.winding.rank(selected) if study.connected(selected) else None
    if rank!=study.winding.required or any(selected.isdisjoint(g) for g in study.doors):
        engine=Selection(study.inputs,study.lines,study.graph,study.data["candidates"],study.clearance)
        return trace,engine.complete(selected,study.data["rankings"]["D"],trace)
    return trace,None


def catalog(study, selected, anchors):
    masks=[sum(1<<x for x in r) for r in study.cover]
    groups,detail=detect_sheaves(selected,study.segments,masks,study.neighbors,SETTINGS)
    def across(i,j):
        return any(a!=b for a in anchors[i] for b in anchors[j])
    groups=[g for g in groups if any(across(i,j) for i,j in combinations(g,2))]
    for g in groups:
        for i in g:
            study.sheaf[i].update(set(g)-{i})
    for (i,j),(a,f,g,*_) in detail.items():
        if across(i,j):
            study.geometric[i][j]=study.geometric[j][i]=f/(1+a/21+g/3)
    return groups


def run(case, structural_only=False):
    path=DEST/case
    path.mkdir(exist_ok=True)
    if (path/"movement.json").exists():
        return
    loaded=monotonic()
    study=CaseStudy(case)
    loading_seconds=monotonic()-loaded
    provenance=read(DEST/"inputs.json")[case]
    if provenance["missing"]:
        raise ValueError("Missing exact input records.")
    archived_d_path=D_ARCHIVE/case/"D.json"
    archived_routes_path=D_ARCHIVE/case/"movement.json"
    archived_movement=read(archived_routes_path) if archived_routes_path.exists() else None
    if archived_d_path.exists():
        archive_d=read(archived_d_path)
        d_path=archived_d_path
    else:
        d_path=path/"D.json"
        if d_path.exists():
            archive_d=read(d_path)
            if archive_d["source"]!=study.source:
                raise ValueError("D checkpoint has different exact inputs.")
        else:
            selector=Selection(study.inputs,study.lines,study.graph,study.data["candidates"],study.clearance)
            archive_d=construct(selector,"D",study.data["rankings"]["D"])|{"source":study.source}
            save(d_path,archive_d)
    strict=study.inputs["analysis"]["maps"]["strict_backward"]["line_ids"]
    control_records={"strict_backward":{"ids":strict,"status":"certified_archive","start_count":len(study.lines),
                     "winding":study.confirmed(frozenset(strict)),"metrics":metrics(study,strict)}}
    if archive_d.get("maps"):
        ids=archive_d["maps"]["exchanged"]
        control_records["D"]={"ids":ids,"status":"independent_success","start_count":len(study.lines),
                   "winding":study.confirmed(frozenset(ids)),"metrics":metrics(study,ids),
                   "seconds":archive_d["seconds"],"peak_rss_mib":archive_d["peak_rss_mib"],
                   "deletions_checked":archive_d["deletions_checked"],"exchanges_checked":archive_d["exchanges_checked"],
                   "archive":str(d_path)}
    else:
        control_records["D"]={"ids":archive_d["partial"],"status":"search_budget_exhausted",
                   "deficiencies":archive_d["validation"],"seconds":archive_d["seconds"],
                   "reason":archive_d["error"],"archive":str(d_path)}
    if (path/"structural.json").exists():
        structure=read(path/"structural.json")
    else:
        started=monotonic()
        raw,anchors,vertices,angles=preselect(study)
        pre_seconds=monotonic()-started
        if any(not study.clear(i) for i in raw):
            raise ValueError("Archived certified complement interval failed clearance.")
        selected=set(raw)
        started=monotonic()
        repairs,error=repair(study,selected)
        repair_seconds=monotonic()-started
        records=control_records.copy()
        metadata={"source":study.source,"configuration":provenance["configuration"],
                  "loading_seconds":loading_seconds,"full_count":len(study.lines),
                  "full_ids":list(study.graph),"regions":len(study.regions),"doorways":len(study.doors),
                  "blocks":study.winding.required,"convex_vertices":len(vertices),"vertices":vertices,
                  "pair_angles_degrees":angles,"excluded_open":len(study.inputs["topology"]["topology"]["excluded_open_cells"]),
                  "complementary_raw":sorted(raw),"complementary_repaired":sorted(selected),
                  "repair_trace":repairs,"preselection_seconds":pre_seconds,"repair_seconds":repair_seconds}
        if error:
            failure=study.geometry.geometry(frozenset(selected))
            for name in ("C-S","C-H"):
                records[name]={"status":"search_budget_exhausted","reason":error,"ids":sorted(selected),
                               "winding":failure}
        else:
            metadata["complementary_winding"]=study.confirmed(frozenset(selected))
            started=monotonic()
            groups=catalog(study,selected,anchors)
            metadata.update(sheaves=groups,sheaf_seconds=monotonic()-started)
            for name,order in [("C-S","shortest"),("C-H","sheaf")]:
                checkpoint=path/f"{name}.json"
                if checkpoint.exists():
                    records[name]=read(checkpoint)
                    continue
                ids=set(selected); study.counts.clear(); study.timings.clear()
                deletions=[]
                started=monotonic()
                blockers=study.reduce(ids,order,deletions)
                direct_secs=monotonic()-started
                direct=sorted(ids)
                direct_w=study.confirmed(frozenset(ids))
                exchange_start=monotonic()
                exchanges=study.exchange(ids,order)
                exchange_seconds=monotonic()-exchange_start
                result={"ids":sorted(ids),"status":"independent_success","start_count":len(selected),
                        "direct_ids":direct,"direct_winding":direct_w,"winding":study.confirmed(frozenset(ids)),
                        "metrics":metrics(study,ids),"deletion_seconds":direct_secs,"exchange_seconds":exchange_seconds,
                        "seconds":pre_seconds+repair_seconds+metadata["sheaf_seconds"]+direct_secs+exchange_seconds,
                        "peak_rss_mib":rss_mib(),"deletions":deletions,"direct_blockers":blockers,
                        "exchanges":exchanges,"validation_counts":dict(study.counts),"validation_seconds":dict(study.timings)}
                records[name]=result
                save(checkpoint,result)
                print(case,name,len(ids),flush=True)
        structure=metadata|{"methods":records}
        save(path/"structural.json",structure)
    if structural_only:
        return
    valid=structure["methods"]
    methods={name:{"maps":{"final":row["ids"]}} for name,row in valid.items()
             if name.startswith("C-") and row["status"]=="independent_success"}
    published={}
    if archived_movement is not None:
        published["strict_backward"]=archived_movement["baseline"]
        if control_records["D"]["status"]=="independent_success":
            published["D"]=archived_movement["methods"]["D"]["exchanged"]
    elif control_records["D"]["status"]=="independent_success":
        methods["D"]={"maps":{"final":control_records["D"]["ids"]}}
    if methods or archived_movement is None:
        new=evaluate_active_union(study.inputs,study.lines,study.clearance,study.reference,methods)
        published.setdefault("strict_backward",new["baseline"] | {"ids":strict})
        published.update({name:r["final"] for name,r in new["methods"].items()})
    else:
        new={"seconds":0,"peak_rss_mib":rss_mib()}
    save(path/"movement.json",{"source":study.source,"methods":published,"seconds":new["seconds"],
                 "active_graph_candidate_ids":new.get("active_graph_candidate_ids"),
                 "peak_rss_mib":new["peak_rss_mib"],
                 "reference_means":{k:sum(study.reference[k])/len(study.reference[k]) for k in ("angular","metric")}})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("inputs","case"))
    parser.add_argument("--case",choices=CASES)
    parser.add_argument("--archive",type=Path,default=Path.home()/"Downloads/voronoi-rerun-inputs.tar")
    parser.add_argument("--structural-only",action="store_true")
    args=parser.parse_args()
    if args.phase=="inputs":
        capture_inputs(args.archive)
    else:
        run(args.case,args.structural_only)


if __name__=="__main__":
    main()
