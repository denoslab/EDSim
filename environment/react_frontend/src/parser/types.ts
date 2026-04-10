/**
 * Strongly-typed data model for the EDSim Tiled-map parser.
 *
 * The simulator's legacy renderer (Phaser) consumed Tiled JSON files directly
 * from `environment/frontend_server/static_dirs/assets/the_ed/visuals/`. The
 * Phase 1 React/Three.js renderer reuses the *same* asset files unchanged, but
 * compiles them to a higher-level {@link MapLayout} structure that downstream
 * UI layers (zones, equipment, walls, agents, debug overlays) can consume
 * without re-walking the raw 2D tile arrays.
 *
 * The data model intentionally separates *tile coordinates* (integer column /
 * row indices into the map grid) from *pixel coordinates* (the projected
 * positions used by the renderer). All entities in this module work in
 * tile coordinates; the {@link ThreeFloorPlan} component performs the final
 * `tile → pixel` projection so that zoom and scaling remain trivial.
 *
 * @packageDocumentation
 */

/**
 * The eight zone categories defined by the EDSim seed map.
 *
 * The string identifiers match the trailing label in
 * `arena_blocks.csv` (the legacy backend's authoritative tile-id → zone
 * mapping), normalised to snake_case.
 */
export type ZoneId =
  | 'triage_room'
  | 'waiting_room'
  | 'hallway'
  | 'minor_injuries_zone'
  | 'major_injuries_zone'
  | 'trauma_room'
  | 'diagnostic_room'
  | 'exit';

/**
 * Equipment types extracted from the Tiled "Object Interaction Layer".
 *
 * The string identifiers match the trailing label in
 * `game_object_blocks.csv` (the backend's authoritative tile-id → object
 * mapping), normalised to snake_case.
 */
export type EquipmentType =
  | 'bed'
  | 'chair'
  | 'wheelchair'
  | 'medical_equipment'
  | 'computer'
  | 'waiting_room_chair'
  | 'diagnostic_table';

/**
 * A 2D point in tile coordinates.
 *
 * Tile coordinates are integer column / row indices: `x` increases to the
 * right, `y` increases downward, and `(0, 0)` is the top-left tile of the
 * map.
 */
export interface TilePoint {
  /** Tile column index (0-based, increases left-to-right). */
  x: number;
  /** Tile row index (0-based, increases top-to-bottom). */
  y: number;
}

/**
 * A single contiguous zone region.
 *
 * Connected components are computed by 4-way flood fill on the Arena Layer.
 * A zone region is therefore a maximal set of orthogonally-adjacent tiles
 * sharing the same {@link ZoneId}. The simulator's seed map exposes one
 * zone per category, but maps with split rooms (e.g. dual triage rooms)
 * are also supported.
 */
export interface ZoneRegion {
  /**
   * Stable identifier for this region. Format: `${zoneId}-${componentIndex}`,
   * where `componentIndex` is 0-based and assigned in scan order.
   */
  zoneRegionId: string;
  /** Zone category (one of the eight predefined zones). */
  zoneId: ZoneId;
  /** Human-readable display label (e.g. "Triage", "Waiting Room"). */
  zoneName: string;
  /**
   * Polygon outline of the region as an ordered list of tile-coordinate
   * vertices in clockwise order. Each vertex sits at a tile *corner*, not
   * a tile *centre* — the polygon traces the outer edge of the contiguous
   * tile cluster. For axis-aligned cluster shapes the polygon is the
   * bounding rectangle; for L-shapes and other non-convex shapes the
   * polygon follows the perimeter exactly.
   *
   * The renderer can use this directly as a closed polygon outline.
   */
  polygon: TilePoint[];
  /**
   * Every individual tile that belongs to this region, in scan order
   * (row-major). Useful for axis-aligned rendering, validation, and
   * debug overlays.
   */
  tilePositions: TilePoint[];
  /**
   * Axis-aligned bounding box of the region. Convenient for label
   * placement and quick spatial queries.
   */
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  /**
   * Geometric centroid of the region in tile coordinates. Used as the
   * default anchor when placing the zone's text label.
   */
  centroid: TilePoint;
}

/**
 * A single piece of equipment placed at a tile coordinate.
 */
export interface EquipmentPlacement {
  /** Stable id of the form `${type}-${tileX}-${tileY}`. */
  equipmentId: string;
  /** Equipment category. */
  type: EquipmentType;
  /** Tile column. */
  tileX: number;
  /** Tile row. */
  tileY: number;
  /** Raw Tiled GID this placement was decoded from. */
  rawTileId: number;
}

/**
 * A spawning slot used by the simulator to seed agents.
 */
export interface SpawningLocation {
  /** Stable id of the form `${zoneId}-${slot}`. */
  spawningId: string;
  /** Zone the slot belongs to. */
  zoneId: ZoneId;
  /** Slot label (e.g. "sp-A", "sp-B", ...). */
  slot: string;
  /** Tile column. */
  tileX: number;
  /** Tile row. */
  tileY: number;
}

/**
 * A wall segment derived from the Walls layer.
 *
 * The parser walks the Walls layer and emits a horizontal segment for each
 * row-run of consecutive wall tiles, plus a vertical segment for each
 * column-run. This produces a compact set of axis-aligned line primitives
 * that the renderer can convert directly into wall geometry.
 *
 * Coordinates are *tile-edge* aligned: the values represent positions along
 * the integer tile grid where the wall starts and ends. A horizontal wall on
 * row `r` running from column `a` to column `b` has `y1 === y2 === r` and
 * `x1 === a, x2 === b + 1`.
 */
export interface WallSegment {
  /** Orientation of the segment. */
  orientation: 'horizontal' | 'vertical';
  /** Start point in tile-edge coordinates. */
  x1: number;
  y1: number;
  /** End point in tile-edge coordinates. */
  x2: number;
  y2: number;
}

/**
 * Top-level parsed map data.
 *
 * This is the single source of truth that the renderer consumes.
 * Construct an instance via {@link parseTiledJSON}; do not mutate it after
 * construction. The parser's tests pin the expected counts and structures so
 * that any future change to the underlying Tiled assets surfaces immediately.
 */
export interface MapLayout {
  /** Display name (matches the source filename without extension). */
  mapId: string;
  /** Map width in tiles. */
  widthInTiles: number;
  /** Map height in tiles. */
  heightInTiles: number;
  /** Native Tiled tile size in pixels (square tiles). */
  tileSizePx: number;
  /** Connected zone regions (one entry per contiguous component). */
  zones: ZoneRegion[];
  /** All equipment placements. */
  equipment: EquipmentPlacement[];
  /** All spawning slots. */
  spawningLocations: SpawningLocation[];
  /** Compact wall segments suitable for direct rendering. */
  walls: WallSegment[];
  /**
   * Boolean collision mask, indexed `[y][x]`. `true` indicates the tile is
   * blocked. Useful for debug overlays and pathfinding validation.
   */
  collisionMask: boolean[][];
}

/**
 * Raw Tiled JSON shape we depend on. Tiled emits dozens of optional fields;
 * we deliberately type only what the parser actually reads, so any future
 * Tiled-format change manifests as a clean type error rather than a silent
 * `undefined` propagation.
 */
export interface TiledLayer {
  name: string;
  type: string;
  width: number;
  height: number;
  data: number[];
  visible?: boolean;
  opacity?: number;
}

export interface TiledMap {
  width: number;
  height: number;
  tilewidth: number;
  tileheight: number;
  layers: TiledLayer[];
}

/**
 * Mapping rows decoded from `arena_blocks.csv`. Each row maps a Tiled GID to
 * the human-readable zone label that appears in the CSV's last column.
 */
export interface ArenaBlockRow {
  tileId: number;
  zoneLabel: string;
}

/**
 * Mapping rows decoded from `game_object_blocks.csv`.
 */
export interface GameObjectBlockRow {
  tileId: number;
  objectLabel: string;
}

/**
 * Mapping rows decoded from `spawning_location_blocks.csv`. Each row carries
 * the destination zone label and the slot identifier in addition to the
 * Tiled GID.
 */
export interface SpawningBlockRow {
  tileId: number;
  zoneLabel: string;
  slot: string;
}

/**
 * Convenience bundle of all special-block tables. Decoded once and passed
 * to {@link parseTiledJSON}.
 */
export interface SpecialBlocks {
  arenaBlocks: ArenaBlockRow[];
  gameObjectBlocks: GameObjectBlockRow[];
  spawningBlocks: SpawningBlockRow[];
}
