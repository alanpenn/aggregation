"""
Registry and orchestration for terrain providers, grid generators, strategies, and measures.
"""

from typing import Dict, Type, Any, Optional
from .core import (
    TerrainProvider, GridGenerator, AggregationStrategy, 
    SpaceSyntaxMeasure, ExperimentPipeline, Grid, UrbanFormComposition,
    AggregationResult, Representation
)


class ComponentRegistry:
    """Central registry for all pluggable components."""
    
    def __init__(self):
        self.terrains: Dict[str, Type[TerrainProvider]] = {}
        self.grids: Dict[str, Type[GridGenerator]] = {}
        self.aggregations: Dict[str, Type[AggregationStrategy]] = {}
        self.measures: Dict[str, Type[SpaceSyntaxMeasure]] = {}
        self._terrain_instances: Dict[str, TerrainProvider] = {}
        self._grid_instances: Dict[str, GridGenerator] = {}
        self._aggregation_instances: Dict[str, AggregationStrategy] = {}
        self._measure_instances: Dict[str, SpaceSyntaxMeasure] = {}
    
    # Terrain registration
    def register_terrain(self, name: str, cls: Type[TerrainProvider]) -> None:
        self.terrains[name] = cls
    
    def get_terrain(self, name: str, params: Optional[Dict[str, Any]] = None) -> TerrainProvider:
        if params:
            if name not in self.terrains:
                raise ValueError(f"Unknown terrain provider: {name}")
            return self.terrains[name](**params)
        if name not in self._terrain_instances:
            if name not in self.terrains:
                raise ValueError(f"Unknown terrain provider: {name}")
            self._terrain_instances[name] = self.terrains[name]()
        return self._terrain_instances[name]
    
    def list_terrains(self) -> Dict[str, str]:
        """Return {name: description} for all registered terrains."""
        result = {}
        for name in self.terrains.keys():
            terrain = self.get_terrain(name)
            result[name] = terrain.description
        return result
    
    # Grid registration
    def register_grid(self, name: str, cls: Type[GridGenerator]) -> None:
        self.grids[name] = cls
    
    def get_grid(self, name: str, params: Optional[Dict[str, Any]] = None) -> GridGenerator:
        if params:
            if name not in self.grids:
                raise ValueError(f"Unknown grid generator: {name}")
            return self.grids[name](**params)
        if name not in self._grid_instances:
            if name not in self.grids:
                raise ValueError(f"Unknown grid generator: {name}")
            self._grid_instances[name] = self.grids[name]()
        return self._grid_instances[name]
    
    def list_grids(self) -> Dict[str, str]:
        """Return {name: description} for all registered grids."""
        result = {}
        for name in self.grids.keys():
            grid = self.get_grid(name)
            result[name] = grid.description
        return result
    
    # Aggregation registration
    def register_aggregation(self, name: str, cls: Type[AggregationStrategy]) -> None:
        self.aggregations[name] = cls
    
    def get_aggregation(self, name: str, params: Optional[Dict[str, Any]] = None) -> AggregationStrategy:
        if params:
            if name not in self.aggregations:
                raise ValueError(f"Unknown aggregation strategy: {name}")
            return self.aggregations[name](**params)
        if name not in self._aggregation_instances:
            if name not in self.aggregations:
                raise ValueError(f"Unknown aggregation strategy: {name}")
            self._aggregation_instances[name] = self.aggregations[name]()
        return self._aggregation_instances[name]
    
    def list_aggregations(self) -> Dict[str, str]:
        """Return {name: description} for all registered strategies."""
        result = {}
        for name in self.aggregations.keys():
            agg = self.get_aggregation(name)
            result[name] = agg.description
        return result
    
    # Measure registration
    def register_measure(self, name: str, cls: Type[SpaceSyntaxMeasure]) -> None:
        self.measures[name] = cls
    
    def get_measure(self, name: str, params: Optional[Dict[str, Any]] = None) -> SpaceSyntaxMeasure:
        if params:
            if name not in self.measures:
                raise ValueError(f"Unknown space-syntax measure: {name}")
            return self.measures[name](**params)
        if name not in self._measure_instances:
            if name not in self.measures:
                raise ValueError(f"Unknown space-syntax measure: {name}")
            self._measure_instances[name] = self.measures[name]()
        return self._measure_instances[name]
    
    def list_measures(self) -> Dict[str, str]:
        """Return {name: description} for all registered measures."""
        result = {}
        for name in self.measures.keys():
            measure = self.get_measure(name)
            result[name] = measure.description
        return result


# Global singleton registry
_global_registry: Optional[ComponentRegistry] = None


def get_registry() -> ComponentRegistry:
    """Get or create the global registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ComponentRegistry()
    return _global_registry


def register_defaults() -> None:
    """Register built-in components. Called on module initialization."""
    from .terrain import (
        FlatTerrainProvider, HillTerrainProvider, RidgeTerrainProvider,
        ShoulderTerrainProvider, TwinPeaksTerrainProvider, ValleyTerrainProvider,
        ConvergingValleysTerrainProvider, SingleSlopeTerrainProvider,
        ThreeConvergingRidgesTerrainProvider,
    )
    from .grid_generators import (
        VoronoiGridGenerator, CartesianGridGenerator, TopographyResponsiveVoronoiGenerator
    )
    from .aggregation import SlopePreferenceStrategy
    from .analysis import MeanDepthMeasure, ConnectivityMeasure
    
    registry = get_registry()
    
    # Register terrain providers
    registry.register_terrain("flat", FlatTerrainProvider)
    registry.register_terrain("hill", HillTerrainProvider)
    registry.register_terrain("ridge", RidgeTerrainProvider)
    registry.register_terrain("shoulder", ShoulderTerrainProvider)
    registry.register_terrain("twin_peaks", TwinPeaksTerrainProvider)
    registry.register_terrain("valley", ValleyTerrainProvider)
    registry.register_terrain("converging_valleys", ConvergingValleysTerrainProvider)
    registry.register_terrain("single_slope", SingleSlopeTerrainProvider)
    registry.register_terrain("three_converging_ridges", ThreeConvergingRidgesTerrainProvider)
    
    # Register grid generators
    registry.register_grid("voronoi", VoronoiGridGenerator)
    registry.register_grid("cartesian", CartesianGridGenerator)
    registry.register_grid("topography_responsive_voronoi", TopographyResponsiveVoronoiGenerator)
    
    # Register aggregation strategies
    registry.register_aggregation("slope_preference", SlopePreferenceStrategy)
    
    # Register space-syntax measures
    registry.register_measure("mean_depth", MeanDepthMeasure)
    registry.register_measure("connectivity", ConnectivityMeasure)
