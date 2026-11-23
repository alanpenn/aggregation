import pytest
from scipy.spatial import Voronoi
from shapely.geometry import box

from experiments.audit_facewise_growth import prefix_audit, ridge_length
from voronoi_app.aggregation import FacewiseSlopePreferenceStrategy, SlopePreferenceStrategy
from voronoi_app.core import ExperimentPipeline, Grid, UrbanFormComposition
from voronoi_app.experimental_circulation_topology import _contact_graph, _edge_graph
from voronoi_app.face_adjacency import face_adjacency
from voronoi_app.orchestrator import ExperimentOrchestrator


def test_facewise_growth_rejects_corner_adjacency_and_keeps_each_prefix_connected():
    polygons = {
        0: box(0, 0, 1, 1), 1: box(0, 1, 1, 2),
        2: box(1, 0, 2, 1), 3: box(2, 0, 3, 1),
        4: box(1, 1, 2, 2), 5: box(2, 1, 3, 2),
    }
    faces = _edge_graph(polygons, polygons)
    assert 4 not in faces[0]  # Corner only.
    assert 2 in faces[0]
    invalid = prefix_audit([(0, 1), (4, 5)], {"1": 1, "5": 2}, [None, 0], polygons)
    assert invalid[1]["parent_contact"] == "Point"
    assert invalid[1]["parent_face_length"] == 0
    assert invalid[1]["components"] == 2

    strategy = FacewiseSlopePreferenceStrategy(max_dyads=3)
    grid = Grid(nodes=[(p.centroid.x, p.centroid.y) for p in polygons.values()],
                edges=[(0, 4), (0, 5)],
                node_attributes={i: {"elevation": float(i)} for i in polygons},
                metadata={"grid_type": "cartesian", "extent": (0, 0, 3, 2), "cell_polygons": polygons})
    result = strategy.aggregate(None, grid, UrbanFormComposition.simple_dyad(), 4)
    placements = result.diagnostics["placements"]
    parents = [row["parent_open_cell"] for row in placements]
    assert len(result.doors) == 3
    rows = prefix_audit(result.doors, {str(i): n for i,n in result.building_labels.items()}, parents, polygons)
    assert all(r["components"] == 1 and r["pair_face_length"] > 0 for r in rows)
    assert all(r["parent_face_length"] > 0 for r in rows[1:])
    assert [r["pair_face_length"] for r in rows] == [r["building_face_length"] for r in placements]
    assert [r["parent_face_length"] for r in rows] == [r["parent_face_length"] for r in placements]
    assert not result.open_spaces & result.buildings


def test_face_lengths_exclude_vertex_contacts_and_disjoint_polygons():
    polygons = {0: box(0, 0, 1, 1), 1: box(1, 0, 2, 1),
                2: box(1, 1, 2, 2), 3: box(3, 3, 4, 4)}
    assert face_adjacency(polygons, polygons)[0] == {1: 1.0}
    assert _edge_graph(polygons, polygons)[0] == {1}
    assert _contact_graph(polygons, polygons)[0] == {1, 2}


def test_unclipped_ridge_outside_canvas_is_legacy_only():
    points = [[6.37, 2.7], [0.41, 0.17], [8.13, 9.13], [6.07, 7.29],
              [5.44, 9.35], [8.16, 0.03], [8.57, 0.34]]
    voronoi = Voronoi(points)
    extent = (0, 0, 10, 10)
    orchestrator = ExperimentOrchestrator(ExperimentPipeline())
    grid = Grid(nodes=points, edges=[], node_attributes={},
                metadata={"grid_type": "voronoi", "extent": extent, "voronoi": voronoi})
    ridge = next(vertices for cells, vertices in zip(voronoi.ridge_points, voronoi.ridge_vertices)
                 if set(cells) == {1, 5})
    assert ridge_length(voronoi, 5, 1, ridge, box(*extent)) == 0
    legacy = SlopePreferenceStrategy()
    corrected = FacewiseSlopePreferenceStrategy()
    assert 5 in legacy._build_adjacency(voronoi, grid, "voronoi")[1]
    with pytest.raises(ValueError, match="clipped cell inventory"):
        corrected._build_adjacency(voronoi, grid, "voronoi")
    orchestrator._prepare_aggregation_geometry(grid, corrected)
    assert 5 not in corrected._build_adjacency(voronoi, grid, "voronoi")[1]



def test_corrected_batch_certificate_rejects_false_parent_and_length():
    from experiments.facewise_rerun import certify

    cells = [box(i, 0, i + 1, 1) for i in range(4)]
    data = {
        "polygons_wkb": {str(i): p.wkb_hex for i, p in enumerate(cells)},
        "building_labels": {"0": 1, "3": 2},
        "doors": [[1, 0], [2, 3]],
        "dyad_open_cells": [1, 2],
        "placements": [
            {"label": 1, "open_cell": 1, "building_cell": 0, "parent_open_cell": None,
             "parent_face_length": None, "building_face_length": 1.0},
            {"label": 2, "open_cell": 2, "building_cell": 3, "parent_open_cell": 1,
             "parent_face_length": 1.0, "building_face_length": 1.0},
        ],
    }
    assert certify(data)["valid"]
    data["placements"][1].update(parent_open_cell=0, building_face_length=2.0)
    rejected = certify(data)
    assert not rejected["valid"]
    assert rejected["assigned_open_components"] == 1
    assert len(rejected["errors"]) == 2


@pytest.mark.parametrize(("seed", "excluded_unassigned"), [(40, 184), (41, 130)])
def test_y_regressions_regenerate_connected_growth(seed, excluded_unassigned):
    from experiments.facewise_rerun import generate_certified
    from voronoi_app.batch_methods import derive_topology

    result = generate_certified({}, {
        "terrain_provider": "converging_valleys",
        "terrain_params": {"depth": 1.0, "valley_width": 0.1},
        "canvas_size": 100.0,
        "grid_generator": "voronoi",
        "grid_params": {"num_points": 500, "jitter_ratio": 1.0},
        "aggregation_params": {
            "building_slope_preference": 0.95, "contour_preference": 0.95,
            "max_dyads": 100, "stagnation_limit": 1000,
        },
        "seed": seed,
    })
    assert result.valid
    certificate = result.output["aggregation_certificate"]
    assert certificate["completed_dyads"] == 100
    assert certificate["assigned_open_components"] == 1
    topology = derive_topology({"settlement": result.output}, {}).output["topology"]
    assigned = set(result.output["dyad_open_cells"])
    excluded = set(topology["excluded_open_cells"])
    assert not assigned & excluded
    assert len(excluded) == excluded_unassigned
    assert len(topology["internal_blocks"]) == len(topology["circulation_holes"]) == 6


def test_ridge_45_seed_component_preserves_all_doorway_cells():
    from experiments.facewise_rerun import generate_certified
    from voronoi_app.batch_methods import derive_topology

    result = generate_certified({}, {
        "terrain_provider": "ridge",
        "terrain_params": {"peak_height": 1.0, "orientation": "y", "width": 12.5},
        "canvas_size": 100.0,
        "grid_generator": "voronoi",
        "grid_params": {"num_points": 500, "jitter_ratio": 1.0},
        "aggregation_params": {
            "building_slope_preference": 0.95, "contour_preference": 0.95,
            "max_dyads": 100, "stagnation_limit": 1000,
        },
        "seed": 45,
    })
    assert result.valid and result.output["aggregation_certificate"]["completed_dyads"] == 100
    inputs = {"settlement": result.output}
    assigned = set(result.output["dyad_open_cells"])
    largest = derive_topology(inputs, {}).output["topology"]
    assert assigned.isdisjoint(largest["main_open_cells"])
    seed = result.output["doors"][0][0]
    seeded = derive_topology(inputs, {"main_open_seed": seed}).output["topology"]
    assert assigned <= set(seeded["main_open_cells"])
    assert len(seeded["circulation_holes"]) == len(seeded["internal_blocks"])
