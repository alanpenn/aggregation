"""
Carrier space and elementary cells for the morphic grammar experiments.

Definitions
-----------
Carrier space : the rectangular domain ``extent`` within which cells exist.
Cell          : a polygon with a stable integer identifier.
Adjacency     : two cells are adjacent iff their shared boundary has positive
                length (> ``ADJACENCY_EPS``). Point contact does not count.
Boundary cell : a cell whose boundary shares positive length with the
                carrier-space boundary.

Discretisation assumptions
--------------------------
* Adjacency is edge adjacency only. Two open cells touching at a single
  vertex are NOT connected, so an enclosure whose occupied cells meet only
  at vertices still counts as closed for open-space connectivity.
* Adjacency is recomputed from clipped cell polygons rather than taken from
  the Voronoi ridge list, because a ridge can lie wholly outside the carrier
  and would then give a false adjacency.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, box

ADJACENCY_EPS = 1e-6

Extent = Tuple[float, float, float, float]


@dataclass
class Carrier:
    """A carrier space partitioned into cells with a precomputed adjacency."""

    polygons: Dict[int, Polygon]
    extent: Extent
    adjacency: Dict[int, Dict[int, float]] = field(default_factory=dict)
    boundary_length: Dict[int, float] = field(default_factory=dict)
    elevations: Dict[int, float] = field(default_factory=dict)
    metadata: Dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_polygons(
        cls,
        polygons: Dict[int, Polygon],
        extent: Extent,
        elevations: Optional[Dict[int, float]] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> "Carrier":
        adjacency: Dict[int, Dict[int, float]] = {cell: {} for cell in polygons}
        ids = sorted(polygons)
        for position, left in enumerate(ids):
            left_poly = polygons[left]
            for right in ids[position + 1:]:
                right_poly = polygons[right]
                if not left_poly.intersects(right_poly):
                    continue
                shared = left_poly.boundary.intersection(right_poly.boundary).length
                if shared > ADJACENCY_EPS:
                    adjacency[left][right] = shared
                    adjacency[right][left] = shared

        outline = box(*extent).exterior
        boundary_length = {
            cell: polygons[cell].boundary.intersection(outline).length
            for cell in ids
        }
        return cls(
            polygons=dict(polygons),
            extent=extent,
            adjacency=adjacency,
            boundary_length=boundary_length,
            elevations=dict(elevations or {}),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_square_grid(cls, columns: int, rows: int, cell_size: float = 1.0) -> "Carrier":
        """Hand-definable rectangular carrier; cell id = row * columns + column."""
        polygons = {
            row * columns + column: box(
                column * cell_size, row * cell_size,
                (column + 1) * cell_size, (row + 1) * cell_size,
            )
            for row in range(rows)
            for column in range(columns)
        }
        extent = (0.0, 0.0, columns * cell_size, rows * cell_size)
        return cls.from_polygons(polygons, extent, metadata={"type": "square_grid"})

    @property
    def cells(self) -> List[int]:
        return sorted(self.polygons)

    @property
    def boundary_cells(self) -> frozenset:
        return frozenset(c for c, length in self.boundary_length.items() if length > ADJACENCY_EPS)

    def neighbours(self, cell: int) -> List[int]:
        return sorted(self.adjacency[cell])

    def centroid(self, cell: int) -> Tuple[float, float]:
        point = self.polygons[cell].centroid
        return point.x, point.y

    def perimeter(self, cells: Iterable[int]) -> float:
        """Length of the boundary of the union of ``cells``, carrier edges included."""
        cell_set = set(cells)
        total = 0.0
        for cell in cell_set:
            total += self.boundary_length[cell]
            for neighbour, length in self.adjacency[cell].items():
                if neighbour not in cell_set:
                    total += length
        return total

    def graph(self, cells: Optional[Iterable[int]] = None) -> nx.Graph:
        """Adjacency graph induced on ``cells`` (all cells by default)."""
        nodes = self.cells if cells is None else sorted(cells)
        node_set = set(nodes)
        graph = nx.Graph()
        graph.add_nodes_from(nodes)
        for cell in nodes:
            for neighbour in self.adjacency[cell]:
                if neighbour in node_set and cell < neighbour:
                    graph.add_edge(cell, neighbour)
        return graph


def _sample_points(num_cells: int, extent: Extent, rng: np.random.Generator) -> np.ndarray:
    """Jittered-grid sampling giving exactly ``num_cells`` points.

    The existing VoronoiGridGenerator returns int(sqrt(N))**2 points (196 for
    N=200), so exact counts are produced here: a jittered square grid with at
    least N sites, from which surplus sites are removed uniformly at random.
    """
    min_x, min_y, max_x, max_y = extent
    side = int(np.ceil(np.sqrt(num_cells)))
    step_x = (max_x - min_x) / side
    step_y = (max_y - min_y) / side
    jitter_x, jitter_y = step_x / 3, step_y / 3
    points = [
        (
            min_x + (i + 0.5) * step_x + rng.uniform(-jitter_x, jitter_x),
            min_y + (j + 0.5) * step_y + rng.uniform(-jitter_y, jitter_y),
        )
        for i in range(side)
        for j in range(side)
    ]
    keep = np.sort(rng.choice(len(points), size=num_cells, replace=False))
    return np.array([points[index] for index in keep])


def build_voronoi_carrier(
    num_cells: int = 200,
    seed: int = 40,
    terrain=None,
    canvas_size: float = 100.0,
) -> Carrier:
    """Build a Voronoi carrier, reusing the app's clipped-cell construction.

    ``terrain`` is an optional TerrainProvider; it only supplies the elevation
    attribute of each cell. The grammar rules in this module do not use it.
    """
    from ..core import ExperimentPipeline
    from ..orchestrator import ExperimentOrchestrator

    extent: Extent = (0.0, 0.0, canvas_size, canvas_size)
    rng = np.random.default_rng(seed)
    points = _sample_points(num_cells, extent, rng)
    voronoi = Voronoi(points)
    helper = ExperimentOrchestrator(ExperimentPipeline(canvas_size=canvas_size))
    polygons = helper._finite_voronoi_polygons(voronoi, extent)
    missing = [index for index in range(len(points)) if index not in polygons]
    if missing:
        raise ValueError(f"Could not construct polygons for cells {missing}")

    elevations = {}
    if terrain is not None:
        elevations = {
            index: float(terrain.evaluate(float(x), float(y)))
            for index, (x, y) in enumerate(points)
        }
    return Carrier.from_polygons(
        polygons,
        extent,
        elevations=elevations,
        metadata={"type": "voronoi", "num_cells": num_cells, "seed": seed},
    )
