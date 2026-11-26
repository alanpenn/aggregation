"""Node statistics and graph summaries shared by the terrain comparisons."""

from collections import Counter

import networkx as nx
import numpy as np

from experiments.flat40_configurational import METRICS
from voronoi_app.configurational import pearson


def distribution(values):
    if not values:
        return None
    sample = np.asarray(values, dtype=float)
    quantiles = np.quantile(sample, [0, .05, .25, .5, .75, .95, 1])
    avg, sd = float(sample.mean()), float(sample.std())
    return dict(zip(("min", "p05", "q1", "median", "q3", "p95", "max"), map(float, quantiles))) | {
        "mean": avg, "population_sd": sd, "iqr": float(quantiles[4] - quantiles[2]),
        "skewness_population": float(np.mean(((sample - avg) / sd)**3)) if sd else None,
        "observations": len(sample)}


def concentration(values):
    values = np.sort(values)
    n, total = len(values), values.sum()
    result = {"gini": None, "top_5_share": None, "top_10_share": None, "max_over_mean": None,
              "zero_fraction": float(np.mean(values == 0)) if n else None}
    if total:
        result["gini"] = min(1.0, max(0.0, float(np.dot(2*np.arange(1, n + 1) - n - 1, values) / (n * total))))
        result["max_over_mean"] = float(values[-1] * n / total)
        for percent in (5, 10):
            count = n * percent / 100
            whole = int(count)
            ordered = values[::-1]
            result[f"top_{percent}_share"] = float((ordered[:whole].sum() + (count - whole)*ordered[whole]) / total)
    return result


def summarize(graph, rows, *, weighted=False):
    x = [r["connectivity"] for r in rows.values()]
    y = [r["integration"] for r in rows.values()]
    r = pearson(x, y)
    components = sorted(map(len, nx.connected_components(graph)), reverse=True)
    connected = len(components) == 1
    diameter = None
    if connected:
        diameter = (max((r["eccentricity"] or 0 for r in rows.values()), default=0) if weighted
                    else nx.diameter(graph))
    return {"nodes": len(graph), "edges": graph.number_of_edges(), "components": components,
            "diameter": diameter, "mean_unweighted_local_clustering": nx.average_clustering(graph),
            "degree_distribution": dict(sorted(Counter(x).items())),
            "intelligibility": {"r": r, "defined": r is not None, "observations": len(x)},
            "measures": {metric: distribution([row[metric] for row in rows.values() if row[metric] is not None])
                         for metric in METRICS},
            "choice_concentration": concentration([row["choice"] for row in rows.values()])}


def high_choice_geometry(graph, rows):
    ordered = sorted(rows, key=lambda i: (-rows[i]["choice"], i))
    cutoff_index = (len(ordered) + 9) // 10
    cutoff = rows[ordered[cutoff_index - 1]]["choice"]
    nodes = [i for i in ordered if rows[i]["choice"] >= cutoff and rows[i]["choice"] > 0]
    centres = np.asarray([[float(sum(p[axis] for p in graph.nodes[i]["points"]) /
                                len(graph.nodes[i]["points"])) for axis in range(2)] for i in nodes])
    if not nodes:
        return {"nodes": [], "centroid": None, "rms_spread": None}
    centroid = centres.mean(axis=0)
    return {"nodes": nodes, "cutoff": cutoff, "centroid": centroid.tolist(),
            "rms_spread": float(np.sqrt(np.mean(np.sum((centres - centroid)**2, axis=1))))}
