"""Exact ray-crossing cycle signatures for experimental axial deletions."""
from voronoi_app.angular import _intersections
from voronoi_app.angular import _exact_point


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
        self.cache = {}
        self.fallbacks = 0
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
        """Return rank, or None when a block's occupied cells are separated."""
        if not selected:
            return 0
        chosen=set(selected)
        start=min(chosen)
        potentials={start:0}
        queue=[start]
        basis={}
        crosses=0
        occupied=0
        for mask in self.masks:
            occupied |= mask
        for i in queue:
            for j in self.graph[i].keys() & chosen:
                value=potentials[i]^self.edge(i,j)
                if j not in potentials:
                    potentials[j]=value
                    queue.append(j)
                    continue
                v=value^potentials[j]
                while v:
                    pivot=v.bit_length()
                    if pivot not in basis:
                        basis[pivot]=v
                        # A full uniform basis can certify full rank immediately
                        # only after all cycles have been checked for splits.
                        for mask in self.masks:
                            part=v&mask
                            if part and part!=mask:
                                return None
                        break
                    v ^= basis[pivot]
        return len(basis)
