/**
 * Standalone parser dump utility.
 *
 * Usage:
 *   npx tsx scripts/dump-parser.mjs
 *
 * Reads the canonical Tiled fixtures from
 * `environment/frontend_server/static_dirs/assets/the_ed/`, runs them through
 * the {@link parseTiledJSON} pipeline, and prints a summary table of the
 * resulting {@link MapLayout}. Handy for spot-checking the parser without
 * spinning up the React viewer or vitest.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseTiledJSON } from '../src/parser/parseTiledJSON.ts';
import { parseSpecialBlocks } from '../src/parser/csv.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const ASSET_ROOT = path.resolve(
  here,
  '../../frontend_server/static_dirs/assets/the_ed'
);

const arena = readFileSync(
  path.join(ASSET_ROOT, 'matrix/special_blocks/arena_blocks.csv'),
  'utf-8'
);
const gameObjects = readFileSync(
  path.join(ASSET_ROOT, 'matrix/special_blocks/game_object_blocks.csv'),
  'utf-8'
);
const spawning = readFileSync(
  path.join(ASSET_ROOT, 'matrix/special_blocks/spawning_location_blocks.csv'),
  'utf-8'
);
const blocks = parseSpecialBlocks({
  arenaBlocks: arena,
  gameObjectBlocks: gameObjects,
  spawningBlocks: spawning
});

const fixtures = [
  ['small_ed_layout', 'visuals/small_ed_layout.json'],
  ['foothills_ed_layout', 'visuals/foothills_ed_layout.json']
];

for (const [name, relative] of fixtures) {
  const tiled = JSON.parse(readFileSync(path.join(ASSET_ROOT, relative), 'utf-8'));
  const layout = parseTiledJSON(name, tiled, blocks);
  const equipmentByType = layout.equipment.reduce((acc, e) => {
    acc[e.type] = (acc[e.type] ?? 0) + 1;
    return acc;
  }, /** @type {Record<string, number>} */ ({}));
  const zonesByType = layout.zones.reduce((acc, z) => {
    acc[z.zoneId] = (acc[z.zoneId] ?? 0) + 1;
    return acc;
  }, /** @type {Record<string, number>} */ ({}));

  console.log(`\n=== ${name} (${layout.widthInTiles}×${layout.heightInTiles}) ===`);
  console.log('  zones        :', layout.zones.length, JSON.stringify(zonesByType));
  console.log('  equipment    :', layout.equipment.length, JSON.stringify(equipmentByType));
  console.log('  spawning     :', layout.spawningLocations.length);
  console.log('  wall segments:', layout.walls.length);
}
