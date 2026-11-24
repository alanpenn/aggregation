"""Exact ray-crossing cycle signatures for experimental axial deletions."""
from .angular import _exact_point, _intersections


class CycleSignatures:
    """Compute winding from the current graph, independently of previous faces.

    Coded intersection edges traverse a line from its start to the junction
    and back to the other line's start. Fundamental cycles span the noded
    arrangement's winding image, including when intervals share a subsegment.
    Each occupied cell has an interior probe. A cycle separating probes of
    one block is sent to the full exact face validator.
    """

    def __init__(self, lines, graph, polygons, blocks):
        self.masks = []
        probes = []
        for block in blocks:
            if block["kind"] == "boundary":
                continue
            start = len(probes)
            probes.extend(_exact_point(polygons[i].representative_point().coords[0])
                          for i in block["cells"])
            self.masks.append(((1 << len(probes)) - 1) ^ ((1 << start) - 1))
        self.required = len(self.masks)
        self.adjacency = {i: {} for i in graph}
        self.neighbors = {i: set(graph[i]) for i in graph}
        self.uniform_roots = []
        self.rays = []
        for line in lines:
            a,b = line.start,line.end
            rays = []
            for k,(x,y) in enumerate(probes):
                if (a[1]>y) == (b[1]>y):
                    continue
                crossing = a[0]+(b[0]-a[0])*(y-a[1])/(b[1]-a[1])
                if crossing>x:
                    rays.append((y,a[1]>y,1<<k))
            self.rays.append(rays)
        self.lines = lines
        self.graph = graph

    def edge(self, i, j):
        a,b = self.adjacency[i], self.adjacency[j]
        if j not in a:
            line,other = self.lines[i],self.lines[j]
            point=min(_intersections(line.start,line.end,other.start,other.end))
            y=point[1]
            value=0
            for k in (i,j):
                for crossing,above,bit in self.rays[k]:
                    if (y>crossing)!=above:
                        value ^= bit
            a[j]=b[i]=value
        return a[j]

    def rank(self, selected):
        if not selected:
            return 0
        uniform = any(selected <= root for root in self.uniform_roots)
        origin = min(selected)
        potentials = {origin: 0}
        pending = [origin]
        basis = {}
        for i in pending:
            for j in self.neighbors[i] & selected:
                value = potentials[i] ^ self.edge(i, j)
                if j not in potentials:
                    potentials[j] = value
                    pending.append(j)
                    continue
                value ^= potentials[j]
                while value:
                    pivot = value.bit_length()
                    if pivot in basis:
                        value ^= basis[pivot]
                        continue
                    basis[pivot] = value
                    if uniform:
                        if len(basis) == self.required:
                            return len(basis)
                    elif any((value & mask) not in (0, mask) for mask in self.masks):
                        return None
                    break
        if not uniform and len(basis) == self.required:
            self.uniform_roots.append(frozenset(selected))
        return len(basis)
