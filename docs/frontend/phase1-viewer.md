# Phase 1 — 3D Floor Plan Viewer

Phase 1 of the frontend redesign ([Issue #15](https://github.com/denoslab/EDSim/issues/15)) delivers a Tiled-JSON parser and a Three.js 3D renderer that visualises the ED floor plan from the same asset files the legacy Phaser renderer consumes.

## Features

- **Interactive 3D scene** — orbit, zoom, and pan the camera around a full 3D model of the emergency department.
- **Extruded walls** — `BoxGeometry` walls with real height and shadow casting.
- **Textured floors** — wood planks in the waiting room, polished concrete in clinical areas, colour-tinted per zone category.
- **Kenney 3D furniture** — 7 GLTF models (beds, chairs, monitors, desks, tables) placed at every equipment position.
- **Google Maps-style navigation** — on-screen buttons for zoom, rotate, and reset.
- **Two seed maps** — Small ED Layout (30 × 20) and Foothills ED Layout (122 × 123).
- **Parsed-count stats** — sidebar shows zone, equipment, spawning, and wall counts.
- **URL persistence** — selected map survives page reloads.

## Running

```bash
./run_map_viewer.sh        # starts Vite dev server on :5173
./run_map_viewer.sh build  # production bundle
./run_map_viewer.sh test   # vitest unit tests
./run_map_viewer.sh test:e2e  # Playwright e2e tests
```

## Future phases

| Phase | Scope |
|---|---|
| Phase 2 | Agent rendering and replay scrubbing |
| Phase 3 | Real-time backend integration |
| Phase 4 | Metrics overlays and dashboards |
| Phase 5 | Production polish and optimisation |
