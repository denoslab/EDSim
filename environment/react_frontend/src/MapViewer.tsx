/**
 * `MapViewer` — top-level page that lets a user pick a map from the
 * catalogue and inspect its parsed floor plan in an interactive 3D view.
 *
 * The viewer is intentionally minimal — Phase 1 ships a sidebar of
 * available maps, display toggles, parsed-count stats, and a full 3D
 * Three.js scene. Future phases will add agent timelines, replays, and
 * metrics on top of the same {@link ThreeFloorPlan}.
 *
 * @packageDocumentation
 */

import { useEffect, useState } from 'react';
import { ThreeFloorPlan } from '@/components/ThreeFloorPlan';
import { loadMapLayout } from '@/parser/loadMapLayout';
import type { MapLayout } from '@/parser/types';
import { MAP_CATALOGUE, getCatalogueEntry, type MapCatalogueEntry } from '@/data/maps';

type LoadingState =
  | { kind: 'idle' }
  | { kind: 'loading'; mapId: string }
  | { kind: 'ready'; layout: MapLayout }
  | { kind: 'error'; mapId: string; error: string };

/**
 * The full map viewer page.
 */
export function MapViewer() {
  const [selected, setSelected] = useState<MapCatalogueEntry>(() => {
    if (typeof window === 'undefined') return MAP_CATALOGUE[0]!;
    const params = new URLSearchParams(window.location.search);
    return getCatalogueEntry(params.get('map'));
  });
  const [state, setState] = useState<LoadingState>({ kind: 'idle' });
  const [showZoneLabels, setShowZoneLabels] = useState(true);
  const [showSpawnOverlay, setShowSpawnOverlay] = useState(false);

  // Load the selected map.
  useEffect(() => {
    let cancelled = false;
    setState({ kind: 'loading', mapId: selected.id });
    loadMapLayout(selected.load)
      .then((layout) => {
        if (cancelled) return;
        setState({ kind: 'ready', layout });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setState({ kind: 'error', mapId: selected.id, error: message });
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  // Reflect the current selection in the URL so it survives reloads and
  // makes the viewer trivially shareable.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('map', selected.id);
    window.history.replaceState(null, '', url.toString());
  }, [selected]);

  return (
    <div className="map-viewer-root" data-testid="map-viewer">
      <header className="map-viewer-header">
        <div>
          <h1>EDSim Floor Plan Viewer</h1>
          <p className="subtitle">
            Phase 1 — Tiled JSON parser + Three.js 3D renderer
          </p>
        </div>
      </header>
      <div className="map-viewer-body">
        <aside className="map-viewer-sidebar" data-testid="map-sidebar">
          <h2>Maps</h2>
          <ul className="map-list">
            {MAP_CATALOGUE.map((entry) => {
              const isActive = entry.id === selected.id;
              return (
                <li key={entry.id}>
                  <button
                    type="button"
                    className={`map-list-item${isActive ? ' active' : ''}`}
                    onClick={() => setSelected(entry)}
                    data-testid={`map-button-${entry.id}`}
                  >
                    <span className="map-name">{entry.displayName}</span>
                    <span className="map-description">{entry.description}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          <h2>Display</h2>
          <label className="toggle">
            <input
              type="checkbox"
              checked={showZoneLabels}
              onChange={(e) => setShowZoneLabels(e.target.checked)}
              data-testid="toggle-zone-labels"
            />
            Show zone labels
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={showSpawnOverlay}
              onChange={(e) => setShowSpawnOverlay(e.target.checked)}
              data-testid="toggle-spawn-overlay"
            />
            Show spawning slots
          </label>

          {state.kind === 'ready' ? (
            <ParserStats layout={state.layout} />
          ) : null}
        </aside>

        <main className="map-viewer-canvas" data-testid="map-viewer-canvas-host">
          {state.kind === 'loading' ? (
            <div className="status" data-testid="loading-state">
              Loading <strong>{state.mapId}</strong>...
            </div>
          ) : null}
          {state.kind === 'error' ? (
            <div className="status error" data-testid="error-state">
              <strong>Failed to load {state.mapId}</strong>
              <pre>{state.error}</pre>
            </div>
          ) : null}
          {state.kind === 'ready' ? (
            <ThreeFloorPlan
              key={state.layout.mapId}
              layout={state.layout}
              showZoneLabels={showZoneLabels}
              showSpawnOverlay={showSpawnOverlay}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}

interface ParserStatsProps {
  layout: MapLayout;
}

/**
 * Compact summary of parser output, rendered in the sidebar so the
 * viewer doubles as a lightweight QA tool.
 */
function ParserStats({ layout }: ParserStatsProps) {
  return (
    <section data-testid="parser-stats" className="parser-stats">
      <h2>Parsed counts</h2>
      <dl>
        <dt>Zones</dt>
        <dd data-testid="stat-zones">{layout.zones.length}</dd>
        <dt>Equipment</dt>
        <dd data-testid="stat-equipment">{layout.equipment.length}</dd>
        <dt>Spawning slots</dt>
        <dd data-testid="stat-spawning">{layout.spawningLocations.length}</dd>
        <dt>Wall segments</dt>
        <dd data-testid="stat-walls">{layout.walls.length}</dd>
        <dt>Map size</dt>
        <dd data-testid="stat-size">
          {layout.widthInTiles} × {layout.heightInTiles}
        </dd>
      </dl>
    </section>
  );
}
