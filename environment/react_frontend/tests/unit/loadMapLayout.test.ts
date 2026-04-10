/**
 * Unit tests for the {@link loadMapLayout} fetch helper.
 *
 * The helper is pure I/O glue, so the tests inject a mock `fetch` and pin
 * the request URLs and parser hand-off behaviour.
 */

import { describe, expect, it, vi } from 'vitest';
import { loadMapLayout } from '@/parser/loadMapLayout';

const TINY_TILED_JSON = {
  width: 1,
  height: 1,
  tilewidth: 32,
  tileheight: 32,
  layers: [
    {
      name: 'Arena Layer',
      type: 'tilelayer',
      width: 1,
      height: 1,
      data: [1314]
    },
    {
      name: 'Object Interaction Layer',
      type: 'tilelayer',
      width: 1,
      height: 1,
      data: [1330]
    },
    {
      name: 'Spawning Blocks',
      type: 'tilelayer',
      width: 1,
      height: 1,
      data: [0]
    },
    {
      name: 'Walls',
      type: 'tilelayer',
      width: 1,
      height: 1,
      data: [0]
    },
    {
      name: 'Collisions',
      type: 'tilelayer',
      width: 1,
      height: 1,
      data: [0]
    }
  ]
};

const ARENA_BLOCKS = '1314, ed map, emergency department, triage room\n';
const GAME_OBJECT_BLOCKS = '1330, ed map, <all>, bed\n';
const SPAWNING_BLOCKS = '1304, ed map, emergency department, triage room, sp-A\n';

function makeFetch(): typeof fetch {
  const mock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    if (url.endsWith('layout.json')) {
      return new Response(JSON.stringify(TINY_TILED_JSON), { status: 200 });
    }
    if (url.endsWith('arena_blocks.csv')) {
      return new Response(ARENA_BLOCKS, { status: 200 });
    }
    if (url.endsWith('game_object_blocks.csv')) {
      return new Response(GAME_OBJECT_BLOCKS, { status: 200 });
    }
    if (url.endsWith('spawning_location_blocks.csv')) {
      return new Response(SPAWNING_BLOCKS, { status: 200 });
    }
    return new Response('not found', { status: 404 });
  });
  return mock as unknown as typeof fetch;
}

describe('loadMapLayout', () => {
  it('fetches all four files and runs the parser pipeline', async () => {
    const layout = await loadMapLayout({
      mapId: 'tiny',
      tiledJsonUrl: '/maps/tiny/layout.json',
      arenaBlocksUrl: '/maps/arena_blocks.csv',
      gameObjectBlocksUrl: '/maps/game_object_blocks.csv',
      spawningBlocksUrl: '/maps/spawning_location_blocks.csv',
      fetchImpl: makeFetch()
    });

    expect(layout.mapId).toBe('tiny');
    expect(layout.zones).toHaveLength(1);
    expect(layout.zones[0]!.zoneId).toBe('triage_room');
    expect(layout.equipment).toHaveLength(1);
    expect(layout.equipment[0]!.type).toBe('bed');
  });

  it('throws if any HTTP request fails', async () => {
    const failing = (async () =>
      new Response('boom', { status: 500, statusText: 'Internal' })) as unknown as typeof fetch;
    await expect(
      loadMapLayout({
        mapId: 'tiny',
        tiledJsonUrl: '/maps/tiny/layout.json',
        arenaBlocksUrl: '/maps/arena_blocks.csv',
        gameObjectBlocksUrl: '/maps/game_object_blocks.csv',
        spawningBlocksUrl: '/maps/spawning_location_blocks.csv',
        fetchImpl: failing
      })
    ).rejects.toThrow(/Failed to fetch/);
  });
});
