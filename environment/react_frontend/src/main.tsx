/**
 * React entry point.
 *
 * Mounts the {@link MapViewer} into `#root` and applies the global stylesheet.
 * Kept intentionally tiny so the viewer is the only consumer of the React
 * runtime in Phase 1.
 *
 * @packageDocumentation
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MapViewer } from './MapViewer';
import './styles.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Could not find #root element to mount the viewer into');
}

createRoot(rootElement).render(
  <StrictMode>
    <MapViewer />
  </StrictMode>
);
