"""Read-only Streamlit viewer for the published strict axial atlas."""
from pathlib import Path
import json
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voronoi_app.research_data import data_path, unavailable

ATLAS = data_path("strict-generalisation/pilot-1/visual-report", local=ROOT / "diagnostics")

st.set_page_config(page_title="Strict axial maps", layout="wide")
st.title("Strict axial maps")


@st.cache_data
def entries(path: Path, modified: int) -> dict:
    return {row["id"]: row for row in json.loads(path.read_text())}


index = ATLAS / "index.json"
if not index.is_file():
    st.error(unavailable(index))
    st.stop()

try:
    maps = entries(index, index.stat().st_mtime_ns)
except (OSError, ValueError) as error:
    st.error(f"{unavailable(index)} {error}")
    st.stop()
selection = st.selectbox("Saved map", list(maps), key="selection", bind="query-params", required=True)
entry = maps[selection]
row = entry["statistics"]
cols = st.columns(4)
cols[0].metric("Lines", row["lines"])
cols[1].metric("Circulation rank", f"{row['rank']} / {row['internal_blocks']}")
cols[2].metric("Convex coverage", f"{row['covered_regions']} / {row['required_regions']}")
cols[3].metric("Validation", row["status"].capitalize())
view = st.segmented_control("View", ["Selected map", "Method comparison", "Corridor changes"],
                            default="Selected map")
image = entry[{"Selected map":"png", "Method comparison":"comparison",
               "Corridor changes":"diagnostic"}[view or "Selected map"]]
image_path = ATLAS / image
pdf = ATLAS / entry["pdf"]
try:
    image_bytes = image_path.read_bytes()
    pdf_bytes = pdf.read_bytes()
except OSError as error:
    st.error(unavailable(error.filename or image_path))
    st.stop()
st.image(image_bytes, width="stretch", alt=f"{view} for {entry['case']} {entry['method']}")
st.caption(f"Analysis record {row['analysis_record']} · physical screen {row['physical_screen_record']} "
           f"· statistical CSV line {entry['statistical_csv_line']}")
st.download_button("Download selected map PDF", pdf_bytes, file_name=pdf.name,
                   mime="application/pdf", on_click="ignore")
