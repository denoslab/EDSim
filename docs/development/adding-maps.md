# Adding New Maps

The 3D viewer supports any Tiled JSON map that follows the EDSim layer convention. Adding a new map is a four-step process with no code changes required.

## Steps

### 1. Create the Tiled JSON

Use the [Tiled](https://www.mapeditor.org/) map editor. The map must contain these named layers:

| Layer name | Purpose |
|---|---|
| `Arena Layer` | Zone classification (tile IDs from `arena_blocks.csv`) |
| `Object Interaction Layer` | Equipment placement (tile IDs from `game_object_blocks.csv`) |
| `Spawning Blocks` | Agent spawn points (tile IDs from `spawning_location_blocks.csv`) |
| `Walls` | Wall tiles (any non-zero tile = wall) |
| `Collisions` | Collision mask (any non-zero tile = blocked) |

Save the map as a JSON file.

### 2. Place the file

Drop the JSON file into:

```
environment/frontend_server/static_dirs/assets/the_ed/visuals/
```

### 3. Update CSV lookup tables (if needed)

If the new map introduces tile GIDs not already in the existing CSV files, add them to the corresponding file under:

```
environment/frontend_server/static_dirs/assets/the_ed/matrix/special_blocks/
```

| CSV file | Format |
|---|---|
| `arena_blocks.csv` | `<tileId>, ed map, emergency department, <zone label>` |
| `game_object_blocks.csv` | `<tileId>, ed map, <all>, <object label>` |
| `spawning_location_blocks.csv` | `<tileId>, ed map, emergency department, <zone label>, <slot label>` |

### 4. Register in the map catalogue

Add a new entry to `environment/react_frontend/src/data/maps.ts`:

```typescript
{
  id: 'my_new_map',
  displayName: 'My New Map',
  description: '50 × 40 custom layout.',
  load: {
    mapId: 'my_new_map',
    tiledJsonUrl: myNewMapJsonUrl,  // import via ?url
    arenaBlocksUrl,
    gameObjectBlocksUrl,
    spawningBlocksUrl
  }
}
```

The sidebar picks up the new entry automatically on the next dev server restart.

## Validation

After adding a map, verify the parser output:

```bash
cd environment/react_frontend
npx tsx scripts/dump-parser.mjs
```

This prints zone counts, equipment counts, and wall segment counts for every registered map. Cross-check these against the Tiled editor to confirm the parser decoded the map correctly.
