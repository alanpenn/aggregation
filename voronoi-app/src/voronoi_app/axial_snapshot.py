"""Portable snapshots of the geometry and candidates used by the axial audit."""

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from shapely.geometry import LineString, mapping, shape
from shapely.ops import unary_union

from .axial import AxialLine
from .axial_diagnostics import audit_axial_candidates
from .axial_generator import _maximal_interval


def _coordinates(line):
    return None if line is None else [list(point) for point in line.coords]


def make_axial_snapshot(config, open_polygons, occupied_polygons, generated, audit,
                        paired_open_cells):
    """Capture the exact audit inputs and evidence for unresolved tangents."""
    occupied = unary_union(list(occupied_polygons.values()))
    accessible = unary_union(list(open_polygons.values())).difference(occupied)
    buffered = accessible.buffer(audit.tolerance)
    unresolved = []
    for pair in audit.pairs:
        if pair.status == "present":
            continue
        seed = LineString((pair.start, pair.end))
        issues = []
        interval = _maximal_interval(
            accessible, pair.start, pair.end, audit.tolerance, ambiguities=issues
        )
        unresolved.append({
            "start": pair.start,
            "end": pair.end,
            "support_direction": [pair.end[0] - pair.start[0], pair.end[1] - pair.start[1]],
            "status": pair.status,
            "attempted": pair.attempted,
            "exact_visible": accessible.covers(seed),
            "buffered_visible": buffered.covers(seed),
            "occupied_relation": seed.relate(occupied),
            "crosses_occupied_interior": seed.relate_pattern(occupied, "T********"),
            "generator_interval": _coordinates(interval),
            "independent_interval": _coordinates(pair.maximal),
            "clipping_issues": issues,
            "reason": pair.reason or (
                "independent clipping failed" if pair.maximal is None
                else "no matching candidate"
            ),
        })
    return {
        "version": 1,
        "configuration": config,
        "axial_coverage_model": generated.coverage_model,
        "open_polygons": [{"cell": int(cell), "geometry": mapping(polygon)}
                          for cell, polygon in sorted(open_polygons.items())],
        "occupied_polygons": [{"cell": int(cell), "geometry": mapping(polygon)}
                              for cell, polygon in sorted(occupied_polygons.items())],
        "paired_open_cells": sorted(int(cell) for cell in paired_open_cells),
        "candidate_lines": [
            {"id": line.line_id, "start": line.start, "end": line.end,
             "attributes": line.attributes}
            for line in generated.candidate_lines
        ],
        "ambiguous_pairs": [
            {"start": start, "end": end, "reason": reason}
            for start, end, reason in generated.ambiguous_pairs
        ],
        "audit": {
            "tolerance": audit.tolerance,
            "present": sum(pair.status == "present" for pair in audit.pairs),
            "missing": sum(pair.status == "missing" for pair in audit.pairs),
            "indeterminate": sum(pair.status == "indeterminate clipping" for pair in audit.pairs),
            "unresolved": unresolved,
        },
    }


def load_axial_snapshot(data):
    """Restore audit inputs from a snapshot, without generating a settlement."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unsupported axial diagnostic snapshot version")
    try:
        def polygons(key):
            entries = data[key]
            result = {int(entry["cell"]): shape(entry["geometry"]) for entry in entries}
            if len(result) != len(entries) or any(
                polygon.geom_type != "Polygon" or polygon.is_empty or not polygon.is_valid
                for polygon in result.values()
            ):
                raise ValueError(f"Invalid or duplicate polygons in {key}")
            return result

        open_polygons = polygons("open_polygons")
        occupied_polygons = polygons("occupied_polygons")
        if not open_polygons or set(open_polygons) & set(occupied_polygons):
            raise ValueError("Snapshot requires disjoint open and occupied cell IDs")
        candidates = [
            AxialLine(int(line["id"]), tuple(line["start"]), tuple(line["end"]),
                      line["attributes"])
            for line in data["candidate_lines"]
        ]
        if len({line.line_id for line in candidates}) != len(candidates):
            raise ValueError("Duplicate candidate line IDs")
        ambiguous = [(tuple(pair["start"]), tuple(pair["end"]), pair["reason"])
                     for pair in data["ambiguous_pairs"]]
        config = data["configuration"]
        paired = set(data["paired_open_cells"])
        if not paired <= set(open_polygons) or not isinstance(config, dict):
            raise ValueError("Invalid snapshot configuration or paired open cells")
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError(f"Invalid axial diagnostic snapshot: {error}") from error
    coverage_model = data.get("axial_coverage_model", "cells")
    if coverage_model not in ("cells", "convex"):
        raise ValueError(f"Unknown snapshot axial coverage model: {coverage_model}")
    return open_polygons, occupied_polygons, SimpleNamespace(
        candidate_lines=candidates, ambiguous_pairs=ambiguous, coverage_model=coverage_model
    ), config, paired


def rerun_axial_snapshot(data):
    """Audit the saved candidate set against the saved polygon geometry."""
    open_polygons, occupied_polygons, generated, config, paired = load_axial_snapshot(data)
    audit = audit_axial_candidates(open_polygons, occupied_polygons, generated)
    return open_polygons, occupied_polygons, generated, config, paired, audit


def save_axial_snapshot(snapshot, directory):
    """Write a uniquely named diagnostic snapshot and return its path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"axial-{uuid4().hex}.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(snapshot, file, indent=2, allow_nan=False)
    return path
