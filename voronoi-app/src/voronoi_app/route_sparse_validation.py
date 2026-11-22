"""Independent geometric verification for retained route-efficient maps."""

from time import monotonic

from .batch_methods import validate_axial_map
from .batch_store import StageResult


def validate_retained(inputs, parameters):
    started = monotonic()
    results = []
    candidates = inputs["candidates"]["pool"]["candidates"]
    for entry in parameters["maps"]:
        selected = set(entry["line_ids"])
        selection = {"line_ids": sorted(selected), "lines": [candidates[i] for i in sorted(selected)]}
        entrances = parameters["doorways"]
        measures = {
            "entrances": entrances,
            "excluded_entrances": inputs["measures"]["excluded_entrances"],
            "entrance_depth": {
                "unreachable": entry["unreachable"],
                "attached_entrances": sum(any(line in selected for line, _ in d["connectors"])
                                          for d in entrances),
            },
            "axial_mean_depth": None,
        }
        result = validate_axial_map(inputs | {"selection": selection, "measures": measures}, {})
        results.append({"index": entry["index"], "line_count": len(selection["line_ids"]),
                        "summary": result.output["summary"],
                        "failed_checks": result.output["failed_checks"]})
    return StageResult({"maps": results, "seconds": monotonic() - started},
                       valid=all(not row["failed_checks"] for row in results))
