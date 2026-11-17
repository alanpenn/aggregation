"""Replay the saved fixed-terminal Valley exchange when its data is available."""

import gzip
import json
import os
from fractions import Fraction
from pathlib import Path

import pytest
from shapely.ops import unary_union

from voronoi_app.angular import LineClearance, SampleAttachment
from voronoi_app.axial_snapshot import load_axial_snapshot
from voronoi_app.exact_axial import ExactCandidate
from voronoi_app.experimental_angular_selection import AngularResult, improve_fidelity


@pytest.mark.skipif(not os.environ.get("VALLEY_EXCHANGE_DATA"),
                    reason="Set VALLEY_EXCHANGE_DATA to the prepared Valley experiment directory")
@pytest.mark.parametrize(
    ("filename", "removal_limit"),
    [("exchange-result.json", 4), ("exchange-revisit-49-23.json", 5)],
)
def test_recorded_valley_exchange_replays_with_fixed_attachments(filename, removal_limit):
    state = Path(os.environ["VALLEY_EXCHANGE_DATA"])
    if not (state / filename).exists():
        pytest.skip(f"Experiment result {filename} has not been generated")
    data = json.loads((state / "prepared.json").read_text())
    saved = json.loads((state / filename).read_text())
    raw_reference = json.loads((state / "reference.json").read_text())
    snapshot = json.loads(gzip.decompress(
        (Path(__file__).parent / "fixtures/exact_y/axial-648f8da1364449a6aa70fd24038eea21.json.gz")
        .read_bytes()
    ))
    opened, buildings, _, _, _ = load_axial_snapshot(snapshot)
    occupied = unary_union(list(buildings.values()))
    accessible = unary_union(list(opened.values())).difference(occupied)
    clearance = LineClearance(accessible, occupied, original_obstacles=buildings.values())
    lines = []
    for i, record in enumerate(data["records"]):
        source = record["baseline"] or record["boundary"][0]
        start, end = (tuple(map(Fraction, source[key])) for key in ("start", "end"))
        lines.append(ExactCandidate(i, start, end, start, end, "combined-experiment"))
    attachments = [SampleAttachment(tuple(map(Fraction, item["sample"])),
                                    tuple(map(Fraction, item["point"])), item["line_id"])
                   for item in data["attachments"]]
    components = [item["component"] for item in data["attachments"]]
    groups = [{i for i, c in enumerate(data["components"]) if c == component}
              for component in range(len(set(data["components"])))]
    reference = AngularResult({(a, b): d for a, b, d in raw_reference["depths"]},
                              frozenset(raw_reference["witness_lines"]))
    removed, added = saved["exchanges"][0]
    assert len(removed) == 2 and len(added) == 1
    result = improve_fidelity(
        lines, [set(c) for c in data["covers"]], set(range(data["regions"])), groups,
        data["obstacles"], attachments, components, reference, saved["epsilon"],
        set(saved["initial"]), clearance, additions=added, attempt_limit=1,
        removal_limit=removal_limit,
    )
    assert result.exchanges == ((tuple(removed), tuple(added)),)
    assert len(result.selected) == len(saved["initial"]) - 1
    assert all(attachment.line_id in result.selected for attachment in attachments)
    assert all(result.depths[pair] <= full + saved["epsilon"] + 1e-10
               for pair, full in reference.depths.items())
