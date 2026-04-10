# Architecture Overview

EDSim consists of three main components and an analysis pipeline.

## Component layout

```
reverie/backend_server/          # Simulation engine
  reverie.py                     # ReverieServer — main simulation loop
  maze.py                        # Tile-based map and spatial state
  persona/                       # Agent classes and cognitive modules
    persona_types/               # Doctor, BedsideNurse, TriageNurse, Patient
    cognitive_modules/           # perceive, plan, reflect, converse, execute
    memory_structures/           # Scratch (short-term), AssociativeMemory (long-term)
    prompt_template/             # LLM prompt templates per role

environment/frontend_server/     # Legacy Django + Phaser frontend
  translator/views.py            # API endpoints
  storage/                       # Simulation state folders
  static_dirs/assets/the_ed/     # Tiled JSON maps and CSV block definitions

environment/react_frontend/      # Phase 1 React + Three.js 3D viewer
  src/parser/                    # Tiled JSON parser pipeline
  src/components/                # ThreeFloorPlan (3D scene)
  src/assets/                    # Textures and furniture sprites
  public/models/                 # Kenney GLTF furniture models

analysis/                        # Post-simulation metrics
  compute_metrics.py             # Patient throughput, wait times
```

## Data flow

1. The **simulation engine** reads its initial state from a seed folder under `environment/frontend_server/storage/`.
2. Each simulation step runs the cognitive loop (perceive → retrieve → plan → execute → converse → reflect).
3. Step output is written as JSON files under the simulation's `environment/` and `personas/` directories.
4. The **legacy frontend** reads those JSON files and renders them via Phaser on a Tiled map.
5. The **3D Floor Plan Viewer** parses the same Tiled JSON map files and renders the static floor plan in Three.js — it does not yet consume live simulation output (that's Phase 2).

## Simulation state

All simulation state lives under `environment/frontend_server/storage/<sim_name>/`:

| Path | Contents |
|---|---|
| `reverie/meta.json` | Simulation parameters |
| `reverie/maze_status.json` | Bed count overrides |
| `environment/` | Per-step movement and environment JSON |
| `personas/<name>/` | Agent memory (scratch, associative memory) |
