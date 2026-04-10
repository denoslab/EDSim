# EDSim React Frontend (Phase 1)

An interactive 3D floor plan renderer for the EDSim emergency department
simulator. Built with **React + Vite + TypeScript + Three.js**
(`@react-three/fiber` + `@react-three/drei`).

This package implements **Phase 1** of the frontend redesign tracked in
[Issue #15](https://github.com/denoslab/EDSim/issues/15): a Tiled-JSON
parser and a 3D Three.js scene with extruded walls, textured floors,
and Kenney furniture models.

## Quick start

```bash
./run_map_viewer.sh        # install deps (first run) and start dev server
```

Open <http://127.0.0.1:5173>. You should see a 3D floor plan of the ED
with:
- Extruded walls with real height and shadow casting
- Textured floors (wood planks in the waiting room, polished concrete elsewhere)
- Kenney 3D furniture models (beds, chairs, desks, monitors, tables)
- Google Maps-style navigation controls (zoom, rotate, reset)
- OrbitControls: drag to orbit, scroll to zoom, right-drag to pan
- Sidebar with map catalogue, display toggles, and parsed-count stats

## Architecture

```
environment/react_frontend/
├── src/
│   ├── main.tsx             # React entry point
│   ├── MapViewer.tsx        # Top-level page (sidebar + 3D canvas)
│   ├── components/
│   │   └── ThreeFloorPlan.tsx  # Three.js scene (walls, floors, furniture, lighting, controls)
│   ├── parser/
│   │   ├── types.ts         # MapLayout, ZoneRegion, EquipmentPlacement, ...
│   │   ├── csv.ts           # Decoders for the special_blocks/*.csv tables
│   │   ├── parseTiledJSON.ts# The parser pipeline
│   │   ├── loadMapLayout.ts # fetch() helper that drives the parser
│   │   └── index.ts         # Public barrel
│   ├── assets/
│   │   ├── index.ts         # Asset catalogue (texture URLs, model paths)
│   │   ├── textures/        # Floor texture PNGs (wood, concrete)
│   │   └── furniture/       # Kenney isometric sprite PNGs (kept for reference)
│   ├── theme/
│   │   └── colors.ts        # Zone colours, canvas background
│   └── data/
│       └── maps.ts          # Catalogue of available Tiled fixtures
├── public/
│   └── models/              # Kenney GLTF furniture models (.glb)
├── tests/
│   ├── unit/                # vitest parser tests (51)
│   └── e2e/                 # Playwright viewer tests (6)
├── scripts/
│   ├── generate-assets.mjs  # Build-time PNG texture generator
│   └── dump-parser.mjs      # CLI parser output dumper
└── README.md
```

### Three.js scene structure

`ThreeFloorPlan` renders the following hierarchy:

1. **GroundPlane** — large dark surface surrounding the building
2. **ZoneFloor** — one `PlaneGeometry` per zone region, textured with
   the raster PNG (wood or concrete) and tinted with the zone colour
3. **Walls** — `BoxGeometry` per wall segment, extruded to 2.5 units
   height, white MeshStandardMaterial, shadow casting enabled
4. **Furniture** — Kenney `.glb` models loaded via `useGLTF`, placed
   at each equipment tile position, casting and receiving shadows
5. **Lighting** — `DirectionalLight` (2048px shadow map) + warm
   `AmbientLight` fill
6. **OrbitControls** — drag/scroll/right-drag camera interaction
7. **NavControls** — HTML overlay with zoom/rotate/reset buttons

### Furniture models

7 Kenney Furniture Kit 2.0 (CC0) GLTF models in `public/models/`:

| Model | Source | Equipment type |
|---|---|---|
| bed.glb | bedSingle.glb | bed |
| chair.glb | chairCushion.glb | chair |
| waiting_chair.glb | loungeChair.glb | waiting_room_chair |
| computer.glb | computerScreen.glb | computer |
| diagnostic_table.glb | table.glb | diagnostic_table |
| medical_cart.glb | desk.glb | medical_equipment |
| wheelchair.glb | chairDesk.glb | wheelchair |

## Running the tests

```bash
./run_map_viewer.sh test        # 51 vitest unit tests (parser)
./run_map_viewer.sh test:e2e    # 6 Playwright e2e tests (viewer)
```

## Adding a new map

1. Drop the Tiled JSON under
   `environment/frontend_server/static_dirs/assets/the_ed/visuals/`.
2. If it introduces new tile GIDs, update the
   `matrix/special_blocks/*.csv` files.
3. Append a new entry to `src/data/maps.ts`.
4. The sidebar picks it up automatically.
