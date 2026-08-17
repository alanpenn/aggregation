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

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Current test status: **18 passing, 1 skipped** (see `tests/test_architecture.py`)

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
