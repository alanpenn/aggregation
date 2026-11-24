"""Opt-in reproduction against the immutable corrected settlement archive."""
import os
from pathlib import Path

import networkx as nx
import pytest

from voronoi_app.complementary_axial import ComplementaryStudy

ROOT = Path("diagnostics/strict-generalisation")
CASES = ("flat-40", "flat-41", "hill-40", "ridge-40", "shoulder-40", "twin_peaks-40", "converging_valleys-40")


@pytest.mark.parametrize("case", CASES)
def test_archived_complementary_reproduction(case):
    if not os.environ.get("VORONOI_ARCHIVE_TESTS"):
        pytest.skip("Set VORONOI_ARCHIVE_TESTS=1 with the restored benchmark records.")
    from experiments.constructive_axial import load
    from experiments.occupied_vertex_pruning import read

    inputs, source, _ = load(case)
    path = ROOT / "cross-terrain-constructive-1" / case
    archived = read(path / "structural.json")
    assert archived["source"] == source
    measures = read(ROOT / "constructive-axial-3" / case / "geometry.json")["candidates"]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(measures)))
    graph.add_edges_from((row["id"], i) for row in measures for i in row["intersections"])
    study = ComplementaryStudy(inputs, graph=graph, measures=measures)
    prepared = study.prepare()
    assert prepared.failure is None
    assert list(prepared.stages["complementary"]) == archived["complementary_raw"]
    assert list(prepared.stages["completed"]) == archived["complementary_repaired"]
    if case == "flat-40":
        assert tuple(map(len, prepared.stages.values())) == (1534, 628, 629)
        assert prepared.repairs == [{"stage": "strict-region", "region": 233, "add": [1212]}]
    for method, order in (("C-S", "shortest"), ("C-H", "sheaf")):
        reduced = study.reduce_prepared(prepared, order)
        assert reduced.certified
        expected = archived["methods"][method]
        assert list(reduced.ids) == expected["direct_ids"]
        exchanged = study.improve(reduced, order, historical=True)
        assert list(exchanged.ids) == expected["ids"]
        assert exchanged.certified
        if case == "flat-40":
            assert len(exchanged.ids) == 34
            assert tuple(exchanged.summary[k] for k in ("regions", "doorways", "components", "rank")) == (292, 100, 1, 24)
            economical = study.improve(reduced, order)
            assert economical.certified
            assert study.exchange_key(economical.ids) <= study.exchange_key(reduced.ids)
            if order == "sheaf":
                import numpy as np
                movement = study.movement(exchanged)
                prior = read(path / "movement.json")["methods"][method]
                assert movement["valid"]
                for cost in ("angular", "metric"):
                    np.testing.assert_allclose(movement[f"{cost}_routes"], prior[f"{cost}_routes"],
                                               atol=1e-9, rtol=0)
