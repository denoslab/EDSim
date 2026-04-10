import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Vitest configuration.
 *
 * - Unit tests live under `tests/unit/**`.
 * - The runner uses `node` for parser tests (pure functions, no DOM) and
 *   `jsdom` for hooks/utilities that touch the browser API surface.
 * - The `@maps` alias maps to the repository's canonical Tiled assets so
 *   tests parse the exact same files the running app would consume.
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
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json-summary'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/**/*.d.ts']
    }
  }
});
