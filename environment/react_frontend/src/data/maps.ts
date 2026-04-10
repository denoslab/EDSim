/**
 * Catalogue of available Tiled maps.
 *
 * Each entry points at the source files for one map. The viewer uses this
 * list to populate its sidebar; the parser uses the URLs verbatim via
 * {@link loadMapLayout}.
 *
 * Asset URLs are produced via Vite's `?url` import suffix, which routes the
 * request through Vite's asset pipeline at dev time and emits a hashed copy
 * in `dist/assets/` at build time. This means the React frontend always
 * consumes the *exact same files* the legacy Phaser/Tiled renderer reads —
 * no copying, no schema drift.
 *
 * @packageDocumentation
 */

import type { LoadMapOptions } from '@/parser/loadMapLayout';

import smallEdJsonUrl from '@maps/visuals/small_ed_layout.json?url';
import foothillsJsonUrl from '@maps/visuals/foothills_ed_layout.json?url';
import arenaBlocksUrl from '@maps/matrix/special_blocks/arena_blocks.csv?url';
import gameObjectBlocksUrl from '@maps/matrix/special_blocks/game_object_blocks.csv?url';
import spawningBlocksUrl from '@maps/matrix/special_blocks/spawning_location_blocks.csv?url';

/** Catalogue entry for one Tiled map. */
export interface MapCatalogueEntry {
  /** Stable id used in URLs and tests. */
  id: string;
  /** Human-readable name shown in the viewer sidebar. */
  displayName: string;
  /** Short description shown beneath the name. */
  description: string;
  /** Resolved load options, ready to pass to {@link loadMapLayout}. */
  load: LoadMapOptions;
}

/**
 * The two Phase 1 target maps.
 *
 * Adding a third map is a one-line change: append a new entry here and the
 * viewer's sidebar picks it up automatically.
 */
export const MAP_CATALOGUE: MapCatalogueEntry[] = [
  {
    id: 'small_ed_layout',
    displayName: 'Small ED Layout',
    description: '30 × 20 seed map used by the default ed_sim_n5 simulation.',
    load: {
      mapId: 'small_ed_layout',
      tiledJsonUrl: smallEdJsonUrl,
      arenaBlocksUrl,
      gameObjectBlocksUrl,
      spawningBlocksUrl
    }
  },
  {
    id: 'foothills_ed_layout',
    displayName: 'Foothills ED Layout',
    description: '122 × 123 high-fidelity reproduction of the Foothills ED.',
    load: {
      mapId: 'foothills_ed_layout',
      tiledJsonUrl: foothillsJsonUrl,
      arenaBlocksUrl,
      gameObjectBlocksUrl,
      spawningBlocksUrl
    }
  }
];

/**
 * Look up a catalogue entry by id, falling back to the first entry if the
 * id is unknown. Useful for query-string driven viewer state.
 */
export function getCatalogueEntry(id: string | null | undefined): MapCatalogueEntry {
  if (!id) return MAP_CATALOGUE[0]!;
  return MAP_CATALOGUE.find((m) => m.id === id) ?? MAP_CATALOGUE[0]!;
}
