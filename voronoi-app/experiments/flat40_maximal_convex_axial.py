"""Controlled Flat 40 comparison with the archived and exhaustive convex covers."""
import argparse
from collections import Counter
from copy import copy
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys
from unittest.mock import patch

import networkx as nx
from shapely.strtree import STRtree

from experiments import cross_terrain_axial as benchmark
from experiments.controlled_preselection import metrics
from experiments.face_extension_cover import bounds, hull
from experiments.flat40_directed_boundary import exact_coverage
from experiments.flat40_exchange_atlas import Atlas
from experiments.flat40_face_extension import points
from experiments.flat40_region257_inspection import exact_area, packed, ring
from experiments.near_collinear_consolidation import CASE, verified_study
from experiments.occupied_vertex_pruning import read
from voronoi_app.batch_store import atomic_write, encode
from voronoi_app.region_incidence_angular import halfplanes, positive_interior
from voronoi_app.research_data import data_root, sha256_file


def save(out, name, value):
    atomic_write(out/f"{name}.json",encode(value))


def exact_incidence(lines, polygons):
    segments = [(line.start,line.end) for line in lines]
    tree = STRtree([bounds(seg) for seg in segments])
    by_region = {}
    by_candidate = {i:[] for i in range(len(lines))}
    for key, vertices in polygons.items():
        planes = halfplanes(vertices+vertices[:1])
        box = bounds((tuple(map(min,zip(*vertices))),tuple(map(max,zip(*vertices)))))
        hits = sorted(int(i) for i in tree.query(box) if positive_interior(*segments[i],planes))
        by_region[key] = hits
        for i in hits:
            by_candidate[i].append(key)
    return {"region_order":list(polygons),"by_region":by_region,"by_candidate":by_candidate,
            "zero":[k for k,v in by_region.items() if not v],
            "singleton":{k:v[0] for k,v in by_region.items() if len(v)==1},
            "region_candidate_count_distribution":dict(Counter(map(len,by_region.values()))),
            "candidate_region_count_distribution":dict(Counter(map(len,by_candidate.values())))}


def variant(study, matrix):
    adapted = copy(study)
    adapted.regions = {i:frozenset(matrix["by_region"][k])
                       for i,k in enumerate(matrix["region_order"])}
    adapted.cover = [set() for _ in study.lines]
    for i, members in adapted.regions.items():
        for j in members:
            adapted.cover[j].add(i)
    adapted.incidence = list(adapted.regions.values()) + study.doors
    adapted.by_line = [set() for _ in study.lines]
    for i, members in enumerate(adapted.incidence):
        for j in members:
            adapted.by_line[j].add(i)
    adapted.sheaf = [set() for _ in study.lines]
    adapted.geometric = [{} for _ in study.lines]
    adapted.counts, adapted.timings = Counter(),Counter()
    return adapted


def reduce(study, cover, out, expected=None):
    class FixedDoorCompletion(benchmark.Selection):
        def __init__(self, *args):
            super().__init__(*args)
            self.regions,self.covers,self.doors = study.regions,study.cover,study.doors
            self.forced = {next(iter(g)) for g in [*self.regions.values(),*self.doors] if len(g)==1}

    raw, anchors, vertices, angles = benchmark.preselect(study)
    selected = set(raw)
    if expected is None:
        with patch.object(benchmark,"Selection",FixedDoorCompletion):
            repairs,error = benchmark.repair(study,selected)
    else:
        repairs,error = benchmark.repair(study,selected)
    if error:
        save(out,f"{cover}-failed-start",{"error":error,"repairs":repairs,"ids":sorted(selected)})
        raise ValueError(error)
    groups = benchmark.catalog(study,selected,anchors)
    start = {"raw":sorted(raw),"completed":sorted(selected),"repairs":repairs,"sheaves":groups,
             "vertices":vertices,"angles":angles,"certificate":study.confirmed(frozenset(selected))}
    save(out,f"{cover}-start",start)
    print(cover,"start",len(raw),len(selected),flush=True)
    results = {}
    for name, order in (("C-S","shortest"),("C-H","sheaf")):
        ids = set(selected)
        deletions = []
        study.counts.clear()
        study.timings.clear()
        checks = []
        original_validate = study.validate
        phase = "direct"
        def logged_validate(current, removed, added, counts):
            status, delta = original_validate(current,removed,added,counts)
            checks.append([phase,sorted(removed),sorted(added),status])
            return status, delta
        with patch.object(study,"validate",logged_validate):
            blockers = study.reduce(ids,order,deletions)
            direct = sorted(ids)
            phase = "exchange_and_cleanup"
            exchanges = study.exchange(ids,order)
        save(out,f"{cover}-{name}-decisions",{
            "row_fields":["phase","removed","added","decision"],"proposals":checks})
        result = {"ids":sorted(ids),"direct":direct,"deletions":deletions,"direct_blockers":blockers,
                  "exchanges":exchanges,"certificate":study.confirmed(frozenset(ids)),
                  "metrics":metrics(study,ids),"validation_counts":dict(study.counts)}
        save(out,f"{cover}-{name}",result)
        print(cover,name,len(ids),flush=True)
        if expected is not None and (result["ids"] != expected[name]["ids"]
                                     or direct != expected[name]["direct_ids"]):
            raise ValueError(f"Archived {name} baseline did not reproduce.")
        results[name] = result
    return results


def load_experiment(manifest, source):
    study,ch,d,provenance = verified_study(manifest)
    atlas = Atlas(study,ch)
    inventory = read(source/"regions.json")
    progress = read(source/"progress.json")
    coverage = read(source/"coverage-maximal.json")
    if not inventory["exhaustive"] or any(p["pending_stack_entries"] or p["pending_faces"] for p in progress.values()):
        raise ValueError("The source region enumeration is incomplete.")
    old = {i:hull(ring(p)[:-1]) for i,p in sorted(atlas.regions.items())}
    new = {}
    for k,v in sorted(inventory["regions"].items()):
        shape = tuple(points(v))
        if sha256(encode(packed(shape))).hexdigest()!=k or shape!=hull(shape) or v["maximality"]["status"]!="proved_global":
            raise ValueError(f"Invalid certified maximal region {k}")
        new[k] = shape
    if (len(old),len(new),len(study.lines)) != (292,596,1534):
        raise ValueError("Unexpected frozen counts.")
    if not coverage["full_coverage"] or Fraction(coverage["uncovered_area"]):
        raise ValueError("Missing exact source coverage certificate.")
    provenance["cover_files"] = {n:sha256_file(source/n) for n in (
        "regions.json","coverage-maximal.json","progress.json","geometry.json","checkpoint-audit.json")}
    provenance["candidate_pool_sha256"] = sha256(encode(study.inputs["candidates"]["pool"])).hexdigest()
    provenance["archived_convex_regions_sha256"] = sha256(encode(study.inputs["candidates"]["regions_wkb"])).hexdigest()
    return study,atlas,old,new,provenance


def main():
    sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","source","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    a = parser.parse_args()
    study,atlas,old,new,provenance = load_experiment(a.manifest,a.source)
    a.output.mkdir(parents=True,exist_ok=False)
    archive = {}
    inventory = read(a.manifest)
    for name in ("C-H","C-S","movement","structural"):
        p = benchmark.DEST/CASE/f"{name}.json"
        relative = p.relative_to(data_root()).as_posix()
        checksum = sha256_file(p)
        if inventory.get(relative)!=checksum:
            raise ValueError(f"Unverified archived reference {relative}")
        archive[name] = read(p)
        provenance["verified_inputs"][relative] = checksum
    sources = ("cross_terrain_axial.py","controlled_preselection.py","unrestricted_axial_reduction.py",
               "constructive_axial.py","dynamic_winding.py",Path(__file__).name)
    save(a.output,"configuration",{
        "archived":read(benchmark.DEST/"protocol.json"),
        "current_source_sha256":{n:sha256_file(Path(__file__).with_name(n)) for n in sources},
        "current_exchange_budget":benchmark.BUDGET,"current_exchange_rounds":benchmark.ROUNDS,
        "current_sheaf_settings":benchmark.SETTINGS,"frozen_doorway_count":len(study.doors),
        "fixed_movement_incidence":"Archived doorway entrances and exact metric stops for every map",
        "line_count_controls":{"Algorithm D":len(archive["structural"]["methods"]["D"]["ids"]),
                               "strict_backward":len(study.inputs["analysis"]["maps"]["strict_backward"]["line_ids"])}})
    save(a.output,"provenance",provenance)
    exact = exact_coverage(atlas.domain,list(new.values()))
    saved = read(a.source/"coverage-maximal.json")
    if not exact["full_coverage"] or any(Fraction(exact["area_by_count"].get(str(i),0)) !=
            Fraction(saved["area_by_count"].get(str(i),0)) for i in range(40)):
        raise ValueError("Independent exact cover overlay differs.")
    save(a.output,"maximal-cover-check",{k:v for k,v in exact.items() if k!="faces"})
    matrix_a = exact_incidence(study.lines,old)
    matrix_b = exact_incidence(study.lines,new)
    for key,matrix in (("A",matrix_a),("B",matrix_b)):
        save(a.output,f"incidence-{key}",matrix)
        print("incidence",key,len(matrix["zero"]),len(matrix["singleton"]),flush=True)
    if any(set(v)!=study.regions[int(k)] for k,v in matrix_a["by_region"].items()):
        raise ValueError("Recalculated archived incidence does not match frozen selector inputs.")
    reduce(study,"A",a.output,expected=archive)
    if not matrix_b["zero"]:
        reduce(variant(study,matrix_b),"B",a.output)
    else:
        save(a.output,"B-infeasible",{"zero_candidate_regions":matrix_b["zero"],
                                     "reason":"Frozen pool cannot satisfy strict incidence."})


if __name__=="__main__":
    main()
