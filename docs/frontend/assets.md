# Assets & Models

The Phase 1 viewer ships pre-baked raster textures and 3D furniture models. No runtime procedural generation is required.

## Floor textures

| File | Size | Used by | Description |
|---|---|---|---|
| `src/assets/textures/wood.png` | 512 × 512 | Waiting room | Warm wood plank pattern with grain, knots, and fBm mottle |
| `src/assets/textures/tile_concrete.png` | 512 × 512 | All clinical rooms | Polished concrete with subtle directional lighting and mottling |

Textures are loaded via Vite's `?url` import suffix, which fingerprints them at build time. The Three.js `TextureLoader` fetches them and applies them as tiling `map` materials on zone floor planes.

## Furniture models (GLTF)

7 models from the [Kenney Furniture Kit 2.0](https://kenney.nl/assets/furniture-kit) (CC0 public domain):

| File | Source model | Equipment type |
|---|---|---|
| `public/models/bed.glb` | bedSingle.glb | `bed` |
| `public/models/chair.glb` | chairCushion.glb | `chair` |
| `public/models/waiting_chair.glb` | loungeChair.glb | `waiting_room_chair` |
| `public/models/computer.glb` | computerScreen.glb | `computer` |
| `public/models/diagnostic_table.glb` | table.glb | `diagnostic_table` |
| `public/models/medical_cart.glb` | desk.glb | `medical_equipment` |
| `public/models/wheelchair.glb` | chairDesk.glb | `wheelchair` |

Models are loaded by `useGLTF` from `@react-three/drei`, cloned per equipment placement, and configured for shadow casting/receiving.

## Furniture sprite PNGs (reference)

5 Kenney isometric sprite PNGs are kept in `src/assets/furniture/` for reference and potential future 2D fallback use. They are not loaded by the Three.js renderer.

## Asset generation pipeline

`scripts/generate-assets.mjs` is a Playwright-based build-time generator that produces the floor texture PNGs. It launches headless Chromium, runs elaborate procedural canvas drawing code (deterministic PRNG, value noise, fBm mottle, directional lighting, pixel noise), and captures each canvas as a PNG.

```bash
npm run generate-assets
```

The generated PNGs are committed to the repository so the runtime has no generation cost.

## Replacing assets

To swap a furniture model or floor texture:

1. Replace the file at its existing path (same filename).
2. The viewer picks up the change on the next `npm run dev` restart.
3. No code changes needed — the asset catalogue (`src/assets/index.ts`) maps by filename.

To add a new equipment type:

1. Add the `.glb` model to `public/models/`.
2. Add the model URL to `MODEL_URLS` in `ThreeFloorPlan.tsx`.
3. Add the equipment type to the parser's `EquipmentType` union in `types.ts`.
4. Add the tile-id → type mapping in `game_object_blocks.csv`.
