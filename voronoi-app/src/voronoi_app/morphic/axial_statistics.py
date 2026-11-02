"""Exploratory paired statistics for common axial-growth stages."""

import statistics
from typing import Dict, Iterable, List, Optional, Sequence

from scipy.stats import wilcoxon


MEASURES = {
    "axial_line_count": lambda metrics: float(metrics["axial_line_count"]),
    "mean_line_length": lambda metrics: (
        statistics.mean(metrics["line_lengths"]) if metrics["line_lengths"] else None
    ),
    "mean_global_integration": lambda metrics: (
        statistics.mean(metrics["global_integration_distribution"])
        if metrics["global_integration_distribution"] else None
    ),
    "intelligibility_r_squared": lambda metrics: metrics["intelligibility_r_squared"],
}


def paired_final_tests(
    runs: Sequence,
    mode_a: str = "random",
    mode_b: str = "adjacent",
    step: int = 60,
) -> List[Dict[str, object]]:
    """Wilcoxon signed-rank tests by seed on shared modes at a common stage.

    These are exploratory tests, not a substitute for a preregistered
    statistical analysis. Mode pairs without a common stage should not be
    compared by this helper.
    """
    indexed = {
        (run.config.mode, run.config.seed): run
        for run in runs
    }
    seeds = sorted({
        seed for mode, seed in indexed
        if mode == mode_a and (mode_b, seed) in indexed
    })
    pairs = []
    for seed in seeds:
        run_a, run_b = indexed[(mode_a, seed)], indexed[(mode_b, seed)]
        snapshot_a = next((item for item in run_a.snapshots if item.step == step), None)
        snapshot_b = next((item for item in run_b.snapshots if item.step == step), None)
        if snapshot_a is not None and snapshot_b is not None:
            pairs.append((snapshot_a.axial_metrics, snapshot_b.axial_metrics))

    results = []
    for name, value in MEASURES.items():
        observations = [
            (left, right)
            for metrics_a, metrics_b in pairs
            if (left := value(metrics_a)) is not None
            and (right := value(metrics_b)) is not None
        ]
        differences = [right - left for left, right in observations]
        if len(differences) < 2:
            p_value = None
        elif all(difference == 0 for difference in differences):
            p_value = 1.0
        else:
            p_value = float(wilcoxon(differences, alternative="two-sided").pvalue)
        results.append({
            "mode_a": mode_a,
            "mode_b": mode_b,
            "stage": step,
            "measure": name,
            "n_pairs": len(differences),
            "mean_a": statistics.mean(left for left, _ in observations) if observations else None,
            "mean_b": statistics.mean(right for _, right in observations) if observations else None,
            "mean_paired_difference_b_minus_a": statistics.mean(differences) if differences else None,
            "median_paired_difference_b_minus_a": statistics.median(differences) if differences else None,
            "p_value": p_value,
        })

    valid = [(index, row["p_value"]) for index, row in enumerate(results)
             if row["p_value"] is not None]
    ordered = sorted(valid, key=lambda item: item[1])
    previous_adjusted = 0.0
    adjusted = {}
    count = len(ordered)
    for rank, (index, p_value) in enumerate(ordered):
        adjusted_value = min(1.0, (count - rank) * p_value)
        previous_adjusted = max(previous_adjusted, adjusted_value)
        adjusted[index] = previous_adjusted
    for index, row in enumerate(results):
        row["p_value_holm"] = adjusted.get(index)
    return results
