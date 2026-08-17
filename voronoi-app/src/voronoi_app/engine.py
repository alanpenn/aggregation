import random
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import networkx as nx
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import LineString, Polygon

from .config import ExperimentConfig


@dataclass
class SimulationResult:
    config: ExperimentConfig
    points: np.ndarray
    voronoi: Voronoi
    buildings: Set[int]
    open_spaces: Set[int]
    doors: List[Tuple[int, int]]
    building_labels: Dict[int, int]
    visibility_graph: nx.Graph
    mean_depth: Dict[int, float]
    los_lines: List[LineString]


class VoronoiEngine:
    def __init__(self, config: ExperimentConfig):
        config.validate()
        self.config = config

        if config.seed is not None:
            random.seed(config.seed)
            np.random.seed(config.seed)

        self.num_points = config.num_points
        self.canvas_size = config.canvas_size
        self.slope_preference = config.slope_preference
        self.max_dyads = config.max_dyads
        self.stagnation_limit = config.stagnation_limit

        self.points = self.generate_poisson_disk_points()
        self.voronoi = Voronoi(self.points)

        self.buildings: Set[int] = set()
        self.open_spaces: Set[int] = set()
        self.vacant: Set[int] = set()
        self.doors: List[Tuple[int, int]] = []
        self.los_lines: List[LineString] = []
        self.building_labels: Dict[int, int] = {}

    def hill_elevation(self, x, y):
        cy = self.canvas_size / 2
        sigma = self.canvas_size / 6
        return np.exp(-(y - cy) ** 2 / (2 * sigma ** 2))

    def generate_poisson_disk_points(self, radius=2):
        points = []
        grid_size = int(np.sqrt(self.num_points))
        jitter = self.canvas_size / (grid_size * 3)
        step = self.canvas_size / grid_size
        for i in range(grid_size):
            for j in range(grid_size):
                x = i * step + step / 2 + random.uniform(-jitter, jitter)
                y = j * step + step / 2 + random.uniform(-jitter, jitter)
                if 0 <= x <= self.canvas_size and 0 <= y <= self.canvas_size:
                    points.append((x, y))
                if len(points) >= self.num_points:
                    break
            if len(points) >= self.num_points:
                break
        return np.array(points)

    def find_adjacent_regions(self, point_index):
        neighbors = set()
        for ridge in self.voronoi.ridge_points:
            if point_index in ridge:
                neighbor = ridge[1] if ridge[0] == point_index else ridge[0]
                neighbors.add(neighbor)
        return neighbors

    def aggregate(self):
        center = np.array([self.canvas_size / 2, self.canvas_size / 2])
        initial_open = np.argmin(np.linalg.norm(self.points - center, axis=1))
        self.open_spaces.add(initial_open)
        neighbors = list(self.find_adjacent_regions(initial_open))
        if not neighbors:
            return

        initial_building = random.choice(neighbors)
        self.buildings.add(initial_building)
        self.building_labels[initial_building] = 1
        self.doors.append((initial_open, initial_building))

        label_counter = 2
        stagnation = 0

        while len(self.buildings) < self.max_dyads and stagnation < self.stagnation_limit:
            candidates = list(self.open_spaces)
            random.shuffle(candidates)
            placed = False

            for open_idx in candidates:
                neighbors = list(self.find_adjacent_regions(open_idx))
                neighbors = [
                    n for n in neighbors
                    if n not in self.buildings and n not in self.open_spaces
                ]
                if not neighbors:
                    continue

                neighbors.sort(
                    key=lambda n: (
                        (1 - self.slope_preference) * random.random()
                        - abs(
                            self.hill_elevation(*self.points[n])
                            - self.hill_elevation(*self.points[open_idx])
                        )
                        * self.slope_preference
                    )
                )
                new_open = neighbors[0]
                self.open_spaces.add(new_open)

                next_neighbors = list(self.find_adjacent_regions(new_open))
                next_neighbors = [
                    n for n in next_neighbors
                    if n not in self.buildings and n not in self.open_spaces
                ]
                if not next_neighbors:
                    self.open_spaces.remove(new_open)
                    continue

                next_neighbors.sort(
                    key=lambda n: (
                        -abs(
                            self.hill_elevation(*self.points[n])
                            - self.hill_elevation(*self.points[new_open])
                        )
                        * self.slope_preference
                        + (1 - self.slope_preference) * random.random()
                    )
                )
                new_building = next_neighbors[0]
                self.buildings.add(new_building)
                self.building_labels[new_building] = label_counter
                label_counter += 1
                self.doors.append((new_open, new_building))
                placed = True
                break

            if not placed:
                stagnation += 1

    def compute_visibility_graph(self):
        graph = nx.Graph()
        building_polys = []
        region_polys = {}

        for idx in self.buildings:
            region = self.voronoi.regions[self.voronoi.point_region[idx]]
            if region is None or len(region) == 0 or -1 in region:
                continue
            coords = [self.voronoi.vertices[i] for i in region if i >= 0]
            if len(coords) >= 3:
                poly = Polygon(coords)
                if poly.is_valid:
                    building_polys.append(poly)

        all_open = self.open_spaces | self.vacant
        for idx in all_open:
            region = self.voronoi.regions[self.voronoi.point_region[idx]]
            if region is None or len(region) == 0 or -1 in region:
                continue
            coords = [self.voronoi.vertices[i] for i in region if i >= 0]
            if len(coords) >= 3:
                poly = Polygon(coords)
                if poly.is_valid:
                    graph.add_node(idx)
                    region_polys[idx] = poly

        for i, pi in region_polys.items():
            for j, pj in region_polys.items():
                if i >= j:
                    continue
                if pi.touches(pj):
                    graph.add_edge(i, j)
                    continue

                visible = False
                for p1 in pi.exterior.coords:
                    for p2 in pj.exterior.coords:
                        line = LineString([p1, p2])
                        if any(b.intersects(line) for b in building_polys):
                            continue
                        graph.add_edge(i, j)
                        self.los_lines.append(line)
                        visible = True
                        break
                    if visible:
                        break

        return graph

    def run(self) -> SimulationResult:
        self.aggregate()
        graph = self.compute_visibility_graph()

        mean_depth: Dict[int, float] = {}
        if graph.number_of_nodes() > 0:
            for node in graph.nodes:
                lengths = nx.single_source_shortest_path_length(graph, node)
                mean_depth[node] = sum(lengths.values()) / len(graph)

        return SimulationResult(
            config=self.config,
            points=self.points,
            voronoi=self.voronoi,
            buildings=self.buildings,
            open_spaces=self.open_spaces,
            doors=self.doors,
            building_labels=self.building_labels,
            visibility_graph=graph,
            mean_depth=mean_depth,
            los_lines=self.los_lines,
        )
