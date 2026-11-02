"""
Experiment orchestrator: combines terrain, grid, aggregation, and analysis.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import networkx as nx
import numpy as np
from shapely.geometry import Polygon, LineString, box
from shapely.prepared import prep

from .core import (
    ExperimentPipeline, Representation, Grid, TerrainMetadata,
    AggregationResult
)
from .registry import get_registry


@dataclass
class ExperimentOutput:
    """Complete output from an experiment run."""
    pipeline: ExperimentPipeline
    terrain_sample: Dict[str, Any]
    grid: Grid
    aggregation: AggregationResult
    visibility_graph: nx.Graph
    representation: Representation
    analysis_results: Dict[str, Dict[int, float]]
    
    # For backwards compatibility with old rendering
    @property
    def voronoi(self):
        return self.grid.metadata.get("voronoi")
    
    @property
    def points(self):
        import numpy as np
        return np.array(self.grid.nodes)
    
    @property
    def buildings(self):
        return self.aggregation.buildings
    
    @property
    def open_spaces(self):
        return self.aggregation.open_spaces
    
    @property
    def doors(self):
        return self.aggregation.doors
    
    @property
    def building_labels(self):
        return self.aggregation.building_labels
    
    @property
    def mean_depth(self):
        return self.analysis_results.get("mean_depth", {})
    
    @property
    def measure_name(self):
        return self.pipeline.space_syntax_measure

    @property
    def measure_values(self):
        """Values of the measure selected in the pipeline."""
        return self.analysis_results.get(self.measure_name, {})

    @property
    def config(self):
        """For backwards compatibility with old render.py code."""
        return self.pipeline
    
    @property
    def los_lines(self):
        # Compute visibility lines from graph (for backwards compatibility)
        lines = []
        voronoi = self.voronoi
        if voronoi is None:
            return lines
        
        # This is a simplified version; full implementation would need geometry
        return lines


class ExperimentOrchestrator:
    """Runs a complete experiment pipeline."""
    
    def __init__(self, pipeline: ExperimentPipeline):
        self.pipeline = pipeline
        self.registry = get_registry()
    
    def run(self) -> ExperimentOutput:
        """Execute the full experiment."""
        # 1. Get terrain
        terrain = self.registry.get_terrain(
            self.pipeline.terrain_provider,
            self.pipeline.terrain_params,
        )
        
        # 2. Generate grid
        grid_gen = self.registry.get_grid(
            self.pipeline.grid_generator,
            self.pipeline.grid_params,
        )
        extent = (0, 0, self.pipeline.canvas_size, self.pipeline.canvas_size)
        grid = grid_gen.generate(
            terrain=terrain,
            extent=extent,
            seed=self.pipeline.seed
        )
        # Store extent in grid metadata for later use
        grid.metadata["extent"] = extent
        
        # 3. Run aggregation
        agg_strategy = self.registry.get_aggregation(
            self.pipeline.aggregation_strategy,
            self.pipeline.aggregation_params,
        )
        aggregation = agg_strategy.aggregate(
            terrain=terrain,
            grid=grid,
            form=self.pipeline.urban_form,
            seed=self.pipeline.seed
        )
        
        # 4. Build the selected open-space representation
        if self.pipeline.representation == "cell_graph":
            representation = self._build_cell_graph_representation(grid, aggregation)
        elif self.pipeline.representation == "visibility_graph":
            representation = self._build_visibility_graph_representation(grid, aggregation)
        else:
            raise ValueError(
                f"Unknown representation '{self.pipeline.representation}'. "
                "Expected 'cell_graph' or 'visibility_graph'."
            )
        
        # 5. Compute space-syntax measures
        measure_name = self.pipeline.space_syntax_measure
        measure = self.registry.get_measure(measure_name, self.pipeline.measure_params)
        analysis_results = {
            measure_name: measure.compute(representation)
        }
        
        # 6. Compute visibility graph
        visibility_graph = self._representation_to_graph(representation)
        
        # 7. Sample terrain field
        terrain_sample = terrain.sample_field(resolution=256)
        
        return ExperimentOutput(
            pipeline=self.pipeline,
            terrain_sample=terrain_sample,
            grid=grid,
            aggregation=aggregation,
            visibility_graph=visibility_graph,
            representation=representation,
            analysis_results=analysis_results,
        )
    
    def _build_cell_graph_representation(
        self,
        grid: Grid,
        aggregation: AggregationResult
    ) -> Representation:
        """Build an open-space graph using immediate grid adjacency."""
        open_spaces = set(aggregation.open_spaces)
        edges = [
            (left, right)
            for left, right in grid.edges
            if left in open_spaces and right in open_spaces
        ]
        return Representation(
            name="cell_graph",
            nodes=sorted(open_spaces),
            edges=edges,
            node_attributes={node: grid.node_attributes[node] for node in open_spaces},
            metadata={"type": "cell_graph", "source": "open_space_adjacency"}
        )
    
    def _build_visibility_graph_representation(
        self,
        grid: Grid,
        aggregation: AggregationResult
    ) -> Representation:
        """Connect open spaces when at least one clear sightline exists."""
        open_spaces = sorted(aggregation.open_spaces)
        polygons = self._space_polygons(grid)
        blocking_polygons = [polygons[index] for index in aggregation.buildings if index in polygons]
        blocking_geometry = None
        if blocking_polygons:
            from shapely.ops import unary_union
            blocking_geometry = prep(unary_union(blocking_polygons))

        # Adjacent open cells share a boundary and are therefore always
        # connected in the visibility graph. Longer sightlines are added below.
        edges = {
            (left, right) if left < right else (right, left)
            for left, right in grid.edges
            if left in aggregation.open_spaces and right in aggregation.open_spaces
        }
        for position, left in enumerate(open_spaces):
            for right in open_spaces[position + 1:]:
                left_polygon = polygons.get(left)
                right_polygon = polygons.get(right)
                if left_polygon is None or right_polygon is None:
                    continue
                if self._spaces_are_visible(left_polygon, right_polygon, blocking_geometry):
                    edges.add((left, right))

        return Representation(
            name="visibility_graph",
            nodes=open_spaces,
            edges=sorted(edges),
            node_attributes={node: grid.node_attributes[node] for node in open_spaces},
            metadata={"type": "visibility_graph", "source": "open_space_sightlines"}
        )

    def _representation_to_graph(self, representation: Representation) -> nx.Graph:
        graph = nx.Graph()
        graph.add_nodes_from(representation.nodes)
        graph.add_edges_from(representation.edges)
        return graph

    def _space_polygons(self, grid: Grid) -> Dict[int, Polygon]:
        """Return clipped polygons for grid nodes where geometry is available."""
        grid_type = grid.metadata.get("grid_type", "voronoi")
        extent = grid.metadata.get("extent", (0, 0, self.pipeline.canvas_size, self.pipeline.canvas_size))
        if grid_type in ("voronoi", "topography_responsive_voronoi"):
            voronoi = grid.metadata.get("voronoi")
            if voronoi is None:
                return {}
            return self._finite_voronoi_polygons(voronoi, extent)

        if grid_type == "cartesian":
            resolution = int(grid.metadata["resolution"])
            x_step = (extent[2] - extent[0]) / max(resolution - 1, 1)
            y_step = (extent[3] - extent[1]) / max(resolution - 1, 1)
            canvas = box(*extent)
            return {
                index: box(x - x_step / 2, y - y_step / 2, x + x_step / 2, y + y_step / 2).intersection(canvas)
                for index, (x, y) in enumerate(grid.nodes)
            }
        return {}

    def _finite_voronoi_polygons(self, voronoi, extent) -> Dict[int, Polygon]:
        """Construct finite Voronoi cells clipped to the experiment extent."""
        center = voronoi.points.mean(axis=0)
        radius = np.ptp(voronoi.points, axis=0).max() * 2
        ridge_map = {}
        for (left, right), (vertex_a, vertex_b) in zip(voronoi.ridge_points, voronoi.ridge_vertices):
            ridge_map.setdefault(left, []).append((right, vertex_a, vertex_b))
            ridge_map.setdefault(right, []).append((left, vertex_a, vertex_b))

        vertices = voronoi.vertices.tolist()
        canvas = box(*extent)
        polygons = {}
        for point_index, region_index in enumerate(voronoi.point_region):
            region = voronoi.regions[region_index]
            if not region:
                continue
            polygon_vertices = [vertices[index] for index in region if index >= 0]
            for neighbor, vertex_a, vertex_b in ridge_map.get(point_index, []):
                if vertex_a >= 0 and vertex_b >= 0:
                    continue
                tangent = voronoi.points[neighbor] - voronoi.points[point_index]
                tangent /= np.linalg.norm(tangent)
                normal = np.array([-tangent[1], tangent[0]])
                midpoint = voronoi.points[[point_index, neighbor]].mean(axis=0)
                direction = np.sign(np.dot(midpoint - center, normal)) * normal
                finite_vertex = vertex_b if vertex_a < 0 else vertex_a
                polygon_vertices.append((np.asarray(vertices[finite_vertex]) + direction * radius).tolist())
            if len(polygon_vertices) < 3:
                continue
            polygon = Polygon(polygon_vertices).convex_hull.intersection(canvas)
            if not polygon.is_empty and polygon.geom_type == "Polygon":
                polygons[point_index] = polygon
        return polygons

    def _spaces_are_visible(self, left, right, blocking_geometry) -> bool:
        """Test representative and boundary points for one unobstructed sightline."""
        left_points = [left.representative_point()] + list(left.exterior.coords[:-1])
        right_points = [right.representative_point()] + list(right.exterior.coords[:-1])
        for left_point in left_points:
            for right_point in right_points:
                sightline = LineString([left_point, right_point])
                if blocking_geometry is None or not blocking_geometry.intersects(sightline):
                    return True
        return False


# Helper function for convenience
def run_experiment_pipeline(pipeline: ExperimentPipeline) -> ExperimentOutput:
    """Run an experiment defined by a pipeline."""
    orchestrator = ExperimentOrchestrator(pipeline)
    return orchestrator.run()
