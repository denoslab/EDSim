import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Vite configuration for the EDSim React frontend.
 *
 * Notable choices:
 * - The Tiled JSON map files and their special-block CSV definitions live
 *   inside `environment/frontend_server/static_dirs/assets/the_ed/`. Vite is
 *   configured to expose that directory as a virtual `/maps` route during
 *   development so the parser can `fetch()` the same files the legacy
 *   Phaser/Tiled renderer consumes — without copying them.
 * - Production builds bundle a snapshot of those files into the `public/maps`
 *   directory at build time (see `scripts/sync-maps.mjs`).
 * - Server is bound to `127.0.0.1:5173` by default. Use `npm run dev -- --host`
 *   to expose it on the LAN.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      '@maps': path.resolve(
        __dirname,
        '../frontend_server/static_dirs/assets/the_ed'
      )
    }
  },
  server: {
    port: 5173,
    strictPort: true,
    host: '127.0.0.1',
    fs: {
      // Allow serving files from the legacy frontend's asset tree so the
      // parser can pull the canonical Tiled JSONs and special-block CSVs.
      allow: [
        path.resolve(__dirname),
        path.resolve(__dirname, '../frontend_server/static_dirs/assets/the_ed')
      ]
    }
  },
  preview: {
    port: 4173,
    strictPort: true,
    host: '127.0.0.1'
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'es2022'
  }
});
