# Voronoi Aggregation App

Experimental research platform for computational urban design, Voronoi aggregation, and space-syntax analysis.

## Architecture

This application has been refactored into a **modular, extensible research platform** with pluggable components for:

- **Terrain Providers** (6 types: Flat, Hill, Ridge, Shoulder, Valley, Twin Peaks)
- **Grid Generators** (Voronoi, Cartesian)
- **Aggregation Strategies** (Slope preference, future: distance, visibility)
- **Space-Syntax Measures** (Mean Depth, Connectivity, Integration, Choice)
- **Representations** (Cell graph, Dual graph, future: Axial maps)

See [ARCHITECTURE_PROGRESS.md](ARCHITECTURE_PROGRESS.md) for detailed refactoring status and extension guide.

## Features

- Interactive Streamlit UI with parameter controls
- Procedural terrain generation
- Voronoi and Cartesian grid generation
- Dyad-based urban aggregation with slope preference
- Visibility graph computation
- Space-syntax analysis (connectivity, integration, choice measures)
- Morphic grammar experiments with random, adjacent and enclosing occupation
- Sampled maximal-line axial approximation and axial graph diagnostics
- Experiment serialization to JSON
- Reproducible research with seed control

## Requirements

- Python 3.8+
- Project virtual environment in `.venv`

## Running the App

From the project root:

```bash
./run_streamlit.sh
```

The script activates the venv, sets PYTHONPATH, and starts Streamlit on port 8501.
The sidebar includes both **Morphic Grammar Experiments** and
**Morphic Grammar - Emergent Axial Structure**.

The axial page derives a sampled maximal-line approximation from continuous
open-space geometry. It is explicitly not presented as a complete or unique
conventional axial map. See [MORPHIC_GRAMMAR_AXIAL_REPORT.md](MORPHIC_GRAMMAR_AXIAL_REPORT.md)
for definitions, validation, limitations and the 30-seed results.

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Run the staged axial comparison (five-seed pilot first, then 30 seeds):

```bash
PYTHONPATH=src .venv/bin/python scripts/run_morphic_axial_batch.py --pilot
PYTHONPATH=src .venv/bin/python scripts/run_morphic_axial_batch.py
```

Outputs are written under `outputs/morphic_axial_batch_pilot/` and
`outputs/morphic_axial_batch/`.

## Project Structure

```
voronoi-app/
├── app/
│   └── streamlit_app.py          # Main UI (being updated)
├── src/voronoi_app/
│   ├── core.py                   # Core abstractions
│   ├── registry.py               # Component registry
│   ├── terrain.py                # Terrain providers
│   ├── grid_generators.py        # Grid strategies
│   ├── aggregation.py            # Aggregation strategies
│   ├── analysis.py               # Space-syntax measures
│   ├── orchestrator.py           # Experiment orchestration
│   ├── config.py                 # Legacy config (preserved)
│   ├── engine.py                 # Legacy engine (preserved)
│   ├── render.py                 # Rendering (works with new architecture)
│   └── runner.py                 # Legacy runner (preserved)
├── tests/
│   ├── test_render_doors.py      # Legacy rendering test
│   └── test_architecture.py      # New architecture tests
├── ARCHITECTURE_PROGRESS.md      # Detailed progress & extension guide
└── README.md                     # This file
```

## Extension Guide

To add a new terrain type, grid generator, or space-syntax measure:

1. **Create your implementation** - Subclass the appropriate abstract base
2. **Register it** - Add to `voronoi_app/registry.py` in `register_defaults()`
3. **Add tests** - Create test cases in `tests/test_architecture.py`
4. **Update UI** - Wire selector controls in `streamlit_app.py` (coming soon)

See [ARCHITECTURE_PROGRESS.md](ARCHITECTURE_PROGRESS.md) for detailed examples and API reference.
