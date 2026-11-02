"""
Morphological primitives on a carrier and a set of occupied cells.

Definitions
-----------
Occupied cell         : a cell designated building/solid.
Open cell             : any cell that is not occupied.
Aggregate             : a connected component of occupied cells in the
                        cell adjacency graph.
Exterior open space   : open cells connected through open-cell adjacency to an
                        open boundary cell of the carrier (a boundary cell is
                        itself exterior when open).
Enclosed open space   : an open-cell component containing no boundary cell.
Graph cycle           : a cycle in the occupied adjacency graph. Measured as the
                        cyclomatic number E - V + C (independent cycles).
Geometric enclosure   : existence of an enclosed open component. A graph cycle
                        does not imply enclosure (e.g. a 2x2 block, or three
                        Voronoi cells meeting at a vertex, is a cycle with no
                        interior open space) and enclosure does not require a
                        single cycle (several partial rings can close a hole).
"""

from typing import Dict, FrozenSet, Iterable, List, Set

import networkx as nx
from shapely.ops import unary_union

from .carrier import Carrier

OCCUPIED = "occupied"
EXTERIOR_OPEN = "exterior_open"
ENCLOSED_OPEN = "enclosed_open"


def connected_components(graph: nx.Graph) -> List[FrozenSet[int]]:
    """Components, ordered by their smallest cell id for determinism."""
    components = [frozenset(component) for component in nx.connected_components(graph)]
    return sorted(components, key=min)


def occupied_components(carrier: Carrier, occupied: Iterable[int]) -> List[FrozenSet[int]]:
    return connected_components(carrier.graph(occupied))


def open_cells(carrier: Carrier, occupied: Iterable[int]) -> Set[int]:
    return set(carrier.cells) - set(occupied)


def open_components(carrier: Carrier, occupied: Iterable[int]) -> List[FrozenSet[int]]:
    return connected_components(carrier.graph(open_cells(carrier, occupied)))


def exterior_open_cells(carrier: Carrier, occupied: Iterable[int]) -> Set[int]:
    boundary = carrier.boundary_cells
    exterior: Set[int] = set()
    for component in open_components(carrier, occupied):
        if component & boundary:
            exterior |= component
    return exterior


def enclosed_open_components(carrier: Carrier, occupied: Iterable[int]) -> List[FrozenSet[int]]:
    boundary = carrier.boundary_cells
    return [c for c in open_components(carrier, occupied) if not (c & boundary)]


def aggregate_boundary_cells(carrier: Carrier, occupied: Iterable[int]) -> Set[int]:
    """Occupied cells touching an open cell or the carrier boundary."""
    occupied_set = set(occupied)
    return {
        cell
        for cell in occupied_set
        if carrier.boundary_length[cell] > 0
        or any(n not in occupied_set for n in carrier.adjacency[cell])
    }


def candidate_cells(carrier: Carrier, occupied: Iterable[int]) -> List[int]:
    """Unoccupied cells sharing a boundary with the occupied set."""
    occupied_set = set(occupied)
    found = {
        neighbour
        for cell in occupied_set
        for neighbour in carrier.adjacency[cell]
        if neighbour not in occupied_set
    }
    return sorted(found)


def graph_cycle_count(carrier: Carrier, occupied: Iterable[int]) -> int:
    """Cyclomatic number E - V + C of the occupied adjacency graph."""
    graph = carrier.graph(occupied)
    if graph.number_of_nodes() == 0:
        return 0
    return graph.number_of_edges() - graph.number_of_nodes() + nx.number_connected_components(graph)


def triangle_count(carrier: Carrier, occupied: Iterable[int]) -> int:
    """Number of 3-cliques in the occupied graph (three cells meeting at a vertex)."""
    return sum(nx.triangles(carrier.graph(occupied)).values()) // 3


def nontrivial_cycle_count(carrier: Carrier, occupied: Iterable[int]) -> int:
    """Cyclomatic number minus triangles.

    On Voronoi cells every vertex where three occupied cells meet adds a
    trivial 3-cycle that encloses nothing, so the raw cyclomatic number
    mostly counts vertices. Subtracting triangles leaves independent cycles
    bounding larger faces (candidate courtyards or merely open notches).
    """
    return graph_cycle_count(carrier, occupied) - triangle_count(carrier, occupied)


def graph_cycles(carrier: Carrier, occupied: Iterable[int]) -> List[List[int]]:
    """A cycle basis of the occupied adjacency graph."""
    return nx.cycle_basis(carrier.graph(occupied))


def enclosure_score(carrier: Carrier, occupied: Iterable[int], target: Iterable[int]) -> float:
    """Fraction of the target's boundary length that is shared with occupied cells.

    ``target`` is a set of cells. Its perimeter is the length of the boundary
    of the union of those cells, carrier-edge contact included (carrier edge
    can never be occupied, so a target on the carrier boundary scores < 1).
    Score is in [0, 1]; 1 means every boundary segment of the target is
    occupied, i.e. a complete surrounding boundary.
    """
    target_set = set(target)
    occupied_set = set(occupied)
    perimeter = carrier.perimeter(target_set)
    if perimeter == 0:
        return 0.0
    shared = sum(
        length
        for cell in target_set
        for neighbour, length in carrier.adjacency[cell].items()
        if neighbour in occupied_set and neighbour not in target_set
    )
    return shared / perimeter


def is_target_enclosed(carrier: Carrier, occupied: Iterable[int], target: Iterable[int]) -> bool:
    """True if every target cell lies in an enclosed open component."""
    target_set = set(target)
    occupied_set = set(occupied)
    if target_set & occupied_set:
        return False
    enclosed: Set[int] = set()
    for component in enclosed_open_components(carrier, occupied_set):
        enclosed |= component
    return target_set <= enclosed


def classify_cells(carrier: Carrier, occupied: Iterable[int]) -> Dict[int, str]:
    occupied_set = set(occupied)
    exterior = exterior_open_cells(carrier, occupied_set)
    categories = {}
    for cell in carrier.cells:
        if cell in occupied_set:
            categories[cell] = OCCUPIED
        elif cell in exterior:
            categories[cell] = EXTERIOR_OPEN
        else:
            categories[cell] = ENCLOSED_OPEN
    return categories


def aggregate_geometry(carrier: Carrier, occupied: Iterable[int]):
    """Union of occupied cell polygons (None when nothing is occupied)."""
    polygons = [carrier.polygons[cell] for cell in occupied]
    return unary_union(polygons) if polygons else None
