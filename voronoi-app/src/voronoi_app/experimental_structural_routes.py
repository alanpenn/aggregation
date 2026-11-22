"""Fixed-connector metric and angular evaluation for experimental axial maps."""

import math
from itertools import combinations

import networkx as nx

from .angular import _intersections, _on_segment
from .experimental_angular_selection import angular_reference


def distance(a, b):
    return math.hypot(float(b[0] - a[0]), float(b[1] - a[1]))


def segment_network(lines, attachments):
    """Node exact intervals at all mutual intersections and fixed connector stops."""
    nodes = [{line.start, line.end} for line in lines]
    intersections = set()
    for i, j in combinations(range(len(lines)), 2):
        points = _intersections(lines[i].start, lines[i].end, lines[j].start, lines[j].end)
        nodes[i].update(points)
        nodes[j].update(points)
        intersections.update(points)
    for attachment in attachments:
        for i, line in enumerate(lines):
            if _on_segment(attachment.point, line.start, line.end):
                nodes[i].add(attachment.point)
    graph = nx.Graph()
    for points in nodes:
        for a, b in zip(sorted(points), sorted(points)[1:]):
            graph.add_edge(a, b, weight=distance(a, b))
    return graph, intersections


def evaluate_routes(lines, fixed, components, references):
    """Evaluate the same terminals, using direct visibility before map attachment."""
    retained = {line.line_id for line in lines}
    options = [[a for a in choices if a.line_id in retained] for choices in fixed]
    attachments = [a for choices in options for a in choices]
    sample_ids = [i for i, choices in enumerate(options) for _ in choices]
    depths = {}
    if attachments:
        raw = angular_reference(lines, attachments, [components[i] for i in sample_ids]).depths
        for (i, j), value in raw.items():
            key = sample_ids[i], sample_ids[j]
            depths[key] = min(depths.get(key, math.inf), value)
    graph, intersections = segment_network(lines, attachments)
    metric = {}
    for i, choices in enumerate(options):
        if not choices:
            continue
        source = object()
        for a in choices:
            graph.add_edge(source, a.point, weight=distance(a.sample, a.point))
        lengths = nx.single_source_dijkstra_path_length(graph, source, weight="weight")
        graph.remove_node(source)
        for j, destinations in enumerate(options):
            if i == j:
                continue
            metric[i, j] = min(
                (lengths.get(a.point, math.inf) + distance(a.point, a.sample)
                 for a in destinations), default=math.inf)
    pairs = []
    for (i, j), reference in sorted(references.items()):
        if components[i] != components[j]:
            pairs.append({"source": i, "destination": j, "status": "different-component"})
            continue
        if reference["status"] == "direct":
            pairs.append({"source": i, "destination": j, "status": "direct",
                          "metric": reference["length"], "reference": reference["length"],
                          "angular": 0.0})
            continue
        if not options[i] or not options[j]:
            pairs.append({"source": i, "destination": j, "status": "attachment-failure"})
            continue
        length, angle = metric.get((i, j), math.inf), depths.get((i, j), math.inf)
        if math.isfinite(length) != math.isfinite(angle):
            raise ValueError(f"Metric and angular networks disagree on reachability for {(i, j)}")
        if not math.isfinite(length):
            pairs.append({"source": i, "destination": j, "status": "network-disconnected"})
            continue
        reference_length = reference["length"]
        if length < reference_length - 1e-9 * max(1.0, reference_length):
            raise ValueError(f"Network route is shorter than visibility reference for {(i, j)}")
        pairs.append({"source": i, "destination": j, "status": "routed", "metric": length,
                      "reference": reference_length, "angular": angle})
    return pairs, {"segment_nodes": graph.number_of_nodes(),
                   "segments": graph.number_of_edges(),
                   "intersection_points": len(intersections),
                   "intersection_degree_histogram": {
                       str(degree): sum(1 for p in intersections if graph.degree[p] == degree)
                       for degree in sorted({graph.degree[p] for p in intersections})},
                   "attached_terminals": sum(bool(item) for item in options)}
