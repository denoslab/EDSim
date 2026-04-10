/**
 * Screenshot capture spec for visual spot-checks.
 *
 * Run with:
 *   CAPTURE_SCREENSHOTS=1 npx playwright test capture-screenshots
 */

import { test } from '@playwright/test';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdirSync } from 'node:fs';

const _dir = join(dirname(fileURLToPath(import.meta.url)), '../../test-results/screenshots');
const shouldRun = !!process.env['CAPTURE_SCREENSHOTS'];

test.describe('Viewer screenshots', () => {
  test.beforeEach(async () => {
    if (shouldRun) mkdirSync(_dir, { recursive: true });
  });

  test('small ED layout 3D', async ({ page }) => {
    test.skip(!shouldRun);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByTestId('three-floor-plan').waitFor();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: join(_dir, 'small_ed_layout_3d.png') });
  });

  test('foothills ED layout 3D', async ({ page }) => {
    test.skip(!shouldRun);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await page.getByTestId('map-button-foothills_ed_layout').click();
    await page.getByTestId('three-floor-plan').waitFor();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: join(_dir, 'foothills_ed_layout_3d.png') });
  });
});
