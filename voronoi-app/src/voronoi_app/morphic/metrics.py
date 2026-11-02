"""
Quantitative analysis of a configuration.

Graphs analysed (never mixed):
* occupied adjacency graph : occupied cells, edges = shared boundary. Used for
  components and cycles.
* open-space accessibility graph : open cells, edges = shared boundary between
  open cells. Used for open-space components and connectivity.

Undefined quantities are returned as ``None`` (never an arbitrary zero).

Compactness is the isoperimetric (Polsby-Popper) quotient 4*pi*A / P**2 of
the union of occupied cells, where P includes hole boundaries and carrier-edge
contact. It is 1 for a disc and smaller for ragged or elongated shapes. For a
disconnected configuration it describes the union, not any single aggregate.
"""

import math
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from ..analysis import ConnectivityMeasure
from ..core import Representation
from . import morphology as mo
from .carrier import Carrier


def open_connectivity_values(carrier: Carrier, occupied: Iterable[int]) -> Dict[int, float]:
    """Degree of each open cell in the open-space accessibility graph.

    Reuses the app's ConnectivityMeasure on an explicit Representation.
    """
    open_set = mo.open_cells(carrier, occupied)
    graph = carrier.graph(open_set)
    representation = Representation(
        name="cell_graph",
        nodes=sorted(open_set),
        edges=sorted(graph.edges()),
        metadata={"graph": "open_space_accessibility"},
    )
    return ConnectivityMeasure().compute(representation)


def measure_configuration(
    carrier: Carrier,
    occupied: Iterable[int],
    target: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    occupied_set = set(occupied)
    open_set = mo.open_cells(carrier, occupied_set)
    occupied_parts = mo.occupied_components(carrier, occupied_set)
    open_parts = mo.open_components(carrier, occupied_set)
    enclosed = mo.enclosed_open_components(carrier, occupied_set)
    exterior = mo.exterior_open_cells(carrier, occupied_set)

    occupied_area = sum(carrier.polygons[c].area for c in occupied_set)
    perimeter: Optional[float] = None
    compactness: Optional[float] = None
    if occupied_set:
        geometry = mo.aggregate_geometry(carrier, occupied_set)
        perimeter = float(geometry.boundary.length)
        if perimeter > 0:
            compactness = 4 * math.pi * occupied_area / perimeter ** 2

    values = list(open_connectivity_values(carrier, occupied_set).values())
    result: Dict[str, Any] = {
        "n_occupied": len(occupied_set),
        "n_occupied_components": len(occupied_parts),
        "largest_occupied_component": max((len(c) for c in occupied_parts), default=None),
        "n_open_cells": len(open_set),
        "n_open_components": len(open_parts),
        "n_exterior_open_cells": len(exterior),
        "n_enclosed_open_components": len(enclosed),
        "n_enclosed_open_cells": sum(len(c) for c in enclosed),
        "enclosed_open_area": float(sum(carrier.polygons[c].area for cell_set in enclosed for c in cell_set)),
        "occupied_graph_cycles": mo.graph_cycle_count(carrier, occupied_set),
        "occupied_triangles": mo.triangle_count(carrier, occupied_set),
        "occupied_nontrivial_cycles": mo.nontrivial_cycle_count(carrier, occupied_set),
        "occupied_area": float(occupied_area),
        "aggregate_perimeter": perimeter,
        "compactness": compactness,
        "open_connectivity_mean": float(np.mean(values)) if values else None,
        "open_connectivity_std": float(np.std(values)) if values else None,
        "open_connectivity_min": float(min(values)) if values else None,
        "open_connectivity_max": float(max(values)) if values else None,
    }
    if target is not None:
        target_set = set(target)
        result["target_enclosure_score"] = mo.enclosure_score(carrier, occupied_set, target_set)
        result["target_enclosed"] = mo.is_target_enclosed(carrier, occupied_set, target_set)
        result["target_fully_surrounded"] = result["target_enclosure_score"] >= 1.0 - 1e-9
    else:
        result["target_enclosure_score"] = None
        result["target_enclosed"] = None
        result["target_fully_surrounded"] = None
    return result


def connectivity_distribution(carrier: Carrier, occupied: Iterable[int]) -> List[float]:
    return list(open_connectivity_values(carrier, occupied).values())
