"""Geometric axial-line maps and graph conversion."""

from dataclasses import dataclass, field
from math import hypot, isfinite
from typing import Any, Dict, List, Tuple

from shapely.geometry import LineString, Point

from .core import Representation


Coordinate = Tuple[float, float]


@dataclass(frozen=True)
class AxialLine:
    """A finite axial line segment with a stable identifier."""

    line_id: int
    start: Coordinate
    end: Coordinate
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.line_id, int) or isinstance(self.line_id, bool):
            raise ValueError("line_id must be an integer")

        for endpoint_name in ("start", "end"):
            endpoint = getattr(self, endpoint_name)
            if len(endpoint) != 2:
                raise ValueError(f"{endpoint_name} must contain exactly two coordinates")
            coordinates = tuple(float(value) for value in endpoint)
            if not all(isfinite(value) for value in coordinates):
                raise ValueError(f"{endpoint_name} coordinates must be finite")
            object.__setattr__(self, endpoint_name, coordinates)

        if self.start == self.end:
            raise ValueError("an axial line must have non-zero length")

    @property
    def length(self) -> float:
        return hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])


@dataclass
class AxialMap:
    """A collection of axial line segments and their intersection graph."""

    lines: List[AxialLine]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(not isinstance(line, AxialLine) for line in self.lines):
            raise ValueError("lines must contain AxialLine instances")
        line_ids = [line.line_id for line in self.lines]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("axial line identifiers must be unique")

    def to_representation(self) -> Representation:
        """Create a graph whose nodes are lines and edges are point intersections."""
        line_geometries = {
            line.line_id: LineString((line.start, line.end))
            for line in self.lines
        }
        edges = []
        for index, left in enumerate(self.lines):
            for right in self.lines[index + 1:]:
                intersection = line_geometries[left.line_id].intersection(
                    line_geometries[right.line_id]
                )
                if isinstance(intersection, Point) and not intersection.is_empty:
                    edges.append((left.line_id, right.line_id))
                elif hasattr(intersection, "geoms"):
                    if any(
                        isinstance(geometry, Point) and not geometry.is_empty
                        for geometry in intersection.geoms
                    ):
                        edges.append((left.line_id, right.line_id))

        node_attributes = {}
        for line in self.lines:
            attributes = dict(line.attributes)
            attributes.update({
                "start": line.start,
                "end": line.end,
                "length": line.length,
                "symbol": attributes.get("symbol", "axial_line"),
            })
            node_attributes[line.line_id] = attributes

        return Representation(
            name="axial_map",
            nodes=sorted(line.line_id for line in self.lines),
            edges=sorted(edges),
            node_attributes=node_attributes,
            metadata={
                **self.metadata,
                "type": "axial_map",
                "source": "line_intersections",
            },
        )
