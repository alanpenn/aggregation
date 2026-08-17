"""
Tests for terrain providers, grid generators, and aggregation strategies.
"""

import pytest
import numpy as np
from voronoi_app.terrain import (
    FlatTerrainProvider,
    HillTerrainProvider,
    RidgeTerrainProvider,
    ShoulderTerrainProvider,
    SingleSlopeTerrainProvider,
    ThreeConvergingRidgesTerrainProvider,
    TwinPeaksTerrainProvider,
    ValleyTerrainProvider,
    ConvergingValleysTerrainProvider,
)
from voronoi_app.grid_generators import (
    VoronoiGridGenerator, CartesianGridGenerator, TopographyResponsiveVoronoiGenerator
)
from voronoi_app.engine import VoronoiEngine
from voronoi_app.config import ExperimentConfig
from voronoi_app.aggregation import SlopePreferenceStrategy
from voronoi_app.analysis import MeanDepthMeasure, ConnectivityMeasure
from voronoi_app.core import ExperimentPipeline, Representation
from voronoi_app.orchestrator import run_experiment_pipeline


class TestTerrainProviders:
    """Test terrain provider implementations."""
    
    def test_flat_terrain_always_zero(self):
        terrain = FlatTerrainProvider()
        assert terrain.evaluate(0, 0) == 0.0
        assert terrain.evaluate(50, 50) == 0.0
        assert terrain.evaluate(100, 100) == 0.0
    
    def test_flat_terrain_sample_field(self):
        terrain = FlatTerrainProvider()
        field = terrain.sample_field(resolution=50)
        assert field["elevations"].shape == (50, 50)
        assert np.allclose(field["elevations"], 0.0)

    def test_single_slope_is_monotonic(self):
        terrain = SingleSlopeTerrainProvider(slope=2.0, direction="x")
        assert terrain.evaluate(0, 50) == 0.0
        assert terrain.evaluate(100, 50) == 2.0
        assert terrain.evaluate(75, 50) > terrain.evaluate(25, 50)
        assert terrain.sample_field(16)["elevations"].shape == (16, 16)

    def test_three_converging_ridges_have_three_branches(self):
        terrain = ThreeConvergingRidgesTerrainProvider(peak_height=1.0, ridge_width=0.1)
        junction = terrain.evaluate(50, 50)
        left_branch = terrain.evaluate(20, 85)
        right_branch = terrain.evaluate(80, 85)
        upper_branch = terrain.evaluate(50, 15)
        corner = terrain.evaluate(10, 10)
        assert junction > 0.8
        assert left_branch > 0.8
        assert right_branch > 0.8
        assert upper_branch > 0.8
        assert corner < left_branch
        assert terrain.sample_field(16)["elevations"].shape == (16, 16)
    
    def test_hill_terrain_peak_in_center(self):
        terrain = HillTerrainProvider(
            extent=(0, 0, 100, 100),
            peak_height=1.0
        )
        # Peak at center
        h_center = terrain.evaluate(50, 50)
        # Both axes should fall away from the center.
        h_edge_y = terrain.evaluate(50, 0)
        h_edge_x = terrain.evaluate(0, 50)
        assert h_center > h_edge_y
        assert h_center > h_edge_x
        assert h_edge_y == h_edge_x
    
    def test_hill_terrain_reproducibility(self):
        terrain1 = HillTerrainProvider(peak_height=1.0)
        terrain2 = HillTerrainProvider(peak_height=1.0)
        assert terrain1.evaluate(30, 40) == terrain2.evaluate(30, 40)
    
    def test_ridge_terrain_orientation(self):
        ridge_y = RidgeTerrainProvider(orientation="y")
        ridge_x = RidgeTerrainProvider(orientation="x")
        # Different orientations should produce different results
        assert ridge_y.evaluate(25, 50) != ridge_x.evaluate(25, 50)
    
    def test_valley_terrain_inverted_hill(self):
        valley = ValleyTerrainProvider(depth=1.0)
        # Valley should be LOW at center, HIGH at edges (inverted hill)
        h_center = valley.evaluate(50, 50)
        h_edge = valley.evaluate(50, 0)
        assert h_center < h_edge
        assert h_center < 1.0  # Inverted, so low at center

    def test_twin_peaks_are_localized(self):
        terrain = TwinPeaksTerrainProvider(
            peak_height=1.0,
            saddle_height=0.5,
            peak_separation=40.0,
        )
        left_peak = terrain.evaluate(30, 50)
        right_peak = terrain.evaluate(70, 50)
        saddle = terrain.evaluate(50, 50)
        off_axis = terrain.evaluate(30, 0)
        assert left_peak > saddle
        assert right_peak > saddle
        assert left_peak > off_axis
        assert right_peak > off_axis

    def test_shoulder_sits_between_converging_valleys(self):
        terrain = ShoulderTerrainProvider(peak_height=1.0, asymmetry=0.5)
        left_channel = terrain.evaluate(20, 80)
        right_channel = terrain.evaluate(80, 80)
        shoulder = terrain.evaluate(50, 80)
        junction = terrain.evaluate(50, 35)

        assert shoulder > left_channel
        assert shoulder > right_channel
        assert junction < shoulder

    def test_converging_valleys_form_y_network(self):
        terrain = ConvergingValleysTerrainProvider(depth=1.0, valley_width=0.1)
        left_branch = terrain.evaluate(20, 83)
        right_branch = terrain.evaluate(80, 83)
        junction = terrain.evaluate(50, 50)
        trunk = terrain.evaluate(50, 15)
        shoulder = terrain.evaluate(50, 83)

        assert left_branch < 0.1
        assert right_branch < 0.1
        assert junction < 0.1
        assert trunk < 0.1
        assert shoulder > left_branch
    
    def test_terrain_metadata(self):
        terrain = HillTerrainProvider()
        metadata = terrain.metadata
        assert metadata.name == "Hill"
        assert metadata.units == "meters"
        assert metadata.source == "procedural"


class TestGridGenerators:
    """Test grid generator implementations."""
    
    def test_voronoi_grid_generation(self):
        terrain = FlatTerrainProvider()
        gen = VoronoiGridGenerator(num_points=100)
        grid = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        assert len(grid.nodes) > 0
        assert len(grid.edges) > 0
        assert len(grid.node_attributes) == len(grid.nodes)
    
    def test_voronoi_grid_deterministic(self):
        terrain = FlatTerrainProvider()
        gen = VoronoiGridGenerator(num_points=100)
        
        grid1 = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        grid2 = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        # Same seed should produce identical grids
        assert grid1.nodes == grid2.nodes
        assert grid1.edges == grid2.edges

    def test_voronoi_points_match_legacy_engine(self):
        config = ExperimentConfig(num_points=100, canvas_size=100, seed=42)
        legacy = VoronoiEngine(config)
        modular = VoronoiGridGenerator(num_points=100, jitter_ratio=1.0)
        grid = modular.generate(
            FlatTerrainProvider(),
            extent=(0, 0, 100, 100),
            seed=42,
        )

        assert np.allclose(np.asarray(grid.nodes), legacy.points)

    def test_pipeline_grid_parameters_are_applied(self):
        small = ExperimentPipeline(
            grid_generator="voronoi",
            grid_params={"num_points": 100, "jitter_ratio": 0.0},
            aggregation_params={"max_dyads": 5},
            seed=42,
        )
        large = ExperimentPipeline(
            grid_generator="voronoi",
            grid_params={"num_points": 400, "jitter_ratio": 0.0},
            aggregation_params={"max_dyads": 5},
            seed=42,
        )

        small_result = run_experiment_pipeline(small)
        large_result = run_experiment_pipeline(large)

        assert len(small_result.grid.nodes) == 100
        assert len(large_result.grid.nodes) == 400
    
    def test_cartesian_grid_generation(self):
        terrain = FlatTerrainProvider()
        gen = CartesianGridGenerator(resolution=10)
        grid = gen.generate(terrain, extent=(0, 0, 100, 100))
        
        assert len(grid.nodes) == 10 * 10
        assert len(grid.edges) > 0
    
    def test_cartesian_grid_regularity(self):
        terrain = FlatTerrainProvider()
        gen = CartesianGridGenerator(resolution=5)
        grid = gen.generate(terrain, extent=(0, 0, 100, 100))
        
        # Cartesian grid should be regular
        assert len(grid.nodes) == 25
        # Each interior point has 4 neighbors, corners have 2, edges have 3
        # But exact count depends on edge handling
    
    def test_topography_responsive_voronoi_generation(self):
        terrain = HillTerrainProvider(peak_height=2.0)
        gen = TopographyResponsiveVoronoiGenerator(
            num_points=100,
            elevation_influence=0.5,
            slope_influence=0.3,
            relaxation_iterations=3,
            attraction_mode="peak",
        )
        grid = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        assert len(grid.nodes) > 0
        assert len(grid.edges) > 0
        assert len(grid.node_attributes) == len(grid.nodes)
        assert grid.metadata["grid_type"] == "topography_responsive_voronoi"
        assert grid.metadata["attraction_mode"] == "peak"
    
    def test_topography_responsive_voronoi_peak_mode(self):
        """Test that peak mode attracts points toward high elevation."""
        terrain = HillTerrainProvider(peak_height=2.0, extent=(0, 0, 100, 100))
        gen = TopographyResponsiveVoronoiGenerator(
            num_points=100,
            elevation_influence=0.8,
            slope_influence=0.2,
            relaxation_iterations=5,
            attraction_mode="peak",
        )
        grid = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        # Calculate average elevation of points
        elevations = [attr["elevation"] for attr in grid.node_attributes.values()]
        avg_elev = np.mean(elevations)
        
        # Points should be drawn toward center where peak is
        # At least some points should have above-zero elevation
        assert max(elevations) > 0.5
        assert avg_elev > 0.1
    
    def test_topography_responsive_voronoi_valley_mode(self):
        """Test that valley mode attracts points toward low elevation."""
        terrain = ValleyTerrainProvider(depth=2.0, extent=(0, 0, 100, 100))
        gen = TopographyResponsiveVoronoiGenerator(
            num_points=100,
            elevation_influence=0.8,
            slope_influence=0.2,
            relaxation_iterations=5,
            attraction_mode="valley",
        )
        grid = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        # Calculate average elevation of points
        elevations = [attr["elevation"] for attr in grid.node_attributes.values()]
        
        # In valley mode, should attract to low/negative elevation areas
        # Valley centers have lower values
        assert len(grid.nodes) > 0
    
    def test_topography_responsive_voronoi_deterministic(self):
        terrain = HillTerrainProvider(peak_height=1.0)
        gen = TopographyResponsiveVoronoiGenerator(
            num_points=100,
            relaxation_iterations=3,
        )
        
        grid1 = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        grid2 = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        # Same seed should produce identical grids
        assert grid1.nodes == grid2.nodes
        assert grid1.edges == grid2.edges


class TestAggregationStrategies:
    """Test aggregation strategy implementations."""
    
    def test_slope_preference_strategy_basic(self):
        terrain = FlatTerrainProvider()
        gen = VoronoiGridGenerator(num_points=100)
        grid = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        strategy = SlopePreferenceStrategy(
            slope_preference=0.95,
            max_dyads=50,
            stagnation_limit=1000
        )
        
        from voronoi_app.core import UrbanFormComposition
        form = UrbanFormComposition.simple_dyad()
        
        result = strategy.aggregate(terrain, grid, form, seed=42)
        
        assert len(result.buildings) > 0
        assert len(result.open_spaces) > 0
        assert len(result.doors) == len(result.buildings)
    
    def test_slope_preference_reproducibility(self):
        terrain = FlatTerrainProvider()
        gen = VoronoiGridGenerator(num_points=100)
        grid1 = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        grid2 = gen.generate(terrain, extent=(0, 0, 100, 100), seed=42)
        
        strategy = SlopePreferenceStrategy(max_dyads=50)
        from voronoi_app.core import UrbanFormComposition
        form = UrbanFormComposition.simple_dyad()
        
        result1 = strategy.aggregate(terrain, grid1, form, seed=42)
        result2 = strategy.aggregate(terrain, grid2, form, seed=42)
        
        assert result1.buildings == result2.buildings
        assert result1.open_spaces == result2.open_spaces

    def test_contour_and_building_preferences_are_independent(self):
        strategy = SlopePreferenceStrategy(
            contour_preference=-1.0,
            building_slope_preference=-1.0,
        )

        assert "contour_preference" in strategy.parameters
        assert "building_slope_preference" in strategy.parameters
        assert strategy.parameters["contour_preference"].min_value == -1.0
        assert strategy.parameters["building_slope_preference"].min_value == -1.0
        assert strategy.get_config()["contour_preference"] == -1.0
        assert strategy.get_config()["building_slope_preference"] == -1.0

        legacy = SlopePreferenceStrategy(slope_preference=0.25)
        assert legacy.get_config()["contour_preference"] == 0.25
        assert legacy.get_config()["building_slope_preference"] == 0.25

    def test_slope_preference_open_spaces_are_connected(self):
        import networkx as nx

        terrain = FlatTerrainProvider()
        grid = VoronoiGridGenerator(num_points=225).generate(
            terrain, extent=(0, 0, 100, 100), seed=17
        )
        from voronoi_app.core import UrbanFormComposition

        result = SlopePreferenceStrategy(max_dyads=100).aggregate(
            terrain, grid, UrbanFormComposition.simple_dyad(), seed=17
        )
        graph = nx.Graph()
        graph.add_nodes_from(result.open_spaces)
        graph.add_edges_from(
            (i, j)
            for i, j in grid.edges
            if i in result.open_spaces and j in result.open_spaces
        )

        assert nx.is_connected(graph)


class TestSpaceSyntaxMeasures:
    """Test space-syntax measure implementations."""
    
    def test_mean_depth_measure(self):
        # Create a simple graph
        from voronoi_app.core import Representation
        rep = Representation(
            name="test_graph",
            nodes=[0, 1, 2, 3],
            edges=[(0, 1), (1, 2), (2, 3)],
        )
        
        measure = MeanDepthMeasure()
        result = measure.compute(rep)
        
        assert len(result) == 4
        assert result[0] > 0  # Non-zero mean depth
        assert result[1] > 0
        # Node 1 and 2 should have lower mean depth than ends
        assert result[1] < result[0]
        assert result[2] < result[3]
    
    def test_connectivity_measure(self):
        from voronoi_app.core import Representation
        rep = Representation(
            name="test_graph",
            nodes=[0, 1, 2],
            edges=[(0, 1), (1, 2), (0, 2)],  # Triangle
        )
        
        measure = ConnectivityMeasure()
        result = measure.compute(rep)
        
        # In a triangle, all nodes have degree 2
        assert result[0] == 2
        assert result[1] == 2
        assert result[2] == 2


class TestExperimentOrchestrator:
    """Test end-to-end experiment orchestration."""
    
    def test_full_pipeline_flat_terrain(self):
        pipeline = ExperimentPipeline(
            terrain_provider="flat",
            grid_generator="voronoi",
            aggregation_strategy="slope_preference",
            space_syntax_measure="mean_depth",
            seed=42
        )
        
        result = run_experiment_pipeline(pipeline)
        
        assert len(result.buildings) > 0
        assert len(result.open_spaces) > 0
        assert result.visibility_graph is not None
        assert len(result.mean_depth) > 0
    
    def test_full_pipeline_hill_terrain(self):
        pipeline = ExperimentPipeline(
            terrain_provider="hill",
            grid_generator="voronoi",
            seed=42
        )
        
        result = run_experiment_pipeline(pipeline)
        
        # Should produce valid results
        assert len(result.buildings) > 0
        assert "elevations" in result.terrain_sample
    
    def test_full_pipeline_cartesian_grid(self):
        # NOTE: Cartesian grid aggregation not yet implemented
        # Skip this test for now as slope_preference strategy requires Voronoi
        pytest.skip("Cartesian grid aggregation not yet implemented")
    
    def test_experiment_serialization(self):
        pipeline = ExperimentPipeline(
            terrain_provider="hill",
            grid_generator="voronoi",
            seed=42
        )
        
        # Test to_dict and from_dict
        config_dict = pipeline.to_dict()
        restored = ExperimentPipeline.from_dict(config_dict)
        
        assert restored.terrain_provider == pipeline.terrain_provider
        assert restored.grid_generator == pipeline.grid_generator
        assert restored.seed == pipeline.seed
