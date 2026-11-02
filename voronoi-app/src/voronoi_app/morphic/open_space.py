"""Continuous open-space geometry derived from a cellular configuration.

The returned geometry is the union of unoccupied cell polygons, including
their shared boundaries. It describes geometric openness, not pedestrian
permeability: this cellular grammar has no door or access restrictions.
"""

from typing import Iterable, Optional

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .carrier import Carrier
from .morphology import open_cells


def open_space_geometry(
    carrier: Carrier, occupied: Iterable[int]
) -> Optional[BaseGeometry]:
    """Return the union of open-cell polygons, or ``None`` if none remain."""
    polygons = [carrier.polygons[cell] for cell in open_cells(carrier, occupied)]
    return unary_union(polygons) if polygons else None
