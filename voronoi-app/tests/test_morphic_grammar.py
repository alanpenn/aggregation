import pytest

from voronoi_app.analysis import ConnectivityMeasure, MeanDepthMeasure
from voronoi_app.axial import AxialLine, AxialMap
from voronoi_app.core import Representation
from voronoi_app.grammar import MorphicGrammar, MorphicRule
from voronoi_app.orchestrator import ExperimentOrchestrator
from shapely.geometry import Polygon, box


def test_axial_map_builds_intersection_graph_and_attributes():
    axial_map = AxialMap(lines=[
        AxialLine(10, (0, 0), (4, 4)),
        AxialLine(20, (0, 4), (4, 0)),
        AxialLine(30, (5, 0), (5, 4)),
    ])

    representation = axial_map.to_representation()

    assert representation.name == "axial_map"
    assert representation.nodes == [10, 20, 30]
    assert representation.edges == [(10, 20)]
    assert representation.node_attributes[10]["symbol"] == "axial_line"
    assert representation.node_attributes[10]["length"] == pytest.approx(4 * 2 ** 0.5)


def test_axial_map_preserves_symbols_and_recognizes_endpoint_intersections():
    axial_map = AxialMap(lines=[
        AxialLine(1, (0, 0), (1, 0), {"symbol": "street"}),
        AxialLine(2, (1, 0), (1, 1)),
    ])

    representation = axial_map.to_representation()

    assert representation.edges == [(1, 2)]
    assert representation.node_attributes[1]["symbol"] == "street"


def test_axial_map_representation_works_with_configurational_measures():
    representation = AxialMap(lines=[
        AxialLine(1, (0, 0), (2, 0)),
        AxialLine(2, (1, -1), (1, 3)),
        AxialLine(3, (0, 2), (2, 2)),
    ]).to_representation()

    assert representation.edges == [(1, 2), (2, 3)]
    assert ConnectivityMeasure().compute(representation) == {1: 1.0, 2: 2.0, 3: 1.0}
    assert MeanDepthMeasure().compute(representation) == {1: 1.5, 2: 1.0, 3: 1.5}
    assert "axial_map" in MeanDepthMeasure().supported_representations


def test_axial_line_and_map_reject_invalid_geometry():
    with pytest.raises(ValueError, match="non-zero length"):
        AxialLine(1, (2, 2), (2, 2))
    with pytest.raises(ValueError, match="unique"):
        AxialMap([AxialLine(1, (0, 0), (1, 0)), AxialLine(1, (0, 1), (1, 1))])


def test_sightline_selection_returns_clear_segment_and_rejects_building_blockage():
    left = box(0, 0, 1, 1)
    right = box(3, 0, 4, 1)

    clear_line = ExperimentOrchestrator._find_space_sightline(left, right, None)
    blocked_line = ExperimentOrchestrator._find_space_sightline(
        left, right, box(1.0, -10, 3.0, 10)
    )

    assert clear_line is not None
    assert clear_line.length > 0
    assert blocked_line is None


def test_morphic_grammar_rewrites_graph_and_preserves_external_adjacency():
    initial = Representation(
        name="axial_map",
        nodes=[1, 2],
        edges=[(1, 2)],
        node_attributes={
            1: {"symbol": "A", "length": 5.0},
            2: {"symbol": "terminal"},
        },
        metadata={"type": "axial_map"},
    )
    grammar = MorphicGrammar([
        MorphicRule(
            name="split-a",
            match_symbol="A",
            replacement_symbols=("B", "C"),
            replacement_edges=((0, 1),),
            attachment_index=1,
        )
    ])

    result = grammar.evaluate(initial)

    assert result.converged
    assert result.final.nodes == [3, 4, 2]
    assert result.final.edges == [(2, 4), (3, 4)]
    assert result.final.node_attributes[3]["symbol"] == "B"
    assert result.final.node_attributes[4]["grammar_parent"] == 1
    assert result.final.node_attributes[4]["length"] == 5.0
    assert result.trace[0].matches == [(1, "split-a")]


def test_morphic_grammar_runs_synchronous_deterministic_generations():
    initial = Representation(
        name="axial_map",
        nodes=[0],
        edges=[],
        node_attributes={0: {"symbol": "A"}},
    )
    grammar = MorphicGrammar([
        MorphicRule("a-to-b", "A", ("B",)),
        MorphicRule("b-to-c", "B", ("C",)),
    ])

    first = grammar.evaluate(initial)
    second = grammar.evaluate(initial)

    assert first.converged
    assert len(first.trace) == 2
    assert first.final.nodes == second.final.nodes
    assert first.final.node_attributes == second.final.node_attributes
    assert first.final.node_attributes[2]["symbol"] == "C"


def test_recursive_rule_reports_iteration_limit_and_validates_limit():
    initial = Representation(
        name="axial_map",
        nodes=[0],
        edges=[],
        node_attributes={0: {"symbol": "A"}},
    )
    grammar = MorphicGrammar([MorphicRule("repeat-a", "A", ("A",))])

    result = grammar.evaluate(initial, max_iterations=2)

    assert not result.converged
    assert len(result.trace) == 2
    with pytest.raises(ValueError, match="non-negative"):
        grammar.evaluate(initial, max_iterations=-1)
