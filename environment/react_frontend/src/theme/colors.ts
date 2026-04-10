/**
 * Centralised colour palette for the EDSim React frontend.
 *
 * These constants are consumed by the Three.js renderer
 * ({@link ThreeFloorPlan}) and the MapViewer chrome. Every visual
 * decision about zone tints, wall colour, canvas background, and
 * spawning-slot overlays lives here so a re-skin is a one-file change.
 *
 * @packageDocumentation
 */

import type { ZoneId } from '@/parser/types';

/* -------------------------------------------------------------------------- */
/* Canvas & wall chrome                                                       */
/* -------------------------------------------------------------------------- */

/** Dark slate ground plane behind the building (CSS background). */
export const CANVAS_BACKGROUND_COLOR = '#3A3F38';

/* -------------------------------------------------------------------------- */
/* Zone colours (used as Three.js material tints)                             */
/* -------------------------------------------------------------------------- */

/**
 * Per-zone colour used as the Three.js MeshStandardMaterial `color`
 * tint, combined with the raster texture `map`. The texture provides
 * the surface detail; this tint provides the categorical identity.
 */
export const ZONE_COLORS: Record<ZoneId, string> = {
  waiting_room: '#A47A4A',
  triage_room: '#B8C8DA',
  hallway: '#C4C6CA',
  minor_injuries_zone: '#BAD0BC',
  major_injuries_zone: '#D6BAB0',
  trauma_room: '#D4B0BE',
  diagnostic_room: '#C4BAD0',
  exit: '#B0B5BA'
};

/**
 * Per-zone label colour (for future HTML or sprite-based labels
 * overlaying the 3D view).
 */
export const ZONE_LABEL_COLORS: Record<ZoneId, string> = {
  triage_room: '#1F375A',
  waiting_room: '#2A1C0B',
  hallway: '#33383F',
  minor_injuries_zone: '#1C431E',
  major_injuries_zone: '#571E11',
  trauma_room: '#521535',
  diagnostic_room: '#3A175D',
  exit: '#242B32'
};

/* -------------------------------------------------------------------------- */
/* Spawning slot overlay                                                      */
/* -------------------------------------------------------------------------- */

/** Fill colour for the spawning-slot debug overlay dots. */
export const SPAWN_OVERLAY_FILL = '#F97316';

/** Stroke colour for the spawning-slot debug overlay dots. */
export const SPAWN_OVERLAY_STROKE = '#7C2D12';
