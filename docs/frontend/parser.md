# Tiled JSON Parser

The parser (`src/parser/`) converts the legacy Tiled JSON map files and their companion CSV lookup tables into a strongly-typed `MapLayout` that the Three.js renderer consumes.

## Pipeline

```
parseTiledJSON(mapId, tiledMap, specialBlocks) → MapLayout
```

1. **Layer lookup** — locates the five required Tiled layers by name: `Arena Layer`, `Object Interaction Layer`, `Spawning Blocks`, `Walls`, `Collisions`.
2. **CSV decoding** — translates `arena_blocks.csv`, `game_object_blocks.csv`, and `spawning_location_blocks.csv` into Tiled-GID-keyed lookup tables. Unknown labels emit a warning.
3. **Zone extraction** — walks the Arena Layer with iterative 4-way flood fill, grouping orthogonally-adjacent tiles that map to the same `ZoneId` into one `ZoneRegion`. Each region carries its full tile cluster, bounding box, centroid, and a clockwise perimeter polygon (collinear vertices removed).
4. **Equipment extraction** — emits one `EquipmentPlacement` per recognised tile in the Object Interaction Layer.
5. **Spawning extraction** — same pattern for the Spawning Blocks layer.
6. **Wall compression** — perimeter-only: for each wall tile, a side is only emitted when the neighbour on that side is not a wall. The resulting edges are merged into long axis-aligned segments.
7. **Collision mask** — straight `boolean[y][x]` projection of the Collisions layer.

## Data model

```typescript
interface MapLayout {
  mapId: string;
  widthInTiles: number;
  heightInTiles: number;
  tileSizePx: number;
  zones: ZoneRegion[];
  equipment: EquipmentPlacement[];
  spawningLocations: SpawningLocation[];
  walls: WallSegment[];
  collisionMask: boolean[][];
}
```

See `src/parser/types.ts` for the full type definitions with TSDoc on every field.

## Zone categories

| ZoneId | Display name | Tile IDs |
|---|---|---|
| `triage_room` | Triage | 1314, 1335 |
| `waiting_room` | Waiting Room | 1313 |
| `hallway` | Hallway | 1315 |
| `minor_injuries_zone` | Minor Injuries | 1299 |
| `major_injuries_zone` | Major Injuries | 1317 |
| `trauma_room` | Trauma | 1345 |
| `diagnostic_room` | Diagnostics | 1316 |
| `exit` | Exit | 1350 |

## Coordinate conventions

- **Tile coordinates** — integer `(x, y)` pairs, origin at top-left, x increases right, y increases down.
- **Tile-corner coordinates** — used in `ZoneRegion.polygon` and `WallSegment` endpoints. A 1 × 1 tile at `(3, 4)` has corners `(3,4)`, `(4,4)`, `(4,5)`, `(3,5)`.

## Fixture-pinned test counts

| Map | Zones | Equipment | Spawning | Wall segments |
|---|---|---|---|---|
| `small_ed_layout` (30 × 20) | 8 | 42 | 18 | 38 |
| `foothills_ed_layout` (122 × 123) | 26 | 219 | 70 | 774 |
