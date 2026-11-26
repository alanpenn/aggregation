"""Continuous directed-segment routes and physical-element centrality."""

from collections import defaultdict
from heapq import heappop, heappush
from math import atan2, degrees, fsum, hypot

from .angular import _cross, _direction

SCALE = 1_000_000


class Traversal:
    """Two directed states per physical segment, with junction-only transitions."""

    def __init__(self, segments):
        self.ids = sorted(segments)
        self.points = []
        self.lengths = []
        leaving = defaultdict(list)
        for identifier in self.ids:
            a, b = segments.nodes[identifier]["points"]
            index = len(self.points)
            self.points.extend(((a, b), (b, a)))
            length = max(1, round(hypot(*_direction(a, b)) * SCALE))
            self.lengths.extend((length, length))
            leaving[a].append(index)
            leaving[b].append(index + 1)
        self.links = []
        for state, (a, b) in enumerate(self.points):
            heading = _direction(a, b)
            links = []
            for following in leaving[b]:
                destination = self.points[following][1]
                outgoing = _direction(b, destination)
                dot = sum(x * y for x, y in zip(heading, outgoing))
                turn = round(degrees(atan2(float(abs(_cross(heading, outgoing))), float(dot))) * SCALE)
                links.append((following, turn, self.lengths[state] + self.lengths[following]))
            self.links.append(links)

    def paths(self, starts, metric="angular"):
        """All predecessor ties from a collection of zero-cost start orientations."""
        if metric not in {"angular", "metric", "angular_metric"}:
            raise ValueError(f"Unknown traversal metric {metric}")
        n = len(self.points)
        distance = [None] * n
        sigma = [0] * n
        parents = [[] for _ in range(n)]
        heap = []
        for state in sorted(set(starts)):
            distance[state] = (0, 0, 0)
            sigma[state] = 1
            heappush(heap, (distance[state], state))
        order = []
        while heap:
            cost, state = heappop(heap)
            if cost != distance[state]:
                continue
            order.append(state)
            for following, turn, length in self.links[state]:
                if metric == "angular":
                    step = (turn, 1, 0)
                elif metric == "metric":
                    step = (length, 1, 0)
                else:
                    step = (turn, length, 1)
                proposed = tuple(x + y for x, y in zip(cost, step))
                old = distance[following]
                if old is None or proposed < old:
                    distance[following] = proposed
                    parents[following] = [state]
                    sigma[following] = sigma[state]
                    heappush(heap, (proposed, following))
                elif proposed == old:
                    parents[following].append(state)
                    sigma[following] += sigma[state]
        return distance, sigma, parents, order

    @staticmethod
    def terminals(distance, physical):
        states = [s for s in (2 * physical, 2 * physical + 1) if distance[s] is not None]
        return [s for s in states if distance[s] == min(distance[t] for t in states)]

    def measures(self, segments, metric="angular"):
        """Compute depth and fractional choice over unordered physical-segment pairs."""
        n = len(self.ids)
        normal = (n - 1) * (n - 2)  # Ordered pairs, equivalent by route reversal.
        scale = 2 * SCALE if metric == "metric" else SCALE
        choice = [0.0] * n
        rows = {}
        for source, identifier in enumerate(self.ids):
            distance, sigma, parents, order = self.paths((2 * source, 2 * source + 1), metric)
            endpoints = [0.0] * len(distance)
            depths = []
            for target in range(n):
                if source == target:
                    continue
                states = self.terminals(distance, target)
                if states:
                    depths.append(distance[states[0]][0] / scale)
                    count = sum(sigma[s] for s in states)
                    for state in states:
                        endpoints[state] = 1 / count
            reach = len(depths)
            depth = fsum(depths) / reach if reach else None
            rows[identifier] = dict(connectivity=segments.degree(identifier), mean_depth=depth,
                                    integration=reach / (n - 1) / (1 + depth) if reach else 0.0,
                                    reachable=reach, eccentricity=max(depths) if reach else None)
            upstream = [0] * len(distance)
            for state in order:
                for parent in parents[state]:
                    upstream[state] |= upstream[parent] | (1 << parent)
            downstream = [0.0] * len(distance)
            for state in reversed(order):
                weight = downstream[state]
                if state // 2 != source:
                    choice[state // 2] += sigma[state] * weight
                    mate = state ^ 1
                    if upstream[state] & (1 << mate):
                        # Count a physical element once if both headings occur on a tied path.
                        counts = {mate: 1}
                        for candidate in order:
                            if upstream[candidate] & (1 << mate):
                                counts[candidate] = sum(counts.get(p, 0) for p in parents[candidate])
                            if candidate == state:
                                break
                        choice[state // 2] -= sigma[mate] * counts[state] * weight
                for parent in parents[state]:
                    downstream[parent] += weight + endpoints[state]
        for i, identifier in enumerate(self.ids):
            rows[identifier]["choice"] = max(0.0, choice[i] / normal) if n > 2 else 0.0
        return rows
