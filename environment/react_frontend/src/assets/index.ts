/**
 * Centralised catalogue of raster assets.
 *
 * Floor textures are loaded by the Three.js renderer as
 * `THREE.TextureLoader` sources. Furniture is loaded as GLTF models
 * from `public/models/`. The 2D sprite PNGs remain for potential
 * future use but the primary renderer is Three.js.
 *
 * @packageDocumentation
 */

import type { ZoneId } from '@/parser/types';

import woodUrl from './textures/wood.png?url';
import tileConcreteUrl from './textures/tile_concrete.png?url';

/**
 * URL of the floor texture for each zone category. Used by
 * {@link ThreeFloorPlan} as `THREE.TextureLoader` sources.
 */
export const ZONE_TEXTURE_URLS: Record<ZoneId, string> = {
  waiting_room: woodUrl,
  triage_room: tileConcreteUrl,
  hallway: tileConcreteUrl,
  minor_injuries_zone: tileConcreteUrl,
  major_injuries_zone: tileConcreteUrl,
  trauma_room: tileConcreteUrl,
  diagnostic_room: tileConcreteUrl,
  exit: tileConcreteUrl
};
