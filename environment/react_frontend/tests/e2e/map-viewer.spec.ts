/**
 * End-to-end tests for the EDSim Floor Plan Viewer.
 *
 * These tests boot the Vite dev server (configured in `playwright.config.ts`)
 * and exercise the React / Three.js viewer with a real Chromium browser.
 * Since the 3D scene renders into a WebGL canvas, assertions target
 * deterministic DOM/text affordances (sidebar stats, toggles, WebGL
 * canvas presence) rather than pixel screenshots.
 */

import { expect, test } from '@playwright/test';

test.describe('Map viewer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('map-viewer')).toBeVisible();
  });

  test('renders the small ED layout by default and shows parsed counts', async ({
    page
  }) => {
    await expect(page.getByTestId('parser-stats')).toBeVisible();

    // Counts pinned in tests/unit/parseTiledJSON.test.ts.
    await expect(page.getByTestId('stat-zones')).toHaveText('8');
    await expect(page.getByTestId('stat-equipment')).toHaveText('42');
    await expect(page.getByTestId('stat-spawning')).toHaveText('18');
    await expect(page.getByTestId('stat-size')).toHaveText('30 × 20');

    // The Three.js scene renders into the page.
    await expect(page.getByTestId('three-floor-plan')).toBeVisible();

    // WebGL canvas should be present and non-empty.
    const canvas = page.locator('canvas').first();
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(100);
    expect(box!.height).toBeGreaterThan(100);
  });

  test('switches to the Foothills layout and updates the parser stats', async ({
    page
  }) => {
    await page.getByTestId('map-button-foothills_ed_layout').click();
    await expect(page.getByTestId('stat-equipment')).toHaveText('219');
    await expect(page.getByTestId('stat-spawning')).toHaveText('70');
    await expect(page.getByTestId('stat-size')).toHaveText('122 × 123');
  });

  test('persists the active map in the URL query string', async ({ page }) => {
    await page.getByTestId('map-button-foothills_ed_layout').click();
    await expect(page.getByTestId('stat-size')).toHaveText('122 × 123');
    expect(page.url()).toContain('map=foothills_ed_layout');

    await page.reload();
    await expect(page.getByTestId('stat-size')).toHaveText('122 × 123');
  });

  test('toggles the spawning-slot debug overlay without crashing', async ({
    page
  }) => {
    await expect(page.getByTestId('parser-stats')).toBeVisible();
    const toggle = page.getByTestId('toggle-spawn-overlay');
    await toggle.check();
    await expect(toggle).toBeChecked();
    await expect(page.locator('canvas').first()).toBeVisible();
    await toggle.uncheck();
    await expect(toggle).not.toBeChecked();
  });

  test('toggles zone labels', async ({ page }) => {
    const toggle = page.getByTestId('toggle-zone-labels');
    await expect(toggle).toBeChecked();
    await toggle.uncheck();
    await expect(toggle).not.toBeChecked();
    await expect(page.locator('canvas').first()).toBeVisible();
  });

  test('navigation controls are visible in the 3D view', async ({ page }) => {
    await expect(page.getByTestId('parser-stats')).toBeVisible();
    await expect(page.getByTestId('nav-controls')).toBeVisible();
    await expect(page.getByTestId('nav-zoom-in')).toBeVisible();
    await expect(page.getByTestId('nav-zoom-out')).toBeVisible();
    await expect(page.getByTestId('nav-rotate-left')).toBeVisible();
    await expect(page.getByTestId('nav-rotate-right')).toBeVisible();
    await expect(page.getByTestId('nav-reset')).toBeVisible();
  });
});
