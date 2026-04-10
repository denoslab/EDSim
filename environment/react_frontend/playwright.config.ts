import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for end-to-end tests of the EDSim React frontend.
 *
 * - Spawns the Vite dev server on `http://127.0.0.1:5173` before tests run
 *   and tears it down afterwards.
 * - Default project is desktop Chromium; additional projects can be added
 *   for cross-browser parity in later phases.
 * - In CI we mark `forbidOnly` so accidentally-merged `.only` tests fail the
 *   build and we retry once to absorb canvas/timing flakes.
 */
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: 'npm run dev -- --strictPort',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 60_000
  }
});
