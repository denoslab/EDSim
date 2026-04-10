# 3D Floor Plan Viewer

The Phase 1 floor plan viewer lives under `environment/react_frontend/` and provides an interactive 3D rendering of the ED layout.

## Technology stack

| Layer | Technology |
|---|---|
| Build tool | Vite 5 |
| Language | TypeScript 5 (strict mode) |
| UI framework | React 18 |
| 3D renderer | Three.js via `@react-three/fiber` + `@react-three/drei` |
| Unit tests | Vitest |
| E2E tests | Playwright (Chromium) |
| Linting | ESLint 9 (flat config) |

## Scene hierarchy

`ThreeFloorPlan` renders the following hierarchy inside a `<Canvas>`:

1. **GroundPlane** — large dark surface surrounding the building.
2. **ZoneFloor** (×N) — one `PlaneGeometry` per zone region, textured with the raster PNG (wood or concrete) and tinted with the zone colour.
3. **Walls** — `BoxGeometry` per wall segment, extruded to 2.5 units height, white `MeshStandardMaterial`, shadow casting enabled.
4. **Furniture** (×N) — Kenney `.glb` models loaded via `useGLTF`, placed at each equipment tile position, casting and receiving shadows.
5. **Lighting** — `DirectionalLight` (2048 px shadow map) + warm `AmbientLight` fill.
6. **OrbitControls** — drag/scroll/right-drag camera interaction.
7. **NavControls** — HTML overlay with zoom/rotate/reset buttons.

## Data flow

```
Tiled JSON + CSV files
        ↓
   parseTiledJSON()  →  MapLayout
        ↓
   ThreeFloorPlan    →  Three.js scene
        ↓
   Browser WebGL canvas
```

The parser is a pure function with no side effects — it takes the raw Tiled data and emits a strongly-typed `MapLayout` object. The renderer consumes `MapLayout` and builds the 3D scene. This separation means the parser can be tested in isolation (42 vitest tests) and the renderer can be swapped without touching any parsing logic.
