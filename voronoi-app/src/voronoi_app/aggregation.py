"""
Aggregation strategy implementations.
"""

import random
import numpy as np
from typing import Dict, Any, Optional, Tuple, Set, List
from scipy.spatial import Voronoi

from .core import (
    AggregationStrategy, Grid, TerrainProvider, UrbanFormComposition,
    AggregationResult, ParameterSchema
)


class SlopePreferenceStrategy(AggregationStrategy):
    """
    Dyad-based growth strategy with slope preference.
    
    This is the default strategy that replicates the original aggregation behavior.
    Grows building + open space pairs greedily, preferring steep slopes.
    """
    
    def __init__(
        self,
        contour_preference: float = 0.95,
        building_slope_preference: float = 0.95,
        max_dyads: int = 100,
        stagnation_limit: int = 1000,
        slope_preference: Optional[float] = None,
    ):
        # Keep the old option as a compatibility alias for saved pipelines.
        if slope_preference is not None:
            contour_preference = slope_preference
            building_slope_preference = slope_preference
        self._contour_preference = contour_preference
        self._building_slope_preference = building_slope_preference
        self._max_dyads = max_dyads
        self._stagnation_limit = stagnation_limit
    
    @property
    def name(self) -> str:
        return "slope_preference"
    
    @property
    def description(self) -> str:
        return "Dyad growth with slope preference (default strategy)"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "contour_preference": ParameterSchema(
                name="contour_preference",
                type="float",
                description="Open-space terrain preference (-1 steep changes, +1 contours)",
                default=0.95,
                min_value=-1.0,
                max_value=1.0,
            ),
            "building_slope_preference": ParameterSchema(
                name="building_slope_preference",
                type="float",
                description="Building terrain preference (-1 flat, +1 steep slopes)",
                default=0.95,
                min_value=-1.0,
                max_value=1.0,
            ),
            "max_dyads": ParameterSchema(
                name="max_dyads",
                type="int",
                description="Maximum number of building + open space pairs",
                default=100,
                min_value=1,
                max_value=1000,
            ),
            "stagnation_limit": ParameterSchema(
                name="stagnation_limit",
                type="int",
                description="Iterations without placement before stopping",
                default=1000,
                min_value=1,
                max_value=10000,
            ),
        }
    
    def aggregate(
        self,
        terrain: TerrainProvider,
        grid: Grid,
        form: UrbanFormComposition,
        seed: Optional[int] = None,
    ) -> AggregationResult:
        """Run slope-preference aggregation."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # Determine grid type and get adjacency info
        grid_type = grid.metadata.get("grid_type", "voronoi")
        
        if grid_type == "voronoi" or grid_type == "topography_responsive_voronoi":
            voronoi = grid.metadata.get("voronoi")
            if voronoi is None:
                raise ValueError("SlopePreferenceStrategy requires Voronoi metadata")
        elif grid_type == "cartesian":
            voronoi = None
        else:
            raise ValueError(f"Unknown grid type: {grid_type}")

        adjacency = self._build_adjacency(voronoi, grid, grid_type)
        
        buildings: Set[int] = set()
        open_spaces: Set[int] = set()
        doors: List[Tuple[int, int]] = []
        building_labels: Dict[int, int] = {}
        
        # Find center and initialize
        center = np.array([
            (grid.metadata.get("extent", (0, 0, 100, 100))[0] +
             grid.metadata.get("extent", (0, 0, 100, 100))[2]) / 2,
            (grid.metadata.get("extent", (0, 0, 100, 100))[1] +
             grid.metadata.get("extent", (0, 0, 100, 100))[3]) / 2,
        ])
        
        # Find closest point to center
        points = np.array(grid.nodes)
        initial_open = np.argmin(np.linalg.norm(points - center, axis=1))
        open_spaces.add(initial_open)
        
        # Find adjacent building
        neighbors = adjacency[initial_open]
        if not neighbors:
            return AggregationResult(
                buildings=buildings,
                open_spaces=open_spaces,
                doors=doors,
                building_labels=building_labels,
            )
        
        initial_building = random.choice(list(neighbors))
        buildings.add(initial_building)
        building_labels[initial_building] = 1
        doors.append((initial_open, initial_building))
        
        # Aggregation loop
        label_counter = 2
        stagnation = 0
        
        while len(buildings) < self._max_dyads and stagnation < self._stagnation_limit:
            if len(buildings) + len(open_spaces) >= len(grid.nodes):
                break
            candidates = list(open_spaces)
            random.shuffle(candidates)
            placed = False
            
            for open_idx in candidates:
                neighbors = adjacency[open_idx]
                neighbors = [
                    n for n in neighbors
                    if n not in buildings and n not in open_spaces
                ]
                
                if not neighbors:
                    continue
                
                # Open spaces should follow contours: prefer small elevation
                # changes between adjacent spaces. Buildings retain the
                # separate steep-slope preference below.
                neighbors.sort(
                    key=lambda n: (
                        (1 - abs(self._contour_preference)) * random.random()
                        + abs(
                            grid.node_attributes[n]["elevation"]
                            - grid.node_attributes[open_idx]["elevation"]
                        ) * self._contour_preference
                    )
                )
                
                new_open = neighbors[0]
                open_spaces.add(new_open)
                
                # Find building for new open space
                next_neighbors = adjacency[new_open]
                next_neighbors = [
                    n for n in next_neighbors
                    if n not in buildings and n not in open_spaces
                ]
                
                if not next_neighbors:
                    open_spaces.remove(new_open)
                    continue
                
                # Prefer high slopes for building placement
                next_neighbors.sort(
                    key=lambda n: (
                        -abs(
                            grid.node_attributes[n]["elevation"]
                            - grid.node_attributes[new_open]["elevation"]
                        ) * self._building_slope_preference
                        + (1 - abs(self._building_slope_preference)) * random.random()
                    )
                )
                
                new_building = next_neighbors[0]
                buildings.add(new_building)
                building_labels[new_building] = label_counter
                label_counter += 1
                doors.append((new_open, new_building))
                placed = True
                break
            
            if not placed:
                stagnation += 1
        
        return AggregationResult(
            buildings=buildings,
            open_spaces=open_spaces,
            doors=doors,
            building_labels=building_labels,
        )
    
    def _find_adjacent_regions(
        self, 
        voronoi: Optional[Any], 
        point_index: int, 
        grid: Grid,
        grid_type: str
    ) -> Set[int]:
        """Find neighbors based on grid type."""
        neighbors = set()
        
        if grid_type == "voronoi" or grid_type == "topography_responsive_voronoi":
            # Use Voronoi ridge_points for adjacency
            if voronoi is not None:
                for ridge in voronoi.ridge_points:
                    if point_index in ridge:
                        neighbor = ridge[1] if ridge[0] == point_index else ridge[0]
                        neighbors.add(neighbor)
        
        elif grid_type == "cartesian":
            # Use grid edges for Cartesian adjacency
            for edge in grid.edges:
                if point_index == edge[0]:
                    neighbors.add(edge[1])
                elif point_index == edge[1]:
                    neighbors.add(edge[0])
        
        return neighbors

    def _build_adjacency(
        self,
        voronoi: Optional[Any],
        grid: Grid,
        grid_type: str,
    ) -> Dict[int, Set[int]]:
        """Build adjacency once instead of rescanning every edge per attempt."""
        adjacency = {index: set() for index in range(len(grid.nodes))}
        if grid_type in ("voronoi", "topography_responsive_voronoi") and voronoi is not None:
            edges = voronoi.ridge_points
        else:
            edges = grid.edges
        for left, right in edges:
            adjacency[left].add(right)
            adjacency[right].add(left)
        return adjacency
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "slope_preference",
            "contour_preference": self._contour_preference,
            "building_slope_preference": self._building_slope_preference,
            "max_dyads": self._max_dyads,
            "stagnation_limit": self._stagnation_limit,
        }


class DistanceBasedStrategy(AggregationStrategy):
    """
    Distance-based aggregation strategy.
    (Future implementation placeholder)
    """
    
    @property
    def name(self) -> str:
        return "distance"
    
    @property
    def description(self) -> str:
        return "Distance-based aggregation (future implementation)"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {}
    
    def aggregate(
        self,
        terrain: TerrainProvider,
        grid: Grid,
        form: UrbanFormComposition,
        seed: Optional[int] = None,
    ) -> AggregationResult:
        raise NotImplementedError("Distance-based aggregation not yet implemented")
    
    def get_config(self) -> Dict[str, Any]:
        return {"type": "distance"}


class VisibilityBasedStrategy(AggregationStrategy):
    """
    Visibility-based aggregation strategy.
    (Future implementation placeholder)
    """
    
    @property
    def name(self) -> str:
        return "visibility"
    
    @property
    def description(self) -> str:
        return "Visibility-based aggregation (future implementation)"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {}
    
    def aggregate(
        self,
        terrain: TerrainProvider,
        grid: Grid,
        form: UrbanFormComposition,
        seed: Optional[int] = None,
    ) -> AggregationResult:
        raise NotImplementedError("Visibility-based aggregation not yet implemented")
    
    def get_config(self) -> Dict[str, Any]:
        return {"type": "visibility"}
