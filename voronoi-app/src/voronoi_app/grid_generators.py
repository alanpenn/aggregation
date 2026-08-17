"""
Grid generator implementations.
"""

import random
import numpy as np
from typing import Dict, Any, Optional, Tuple
from scipy.spatial import Voronoi

from .core import GridGenerator, Grid, TerrainProvider, ParameterSchema


class VoronoiGridGenerator(GridGenerator):
    """Standard Voronoi grid generator using Poisson disk sampling."""
    
    def __init__(
        self,
        num_points: int = 500,
        jitter_ratio: float = 1.0,
    ):
        self._num_points = num_points
        self._jitter_ratio = jitter_ratio
    
    @property
    def name(self) -> str:
        return "voronoi"
    
    @property
    def description(self) -> str:
        return "Standard Voronoi grid with Poisson disk sampling"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "num_points": ParameterSchema(
                name="num_points",
                type="int",
                description="Number of Voronoi points",
                default=500,
                min_value=10,
                max_value=5000,
            ),
            "jitter_ratio": ParameterSchema(
                name="jitter_ratio",
                type="float",
                description="Jitter applied to grid points (0-1)",
                default=1.0,
                min_value=0.0,
                max_value=1.0,
            ),
        }
    
    def generate(
        self,
        terrain: TerrainProvider,
        extent: Tuple[float, float, float, float],
        seed: Optional[int] = None,
    ) -> Grid:
        """Generate Voronoi grid over extent."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        
        # Poisson disk sampling
        points = self._generate_poisson_disk_points(
            extent,
            self._num_points,
            self._jitter_ratio
        )
        
        # Generate Voronoi
        voronoi = Voronoi(points)
        
        # Convert to Grid representation
        nodes = [(p[0], p[1]) for p in points]
        
        # Extract edges from ridge_points
        edges = []
        for ridge in voronoi.ridge_points:
            if ridge[0] < len(points) and ridge[1] < len(points):
                edges.append(tuple(ridge))
        
        # Compute elevation for each point
        node_attributes = {}
        for i, (x, y) in enumerate(nodes):
            elevation = terrain.evaluate(x, y)
            node_attributes[i] = {
                "elevation": elevation,
                "x": x,
                "y": y,
            }
        
        metadata = {
            "grid_type": "voronoi",
            "num_points": len(points),
            "voronoi": voronoi,  # Store for backwards compatibility
        }
        
        return Grid(
            nodes=nodes,
            edges=edges,
            node_attributes=node_attributes,
            metadata=metadata
        )
    
    def _generate_poisson_disk_points(
        self,
        extent: Tuple[float, float, float, float],
        num_points: int,
        jitter_ratio: float,
    ) -> np.ndarray:
        """Generate points using grid + jitter."""
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        
        grid_size = int(np.sqrt(num_points))
        jitter = min(width, height) / (grid_size * 3) * jitter_ratio
        step_x = width / grid_size
        step_y = height / grid_size
        
        points = []
        for i in range(grid_size):
            for j in range(grid_size):
                x = min_x + i * step_x + step_x / 2 + random.uniform(-jitter, jitter)
                y = min_y + j * step_y + step_y / 2 + random.uniform(-jitter, jitter)
                if min_x <= x <= max_x and min_y <= y <= max_y:
                    points.append((x, y))
                if len(points) >= num_points:
                    break
            if len(points) >= num_points:
                break
        
        return np.array(points)
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "voronoi",
            "num_points": self._num_points,
            "jitter_ratio": self._jitter_ratio,
        }


class CartesianGridGenerator(GridGenerator):
    """Regular Cartesian grid."""
    
    def __init__(self, resolution: int = 20):
        self._resolution = resolution
    
    @property
    def name(self) -> str:
        return "cartesian"
    
    @property
    def description(self) -> str:
        return "Regular Cartesian grid"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "resolution": ParameterSchema(
                name="resolution",
                type="int",
                description="Grid resolution (points per side)",
                default=20,
                min_value=2,
                max_value=100,
            ),
        }
    
    def generate(
        self,
        terrain: TerrainProvider,
        extent: Tuple[float, float, float, float],
        seed: Optional[int] = None,
    ) -> Grid:
        """Generate Cartesian grid."""
        min_x, min_y, max_x, max_y = extent
        
        x = np.linspace(min_x, max_x, self._resolution)
        y = np.linspace(min_y, max_y, self._resolution)
        
        nodes = []
        node_idx = {}
        idx = 0
        for j in range(self._resolution):
            for i in range(self._resolution):
                nodes.append((x[i], y[j]))
                node_idx[(i, j)] = idx
                idx += 1
        
        # Create edges: connect each cell to its neighbors
        edges = []
        for j in range(self._resolution):
            for i in range(self._resolution):
                curr_idx = node_idx[(i, j)]
                if i + 1 < self._resolution:
                    next_idx = node_idx[(i + 1, j)]
                    edges.append((curr_idx, next_idx))
                if j + 1 < self._resolution:
                    next_idx = node_idx[(i, j + 1)]
                    edges.append((curr_idx, next_idx))
        
        # Compute elevation for each node
        node_attributes = {}
        for idx, (px, py) in enumerate(nodes):
            elevation = terrain.evaluate(px, py)
            node_attributes[idx] = {
                "elevation": elevation,
                "x": px,
                "y": py,
            }
        
        metadata = {
            "grid_type": "cartesian",
            "resolution": self._resolution,
        }
        
        return Grid(
            nodes=nodes,
            edges=edges,
            node_attributes=node_attributes,
            metadata=metadata
        )
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "cartesian",
            "resolution": self._resolution,
        }


class TopographyResponsiveVoronoiGenerator(GridGenerator):
    """Voronoi grid with topography-aware centroid placement."""
    
    def __init__(
        self,
        num_points: int = 500,
        jitter_ratio: float = 0.3,
        elevation_influence: float = 0.3,
        slope_influence: float = 0.5,
        relaxation_iterations: int = 5,
        attraction_mode: str = "peak",
    ):
        self._num_points = num_points
        self._jitter_ratio = jitter_ratio
        self._elevation_influence = elevation_influence
        self._slope_influence = slope_influence
        self._relaxation_iterations = relaxation_iterations
        self._attraction_mode = attraction_mode
    
    @property
    def name(self) -> str:
        return "topography_responsive_voronoi"
    
    @property
    def description(self) -> str:
        return "Voronoi grid with topography-aware centroid attraction"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "num_points": ParameterSchema(
                name="num_points",
                type="int",
                description="Number of Voronoi points",
                default=500,
                min_value=10,
                max_value=5000,
            ),
            "jitter_ratio": ParameterSchema(
                name="jitter_ratio",
                type="float",
                description="Initial jitter applied to grid points (0-1)",
                default=0.3,
                min_value=0.0,
                max_value=1.0,
            ),
            "elevation_influence": ParameterSchema(
                name="elevation_influence",
                type="float",
                description="Strength of elevation attraction (0-1)",
                default=0.3,
                min_value=0.0,
                max_value=1.0,
            ),
            "slope_influence": ParameterSchema(
                name="slope_influence",
                type="float",
                description="Strength of slope attraction (0-1)",
                default=0.5,
                min_value=0.0,
                max_value=1.0,
            ),
            "relaxation_iterations": ParameterSchema(
                name="relaxation_iterations",
                type="int",
                description="Number of centroid relaxation iterations",
                default=5,
                min_value=1,
                max_value=20,
            ),
            "attraction_mode": ParameterSchema(
                name="attraction_mode",
                type="choice",
                description="Terrain feature to attract centroids toward",
                default="peak",
                choices=["peak", "slope", "valley"],
            ),
        }
    
    def generate(
        self,
        terrain: TerrainProvider,
        extent: Tuple[float, float, float, float],
        seed: Optional[int] = None,
    ) -> Grid:
        """Generate topography-aware Voronoi grid."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        
        # Initial point generation (standard grid + jitter)
        points = self._generate_initial_points(
            extent,
            self._num_points,
            self._jitter_ratio
        )
        
        # Topography-aware relaxation
        points = self._relax_points(
            points,
            terrain,
            extent,
            self._relaxation_iterations
        )
        
        # Generate Voronoi
        voronoi = Voronoi(points)
        
        # Convert to Grid representation
        nodes = [(p[0], p[1]) for p in points]
        
        # Extract edges from ridge_points
        edges = []
        for ridge in voronoi.ridge_points:
            if ridge[0] < len(points) and ridge[1] < len(points):
                edges.append(tuple(ridge))
        
        # Compute elevation for each point
        node_attributes = {}
        for i, (x, y) in enumerate(nodes):
            elevation = terrain.evaluate(x, y)
            node_attributes[i] = {
                "elevation": elevation,
                "x": x,
                "y": y,
            }
        
        metadata = {
            "grid_type": "topography_responsive_voronoi",
            "num_points": len(points),
            "voronoi": voronoi,
            "attraction_mode": self._attraction_mode,
        }
        
        return Grid(
            nodes=nodes,
            edges=edges,
            node_attributes=node_attributes,
            metadata=metadata
        )
    
    def _generate_initial_points(
        self,
        extent: Tuple[float, float, float, float],
        num_points: int,
        jitter_ratio: float,
    ) -> np.ndarray:
        """Generate initial points using grid + jitter."""
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        
        grid_size = int(np.sqrt(num_points))
        jitter = min(width, height) / (grid_size * 3) * jitter_ratio
        step_x = width / grid_size
        step_y = height / grid_size
        
        points = []
        for i in range(grid_size):
            for j in range(grid_size):
                x = min_x + i * step_x + step_x / 2 + random.uniform(-jitter, jitter)
                y = min_y + j * step_y + step_y / 2 + random.uniform(-jitter, jitter)
                if min_x <= x <= max_x and min_y <= y <= max_y:
                    points.append([x, y])
                if len(points) >= num_points:
                    break
            if len(points) >= num_points:
                break
        
        return np.array(points)
    
    def _relax_points(
        self,
        points: np.ndarray,
        terrain: TerrainProvider,
        extent: Tuple[float, float, float, float],
        iterations: int,
    ) -> np.ndarray:
        """Relax points toward topographic features."""
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        sample_distance = min(width, height) / 20.0
        
        points = points.copy().astype(float)
        
        for iteration in range(iterations):
            new_points = points.copy()
            
            for i, (x, y) in enumerate(points):
                # Sample terrain around point
                neighbors = [
                    (x - sample_distance, y),
                    (x + sample_distance, y),
                    (x, y - sample_distance),
                    (x, y + sample_distance),
                    (x, y),  # Center
                ]
                
                elevations = [terrain.evaluate(nx, ny) for nx, ny in neighbors]
                center_elev = elevations[4]
                
                # Compute gradient (slope direction)
                grad_x = (elevations[1] - elevations[0]) / (2 * sample_distance)
                grad_y = (elevations[3] - elevations[2]) / (2 * sample_distance)
                
                # Normalize gradient
                grad_mag = np.sqrt(grad_x**2 + grad_y**2)
                if grad_mag > 1e-6:
                    grad_x /= grad_mag
                    grad_y /= grad_mag
                
                # Determine attraction direction based on mode
                if self._attraction_mode == "peak":
                    # Move uphill (follow gradient)
                    attraction_x = grad_x
                    attraction_y = grad_y
                    elevation_factor = 1.0 if center_elev > 0 else -1.0
                elif self._attraction_mode == "slope":
                    # Move toward steepest slope
                    attraction_x = grad_x
                    attraction_y = grad_y
                    elevation_factor = grad_mag
                elif self._attraction_mode == "valley":
                    # Move downhill (opposite of gradient)
                    attraction_x = -grad_x
                    attraction_y = -grad_y
                    elevation_factor = 1.0 if center_elev < 0 else -1.0
                else:
                    attraction_x = 0.0
                    attraction_y = 0.0
                    elevation_factor = 0.0
                
                # Combine influences
                move_x = (
                    self._elevation_influence * elevation_factor * (elevations[1] - elevations[0]) / (2 * sample_distance) +
                    self._slope_influence * attraction_x
                )
                move_y = (
                    self._elevation_influence * elevation_factor * (elevations[3] - elevations[2]) / (2 * sample_distance) +
                    self._slope_influence * attraction_y
                )
                
                # Apply movement with damping
                step_size = min(width, height) / 100.0
                new_x = x + move_x * step_size
                new_y = y + move_y * step_size
                
                # Clamp to extent
                new_x = np.clip(new_x, min_x, max_x)
                new_y = np.clip(new_y, min_y, max_y)
                
                new_points[i] = [new_x, new_y]
            
            points = new_points
        
        return points
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "topography_responsive_voronoi",
            "num_points": self._num_points,
            "jitter_ratio": self._jitter_ratio,
            "elevation_influence": self._elevation_influence,
            "slope_influence": self._slope_influence,
            "relaxation_iterations": self._relaxation_iterations,
            "attraction_mode": self._attraction_mode,
        }
