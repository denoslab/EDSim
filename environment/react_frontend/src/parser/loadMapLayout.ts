/**
 * Browser-side helper that fetches the four files needed to parse a map and
 * runs the {@link parseTiledJSON} pipeline. Pure I/O glue — separate from the
 * parser core so the parser stays unit-testable without `fetch`.
 *
 * @packageDocumentation
 */

import {
  parseTiledJSON,
  type MapLayout,
  type TiledMap
} from './index.js';
import { parseSpecialBlocks } from './csv.js';

/**
 * Source URLs for one Tiled map. The defaults assume the Vite dev server is
 * running with the `@maps` alias mounted on `/maps` (see {@link buildDefaultLoadOptions}).
 */
export interface LoadMapOptions {
  /** Display id (e.g. `"small_ed_layout"`). */
  mapId: string;
  /** URL of the Tiled JSON file. */
  tiledJsonUrl: string;
  /** URL of `arena_blocks.csv`. */
  arenaBlocksUrl: string;
  /** URL of `game_object_blocks.csv`. */
  gameObjectBlocksUrl: string;
  /** URL of `spawning_location_blocks.csv`. */
  spawningBlocksUrl: string;
  /** Optional fetch override for testing. Defaults to global `fetch`. */
  fetchImpl?: typeof fetch;
  /** Optional warning sink (parser non-fatal warnings). */
  onWarning?: (msg: string) => void;
}

/**
 * Fetch all four files in parallel, decode them, and produce a
 * {@link MapLayout}.
 *
 * @throws If any HTTP request fails or the parser surfaces a fatal error
 *         (e.g. missing required Tiled layer).
 */
export async function loadMapLayout(opts: LoadMapOptions): Promise<MapLayout> {
  const fetchImpl = opts.fetchImpl ?? fetch;

  const [tiledRes, arenaRes, gameObjectRes, spawningRes] = await Promise.all([
    fetchImpl(opts.tiledJsonUrl),
    fetchImpl(opts.arenaBlocksUrl),
    fetchImpl(opts.gameObjectBlocksUrl),
    fetchImpl(opts.spawningBlocksUrl)
  ]);

  for (const [name, res] of [
    [opts.tiledJsonUrl, tiledRes],
    [opts.arenaBlocksUrl, arenaRes],
    [opts.gameObjectBlocksUrl, gameObjectRes],
    [opts.spawningBlocksUrl, spawningRes]
  ] as const) {
    if (!res.ok) {
      throw new Error(`Failed to fetch "${name}": ${res.status} ${res.statusText}`);
    }
  }

  const tiled = (await tiledRes.json()) as TiledMap;
  const arenaBlocks = await arenaRes.text();
  const gameObjectBlocks = await gameObjectRes.text();
  const spawningBlocks = await spawningRes.text();

  const specialBlocks = parseSpecialBlocks({
    arenaBlocks,
    gameObjectBlocks,
    spawningBlocks
  });

  return parseTiledJSON(opts.mapId, tiled, specialBlocks, opts.onWarning);
}
