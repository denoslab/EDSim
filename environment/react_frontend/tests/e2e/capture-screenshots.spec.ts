/**
 * Screenshot capture spec for visual spot-checks.
 *
 * Run with:
 *   CAPTURE_SCREENSHOTS=1 npx playwright test capture-screenshots
 */

import { test } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdirSync } from 'node:fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(__dirname, '../../test-results/screenshots');

const shouldRun = process.env.CAPTURE_SCREENSHOTS === '1';

test.describe.configure({ mode: 'serial' });

test.beforeAll(() => {
  if (shouldRun) {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
  }
});

test.describe('Viewer screenshots', () => {
  test.skip(!shouldRun, 'Set CAPTURE_SCREENSHOTS=1 to enable.');

  test('small ED layout — 3D view', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByTestId('three-floor-plan').waitFor();
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'small_ed_layout_3d.png'),
      fullPage: false
    });
  });

  test('small ED layout — 3D view with spawn overlay', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByTestId('three-floor-plan').waitFor();
    await page.getByTestId('toggle-spawn-overlay').check();
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'small_ed_layout_3d_spawn.png'),
      fullPage: false
    });
  });

  test('foothills ED layout — 3D view', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByTestId('map-button-foothills_ed_layout').click();
    await page.getByTestId('three-floor-plan').waitFor();
    await page.waitForTimeout(3000);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'foothills_ed_layout_3d.png'),
      fullPage: false
    });
  });
});
