/**
 * Tiled JSON → MapLayout parser for the EDSim React/Three.js frontend.
 *
 * This module is the single point at which the legacy Tiled assets are
 * converted into the strongly-typed {@link MapLayout} structure that the
 * the Three.js renderer consumes. The parser is intentionally pure: every
 * function takes its inputs explicitly and returns a fresh object. There is
 * no module-level state, no caching, and no I/O — callers are responsible
 * for fetching the JSON and CSV files however they prefer (browser `fetch`,
 * Node `readFileSync`, etc.).
 *
 * The high-level pipeline:
 *
 * 1. Locate the named layers in the Tiled JSON: Arena, Object Interaction,
 *    Spawning Blocks, Walls, Collisions.
 * 2. Translate the special-block CSVs into Tiled-GID-keyed lookup tables.
 * 3. Walk the Arena Layer with a 4-way flood fill to extract one
 *    {@link ZoneRegion} per contiguous component, then trace its perimeter
 *    polygon and compute its bounds and centroid.
 * 4. Walk the Object Interaction Layer and emit one
 *    {@link EquipmentPlacement} per recognised tile.
 * 5. Walk the Spawning Blocks layer and emit one {@link SpawningLocation}
 *    per recognised tile.
 * 6. Compress the Walls layer into axis-aligned {@link WallSegment}s.
 * 7. Convert the Collisions layer into a `boolean[][]` mask.
 *
 * Tile coordinates everywhere are integer `(column, row)` pairs with the
 * origin at the top-left of the map. The pixel projection is left to the
 * Three.js scene component.
 *
 * @packageDocumentation
 */

import type {
  EquipmentPlacement,
  EquipmentType,
  MapLayout,
  SpawningLocation,
  SpecialBlocks,
  TiledLayer,
  TiledMap,
  TilePoint,
  WallSegment,
  ZoneId,
  ZoneRegion
} from './types.js';

/* -------------------------------------------------------------------------- */
/* Layer name constants                                                       */
/* -------------------------------------------------------------------------- */

/** Layer names used by the EDSim seed Tiled maps. */
export const LAYER_NAMES = {
  arena: 'Arena Layer',
  objectInteraction: 'Object Interaction Layer',
  spawningBlocks: 'Spawning Blocks',
  walls: 'Walls',
  collisions: 'Collisions'
} as const;

/* -------------------------------------------------------------------------- */
/* CSV-label normalisation                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Normalise a free-form zone label from `arena_blocks.csv` into the
 * canonical {@link ZoneId} the rest of the renderer uses.
 *
 * The mapping is intentionally conservative: unknown labels return
 * `undefined` so that the parser can warn instead of silently mis-classifying
 * tiles.
 *
 * @param label - Raw label string from the CSV (e.g. `"triage room"`).
 * @returns The matching {@link ZoneId}, or `undefined` if no match.
 */
export function normaliseZoneId(label: string): ZoneId | undefined {
  const cleaned = label.trim().toLowerCase();
  switch (cleaned) {
    case 'triage room':
      return 'triage_room';
    case 'waiting room':
      return 'waiting_room';
    case 'hallway':
      return 'hallway';
    case 'minor injuries zone':
      return 'minor_injuries_zone';
    case 'major injuries zone':
      return 'major_injuries_zone';
    case 'trauma room':
      return 'trauma_room';
    case 'diagnostic room':
      return 'diagnostic_room';
    case 'exit':
      return 'exit';
    default:
      return undefined;
  }
}

/**
 * Human-readable display name for a zone, used as the centred label drawn
 * on top of the zone's polygon.
 */
export function zoneDisplayName(zoneId: ZoneId): string {
  switch (zoneId) {
    case 'triage_room':
      return 'Triage';
    case 'waiting_room':
      return 'Waiting Room';
    case 'hallway':
      return 'Hallway';
    case 'minor_injuries_zone':
      return 'Minor Injuries';
    case 'major_injuries_zone':
      return 'Major Injuries';
    case 'trauma_room':
      return 'Trauma';
    case 'diagnostic_room':
      return 'Diagnostics';
    case 'exit':
      return 'Exit';
  }
}

/**
 * Normalise a free-form object label from `game_object_blocks.csv` into the
 * canonical {@link EquipmentType}.
 */
export function normaliseEquipmentType(label: string): EquipmentType | undefined {
  const cleaned = label.trim().toLowerCase();
  switch (cleaned) {
    case 'bed':
      return 'bed';
    case 'chair':
      return 'chair';
    case 'wheelchair':
      return 'wheelchair';
    case 'medical equipment':
      return 'medical_equipment';
    case 'computer':
      return 'computer';
    case 'waiting room chair':
      return 'waiting_room_chair';
    case 'diagnostic table':
      return 'diagnostic_table';
    default:
      return undefined;
  }
}

/* -------------------------------------------------------------------------- */
/* Tiled layer helpers                                                        */
/* -------------------------------------------------------------------------- */

/**
 * Look up a Tiled layer by name. Throws a clear error if the layer is missing
 * — silent failure here would propagate as confusing empty arrays downstream.
 */
function findLayer(map: TiledMap, name: string): TiledLayer {
  const layer = map.layers.find((l) => l.name === name);
  if (!layer) {
    throw new Error(
      `Tiled map is missing required layer "${name}". Available layers: ${map.layers
        .map((l) => l.name)
        .join(', ')}`
    );
  }
  if (layer.type !== 'tilelayer') {
    throw new Error(
      `Tiled layer "${name}" must be of type "tilelayer", got "${layer.type}".`
    );
  }
  if (layer.data.length !== layer.width * layer.height) {
    throw new Error(
      `Tiled layer "${name}" has data length ${layer.data.length} but expected ${
        layer.width * layer.height
      } (${layer.width}×${layer.height}).`
    );
  }
  return layer;
}

/**
 * Read a tile id at `(x, y)` from a Tiled layer's flat data array. Returns
 * `0` for out-of-range coordinates so callers can skip neighbour checks.
 */
function tileAt(layer: TiledLayer, x: number, y: number): number {
  if (x < 0 || y < 0 || x >= layer.width || y >= layer.height) {
    return 0;
  }
  return layer.data[y * layer.width + x] ?? 0;
}

/* -------------------------------------------------------------------------- */
/* Zone extraction (4-way flood fill)                                         */
/* -------------------------------------------------------------------------- */

/**
 * Extract all contiguous zone regions from the Arena Layer.
 *
 * The algorithm walks the layer in row-major order. For each unvisited tile
 * whose GID maps to a known {@link ZoneId}, it runs an iterative 4-way flood
 * fill collecting every orthogonally-adjacent tile that maps to the *same*
 * zone id. The collected tile set becomes one {@link ZoneRegion}, with its
 * polygon, bounds, and centroid computed via the helpers below.
 *
 * Two important details:
 *
 * - We compare on the *normalised* {@link ZoneId}, not the raw Tiled GID.
 *   This means that two adjacent triage tiles using different art GIDs
 *   (which the legacy maps do — e.g. 1314 vs 1335) still merge into a
 *   single triage region.
 * - The fill is iterative (uses an explicit stack) rather than recursive,
 *   so we don't blow the call stack on the 122×123 Foothills map.
 */
export function extractZoneRegions(
  arena: TiledLayer,
  arenaTileToZone: Map<number, ZoneId>
): ZoneRegion[] {
  const visited: boolean[] = new Array(arena.data.length).fill(false);
  const regions: ZoneRegion[] = [];
  const componentCounts = new Map<ZoneId, number>();

  for (let y = 0; y < arena.height; y++) {
    for (let x = 0; x < arena.width; x++) {
      const idx = y * arena.width + x;
      if (visited[idx]) continue;

      const tileId = arena.data[idx]!;
      const zoneId = arenaTileToZone.get(tileId);
      if (!zoneId) {
        visited[idx] = true;
        continue;
      }

      const tilePositions: TilePoint[] = [];
      const stack: TilePoint[] = [{ x, y }];

      while (stack.length > 0) {
        const point = stack.pop()!;
        const pIdx = point.y * arena.width + point.x;
        if (visited[pIdx]) continue;

        const pTileId = arena.data[pIdx]!;
        const pZoneId = arenaTileToZone.get(pTileId);
        if (pZoneId !== zoneId) continue;

        visited[pIdx] = true;
        tilePositions.push(point);

        // 4-way neighbours
        if (point.x > 0) stack.push({ x: point.x - 1, y: point.y });
        if (point.x < arena.width - 1) stack.push({ x: point.x + 1, y: point.y });
        if (point.y > 0) stack.push({ x: point.x, y: point.y - 1 });
        if (point.y < arena.height - 1) stack.push({ x: point.x, y: point.y + 1 });
      }

      const componentIndex = componentCounts.get(zoneId) ?? 0;
      componentCounts.set(zoneId, componentIndex + 1);

      // Sort tile positions in row-major order so callers get a stable
      // iteration order independent of the flood-fill traversal pattern.
      tilePositions.sort((a, b) => (a.y - b.y) || (a.x - b.x));

      regions.push({
        zoneRegionId: `${zoneId}-${componentIndex}`,
        zoneId,
        zoneName: zoneDisplayName(zoneId),
        polygon: tracePerimeterPolygon(tilePositions),
        tilePositions,
        bounds: computeBounds(tilePositions),
        centroid: computeCentroid(tilePositions)
      });
    }
  }

  return regions;
}

/**
 * Compute the axis-aligned bounding box of a tile cluster.
 */
export function computeBounds(tiles: readonly TilePoint[]): ZoneRegion['bounds'] {
  if (tiles.length === 0) {
    throw new Error('computeBounds called with empty tile cluster');
  }
  let minX = tiles[0]!.x;
  let minY = tiles[0]!.y;
  let maxX = tiles[0]!.x;
  let maxY = tiles[0]!.y;
  for (const t of tiles) {
    if (t.x < minX) minX = t.x;
    if (t.y < minY) minY = t.y;
    if (t.x > maxX) maxX = t.x;
    if (t.y > maxY) maxY = t.y;
  }
  return { minX, minY, maxX, maxY };
}

/**
 * Compute the geometric centroid of a tile cluster, expressed in tile
 * coordinates. The centroid is the *mean* of the tile centres, not the
 * centre of the bounding box; this places labels more accurately for
 * non-rectangular zones (e.g. an L-shaped hallway).
 */
export function computeCentroid(tiles: readonly TilePoint[]): TilePoint {
  if (tiles.length === 0) {
    throw new Error('computeCentroid called with empty tile cluster');
  }
  let sumX = 0;
  let sumY = 0;
  for (const t of tiles) {
    sumX += t.x + 0.5;
    sumY += t.y + 0.5;
  }
  return {
    x: sumX / tiles.length,
    y: sumY / tiles.length
  };
}

/**
 * Trace a clockwise perimeter polygon around a contiguous tile cluster.
 *
 * The algorithm builds the set of *boundary edges* — every tile edge that
 * is shared with a neighbour outside the cluster — and then walks them
 * head-to-tail to form one or more closed loops. For the EDSim seed maps
 * each cluster is simply connected (no holes), so the algorithm always
 * returns the single outer loop.
 *
 * Vertices are returned in tile-corner coordinates: a 2×2 cluster anchored
 * at `(0, 0)` returns the polygon `[(0,0), (2,0), (2,2), (0,2)]`.
 */
export function tracePerimeterPolygon(tiles: readonly TilePoint[]): TilePoint[] {
  if (tiles.length === 0) return [];

  const inCluster = new Set<string>();
  for (const t of tiles) inCluster.add(`${t.x},${t.y}`);
  const has = (x: number, y: number) => inCluster.has(`${x},${y}`);

  // Each boundary edge is keyed by its directed start → end vertex pair so
  // we can chain them later. We choose orientations so that each edge has
  // the *cluster interior on its left* — that yields a clockwise outer loop
  // when y increases downward (screen coordinates).
  type Edge = { x1: number; y1: number; x2: number; y2: number };
  const edges: Edge[] = [];

  for (const t of tiles) {
    const { x, y } = t;
    // Top edge: present if the tile above is outside the cluster.
    // Walk left → right (interior below = on the right in math coords, but
    // because screen y goes down, "interior on the left" in screen space
    // corresponds to top→right→bottom→left, which is clockwise visually).
    if (!has(x, y - 1)) edges.push({ x1: x, y1: y, x2: x + 1, y2: y });
    // Right edge: present if the tile to the right is outside.
    if (!has(x + 1, y)) edges.push({ x1: x + 1, y1: y, x2: x + 1, y2: y + 1 });
    // Bottom edge: present if the tile below is outside.
    if (!has(x, y + 1)) edges.push({ x1: x + 1, y1: y + 1, x2: x, y2: y + 1 });
    // Left edge: present if the tile to the left is outside.
    if (!has(x - 1, y)) edges.push({ x1: x, y1: y + 1, x2: x, y2: y });
  }

  // Walk the edge graph head-to-tail. Each vertex appears at most twice in
  // a simply-connected outline (once as the end of one edge, once as the
  // start of the next). We start from the lexicographically smallest start
  // point so the result is deterministic across runs.
  const byStart = new Map<string, Edge[]>();
  for (const e of edges) {
    const key = `${e.x1},${e.y1}`;
    const list = byStart.get(key) ?? [];
    list.push(e);
    byStart.set(key, list);
  }

  const startKeys = Array.from(byStart.keys()).sort((a, b) => {
    const [ax, ay] = a.split(',').map(Number);
    const [bx, by] = b.split(',').map(Number);
    if (ay !== by) return ay! - by!;
    return ax! - bx!;
  });
  if (startKeys.length === 0) return [];

  const polygon: TilePoint[] = [];
  let cursorKey = startKeys[0]!;
  const startKey = cursorKey;

  // Safety bound: a simply-connected polygon has at most 4 × tile_count
  // edges, so iterate at most that many times.
  const maxIterations = edges.length + 1;
  for (let i = 0; i < maxIterations; i++) {
    const candidates = byStart.get(cursorKey);
    if (!candidates || candidates.length === 0) break;
    const edge = candidates.shift()!;
    polygon.push({ x: edge.x1, y: edge.y1 });
    cursorKey = `${edge.x2},${edge.y2}`;
    if (cursorKey === startKey) break;
  }

  return simplifyCollinear(polygon);
}

/**
 * Drop interior collinear vertices so the polygon stores only its corners.
 */
function simplifyCollinear(polygon: TilePoint[]): TilePoint[] {
  if (polygon.length < 3) return polygon.slice();
  const out: TilePoint[] = [];
  for (let i = 0; i < polygon.length; i++) {
    const prev = polygon[(i - 1 + polygon.length) % polygon.length]!;
    const cur = polygon[i]!;
    const next = polygon[(i + 1) % polygon.length]!;
    const dx1 = cur.x - prev.x;
    const dy1 = cur.y - prev.y;
    const dx2 = next.x - cur.x;
    const dy2 = next.y - cur.y;
    // Cross-product zero ⇒ prev, cur, next are colinear.
    if (dx1 * dy2 - dy1 * dx2 !== 0) {
      out.push(cur);
    }
  }
  return out;
}

/* -------------------------------------------------------------------------- */
/* Equipment extraction                                                       */
/* -------------------------------------------------------------------------- */

/**
 * Walk the Object Interaction Layer and emit one {@link EquipmentPlacement}
 * per recognised tile. Tiles whose GID is not in the equipment lookup are
 * silently skipped (they are decorative props that the simulator does not
 * model).
 */
export function extractEquipment(
  layer: TiledLayer,
  equipmentLookup: Map<number, EquipmentType>
): EquipmentPlacement[] {
  const out: EquipmentPlacement[] = [];
  for (let y = 0; y < layer.height; y++) {
    for (let x = 0; x < layer.width; x++) {
      const tileId = tileAt(layer, x, y);
      if (tileId === 0) continue;
      const type = equipmentLookup.get(tileId);
      if (!type) continue;
      out.push({
        equipmentId: `${type}-${x}-${y}`,
        type,
        tileX: x,
        tileY: y,
        rawTileId: tileId
      });
    }
  }
  return out;
}

/* -------------------------------------------------------------------------- */
/* Spawning extraction                                                        */
/* -------------------------------------------------------------------------- */

/**
 * Walk the Spawning Blocks layer and emit one {@link SpawningLocation} per
 * recognised tile.
 */
export function extractSpawningLocations(
  layer: TiledLayer,
  spawningLookup: Map<number, { zoneId: ZoneId; slot: string }>
): SpawningLocation[] {
  const out: SpawningLocation[] = [];
  for (let y = 0; y < layer.height; y++) {
    for (let x = 0; x < layer.width; x++) {
      const tileId = tileAt(layer, x, y);
      if (tileId === 0) continue;
      const meta = spawningLookup.get(tileId);
      if (!meta) continue;
      out.push({
        spawningId: `${meta.zoneId}-${meta.slot}`,
        zoneId: meta.zoneId,
        slot: meta.slot,
        tileX: x,
        tileY: y
      });
    }
  }
  return out;
}

/* -------------------------------------------------------------------------- */
/* Wall extraction                                                            */
/* -------------------------------------------------------------------------- */

/**
 * Compress the Walls layer into a compact list of axis-aligned
 * **perimeter-only** wall segments, ready to be rendered as clean
 * architectural lines.
 *
 * Naïve approaches — one line per wall tile, or one line per
 * row-run / column-run of wall tiles — both draw *interior* tile edges
 * inside solid wall blocks. A 2×2 solid block rendered that way shows
 * four grid lines instead of one crisp square outline, which is what
 * produced the "sloppy" grid artefacts in the Phase 1 first pass.
 *
 * This implementation walks every wall tile and emits an edge *only when
 * the neighbour on that side is not a wall*. Shared interior edges are
 * therefore never drawn. The resulting edge set is then merged into
 * longer horizontal and vertical runs so the renderer stays cheap.
 *
 * Edges are expressed in *tile-corner coordinates*: a wall tile at
 * `(x, y)` contributes a top edge from `(x, y)` → `(x+1, y)`, a bottom
 * edge from `(x, y+1)` → `(x+1, y+1)`, a left edge from `(x, y)` →
 * `(x, y+1)`, and a right edge from `(x+1, y)` → `(x+1, y+1)`.
 *
 * @param layer - Tiled Walls layer. Any non-zero tile id counts as a wall.
 * @returns Horizontal and vertical wall segments forming the outer (and
 *          any inner) perimeter of every connected wall region.
 */
export function extractWallSegments(layer: TiledLayer): WallSegment[] {
  const isWall = (x: number, y: number): boolean => {
    if (x < 0 || y < 0 || x >= layer.width || y >= layer.height) return false;
    return (layer.data[y * layer.width + x] ?? 0) !== 0;
  };

  // Collect perimeter-edge cells. Horizontal edges are keyed by the tile-edge
  // y-value; the set holds tile columns `x` where a horizontal edge runs from
  // (x, y) to (x+1, y). Vertical edges are the dual.
  const horizontalEdges = new Map<number, Set<number>>();
  const verticalEdges = new Map<number, Set<number>>();

  const addHorizontal = (y: number, x: number): void => {
    let bucket = horizontalEdges.get(y);
    if (!bucket) {
      bucket = new Set<number>();
      horizontalEdges.set(y, bucket);
    }
    bucket.add(x);
  };
  const addVertical = (x: number, y: number): void => {
    let bucket = verticalEdges.get(x);
    if (!bucket) {
      bucket = new Set<number>();
      verticalEdges.set(x, bucket);
    }
    bucket.add(y);
  };

  for (let y = 0; y < layer.height; y++) {
    for (let x = 0; x < layer.width; x++) {
      if (!isWall(x, y)) continue;
      // Top edge (between this tile and the tile above).
      if (!isWall(x, y - 1)) addHorizontal(y, x);
      // Bottom edge (between this tile and the tile below).
      if (!isWall(x, y + 1)) addHorizontal(y + 1, x);
      // Left edge (between this tile and the tile on the left).
      if (!isWall(x - 1, y)) addVertical(x, y);
      // Right edge (between this tile and the tile on the right).
      if (!isWall(x + 1, y)) addVertical(x + 1, y);
    }
  }

  const segments: WallSegment[] = [];

  // Merge consecutive horizontal edges sharing the same y value into runs.
  const sortedYs = Array.from(horizontalEdges.keys()).sort((a, b) => a - b);
  for (const y of sortedYs) {
    const xs = Array.from(horizontalEdges.get(y)!).sort((a, b) => a - b);
    let runStart: number | null = null;
    let runEnd = 0;
    for (const x of xs) {
      if (runStart === null) {
        runStart = x;
        runEnd = x + 1;
      } else if (x === runEnd) {
        runEnd = x + 1;
      } else {
        segments.push({
          orientation: 'horizontal',
          x1: runStart,
          y1: y,
          x2: runEnd,
          y2: y
        });
        runStart = x;
        runEnd = x + 1;
      }
    }
    if (runStart !== null) {
      segments.push({
        orientation: 'horizontal',
        x1: runStart,
        y1: y,
        x2: runEnd,
        y2: y
      });
    }
  }

  // Merge consecutive vertical edges sharing the same x value into runs.
  const sortedXs = Array.from(verticalEdges.keys()).sort((a, b) => a - b);
  for (const x of sortedXs) {
    const ys = Array.from(verticalEdges.get(x)!).sort((a, b) => a - b);
    let runStart: number | null = null;
    let runEnd = 0;
    for (const y of ys) {
      if (runStart === null) {
        runStart = y;
        runEnd = y + 1;
      } else if (y === runEnd) {
        runEnd = y + 1;
      } else {
        segments.push({
          orientation: 'vertical',
          x1: x,
          y1: runStart,
          x2: x,
          y2: runEnd
        });
        runStart = y;
        runEnd = y + 1;
      }
    }
    if (runStart !== null) {
      segments.push({
        orientation: 'vertical',
        x1: x,
        y1: runStart,
        x2: x,
        y2: runEnd
      });
    }
  }

  return segments;
}

/* -------------------------------------------------------------------------- */
/* Collision mask extraction                                                  */
/* -------------------------------------------------------------------------- */

/**
 * Convert the Collisions layer into a 2D boolean mask, indexed `[y][x]`.
 */
export function extractCollisionMask(layer: TiledLayer): boolean[][] {
  const mask: boolean[][] = [];
  for (let y = 0; y < layer.height; y++) {
    const row: boolean[] = [];
    for (let x = 0; x < layer.width; x++) {
      row.push(tileAt(layer, x, y) !== 0);
    }
    mask.push(row);
  }
  return mask;
}

/* -------------------------------------------------------------------------- */
/* Top-level orchestration                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Build the Tiled-GID → ZoneId lookup table from the decoded
 * `arena_blocks.csv` rows.
 *
 * Unknown labels are reported via `onWarning` (default: `console.warn`)
 * and skipped, so callers can detect schema drift early.
 */
export function buildArenaTileLookup(
  blocks: SpecialBlocks['arenaBlocks'],
  onWarning?: (msg: string) => void
): Map<number, ZoneId> {
  const lookup = new Map<number, ZoneId>();
  const warn = onWarning ?? ((m: string) => console.warn(m));
  for (const row of blocks) {
    const zoneId = normaliseZoneId(row.zoneLabel);
    if (!zoneId) {
      warn(`arena_blocks: unknown zone label "${row.zoneLabel}" for tile ${row.tileId}`);
      continue;
    }
    lookup.set(row.tileId, zoneId);
  }
  return lookup;
}

/**
 * Build the Tiled-GID → EquipmentType lookup table.
 */
export function buildEquipmentLookup(
  blocks: SpecialBlocks['gameObjectBlocks'],
  onWarning?: (msg: string) => void
): Map<number, EquipmentType> {
  const lookup = new Map<number, EquipmentType>();
  const warn = onWarning ?? ((m: string) => console.warn(m));
  for (const row of blocks) {
    const type = normaliseEquipmentType(row.objectLabel);
    if (!type) {
      warn(
        `game_object_blocks: unknown object label "${row.objectLabel}" for tile ${row.tileId}`
      );
      continue;
    }
    lookup.set(row.tileId, type);
  }
  return lookup;
}

/**
 * Build the Tiled-GID → spawning slot metadata lookup table.
 */
export function buildSpawningLookup(
  blocks: SpecialBlocks['spawningBlocks'],
  onWarning?: (msg: string) => void
): Map<number, { zoneId: ZoneId; slot: string }> {
  const lookup = new Map<number, { zoneId: ZoneId; slot: string }>();
  const warn = onWarning ?? ((m: string) => console.warn(m));
  for (const row of blocks) {
    const zoneId = normaliseZoneId(row.zoneLabel);
    if (!zoneId) {
      warn(
        `spawning_location_blocks: unknown zone label "${row.zoneLabel}" for tile ${row.tileId}`
      );
      continue;
    }
    lookup.set(row.tileId, { zoneId, slot: row.slot });
  }
  return lookup;
}

/**
 * Top-level entry point: convert a parsed Tiled JSON object plus the decoded
 * special-block tables into a {@link MapLayout}.
 *
 * @param mapId - Display id for the layout (typically the source filename
 *                without extension, e.g. `"small_ed_layout"`).
 * @param tiled - Parsed Tiled JSON object.
 * @param specialBlocks - Decoded special-block CSVs.
 * @param onWarning - Optional callback invoked for non-fatal schema drift
 *                    (e.g. unknown zone labels). Defaults to `console.warn`.
 * @returns A fully populated, immutable-by-convention {@link MapLayout}.
 */
export function parseTiledJSON(
  mapId: string,
  tiled: TiledMap,
  specialBlocks: SpecialBlocks,
  onWarning?: (msg: string) => void
): MapLayout {
  const arenaLayer = findLayer(tiled, LAYER_NAMES.arena);
  const objectLayer = findLayer(tiled, LAYER_NAMES.objectInteraction);
  const spawningLayer = findLayer(tiled, LAYER_NAMES.spawningBlocks);
  const wallsLayer = findLayer(tiled, LAYER_NAMES.walls);
  const collisionsLayer = findLayer(tiled, LAYER_NAMES.collisions);

  const arenaLookup = buildArenaTileLookup(specialBlocks.arenaBlocks, onWarning);
  const equipmentLookup = buildEquipmentLookup(
    specialBlocks.gameObjectBlocks,
    onWarning
  );
  const spawningLookup = buildSpawningLookup(specialBlocks.spawningBlocks, onWarning);

  return {
    mapId,
    widthInTiles: tiled.width,
    heightInTiles: tiled.height,
    tileSizePx: tiled.tilewidth,
    zones: extractZoneRegions(arenaLayer, arenaLookup),
    equipment: extractEquipment(objectLayer, equipmentLookup),
    spawningLocations: extractSpawningLocations(spawningLayer, spawningLookup),
    walls: extractWallSegments(wallsLayer),
    collisionMask: extractCollisionMask(collisionsLayer)
  };
}
