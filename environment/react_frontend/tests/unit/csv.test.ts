/**
 * Unit tests for the special-block CSV decoders.
 */

import { describe, expect, it } from 'vitest';
import {
  parseArenaBlocksCSV,
  parseGameObjectBlocksCSV,
  parseSpawningBlocksCSV
} from '@/parser/csv';

describe('parseArenaBlocksCSV', () => {
  it('decodes the canonical seed file', () => {
    const raw =
      '1299, ed map, emergency department, minor injuries zone\n' +
      '1313, ed map, emergency department, waiting room\n' +
      '1314, ed map, emergency department, triage room\n';
    const rows = parseArenaBlocksCSV(raw);
    expect(rows).toEqual([
      { tileId: 1299, zoneLabel: 'minor injuries zone' },
      { tileId: 1313, zoneLabel: 'waiting room' },
      { tileId: 1314, zoneLabel: 'triage room' }
    ]);
  });

  it('strips trailing whitespace and ignores blank lines', () => {
    const raw =
      '   1350, ed map, emergency department, exit   \n' +
      '\n' +
      '1345, ed map, emergency department, trauma room\n\n';
    const rows = parseArenaBlocksCSV(raw);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({ tileId: 1350, zoneLabel: 'exit' });
    expect(rows[1]).toEqual({ tileId: 1345, zoneLabel: 'trauma room' });
  });

  it('throws on a non-numeric tile id', () => {
    expect(() =>
      parseArenaBlocksCSV('abc, ed map, emergency department, exit')
    ).toThrow(/not numeric/);
  });

  it('throws when a row is too short', () => {
    expect(() => parseArenaBlocksCSV('1299, ed map, exit')).toThrow(
      /at least 4 cells/
    );
  });
});

describe('parseGameObjectBlocksCSV', () => {
  it('decodes the canonical seed file', () => {
    const raw =
      '1299, ed map, <all>, diagnostic table\n' +
      '1330, ed map, <all>, bed\n' +
      '1342, ed map, <all>, waiting room chair\n';
    const rows = parseGameObjectBlocksCSV(raw);
    expect(rows).toEqual([
      { tileId: 1299, objectLabel: 'diagnostic table' },
      { tileId: 1330, objectLabel: 'bed' },
      { tileId: 1342, objectLabel: 'waiting room chair' }
    ]);
  });
});

describe('parseSpawningBlocksCSV', () => {
  it('decodes the canonical seed file with slot labels', () => {
    const raw =
      '1291, ed map, emergency department, diagnostic room, sp-A\n' +
      '1304, ed map, emergency department, triage room, sp-A\n';
    const rows = parseSpawningBlocksCSV(raw);
    expect(rows).toEqual([
      { tileId: 1291, zoneLabel: 'diagnostic room', slot: 'sp-A' },
      { tileId: 1304, zoneLabel: 'triage room', slot: 'sp-A' }
    ]);
  });

  it('throws when the slot column is missing', () => {
    expect(() =>
      parseSpawningBlocksCSV('1291, ed map, emergency department, diagnostic room')
    ).toThrow(/at least 5 cells/);
  });
});
