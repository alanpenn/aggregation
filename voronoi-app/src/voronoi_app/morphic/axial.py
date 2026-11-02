"""Sampled maximal-line axial approximation and graph diagnostics.

Axial maps are not uniquely recoverable from a polygonal domain. This module
therefore provides a documented approximation, not a conventional or
complete axial map:

1. Sample interior points on a regular grid.
2. Cast lines through those points at uniformly spaced orientations.
3. Keep the maximal contiguous segment of open geometry containing the sample.
4. Greedily select long candidates that cover sampled open-space locations.
5. Connect selected lines only where they cross inside open geometry.

The sampling interval and angular resolution are recorded in each result.
"""

from dataclasses import dataclass
from math import log2
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx
import numpy as np
from scipy.stats import pearsonr
from shapely.geometry import LineString, MultiLineString, Point
from shapely.geometry.base import BaseGeometry

from .open_space import open_space_geometry
from .carrier import Carrier


@dataclass(frozen=True)
class AxialLine:
    id: int
    geometry: LineString
    length: float
    covered_samples: Tuple[int, ...]


@dataclass
class AxialRepresentation:
    method: str
    settings: Dict[str, float]
    open_geometry: BaseGeometry
    lines: List[AxialLine]
    graph: nx.Graph
    candidate_count: int
    sample_count: int = 0
    covered_sample_count: int = 0


def _line_parts(geometry: BaseGeometry) -> List[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    if hasattr(geometry, "geoms"):
        return [part for item in geometry.geoms for part in _line_parts(item)]
    return []


def _interior_samples(geometry: BaseGeometry, spacing: float) -> List[Point]:
    min_x, min_y, max_x, max_y = geometry.bounds
    # Quarter-step phase avoids regularly aligning samples with common cell
    # boundaries (which can miss narrow corridor arms in synthetic geometry).
    xs = np.arange(min_x + spacing / 4, max_x, spacing)
    ys = np.arange(min_y + spacing / 4, max_y, spacing)
    samples = [
        Point(float(x), float(y))
        for y in ys
        for x in xs
        if geometry.contains(Point(float(x), float(y)))
    ]
    if not samples:
        samples = [geometry.representative_point()]
    return samples


def _maximal_chord(
    domain: BaseGeometry,
    origin: Point,
    angle: float,
    extent_diagonal: float,
) -> Optional[LineString]:
    dx, dy = np.cos(angle), np.sin(angle)
    ray = LineString([
        (origin.x - 2 * extent_diagonal * dx, origin.y - 2 * extent_diagonal * dy),
        (origin.x + 2 * extent_diagonal * dx, origin.y + 2 * extent_diagonal * dy),
    ])
    parts = _line_parts(domain.intersection(ray))
    tolerance = max(extent_diagonal * 1e-9, 1e-8)
    containing = [part for part in parts if part.distance(origin) <= tolerance]
    if not containing:
        return None
    return max(containing, key=lambda part: part.length)


def _canonical_key(line: LineString, precision: int = 5) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    coords = list(line.coords)
    endpoints = [tuple(round(float(v), precision) for v in coords[0]),
                 tuple(round(float(v), precision) for v in coords[-1])]
    return tuple(sorted(endpoints))  # type: ignore[return-value]


def _intersection_inside_domain(
    left: LineString, right: LineString, domain: BaseGeometry
) -> bool:
    intersection = left.intersection(right)
    if intersection.is_empty:
        return False
    points = []
    if isinstance(intersection, Point):
        points = [intersection]
    elif hasattr(intersection, "geoms"):
        points = [part for part in intersection.geoms if isinstance(part, Point)]
    return any(domain.covers(point) for point in points)


def extract_axial_representation(
    open_geometry: BaseGeometry,
    sample_spacing: float = 8.0,
    angle_step_degrees: float = 15.0,
    coverage_tolerance: Optional[float] = None,
) -> AxialRepresentation:
    """Extract a greedy sampled maximal-line approximation from open geometry.

    Candidate lines are straight and entirely contained in one contiguous
    portion of the open geometry. Selected lines greedily cover interior
    samples, preferring the candidate covering the most still-uncovered
    samples, then greater length. The resulting lines are not guaranteed to
    be a minimal or unique axial map.
    """
    if sample_spacing <= 0:
        raise ValueError("sample_spacing must be positive")
    if not 0 < angle_step_degrees < 180:
        raise ValueError("angle_step_degrees must be between 0 and 180")
    if open_geometry.is_empty:
        graph = nx.Graph()
        return AxialRepresentation(
            "sampled_maximal_lines_v1",
            {"sample_spacing": sample_spacing, "angle_step_degrees": angle_step_degrees},
            open_geometry, [], graph, 0, 0, 0,
        )

    samples = _interior_samples(open_geometry, sample_spacing)
    min_x, min_y, max_x, max_y = open_geometry.bounds
    diagonal = float(np.hypot(max_x - min_x, max_y - min_y))
    angles = np.deg2rad(np.arange(0.0, 180.0, angle_step_degrees))

    candidates: Dict[Tuple[Tuple[float, float], Tuple[float, float]], LineString] = {}
    for sample in samples:
        for angle in angles:
            line = _maximal_chord(open_geometry, sample, float(angle), diagonal)
            if line is not None and line.length > 1e-8:
                candidates.setdefault(_canonical_key(line), line)

    tolerance = coverage_tolerance or sample_spacing * 0.55
    candidate_coverage: Dict[Tuple[Tuple[float, float], Tuple[float, float]], Set[int]] = {
        key: {index for index, point in enumerate(samples) if line.distance(point) <= tolerance}
        for key, line in candidates.items()
    }
    uncovered = set(range(len(samples)))
    selected: List[AxialLine] = []
    while uncovered:
        choices = [
            (len(cover & uncovered), line.length, key, line, cover)
            for key, line in candidates.items()
            if (cover := candidate_coverage[key]) & uncovered
        ]
        if not choices:
            break
        _, _, key, line, cover = max(choices, key=lambda item: (item[0], item[1], item[2]))
        selected.append(AxialLine(
            id=len(selected), geometry=line, length=float(line.length),
            covered_samples=tuple(sorted(cover)),
        ))
        uncovered -= cover
        candidates.pop(key)

    graph = nx.Graph()
    graph.add_nodes_from(line.id for line in selected)
    for position, left in enumerate(selected):
        for right in selected[position + 1:]:
            if _intersection_inside_domain(left.geometry, right.geometry, open_geometry):
                graph.add_edge(left.id, right.id)

    covered_samples = set().union(*(set(line.covered_samples) for line in selected)) if selected else set()
    return AxialRepresentation(
        method="sampled_maximal_lines_v1",
        settings={
            "sample_spacing": float(sample_spacing),
            "angle_step_degrees": float(angle_step_degrees),
            "coverage_tolerance": float(tolerance),
        },
        open_geometry=open_geometry,
        lines=selected,
        graph=graph,
        candidate_count=len(candidate_coverage),
        sample_count=len(samples),
        covered_sample_count=len(covered_samples),
    )


def extract_from_cells(
    carrier: Carrier,
    occupied: Iterable[int],
    sample_spacing: float = 8.0,
    angle_step_degrees: float = 15.0,
    coverage_tolerance: Optional[float] = None,
) -> AxialRepresentation:
    """Build continuous open geometry from cells, then extract axial lines."""
    geometry = open_space_geometry(carrier, occupied)
    if geometry is None:
        geometry = LineString()
    return extract_axial_representation(
        geometry, sample_spacing, angle_step_degrees, coverage_tolerance
    )


def _d_value(size: int) -> Optional[float]:
    if size <= 2:
        return None
    return 2 * (size * (log2((size + 2) / 3) - 1) + 1) / ((size - 1) * (size - 2))


def _integration_for_depths(depths: Sequence[int], component_size: int) -> Optional[float]:
    if component_size <= 2 or not depths:
        return None
    mean_depth = float(np.mean(depths))
    ra = 2 * (mean_depth - 1) / (component_size - 2)
    d_value = _d_value(component_size)
    if d_value is None or ra <= 0:
        return None
    return float(1 / (ra / d_value))


def axial_diagnostics(
    representation: AxialRepresentation, local_radius: int = 3
) -> Dict[str, object]:
    """Compute axial graph measures and intelligibility.

    Global integration is Hillier-Hanson real relative asymmetry (RRA):
    ``Integration = 1 / (RA / Dk)``, with ``RA = 2(MD - 1)/(k - 2)`` and
    ``Dk = 2*(k*(log2((k+2)/3)-1)+1)/((k-1)*(k-2))``. Here k is the size of
    the node's connected component; disconnected components are analysed
    independently. Values for components smaller than 3, or degenerate RRA,
    are undefined (None). Local integration applies the same formula to the
    radius-limited reachable neighbourhood.
    """
    if local_radius < 1:
        raise ValueError("local_radius must be >= 1")
    graph = representation.graph
    components = list(nx.connected_components(graph))
    component_sizes = {node: len(component) for component in components for node in component}
    connectivity = dict(graph.degree())
    mean_depth: Dict[int, Optional[float]] = {}
    global_integration: Dict[int, Optional[float]] = {}
    local_integration: Dict[int, Optional[float]] = {}

    for node in graph:
        distances = nx.single_source_shortest_path_length(graph, node)
        depth_values = [distance for other, distance in distances.items() if other != node]
        mean_depth[node] = float(np.mean(depth_values)) if depth_values else None
        global_integration[node] = _integration_for_depths(
            [d for other, d in distances.items() if other != node], component_sizes[node]
        )
        local_nodes = [other for other, distance in distances.items() if distance <= local_radius]
        local_depths = [
            nx.shortest_path_length(graph.subgraph(local_nodes), node, other)
            for other in local_nodes if other != node
        ]
        local_integration[node] = _integration_for_depths(local_depths, len(local_nodes))

    valid = [
        (float(connectivity[node]), value)
        for node, value in global_integration.items()
        if value is not None
    ]
    if len(valid) < 3 or len({x for x, _ in valid}) < 2 or len({y for _, y in valid}) < 2:
        pearson = r_squared = None
    else:
        pearson = float(pearsonr([x for x, _ in valid], [y for _, y in valid])[0])
        r_squared = pearson ** 2

    cycle_rank = graph.number_of_edges() - graph.number_of_nodes() + len(components)
    return {
        "method": representation.method,
        "axial_line_count": len(representation.lines),
        "candidate_line_count": representation.candidate_count,
        "open_sample_count": representation.sample_count,
        "covered_sample_count": representation.covered_sample_count,
        "sample_coverage_fraction": (
            representation.covered_sample_count / representation.sample_count
            if representation.sample_count else None
        ),
        "intersection_count": graph.number_of_edges(),
        "component_count": len(components),
        "cycle_rank": cycle_rank,
        "connectivity": connectivity,
        "mean_depth": mean_depth,
        "global_integration_rra": global_integration,
        "local_integration_rra": local_integration,
        "intelligibility_pearson": pearson,
        "intelligibility_r_squared": r_squared,
        "intelligibility_n": len(valid),
        "connectivity_distribution": list(connectivity.values()),
        "mean_depth_distribution": [v for v in mean_depth.values() if v is not None],
        "global_integration_distribution": [v for v in global_integration.values() if v is not None],
        "local_integration_distribution": [v for v in local_integration.values() if v is not None],
        "line_lengths": [line.length for line in representation.lines],
        "local_radius": local_radius,
    }
