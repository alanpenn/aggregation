from dataclasses import replace
from fractions import Fraction as F

from shapely.geometry import box, LineString

from voronoi_app.exact_axial import ExactCandidate, ExactCandidateSet
from voronoi_app.exact_enumeration import exact_pool_to_dict
from voronoi_app.sheaf_experiment import DEFAULTS, Experiment, detect_sheaves, interval


def make_line(i, a, b):
    a, b = tuple(map(F, a)), tuple(map(F, b))
    return ExactCandidate(i, a, b, a, b, "fixture")


def test_overlapping_sheaf_uses_external_connections_and_rejects_different_corridor():
    lines = [
        LineString([(0, 1), (10, 1)]),
        LineString([(1, 2), (9, 2)]),
        LineString([(0, 7), (10, 7)]),
        LineString([(4, 0), (4, 4)]),
        LineString([(6, 0), (6, 4)]),
    ]
    neighbors = [{3, 4}, {3, 4}, set(), {0, 1}, {0, 1}]
    settings = DEFAULTS | {"minimum_line_length": 5}
    masks = [3, 3, 4, 7, 7]
    groups, pairs = detect_sheaves(set(range(5)), lines, masks, neighbors, settings)
    assert groups == [[0, 1]]
    assert pairs[0, 1][3:] == [1, 1]
    assert detect_sheaves(set(reversed(range(5))), lines, masks, neighbors, settings)[0] == groups


def fixture(order):
    polygons = {r * 7 + c: box(c, r, c + 1, r + 1) for r in range(7) for c in range(7)}
    lines = [
        make_line(0, (0, 2), (7, 2)),
        make_line(1, (1, F(3, 2)), (6, F(3, 2))),
        make_line(2, (2, 0), (2, 7)),
        make_line(3, (5, 0), (5, 7)),
        make_line(4, (0, 5), (7, 5)),
        make_line(5, (5, 1), (F(13, 2), 1)),
        make_line(6, (F(13, 2), F(1, 2)), (F(13, 2), F(5, 4))),
    ]
    ids = {old: new for new, old in enumerate(order)}
    candidates = [replace(lines[old], line_id=i) for i, old in enumerate(order)]
    pool = ExactCandidateSet(candidates, [set()] * len(lines), set(), [], set())
    inputs = {
        "settlement": {"polygons_wkb": {str(i): p.wkb_hex for i, p in polygons.items()},
                       "dyad_open_cells": [], "building_labels": {"24": 1}},
        "topology": {"topology": {}},
        "candidates": {"pool": exact_pool_to_dict(pool), "regions_wkb": {}},
        "selection": {"line_ids": list(range(len(lines)))},
        "measures": {"entrances": [
            {"point": ["2", "6"], "connectors": [{"line": ids[2], "point": ["2", "6"]}]},
            {"point": ["5", "6"], "connectors": [{"line": ids[3], "point": ["5", "6"]}]},
        ]},
    }
    experiment = Experiment(inputs, DEFAULTS | {"minimum_line_length": 4})
    return experiment, {old: experiment.original_ids.index(new) for old, new in ids.items()}


def test_alternative_representatives_keep_ring_and_essential_external_connection():
    experiment, ids = fixture(list(range(7)))
    assert experiment.validate(experiment.selected)["status"] == "valid"
    assert experiment.validate(experiment.selected - {ids[0], ids[1]})["status"] == "circulation"
    assert experiment.validate(experiment.selected - {ids[5]})["status"] == "connectivity"
    assert experiment.validate(experiment.selected - {ids[0]})["status"] == "valid"
    assert experiment.validate(experiment.selected - {ids[1]})["status"] == "valid"
    experiment.groups = [[ids[0], ids[1]]]
    chosen, trace = experiment.group_search(experiment.selected)
    assert experiment.selected - chosen == {ids[0]}
    assert trace[0]["tested"] == 4 and trace[0]["exhaustive"]
    original = experiment.selected - {ids[1]}
    replacement, exchanges = experiment.exchanges(original)
    assert replacement == (original - {ids[0]}) | {ids[1]}
    assert exchanges[0]["added"] == [ids[1]]


def test_canonical_reduction_ignores_source_enumeration():
    forward, _ = fixture(list(range(7)))
    reverse, _ = fixture(list(reversed(range(7))))
    for order in ("geometry", "shortest", "longest"):
        selected_a, _ = forward.backward(forward.selected, order)
        selected_b, _ = reverse.backward(reverse.selected, order)
        assert [interval(forward.lines[i]) for i in sorted(selected_a)] == [
            interval(reverse.lines[i]) for i in sorted(selected_b)
        ]


def test_cached_geometry_agrees_with_original_exact_validation():
    experiment, ids = fixture(list(range(7)))
    for selected in (
        experiment.selected,
        experiment.selected - {ids[0]},
        experiment.selected - {ids[0], ids[1]},
    ):
        cached = experiment.geometry(selected)
        original = experiment.geometry(selected, witness=True)
        for key in ("independent_circulation_rank", "required_circulation_rank",
                    "bounded_axial_faces", "lines_crossing_effective_occupied_space",
                    "missing_axial_rings"):
            assert cached[key] == original[key]
