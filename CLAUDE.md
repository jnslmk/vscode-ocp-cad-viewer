# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Overview

vscode-ocp-cad-viewer is a VS Code extension for viewing CadQuery and build123d CAD models. It combines:
- A VS Code extension (TypeScript in `src/`)
- A Python backend (`ocp_vscode/`) for tessellation and geometry analysis
- A web-based viewer using three-cad-viewer

## Commands

```bash
# Install Python package in development mode
pip install -e .

# Run standalone viewer (outside VS Code)
python -m ocp_vscode.standalone --port 3939

# TypeScript compilation (VS Code extension)
npm run compile

# Package VS Code extension
vsce package
```

## Architecture

- `src/` - VS Code extension TypeScript source
- `ocp_vscode/` - Python backend package
  - `backend.py` - WebSocket backend handling model data and tool responses
  - `standalone.py` - Flask server for standalone viewer mode
  - `selector_inference.py` - build123d selector expression inference
  - `static/js/` - Frontend JavaScript (from three-cad-viewer)
  - `static/css/` - Frontend styles (from three-cad-viewer)

## Frontend Build Workflow

The frontend viewer (`static/js/three-cad-viewer.esm.js`) comes from the [three-cad-viewer](https://github.com/bernhard-42/three-cad-viewer) package.

**For development with local three-cad-viewer changes:**

```bash
# 1. Make changes in three-cad-viewer repo
cd ../three-cad-viewer
# ... edit files in src/cad_tools/, src/viewer.js, etc.

# 2. Build three-cad-viewer
npm run build

# 3. Copy built files here
cp dist/three-cad-viewer.esm.js ../vscode-ocp-cad-viewer/ocp_vscode/static/js/
cp dist/three-cad-viewer.css ../vscode-ocp-cad-viewer/ocp_vscode/static/css/

# 4. Test with standalone viewer
python -m ocp_vscode.standalone --port 3939
```

**Note:** The `static/js/*.js` and `static/css/*.css` files are gitignored because they're built artifacts from three-cad-viewer. For production releases, they come from the npm package.

## Backend Tool Development

Tools have both frontend (three-cad-viewer) and backend (ocp_vscode) components:

**Backend side (`backend.py`):**
1. Add tool type to `Tool` class
2. Add handler case in `handle_activated_tool()`
3. Implement `handle_<toolname>()` method
4. Send response via `send_response()`

**Frontend side (in three-cad-viewer):**
1. Create tool class in `src/cad_tools/`
2. Integrate in `tools.js`
3. Build and copy as described above

## HTTP Endpoints (Standalone Mode)

- `GET /viewer` - Main viewer page
- `GET /selection` - Current element picker selection buffer (JSON)
- `POST /selection/clear` - Clear selection buffer
