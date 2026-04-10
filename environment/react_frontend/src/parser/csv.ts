/**
 * Lightweight CSV decoder for the EDSim "special block" mapping files.
 *
 * The legacy backend stores zone, equipment, and spawning lookups as
 * comma-separated text under
 * `environment/frontend_server/static_dirs/assets/the_ed/matrix/special_blocks/`.
 * The format is *not* RFC 4180 — fields are not quoted and the file simply
 * uses comma + space as the separator. Lines are also occasionally trailed
 * with whitespace, so we trim every field aggressively.
 *
 * We deliberately avoid pulling in a full CSV library because:
 *  1. The schema is fixed and trivially parseable.
 *  2. Keeping dependencies minimal makes the parser easy to vendor into
 *     other tooling (e.g. backend Python tests via a future port).
 *
 * @packageDocumentation
 */

import type {
  ArenaBlockRow,
  GameObjectBlockRow,
  SpawningBlockRow,
  SpecialBlocks
} from './types.js';

/**
 * Split CSV text into trimmed, non-empty rows.
 *
 * @param raw - Raw CSV file contents.
 * @returns Array of row strings with leading/trailing whitespace stripped
 *          and blank lines removed.
 */
function splitRows(raw: string): string[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

/**
 * Split a single CSV row into trimmed cells.
 *
 * @param row - A single line from a CSV file (no trailing newline).
 * @returns Trimmed cell values.
 */
function splitCells(row: string): string[] {
  return row.split(',').map((cell) => cell.trim());
}

/**
 * Decode `arena_blocks.csv`.
 *
 * Expected format (one row per line):
 *
 * ```
 * <tileId>, ed map, emergency department, <zone label>
 * ```
 *
 * Only the first column (Tiled GID) and the *last* column (zone label) are
 * meaningful; the middle columns are legacy provenance and ignored.
 *
 * @param raw - Raw contents of `arena_blocks.csv`.
 * @returns Decoded rows, in source order.
 * @throws If a row has fewer than 4 cells or a non-numeric tile id.
 */
export function parseArenaBlocksCSV(raw: string): ArenaBlockRow[] {
  return splitRows(raw).map((row, index) => {
    const cells = splitCells(row);
    if (cells.length < 4) {
      throw new Error(
        `arena_blocks.csv row ${index + 1}: expected at least 4 cells, got ${cells.length} (${row})`
      );
    }
    const tileId = Number.parseInt(cells[0]!, 10);
    if (!Number.isFinite(tileId)) {
      throw new Error(
        `arena_blocks.csv row ${index + 1}: tile id is not numeric (${cells[0]})`
      );
    }
    return {
      tileId,
      // The zone label always lives in the *last* column. Some rows may have
      // extra commas inside the label (none today, but the spec leaves room
      // for that), so prefer "join everything from index 3 onward".
      zoneLabel: cells.slice(3).join(', ').trim()
    };
  });
}

/**
 * Decode `game_object_blocks.csv`.
 *
 * Expected format (one row per line):
 *
 * ```
 * <tileId>, ed map, <all>, <object label>
 * ```
 *
 * @param raw - Raw contents of `game_object_blocks.csv`.
 * @returns Decoded rows, in source order.
 * @throws If a row has fewer than 4 cells or a non-numeric tile id.
 */
export function parseGameObjectBlocksCSV(raw: string): GameObjectBlockRow[] {
  return splitRows(raw).map((row, index) => {
    const cells = splitCells(row);
    if (cells.length < 4) {
      throw new Error(
        `game_object_blocks.csv row ${index + 1}: expected at least 4 cells, got ${cells.length} (${row})`
      );
    }
    const tileId = Number.parseInt(cells[0]!, 10);
    if (!Number.isFinite(tileId)) {
      throw new Error(
        `game_object_blocks.csv row ${index + 1}: tile id is not numeric (${cells[0]})`
      );
    }
    return {
      tileId,
      objectLabel: cells.slice(3).join(', ').trim()
    };
  });
}

/**
 * Decode `spawning_location_blocks.csv`.
 *
 * Expected format (one row per line):
 *
 * ```
 * <tileId>, ed map, emergency department, <zone label>, <slot label>
 * ```
 *
 * Both the zone label and the trailing slot label are extracted.
 *
 * @param raw - Raw contents of `spawning_location_blocks.csv`.
 * @returns Decoded rows, in source order.
 * @throws If a row has fewer than 5 cells or a non-numeric tile id.
 */
export function parseSpawningBlocksCSV(raw: string): SpawningBlockRow[] {
  return splitRows(raw).map((row, index) => {
    const cells = splitCells(row);
    if (cells.length < 5) {
      throw new Error(
        `spawning_location_blocks.csv row ${index + 1}: expected at least 5 cells, got ${cells.length} (${row})`
      );
    }
    const tileId = Number.parseInt(cells[0]!, 10);
    if (!Number.isFinite(tileId)) {
      throw new Error(
        `spawning_location_blocks.csv row ${index + 1}: tile id is not numeric (${cells[0]})`
      );
    }
    return {
      tileId,
      zoneLabel: cells[3]!,
      slot: cells[4]!
    };
  });
}

/**
 * Convenience helper that decodes all three special-block files into a
 * single bundle.
 *
 * @param raw - Object containing the raw text of each CSV file.
 * @returns Decoded bundle ready to be passed to `parseTiledJSON`.
 */
export function parseSpecialBlocks(raw: {
  arenaBlocks: string;
  gameObjectBlocks: string;
  spawningBlocks: string;
}): SpecialBlocks {
  return {
    arenaBlocks: parseArenaBlocksCSV(raw.arenaBlocks),
    gameObjectBlocks: parseGameObjectBlocksCSV(raw.gameObjectBlocks),
    spawningBlocks: parseSpawningBlocksCSV(raw.spawningBlocks)
  };
}
