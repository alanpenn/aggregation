"""Small geometry gate for external-wall committed walks."""
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from experiments.directed_boundary_reference import L_ROOM
from experiments.flat40_committed_replay import NEW_BLOCKS, NEW_DOMAIN
from experiments.oriented_extension_reference import BLOCKS, DOMAIN


def room(blocks, boundary=None):
    frame=box(0,0,10,10) if boundary is None else boundary
    return frame.difference(unary_union(list(blocks.values()))),blocks


def fixtures():
    yield "empty_rectangle",box(0,0,10,6),{}
    yield "L_room",L_ROOM,{}
    yield "three_blocks",DOMAIN,BLOCKS
    yield "four_blocks",NEW_DOMAIN,NEW_BLOCKS
    yield "enclosed_island",*room({"I":box(3,3,6,6)})
    yield "multiple_islands",*room({"I":box(2,2,4,4),"J":box(6,5,8,7)})
    yield "narrow_passage",*room({"I":box(1,4,6,6),"J":box(7,4,9,6)})
    yield "T_junction",Polygon([(0,4),(4,4),(4,0),(6,0),(6,4),(10,4),(10,6),(0,6)]),{}
    yield "four_way",Polygon([(4,0),(6,0),(6,4),(10,4),(10,6),(6,6),(6,10),(4,10),(4,6),(0,6),(0,4),(4,4)]),{}
    yield "vertex_contact",*room({"I":box(2,2,4,4),"J":box(4,4,6,6)})
    yield "complete_face_contact",*room({"I":box(2,2,4,4),"J":box(4,2,7,4)})
    yield "near_external_wall",*room({"I":box(.25,2,4,6)})
    yield "concave_external",*room({"I":box(1,1,2,3)},Polygon([(0,0),(8,0),(8,4),(4,4),(4,8),(0,8)]))
    # Slanted exposed edges cross in the interior of the common free component.
    yield "slanted_competing_branches",*room({
        "I":Polygon([(0,0),(4,0),(2,2)]),
        "J":Polygon([(8,0),(10,0),(10,4),(8,3)]),
        "K":Polygon([(2,10),(5,10),(4,8)])})


def certify(domain, blocks):
    from collections import Counter
    from experiments.external_committed_crawler import ExternalCommittedCrawler
    from experiments.flat40_convex_enlargement import Checker
    from experiments.flat40_directed_boundary import exact_coverage
    from experiments.flat40_enlarged_cover import blocked_facets
    from experiments.flat40_region257_inspection import packed
    from experiments.oriented_extension_turns import ADMISSIBLE

    crawler = ExternalCommittedCrawler(domain, blocks.items())
    checker = Checker(domain, blocks)
    polygons, rejected = crawler.construct(blocks)
    for polygon in polygons:
        if not checker.witness([], polygon, independent=True):
            raise ValueError("Invalid reference polygon.")
    proofs = {p: blocked_facets(checker, p) for p in polygons}
    overlay = exact_coverage(domain, [p for p, proof in proofs.items() if proof])
    if not overlay["full_coverage"] or any(not proof for proof in proofs.values()):
        raise ValueError("The fixture requires complete coverage by certified maximal polygons.")
    origins = Counter(hand for hand, _ in crawler.starts())
    mixed = []
    for point, states in crawler.outgoing.items():
        origins_here = {crawler.tracks[i].face for i, _, _ in states if not crawler.tracks[i].wall}
        if origins_here & crawler.external and origins_here - crawler.external:
            mixed.append({"point": packed((point,))[0], "faces": sorted(origins_here)})
    mixed_turns = set()
    for paths in polygons.values():
        for path in paths:
            for before, after, action, _ in path["transitions"]:
                incoming, outgoing = crawler.tracks[before[0]], crawler.tracks[after[0]]
                if (action == "turn_towards_originating_face" and not incoming.wall
                        and (incoming.face in crawler.external) != (outgoing.face in crawler.external)):
                    mixed_turns.add((path["sign"], incoming.face, outgoing.face, before[2]))
    return polygons, {
        "old_and_new_branches_exhausted": True, "origins": dict(origins),
        "physical_faces": [f.record() for f in crawler.faces], "external_faces": sorted(crawler.external),
        "mixed_extension_intersections": mixed,
        "mixed_completed_turns": [{"hand": h, "from_face": a, "to_face": b, "point": packed((p,))[0]}
                                  for h,a,b,p in sorted(mixed_turns)],
        "branching_prefixes": sum(sum(s in ADMISSIBLE for _,s in options) > 1
                                  for _,_,options in crawler.branch_log),
        "rejections": rejected, "coverage": overlay,
        "regions": [{"vertices": packed(p), "facet_certificate": proofs[p],
                     "hands": dict(Counter(path["sign"] for path in paths))}
                    for p, paths in polygons.items()],
    }


def main():
    import argparse
    from pathlib import Path
    from voronoi_app.batch_store import atomic_write, encode

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = {name: certify(domain, blocks)[1] for name, domain, blocks in fixtures()}
    if {r["hand"] for r in data["concave_external"]["mixed_completed_turns"]} != {-1, 1}:
        raise ValueError("Missing mixed building/external extension regression.")
    atomic_write(args.output, encode(data))
    print({name: len(row["regions"]) for name, row in data.items()})


if __name__ == "__main__":
    main()
