/**
 * Unit tests for the {@link parseTiledJSON} pipeline.
 *
 * The tests use both small synthetic Tiled maps (so the algorithms are
 * easy to reason about) and end-to-end fixtures loaded from the canonical
 * `small_ed_layout.json` and `foothills_ed_layout.json` files. The latter
 * pin the *parser* against the actual seed assets so a future Tiled-side
 * change surfaces immediately.
 */

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  buildArenaTileLookup,
  buildEquipmentLookup,
  buildSpawningLookup,
  computeBounds,
  computeCentroid,
  extractCollisionMask,
  extractEquipment,
  extractSpawningLocations,
  extractWallSegments,
  extractZoneRegions,
  normaliseEquipmentType,
  normaliseZoneId,
  parseTiledJSON,
  tracePerimeterPolygon
} from '@/parser/parseTiledJSON';
import { parseSpecialBlocks } from '@/parser/csv';
import type { TiledLayer, TiledMap } from '@/parser/types';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const ASSET_ROOT = path.resolve(
  __dirname,
  '../../../frontend_server/static_dirs/assets/the_ed'
);

function readFixture(relative: string): string {
  return readFileSync(path.join(ASSET_ROOT, relative), 'utf-8');
}

function loadSpecialBlocks() {
  return parseSpecialBlocks({
    arenaBlocks: readFixture('matrix/special_blocks/arena_blocks.csv'),
    gameObjectBlocks: readFixture('matrix/special_blocks/game_object_blocks.csv'),
    spawningBlocks: readFixture('matrix/special_blocks/spawning_location_blocks.csv')
  });
}

function loadTiledMap(filename: string): TiledMap {
  return JSON.parse(readFixture(`visuals/${filename}`)) as TiledMap;
}

/* -------------------------------------------------------------------------- */
/* Pure helper unit tests                                                     */
/* -------------------------------------------------------------------------- */

describe('normaliseZoneId', () => {
  it('maps every canonical label', () => {
    expect(normaliseZoneId('triage room')).toBe('triage_room');
    expect(normaliseZoneId('Waiting Room')).toBe('waiting_room');
    expect(normaliseZoneId('hallway')).toBe('hallway');
    expect(normaliseZoneId('minor injuries zone')).toBe('minor_injuries_zone');
    expect(normaliseZoneId('major injuries zone')).toBe('major_injuries_zone');
    expect(normaliseZoneId('trauma room')).toBe('trauma_room');
    expect(normaliseZoneId('diagnostic room')).toBe('diagnostic_room');
    expect(normaliseZoneId('exit')).toBe('exit');
  });

  it('returns undefined for unknown labels', () => {
    expect(normaliseZoneId('helipad')).toBeUndefined();
  });
});

describe('normaliseEquipmentType', () => {
  it('maps every canonical equipment label', () => {
    expect(normaliseEquipmentType('bed')).toBe('bed');
    expect(normaliseEquipmentType('chair')).toBe('chair');
    expect(normaliseEquipmentType('wheelchair')).toBe('wheelchair');
    expect(normaliseEquipmentType('medical equipment')).toBe('medical_equipment');
    expect(normaliseEquipmentType('computer')).toBe('computer');
    expect(normaliseEquipmentType('waiting room chair')).toBe('waiting_room_chair');
    expect(normaliseEquipmentType('diagnostic table')).toBe('diagnostic_table');
  });
});

describe('computeBounds & computeCentroid', () => {
  it('produces correct values for a 2x2 cluster at origin', () => {
    const tiles = [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 0, y: 1 },
      { x: 1, y: 1 }
    ];
    expect(computeBounds(tiles)).toEqual({ minX: 0, minY: 0, maxX: 1, maxY: 1 });
    expect(computeCentroid(tiles)).toEqual({ x: 1, y: 1 });
  });

  it('throws on empty input', () => {
    expect(() => computeBounds([])).toThrow();
    expect(() => computeCentroid([])).toThrow();
  });
});

describe('tracePerimeterPolygon', () => {
  it('returns a 4-corner polygon for a single tile', () => {
    const polygon = tracePerimeterPolygon([{ x: 3, y: 4 }]);
    // The corners of the 1x1 tile are (3,4), (4,4), (4,5), (3,5).
    expect(polygon).toHaveLength(4);
    expect(new Set(polygon.map((p) => `${p.x},${p.y}`))).toEqual(
      new Set(['3,4', '4,4', '4,5', '3,5'])
    );
  });

  it('returns a 4-corner polygon for a 3x2 rectangle', () => {
    const tiles = [];
    for (let y = 5; y < 7; y++) {
      for (let x = 2; x < 5; x++) {
        tiles.push({ x, y });
      }
    }
    const polygon = tracePerimeterPolygon(tiles);
    expect(polygon).toHaveLength(4);
    const corners = new Set(polygon.map((p) => `${p.x},${p.y}`));
    expect(corners).toEqual(new Set(['2,5', '5,5', '5,7', '2,7']));
  });

  it('handles an L-shape with six corners', () => {
    // Three tiles arranged in an L:
    //  X X
    //  X
    const tiles = [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 0, y: 1 }
    ];
    const polygon = tracePerimeterPolygon(tiles);
    // The L has 6 corners: (0,0), (2,0), (2,1), (1,1), (1,2), (0,2).
    expect(polygon).toHaveLength(6);
    const corners = new Set(polygon.map((p) => `${p.x},${p.y}`));
    expect(corners).toEqual(
      new Set(['0,0', '2,0', '2,1', '1,1', '1,2', '0,2'])
    );
  });
});

describe('extractZoneRegions', () => {
  function makeArenaLayer(rows: number[][]): TiledLayer {
    const height = rows.length;
    const width = rows[0]!.length;
    return {
      name: 'Arena Layer',
      type: 'tilelayer',
      width,
      height,
      data: rows.flat()
    };
  }

  it('groups identical tile ids into a single region', () => {
    // 3x3 of zone 1314 (triage)
    const arena = makeArenaLayer([
      [1314, 1314, 1314],
      [1314, 1314, 1314],
      [1314, 1314, 1314]
    ]);
    const lookup = new Map([[1314, 'triage_room' as const]]);
    const regions = extractZoneRegions(arena, lookup);
    expect(regions).toHaveLength(1);
    expect(regions[0]!.zoneId).toBe('triage_room');
    expect(regions[0]!.tilePositions).toHaveLength(9);
  });

  it('merges different tile ids that map to the same zone', () => {
    // The seed map uses both 1314 and 1335 for triage tiles.
    const arena = makeArenaLayer([
      [1314, 1335, 1314],
      [1314, 1314, 1335]
    ]);
    const lookup = new Map([
      [1314, 'triage_room' as const],
      [1335, 'triage_room' as const]
    ]);
    const regions = extractZoneRegions(arena, lookup);
    expect(regions).toHaveLength(1);
    expect(regions[0]!.tilePositions).toHaveLength(6);
  });

  it('produces separate regions for non-contiguous clusters', () => {
    const arena = makeArenaLayer([
      [1314, 0, 1314],
      [1314, 0, 1314]
    ]);
    const lookup = new Map([[1314, 'triage_room' as const]]);
    const regions = extractZoneRegions(arena, lookup);
    expect(regions).toHaveLength(2);
    expect(regions[0]!.zoneRegionId).toBe('triage_room-0');
    expect(regions[1]!.zoneRegionId).toBe('triage_room-1');
  });
});

describe('extractWallSegments', () => {
  it('emits a tight rectangular perimeter for a 1×3 wall run', () => {
    const layer: TiledLayer = {
      name: 'Walls',
      type: 'tilelayer',
      width: 4,
      height: 1,
      data: [1, 1, 1, 0]
    };
    const segments = extractWallSegments(layer);
    const horizontals = segments.filter((s) => s.orientation === 'horizontal');
    const verticals = segments.filter((s) => s.orientation === 'vertical');

    // Expect exactly four segments: the top and bottom edges of the run
    // (both spanning x ∈ [0, 3]) plus two caps on the left and right.
    expect(horizontals).toHaveLength(2);
    expect(horizontals).toEqual(
      expect.arrayContaining([
        { orientation: 'horizontal', x1: 0, y1: 0, x2: 3, y2: 0 },
        { orientation: 'horizontal', x1: 0, y1: 1, x2: 3, y2: 1 }
      ])
    );
    expect(verticals).toHaveLength(2);
    expect(verticals).toEqual(
      expect.arrayContaining([
        { orientation: 'vertical', x1: 0, y1: 0, x2: 0, y2: 1 },
        { orientation: 'vertical', x1: 3, y1: 0, x2: 3, y2: 1 }
      ])
    );
  });

  it('never emits interior edges inside a solid 2×2 wall block', () => {
    // 4×4 layer with a solid 2×2 wall block in the middle. A naïve
    // per-tile renderer would draw grid lines through the interior of the
    // block; perimeter-only extraction must produce exactly four segments
    // forming a 2×2 square.
    const layer: TiledLayer = {
      name: 'Walls',
      type: 'tilelayer',
      width: 4,
      height: 4,
      // prettier-ignore
      data: [
        0, 0, 0, 0,
        0, 1, 1, 0,
        0, 1, 1, 0,
        0, 0, 0, 0
      ]
    };
    const segments = extractWallSegments(layer);
    expect(segments).toHaveLength(4);
    expect(segments).toEqual(
      expect.arrayContaining([
        { orientation: 'horizontal', x1: 1, y1: 1, x2: 3, y2: 1 },
        { orientation: 'horizontal', x1: 1, y1: 3, x2: 3, y2: 3 },
        { orientation: 'vertical', x1: 1, y1: 1, x2: 1, y2: 3 },
        { orientation: 'vertical', x1: 3, y1: 1, x2: 3, y2: 3 }
      ])
    );
  });
});

describe('extractCollisionMask', () => {
  it('flips non-zero tiles to true', () => {
    const layer: TiledLayer = {
      name: 'Collisions',
      type: 'tilelayer',
      width: 2,
      height: 2,
      data: [0, 1, 1, 0]
    };
    expect(extractCollisionMask(layer)).toEqual([
      [false, true],
      [true, false]
    ]);
  });
});

describe('lookup builders', () => {
  it('builds the arena lookup and warns on unknown labels', () => {
    const warnings: string[] = [];
    const lookup = buildArenaTileLookup(
      [
        { tileId: 1314, zoneLabel: 'triage room' },
        { tileId: 9999, zoneLabel: 'helipad' }
      ],
      (m) => warnings.push(m)
    );
    expect(lookup.get(1314)).toBe('triage_room');
    expect(lookup.has(9999)).toBe(false);
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toMatch(/helipad/);
  });

  it('builds the equipment lookup', () => {
    const lookup = buildEquipmentLookup([
      { tileId: 1330, objectLabel: 'bed' }
    ]);
    expect(lookup.get(1330)).toBe('bed');
  });

  it('builds the spawning lookup with slot metadata', () => {
    const lookup = buildSpawningLookup([
      { tileId: 1304, zoneLabel: 'triage room', slot: 'sp-A' }
    ]);
    expect(lookup.get(1304)).toEqual({ zoneId: 'triage_room', slot: 'sp-A' });
  });
});

/* -------------------------------------------------------------------------- */
/* End-to-end fixture tests                                                   */
/* -------------------------------------------------------------------------- */

describe('parseTiledJSON — small_ed_layout.json fixture', () => {
  const blocks = loadSpecialBlocks();
  const tiled = loadTiledMap('small_ed_layout.json');
  const layout = parseTiledJSON('small_ed_layout', tiled, blocks);

  it('exposes the correct top-level metadata', () => {
    expect(layout.mapId).toBe('small_ed_layout');
    expect(layout.widthInTiles).toBe(30);
    expect(layout.heightInTiles).toBe(20);
    expect(layout.tileSizePx).toBe(32);
  });

  it('extracts every Phase 1 zone category', () => {
    const zoneIds = new Set(layout.zones.map((z) => z.zoneId));
    expect(zoneIds.has('triage_room')).toBe(true);
    expect(zoneIds.has('waiting_room')).toBe(true);
    expect(zoneIds.has('hallway')).toBe(true);
    expect(zoneIds.has('minor_injuries_zone')).toBe(true);
    expect(zoneIds.has('major_injuries_zone')).toBe(true);
    expect(zoneIds.has('trauma_room')).toBe(true);
    expect(zoneIds.has('diagnostic_room')).toBe(true);
    expect(zoneIds.has('exit')).toBe(true);
  });

  it('zone regions all carry a non-empty polygon and tile cluster', () => {
    for (const zone of layout.zones) {
      expect(zone.polygon.length).toBeGreaterThanOrEqual(4);
      expect(zone.tilePositions.length).toBeGreaterThan(0);
      expect(zone.bounds.minX).toBeLessThanOrEqual(zone.bounds.maxX);
      expect(zone.bounds.minY).toBeLessThanOrEqual(zone.bounds.maxY);
    }
  });

  it('extracts the exact equipment counts from the seed map', () => {
    // Counts pinned against the canonical small_ed_layout.json. They were
    // verified by hand against the legacy Phaser view; any future change
    // here means either the asset file or the parser regressed.
    expect(layout.equipment.length).toBe(42);
    const counts: Record<string, number> = {};
    for (const e of layout.equipment) counts[e.type] = (counts[e.type] ?? 0) + 1;
    expect(counts).toEqual({
      bed: 11,
      medical_equipment: 12,
      waiting_room_chair: 12,
      chair: 2,
      computer: 2,
      wheelchair: 2,
      diagnostic_table: 1
    });
  });

  it('extracts the expected number of spawning slots', () => {
    // Pinned against the canonical small_ed_layout.json.
    expect(layout.spawningLocations.length).toBe(18);
    const spawningZones = new Set(layout.spawningLocations.map((s) => s.zoneId));
    expect(spawningZones.has('triage_room')).toBe(true);
    expect(spawningZones.has('waiting_room')).toBe(true);
    expect(spawningZones.has('major_injuries_zone')).toBe(true);
    expect(spawningZones.has('minor_injuries_zone')).toBe(true);
    expect(spawningZones.has('diagnostic_room')).toBe(true);
  });

  it('exactly one connected zone region per zone category in the seed map', () => {
    const counts = new Map<string, number>();
    for (const z of layout.zones) {
      counts.set(z.zoneId, (counts.get(z.zoneId) ?? 0) + 1);
    }
    // The seed map has exactly one component per zone. The Foothills map
    // splits some zones into multiple rooms; that case is exercised in the
    // foothills fixture block below.
    for (const value of counts.values()) {
      expect(value).toBe(1);
    }
    expect(layout.zones.length).toBe(8);
  });

  it('extracts wall segments', () => {
    expect(layout.walls.length).toBeGreaterThan(0);
    const orientations = new Set(layout.walls.map((w) => w.orientation));
    expect(orientations).toEqual(new Set(['horizontal', 'vertical']));
  });

  it('produces a collision mask with the expected dimensions', () => {
    expect(layout.collisionMask).toHaveLength(20);
    for (const row of layout.collisionMask) {
      expect(row).toHaveLength(30);
    }
  });
});

describe('parseTiledJSON — foothills_ed_layout.json fixture', () => {
  const blocks = loadSpecialBlocks();
  const tiled = loadTiledMap('foothills_ed_layout.json');
  const layout = parseTiledJSON('foothills_ed_layout', tiled, blocks);

  it('matches the foothills dimensions', () => {
    expect(layout.widthInTiles).toBe(122);
    expect(layout.heightInTiles).toBe(123);
    expect(layout.collisionMask).toHaveLength(123);
    expect(layout.collisionMask[0]).toHaveLength(122);
  });

  it('extracts every Phase 1 zone category at least once', () => {
    const zoneIds = new Set(layout.zones.map((z) => z.zoneId));
    expect(zoneIds.size).toBeGreaterThanOrEqual(8);
  });

  it('extracts the exact equipment count from the foothills fixture', () => {
    // Pinned against the canonical foothills_ed_layout.json.
    expect(layout.equipment.length).toBe(219);
  });

  it('extracts the exact spawning-slot count from the foothills fixture', () => {
    expect(layout.spawningLocations.length).toBe(70);
  });

  it('produces multi-component zone regions where the layout has split rooms', () => {
    const minorRegions = layout.zones.filter(
      (z) => z.zoneId === 'minor_injuries_zone'
    );
    const majorRegions = layout.zones.filter(
      (z) => z.zoneId === 'major_injuries_zone'
    );
    // Foothills has multiple distinct injury rooms; the parser must surface
    // each one as its own component instead of merging them across walls.
    expect(minorRegions.length).toBeGreaterThan(1);
    expect(majorRegions.length).toBeGreaterThan(1);
  });

  it('compresses the walls layer into well under one segment per tile', () => {
    // The Foothills walls layer has thousands of wall tiles. The compaction
    // pass should produce orders of magnitude fewer segments than tiles.
    expect(layout.walls.length).toBeLessThan(layout.widthInTiles * layout.heightInTiles);
    expect(layout.walls.length).toBeGreaterThan(100);
  });
});

/* -------------------------------------------------------------------------- */
/* Integration: equipment + spawning extraction on a synthetic layer          */
/* -------------------------------------------------------------------------- */

describe('extractEquipment / extractSpawningLocations', () => {
  it('emits one entry per recognised tile and skips unknown ones', () => {
    const layer: TiledLayer = {
      name: 'Object Interaction Layer',
      type: 'tilelayer',
      width: 3,
      height: 1,
      data: [1330, 0, 9999]
    };
    const eqLookup = new Map([[1330, 'bed' as const]]);
    const equipment = extractEquipment(layer, eqLookup);
    expect(equipment).toHaveLength(1);
    expect(equipment[0]).toMatchObject({
      type: 'bed',
      tileX: 0,
      tileY: 0,
      rawTileId: 1330
    });
  });

  it('emits spawning locations with stable ids', () => {
    const layer: TiledLayer = {
      name: 'Spawning Blocks',
      type: 'tilelayer',
      width: 2,
      height: 1,
      data: [1304, 0]
    };
    const lookup = new Map([
      [1304, { zoneId: 'triage_room' as const, slot: 'sp-A' }]
    ]);
    const spawning = extractSpawningLocations(layer, lookup);
    expect(spawning).toEqual([
      {
        spawningId: 'triage_room-sp-A',
        zoneId: 'triage_room',
        slot: 'sp-A',
        tileX: 0,
        tileY: 0
      }
    ]);
  });
});
