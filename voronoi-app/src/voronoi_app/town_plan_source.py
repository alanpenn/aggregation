"""Town-plan decoding, conservative colour classification, and polygon extraction."""
from dataclasses import asdict, dataclass
from io import BytesIO

import numpy as np
from PIL import Image
from shapely import contains_xy, union_all
from shapely.affinity import affine_transform
from shapely.geometry import Polygon, box

from .imported_town import collection, feature, ordered, polygon_parts


@dataclass(frozen=True)
class ExtractionSettings:
    page: int = 1
    resolution: int = 1200
    crop: tuple = (0., 0., 1., 1.)
    colour_margin: float = 28.
    pale_min: float = 180.
    pale_chroma: float = 42.
    dark_max: float = 100.
    min_pixels: int = 8
    simplify: float = 0.
    prefer_vector: bool = True


COLORS = {"building": "#b23538", "exclude": "#59934f", "pale": "#7bcbdf",
          "annotation": "#6d528d", "uncertain": "#e4ab4d"}


def pdf_document(payload):
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError("Install the project requirements to enable PDF import (PyMuPDF).") from error
    return pymupdf.open(stream=payload, filetype="pdf")


def plan_pages(payload, filename):
    if filename.lower().endswith(".pdf"):
        with pdf_document(payload) as document:
            return len(document)
    with Image.open(BytesIO(payload)) as image:
        return getattr(image, "n_frames", 1)


def classes(rgb, settings):
    r, g, b = np.moveaxis(np.asarray(rgb, dtype=np.float32), -1, 0)
    highest, lowest = np.max(rgb, axis=-1), np.min(rgb, axis=-1)
    red = (r - np.maximum(g, b) >= settings.colour_margin) & (r >= settings.dark_max)
    green = (g - np.maximum(r, b) >= settings.colour_margin) & (g >= settings.dark_max)
    pale = (lowest >= settings.pale_min) & (highest - lowest <= settings.pale_chroma)
    dark = (highest <= settings.dark_max) & ~(red | green)
    pale &= ~(red | green | dark)
    return {"building": red, "exclude": green, "pale": pale, "annotation": dark,
            "uncertain": ~(red | green | pale | dark)}


@dataclass
class PlanExtraction:
    original: Image.Image
    preview: Image.Image
    crop_image: Image.Image
    extent: tuple
    features: dict
    settings: dict
    audit: dict


def simple_fill(path, rotation, height):
    """Return one simple filled straight path, declining compound or curved paths."""
    items = path["items"]
    if len(items) == 1 and items[0][0] == "re":
        rect = items[0][1]
        vertices = [rect.tl, rect.tr, rect.br, rect.bl]
    elif len(items) == 1 and items[0][0] == "qu":
        quad = items[0][1]
        vertices = [quad.ul, quad.ur, quad.lr, quad.ll]
    elif len(items) >= 3 and all(item[0] == "l" for item in items):
        if any(a[2] != b[1] for a, b in zip(items, items[1:])):
            return None
        vertices = [items[0][1], *(item[2] for item in items)]
    else:
        return None
    points = [point * rotation for point in vertices]
    polygon = Polygon([(p.x, height - p.y) for p in points])
    return polygon if polygon.is_valid and polygon.area else None


def read_plan(payload, filename, settings):
    paths, skipped = [], set()
    if filename.lower().endswith(".pdf"):
        with pdf_document(payload) as document:
            if not 1 <= settings.page <= len(document):
                raise ValueError("PDF page is out of range.")
            page = document[settings.page-1]
            width, height = page.rect.width, page.rect.height
            scale = settings.resolution / max(width, height)
            pixmap = page.get_pixmap(matrix=_pdf_matrix(scale), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            if settings.prefer_vector:
                try:
                    drawings = page.get_drawings(extended=True)
                except (RuntimeError, ValueError):
                    drawings = []
                    skipped.update(("building", "exclude", "pale"))
                for path in drawings:
                    fill = path.get("fill")
                    if not fill or len(fill) != 3:
                        continue
                    mask = classes(np.asarray(fill) * 255, settings)
                    role = next((name for name in ("building", "exclude", "pale") if mask[name]), None)
                    if role is None:
                        continue
                    polygon = simple_fill(path, page.rotation_matrix, height)
                    if polygon is None or path.get("level", 0) or path.get("fill_opacity", 1) != 1:
                        skipped.add(role)
                    else:
                        paths.append((role, polygon, path.get("layer") or "", path.get("seqno")))
    else:
        with Image.open(BytesIO(payload)) as source:
            if not 1 <= settings.page <= getattr(source, "n_frames", 1):
                raise ValueError("Image page is out of range.")
            source.seek(settings.page - 1)
            rgba = source.convert("RGBA")
            image = Image.new("RGB", rgba.size, "white")
            image.paste(rgba, mask=rgba.getchannel("A"))
        width, height = image.size
    return image, (width, height), paths, skipped


def _pdf_matrix(scale):
    import pymupdf
    return pymupdf.Matrix(scale, scale)


def mask_polygons(mask, transform, settings):
    """Union horizontal pixel runs, preserving holes and point-touch boundaries."""
    padded = np.pad(mask, ((0, 0), (1, 1)))
    rectangles = []
    for row, edges in enumerate(padded[:, 1:] != padded[:, :-1]):
        transitions = np.flatnonzero(edges)
        rectangles.extend(box(a, row, b, row+1) for a, b in zip(transitions[::2], transitions[1::2]))
    polygons = ordered(polygon_parts(union_all(rectangles)))
    records = []
    for polygon in polygons:
        if polygon.area < settings.min_pixels:
            continue
        original = affine_transform(polygon, transform)
        simplified = original.simplify(settings.simplify, preserve_topology=True) if settings.simplify else original
        records.append((simplified, original.symmetric_difference(simplified).area))
    return records


def extract_plan(payload, filename, settings=ExtractionSettings()):
    if settings.resolution < 64 or settings.resolution > 6000:
        raise ValueError("Use an extraction resolution between 64 and 6000 pixels.")
    x0, y0, x1, y1 = settings.crop
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Crop edges must form a non-empty rectangle within the source.")
    original, (width, height), paths, skipped = read_plan(payload, filename, settings)
    work = original.copy()
    work.thumbnail((settings.resolution, settings.resolution), Image.Resampling.LANCZOS)
    source_w, source_h = work.size
    xlo, ylo, xhi, yhi = (round(x0*source_w), round(y0*source_h),
                         round(x1*source_w), round(y1*source_h))
    if xlo == xhi or ylo == yhi:
        raise ValueError("The crop is smaller than one extraction pixel.")
    work = work.crop((xlo, ylo, xhi, yhi))
    sx, sy = width/source_w, height/source_h
    left, top = xlo*sx, height-ylo*sy
    extent = (left, xhi*sx, height-yhi*sy, top)
    crop = box(extent[0], extent[2], extent[1], extent[3])
    masks = classes(np.asarray(work), settings)
    preview = np.empty((work.height, work.width, 3), dtype=np.uint8)
    records, methods = [], {}
    xs = left + sx*(np.arange(work.width) + .5)
    ys = top - sy*(np.arange(work.height) + .5)
    for role, mask in masks.items():
        preview[mask] = tuple(bytes.fromhex(COLORS[role][1:]))
        vectors = [(part, layer, sequence) for kind, path, layer, sequence in paths if kind == role
                   for part in polygon_parts(path.intersection(crop))]
        vector_mask = np.zeros_like(mask)
        if vectors and role not in skipped:
            vector_mask = contains_xy(union_all([path for path, _, _ in vectors]), xs[None, :], ys[:, None])
        union_count = (mask | vector_mask).sum()
        intersection = (mask & vector_mask).sum()
        agreement = float(intersection / union_count) if union_count else 0.
        prefix = {"building": "B", "exclude": "X", "pale": "P", "annotation": "A", "uncertain": "U"}[role]
        if vectors and agreement >= .95:
            methods[role] = {"method": "PDF vector", "rendered_agreement": agreement}
            for polygon, layer, sequence in vectors:
                records.append(feature(f"{prefix}{len(records)+1}", role, polygon,
                                       layer=layer, pdf_path=sequence))
        else:
            methods[role] = {"method": "raster", "rendered_vector_agreement": agreement}
            for polygon, change in mask_polygons(mask, (sx, 0, 0, -sy, left, top), settings):
                records.append(feature(f"{prefix}{len(records)+1}", role, polygon, simplification_area=change))
    audit = {"methods": methods, "pixel_counts": {k: int(v.sum()) for k, v in masks.items()},
             "pixel_size_plan_units": [sx, sy], "coordinate_system": "plan x right, y up, origin bottom left",
             "units": "PDF points" if filename.lower().endswith(".pdf") else "source pixels"}
    return PlanExtraction(original, Image.fromarray(preview), work, extent, collection(records),
                          asdict(settings), audit)
