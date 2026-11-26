"""Versioned research-case exchange and publication."""
from hashlib import sha256
from io import BytesIO
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from .batch_store import encode
from .imported_town import collection, feature
from .research_data import copy_verified, data_path


def case_bytes(filename, source, extraction, town, component, analysis, overlay, options):
    review = {"schema": 1, "version": uuid4().hex, "source_name": Path(filename).name,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "source_sha256": sha256(source).hexdigest(), "settings": extraction.settings,
              "extraction_audit": extraction.audit, "source_extent": extraction.extent,
              "quantisation_step": str(town.grid), "geometry_report": town.report,
              "component": component, "options": options, "movement": analysis.movement,
              "adjacency": analysis.adjacency, "contacts": analysis.contacts,
              "enumeration": analysis.audit, "repairs": analysis.prepared.repairs,
              "vertices": analysis.prepared.vertices, "stages": analysis.prepared.stages,
              "summaries": analysis.prepared.summaries, "preparation_failure": analysis.prepared.failure,
              "final": vars(analysis.result) if analysis.result else None}
    exact = analysis.study.inputs
    from shapely.geometry import LineString
    axial = collection(feature(line.line_id, "axial", LineString([line.start, line.end]),
                                selected=bool(analysis.result and line.line_id in analysis.result.ids))
                       for line in analysis.study.lines)
    geometry = collection([*town.approved["features"], feature("domain", "approved_domain", town.streets),
                           feature("selected", "selected_domain", analysis.domain),
                           *(feature(f"block-{i}", "block", p) for i, p in analysis.blocks.items()),
                           *(feature(f"region-{i}", "convex_region", p) for i, p in analysis.regions.items())])
    def png(image):
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    files = {"source": source, "original-page.png": png(extraction.original),
             "source-crop.png": png(extraction.crop_image), "classification.png": png(extraction.preview),
             "extraction.geojson": encode(extraction.features),
             "approved.geojson": encode(town.approved), "analysis.geojson": encode(geometry),
             "axial.geojson": encode(axial), "exact-geometry.json": encode(exact),
             "overlay.svg": overlay, "case.json": encode(review)}
    manifest = {name: sha256(payload).hexdigest() for name, payload in files.items()}
    result = BytesIO()
    with ZipFile(result, "w", compression=ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
        archive.writestr("manifest.json", encode(manifest))
    return result.getvalue()


def load_case(payload):
    with ZipFile(BytesIO(payload)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or sum(item.file_size for item in archive.infolist()) > 400_000_000:
            raise ValueError("The research case has duplicate entries or exceeds the expanded size limit.")
        manifest = json.loads(archive.read("manifest.json"))
        required = {"case.json", "source", "original-page.png", "source-crop.png", "classification.png",
                    "extraction.geojson", "approved.geojson", "analysis.geojson", "axial.geojson",
                    "exact-geometry.json", "overlay.svg"}
        if set(names) != required | {"manifest.json"} or set(manifest) != required:
            raise ValueError("Unexpected research-case inventory.")
        files = {name: archive.read(name) for name in required}
    if any(sha256(data).hexdigest() != manifest[name] for name, data in files.items()):
        raise ValueError("Research-case checksum mismatch.")
    record = json.loads(files["case.json"])
    if record["schema"] != 1 or manifest["source"] != record["source_sha256"]:
        raise ValueError("Unsupported research-case schema or source checksum mismatch.")
    return record, files


def save_case(payload, *, local="diagnostics"):
    record, _ = load_case(payload)
    version = record["version"]
    if len(version) != 32 or any(c not in "0123456789abcdef" for c in version):
        raise ValueError("Invalid research-case version.")
    path = data_path(f"imported-towns/{version}.zip", local=local)
    with TemporaryDirectory() as temporary:
        staging = Path(temporary) / path.name
        staging.write_bytes(payload)
        if copy_verified(staging, path) == "conflict":
            raise ValueError(f"A different case already exists at {path}.")
    return path
