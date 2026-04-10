# Three.js Renderer

`ThreeFloorPlan` (`src/components/ThreeFloorPlan.tsx`) is the sole renderer for the Phase 1 floor plan viewer. It consumes a `MapLayout` and produces a full 3D scene using `@react-three/fiber`.

## Scene components

### Zone floors

Each `ZoneRegion` becomes a `PlaneGeometry` positioned at its bounding-box centre, textured with either wood (waiting room) or polished concrete (clinical rooms), and tinted with a per-zone colour from `@/theme/colors`.

### Walls

Each `WallSegment` becomes a `BoxGeometry` with:

- Width = segment length (horizontal) or wall thickness (vertical)
- Depth = wall thickness (horizontal) or segment length (vertical)
- Height = 2.5 Three.js units
- Material: white `MeshStandardMaterial` with shadow casting

### Furniture

7 Kenney Furniture Kit 2.0 (CC0) GLTF models loaded via `useGLTF`:

| Equipment type | Model file | Scale |
|---|---|---|
| `bed` | `bed.glb` (bedSingle) | 1.2 |
| `chair` | `chair.glb` (chairCushion) | 0.8 |
| `waiting_room_chair` | `waiting_chair.glb` (loungeChair) | 0.8 |
| `computer` | `computer.glb` (computerScreen) | 0.8 |
| `diagnostic_table` | `diagnostic_table.glb` (table) | 0.8 |
| `medical_equipment` | `medical_cart.glb` (desk) | 0.8 |
| `wheelchair` | `wheelchair.glb` (chairDesk) | 0.8 |

Each model is cloned per placement, positioned at `(tileX + 0.5, 0, tileY + 0.5)`, and configured to cast and receive shadows.

### Lighting

- **DirectionalLight** — positioned top-left of the map, 2048 px shadow map, warm colour `#FFFAF0`, intensity 1.2.
- **AmbientLight** — intensity 0.5, colour `#E8E4DC`.

### Camera

`OrbitControls` from `@react-three/drei`:

- **Drag** to orbit
- **Scroll** to zoom (clamped: min 3 units, max 2.5 × map diagonal)
- **Right-drag** to pan
- **Max polar angle** clamped to prevent flipping below the ground plane

### Navigation overlay

HTML buttons overlaying the WebGL canvas:

| Button | Action |
|---|---|
| **+** | Zoom in (camera moves 20% closer to orbit target) |
| **-** | Zoom out (camera moves 20% farther) |
| **Rotate left** | Orbits camera 22.5 degrees counter-clockwise |
| **Rotate right** | Orbits camera 22.5 degrees clockwise |
| **Reset** | Returns camera to initial bird's-eye position |
