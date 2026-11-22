"""Positive-length shared boundaries for clipped cell polygons."""

from shapely.strtree import STRtree


def face_adjacency(cell_ids, polygons):
    """Return the symmetric graph with shared boundary lengths as weights."""
    ids = sorted(cell_ids)
    graph = {cell: {} for cell in ids}
    if not ids:
        return graph
    tree = STRtree([polygons[cell].envelope for cell in ids])
    for left in ids:
        boundary = polygons[left].boundary
        for index in tree.query(polygons[left].envelope):
            right = ids[int(index)]
            if right <= left:
                continue
            length = boundary.intersection(polygons[right].boundary).length
            if length > 0:
                graph[left][right] = graph[right][left] = length
    return graph
