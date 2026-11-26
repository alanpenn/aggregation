from hashlib import sha256
from io import BytesIO
import json
from zipfile import ZipFile

from PIL import Image, ImageDraw
import pytest
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from voronoi_app.angular import _on_segment
from voronoi_app.imported_town import (
    analyse_entrances, analyse_town, collection, exact_area, feature, review_geometry,
)
from voronoi_app.town_case import case_bytes, load_case, save_case
from voronoi_app.town_plan_source import ExtractionSettings, extract_plan, plan_pages


CORRIDOR = box(0, 0, 12, 4)
T_JUNCTION = unary_union([box(0, 0, 12, 3), box(4, 3, 8, 8)])
CROSSROADS = unary_union([box(0, 3, 12, 6), box(4, 0, 8, 10)])
IRREGULAR = Polygon([(0, 0), (7, 0), (11, 4), (15, 5), (15, 7), (10, 6), (6, 2), (0, 2)])
RING = box(0, 0, 14, 10)
ISLAND = box(5, 3, 9, 7)


def reviewed(streets, *, buildings=(), excluded=(), boundary=None):
    if boundary is None:
        boundary = box(*streets.bounds)
    return review_geometry(collection([
        feature("review-area", "boundary", boundary),
        feature("streets", "street", streets),
        *(feature(f"building-{i}", "building", p) for i, p in enumerate(buildings)),
        *(feature(f"excluded-{i}", "exclude", p) for i, p in enumerate(excluded)),
    ]))


@pytest.mark.parametrize(("street", "buildings", "exclusions", "holes"), [
    pytest.param(CORRIDOR, [box(0, 4, 12, 7), box(0, -3, 12, 0)], [], 0, id="corridor"),
    pytest.param(T_JUNCTION, [], [], 0, id="t-junction"),
    pytest.param(CROSSROADS, [], [], 0, id="four-way-junction"),
    pytest.param(IRREGULAR, [], [], 0, id="irregular-lane"),
    pytest.param(RING, [ISLAND], [], 1, id="occupied-island"),
    pytest.param(RING, [], [ISLAND], 1, id="enclosed-courtyard"),
    pytest.param(unary_union([box(0, 0, 4, 4), box(4, 1.875, 8, 2.125), box(8, 0, 12, 4)]),
                 [], [], 0, id="narrow-passage"),
    pytest.param(CORRIDOR, [], [box(8, 2, 12, 5)], 0, id="adjacent-green-land"),
    pytest.param(CORRIDOR, [], [], 0, id="at-analysis-boundary"),
])
def test_certified_approved_domains(street, buildings, exclusions, holes):
    town = reviewed(street, buildings=buildings, excluded=exclusions)
    analysis = analyse_town(town, 0)
    assert analysis.prepared.failure is None
    assert analysis.result and analysis.result.certified, analysis.result
    summary = analysis.result.summary
    assert summary["rank"] == summary["required_rank"] == holes
    assert summary["components"] == 1
    assert summary["regions"] == summary["required_regions"]
    assert sum(map(exact_area, analysis.regions.values())) == exact_area(analysis.domain)
    assert unary_union(list(analysis.regions.values())).equals(analysis.domain)
    for i, neighbors in analysis.adjacency.items():
        for j in neighbors:
            assert i in analysis.adjacency[j]
    for line in analysis.study.lines:
        assert analysis.study.clearance.permits(line.start, line.end)


@pytest.mark.parametrize(("second", "contact"), [(box(6, 6, 8, 8), "vertex"), (box(6, 4, 8, 6), "edge")])
def test_building_contact_groups(second, contact):
    a = analyse_town(reviewed(RING, buildings=[box(4, 4, 6, 6), second]), 0)
    assert len(a.blocks) == 1
    assert a.contacts == [{"left": "building-0", "right": "building-1", "kind": contact}]
    assert a.result and a.result.certified
    assert a.result.summary["rank"] == a.result.summary["required_rank"] == 1
    if contact == "vertex":
        assert a.study.inputs["topology"]["non_traversable_contacts"] == [["6", "6"]]
        assert all(not _on_segment((6, 6), line.start, line.end) for line in a.study.lines)


def test_independent_winding_around_separate_holes():
    street = box(0, 0, 20, 10)
    a = analyse_town(reviewed(street, buildings=[box(3, 3, 6, 6)],
                              excluded=[box(12, 3, 15, 6)]), 0)
    assert a.result and a.result.certified
    assert a.result.summary["rank"] == 2


def test_disconnected_streets_are_analysed_separately():
    town = reviewed(MultiPolygon([CORRIDOR, box(15, 0, 20, 4)]))
    assert len(town.components) == 2
    for index in range(2):
        a = analyse_town(town, index)
        assert a.domain.equals(town.components[index])
        assert a.result and a.result.certified
        assert a.result.summary["components"] == 1


def test_invalid_features_grid_displacement_and_overlap():
    outer = box(0, 0, 20, 10)
    bowtie = Polygon([(2, 1), (8, 6), (2, 6), (8, 1)])
    t = reviewed(outer, buildings=[bowtie, box(10.02, 2.03, 11.02, 3.03)])
    assert t.report["repaired"] == ["building-0"]
    assert t.report["quantisation_changes"][0]["id"] == "building-1"
    with pytest.raises(ValueError, match="interiors overlap"):
        reviewed(outer, buildings=[box(2, 1, 8, 8), box(3, 3, 7, 7)])
    with pytest.raises(ValueError, match="analysis boundary"):
        review_geometry(collection([feature("street", "street", outer)]))


def test_subdivision_sensitivity():
    def run(streets, buildings):
        town = reviewed(streets, buildings=buildings)
        pair = [analyse_town(town, 0, merge=merge) for merge in (False, True)]
        assert all(a.result and a.result.certified for a in pair)
        assert len(pair[0].regions) > len(pair[1].regions)
        return pair

    def intervals(a, ids=None):
        return {tuple(sorted((line.start, line.end))) for line in a.study.lines
                if ids is None or line.line_id in ids}

    dense, merged = run(T_JUNCTION, [])
    assert intervals(dense) != intervals(merged)
    assert [a.result.summary["count"] for a in (dense, merged)] == [3, 1]
    assert dense.result.summary["rank"] == merged.result.summary["rank"] == 0
    dense, merged = run(RING, [ISLAND])
    assert intervals(dense) == intervals(merged)
    assert intervals(dense, dense.result.ids) != intervals(merged, merged.result.ids)
    assert [a.result.summary["count"] for a in (dense, merged)] == [4, 4]
    assert dense.result.summary["rank"] == merged.result.summary["rank"] == 1


def make_image(fmt="PNG"):
    image = Image.new("RGB", (80, 60), "#faf4ea")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 30, 30), fill="#bd3639")
    draw.rectangle((50, 10, 70, 30), fill="#559853")
    draw.rectangle((40, 40, 43, 49), fill="#232323")
    stream = BytesIO()
    image.save(stream, format=fmt)
    return stream.getvalue()


@pytest.mark.parametrize(("format", "extension"), [("PNG", "png"), ("TIFF", "tif"), ("JPEG", "jpeg")])
def test_raster_buildings_green_and_marks(format, extension):
    extraction = extract_plan(make_image(format), f"plan.{extension}", ExtractionSettings(resolution=128))
    roles = [f["properties"]["role"] for f in extraction.features["features"]]
    assert roles.count("building") == 1
    assert roles.count("exclude") == 1
    assert roles.count("annotation") >= 1
    assert "street" not in roles
    assert extraction.original.size == (80, 60)


def test_vector_pdf_and_raster_pdf_fallback():
    pdf = pytest.importorskip("pymupdf")
    document = pdf.open()
    page = document.new_page(width=80, height=60)
    page.draw_rect(pdf.Rect(20, 20, 40, 40), color=None, fill=(.8, .1, .1))
    page = document.new_page(width=80, height=60)
    page.insert_image(page.rect, stream=make_image())
    payload = document.tobytes()
    assert plan_pages(payload, "plan.pdf") == 2
    vector = extract_plan(payload, "plan.pdf", ExtractionSettings(resolution=800, crop=(.1,.1,.9,.9)))
    assert vector.audit["methods"]["building"]["method"] == "PDF vector"
    raster = extract_plan(payload, "plan.pdf", ExtractionSettings(page=2, resolution=240))
    assert raster.audit["methods"]["building"]["method"] == "raster"
    assert raster.audit["pixel_counts"]["building"] > 0


def test_entrances_and_versioned_case(tmp_path, monkeypatch):
    town = reviewed(CORRIDOR, buildings=[box(0, 4, 12, 7)])
    analysis = analyse_town(town, 0, order="shortest", exchange=True)
    before = analysis.result.ids
    movement = analyse_entrances(analysis, [{"coordinates": (1, 2)}, {"coordinates": (11, 2)}])
    assert movement["routing"]["valid"]
    assert analysis.result.ids == before
    assert analysis.result.summary["required_doorways"] == 0
    with pytest.raises(ValueError, match="outside"):
        analyse_entrances(analysis, [{"coordinates": (1, 8)}])
    source = make_image()
    extraction = extract_plan(source, "pilot.png", ExtractionSettings(resolution=128))
    bundle = case_bytes("pilot.png", source, extraction, town, 0, analysis, b"<svg/>", {"order": "shortest"})
    record, files = load_case(bundle)
    assert record["source_sha256"] == sha256(source).hexdigest()
    assert record["final"]["summary"]["certified"]
    assert json.loads(files["approved.geojson"])["type"] == "FeatureCollection"
    assert json.loads(files["exact-geometry.json"])["candidates"]["pool"]["candidates"]
    monkeypatch.setenv("AGGREGATION_DATA_ROOT", str(tmp_path))
    location = save_case(bundle)
    assert location.parent == tmp_path / "imported-towns"
    assert location.read_bytes() == bundle and save_case(bundle) == location
    changed = BytesIO()
    with ZipFile(BytesIO(bundle)) as old, ZipFile(changed, "w") as bad:
        for name in old.namelist():
            bad.writestr(name, b"altered" if name == "source" else old.read(name))
    with pytest.raises(ValueError, match="checksum"):
        load_case(changed.getvalue())


def test_streamlit_source_navigation():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/streamlit_app.py"),
                           default_timeout=60).run()
    assert not app.exception
    app.radio(key="settlement_source").set_value("Import real town plan").run()
    assert not app.exception
    assert any("Pale areas need explicit approval" in notice.value for notice in app.info)
    app.radio(key="settlement_source").set_value("Generate synthetic settlement").run()
    assert not app.exception
    assert any(heading.value == "Experiment Configuration" for heading in app.sidebar.header)


def test_streamlit_upload_review_certification_and_reload(tmp_path, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("AGGREGATION_DATA_ROOT", str(tmp_path))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/streamlit_app.py"),
                           default_timeout=60).run()
    app.radio(key="settlement_source").set_value("Import real town plan").run()
    app.file_uploader[0].upload("town.png", make_image()).run()
    assert not app.exception and not app.error
    assert not any(b.label == "Generate and certify axial map" for b in app.button)
    assert any("Select at least one polygon" in message.value for message in app.info)
    boundary = next(w for w in app.checkbox if w.label.startswith("Use the drawing-region"))
    boundary.check().run()
    assert any("Select at least one polygon" in message.value for message in app.info)
    assert not any("Check **Use the drawing-region" in message.value for message in app.info)
    doc = collection([feature("outer", "boundary", box(0,0,80,60)),
                      feature("street", "street", box(0, 30, 80, 40)),
                      feature("north bank", "building", box(10,40,30,50))])
    upload = next(w for w in app.file_uploader if w.label == "Corrected GeoJSON (optional)")
    upload.upload("reviewed.geojson", json.dumps(doc).encode()).run()
    assert not app.exception and not app.error
    approval = next(w for w in app.checkbox if w.label.startswith("Approve these polygons"))
    approval.check().run()
    next(w for w in app.button if w.label == "Generate and certify axial map").click().run()
    assert not app.exception and not app.error
    assert any("Independently certified" in notice.value for notice in app.success)
    next(w for w in app.selectbox if w.label == "Map view").select("Final reduced map").run()
    assert not app.exception and not app.error
    next(w for w in app.text_area if w.label.startswith("Manual entrance points")).set_value("5,35").run()
    next(w for w in app.checkbox if w.label.startswith("Include experimental entrances")).check().run()
    next(w for w in app.button if w.label == "Calculate entrance routes").click().run()
    assert not app.exception and not app.error
    next(w for w in app.button if w.label == "Prepare versioned research case").click().run()
    next(w for w in app.button if w.label == "Save in research data directory").click().run()
    assert not app.exception and not app.error
    bundle, = (tmp_path / "imported-towns").glob("*.zip")
    record, _ = load_case(bundle.read_bytes())
    assert record["final"]["summary"]["certified"]
    assert record["movement"]["entrances"][1]["status"] == "synthetic"
    next(w for w in app.radio if w.label == "Research case").set_value("Reload a saved case").run()
    next(w for w in app.selectbox if w.label == "Saved version").select(bundle).run()
    assert not app.exception and not app.error
    assert any("Independently certified" in notice.value for notice in app.success)
