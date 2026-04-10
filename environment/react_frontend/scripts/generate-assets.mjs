/**
 * Raster asset generator.
 *
 * Usage:
 *   npm run generate-assets
 *
 * Launches a headless Chromium (via Playwright) in a blank page, runs
 * elaborate procedural canvas drawing code via `page.evaluate`, captures
 * each resulting canvas as a PNG, and writes the PNGs to
 * `public/assets/`.
 *
 * The generator is deliberately build-time: we only pay the drawing cost
 * once per asset refresh and the runtime just loads the pre-baked PNGs.
 * That lets the generation pipeline be much more elaborate than anything
 * you'd want to run on every frame at runtime — multi-octave fBm mottle,
 * dozens of grain strokes per plank, radial-gradient drop shadows, etc.
 *
 * Outputs (under public/assets/):
 *
 *   textures/
 *     wood.png                    (512×512, waiting room)
 *     tile_clinical.png           (512×512, generic cream)
 *     tile_hallway.png            (512×512, neutral gray)
 *     tile_triage.png             (512×512, cool blue)
 *     tile_minor_injuries.png     (512×512, soft green)
 *     tile_major_injuries.png     (512×512, muted coral)
 *     tile_trauma.png             (512×512, rose)
 *     tile_diagnostic.png         (512×512, lavender)
 *     tile_exit.png               (512×512, threshold gray)
 *
 *   furniture/
 *     bed.png                     (256×256)
 *     medical_cart.png            (256×256)
 *     chair.png                   (256×256)
 *     waiting_chair.png           (256×256)
 *     wheelchair.png              (256×256)
 *     computer.png                (256×256)
 *     diagnostic_table.png        (256×256)
 */

import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_ROOT = join(__dirname, '..', 'src', 'assets');
const TEXTURE_DIR = join(OUTPUT_ROOT, 'textures');
const FURNITURE_DIR = join(OUTPUT_ROOT, 'furniture');

mkdirSync(TEXTURE_DIR, { recursive: true });
mkdirSync(FURNITURE_DIR, { recursive: true });

/**
 * The full generation pipeline, sent to the browser via
 * `page.evaluate`. Defined as a plain `function` so that Playwright can
 * serialise it cleanly; it therefore cannot close over any Node scope.
 */
function runInBrowser(jobs) {
  /* ---------------- Deterministic PRNG + helpers ---------------- */
  function mulberry32(seed) {
    let s = seed >>> 0;
    return function next() {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hashString(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }
  function parseHex(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
  }
  function toHex(r, g, b) {
    const clamp = (n) => Math.max(0, Math.min(255, Math.round(n)));
    const hex = ((clamp(r) << 16) | (clamp(g) << 8) | clamp(b))
      .toString(16)
      .padStart(6, '0');
    return '#' + hex;
  }
  function lerpColor(a, b, t) {
    const [ar, ag, ab] = parseHex(a);
    const [br, bg, bb] = parseHex(b);
    return toHex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t);
  }

  /* ---------------- Value noise + fBm ---------------- */
  function buildValueNoise(gridWidth, gridHeight, rng) {
    const grid = new Array(gridWidth * gridHeight);
    for (let i = 0; i < grid.length; i++) grid[i] = rng();
    const fade = (t) => t * t * (3 - 2 * t);
    const get = (ix, iy) => {
      const wx = ((ix % gridWidth) + gridWidth) % gridWidth;
      const wy = ((iy % gridHeight) + gridHeight) % gridHeight;
      return grid[wy * gridWidth + wx];
    };
    return (x, y) => {
      const ix = Math.floor(x);
      const iy = Math.floor(y);
      const fx = fade(x - ix);
      const fy = fade(y - iy);
      const a = get(ix, iy);
      const b = get(ix + 1, iy);
      const c = get(ix, iy + 1);
      const d = get(ix + 1, iy + 1);
      const abx = a + (b - a) * fx;
      const cdx = c + (d - c) * fx;
      return abx + (cdx - abx) * fy;
    };
  }
  function fbm(sample, x, y, octaves) {
    let amplitude = 1;
    let frequency = 1;
    let sum = 0;
    let norm = 0;
    for (let i = 0; i < octaves; i++) {
      sum += amplitude * sample(x * frequency, y * frequency);
      norm += amplitude;
      amplitude *= 0.5;
      frequency *= 2;
    }
    return sum / norm;
  }

  /* ---------------- Full-canvas mottle + noise ---------------- */
  function applyFbmMottle(ctx, width, height, darkColor, lightColor, strength, rng) {
    const sample = buildValueNoise(16, 16, rng);
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    const [dr, dg, db] = parseHex(darkColor);
    const [lr, lg, lb] = parseHex(lightColor);
    for (let py = 0; py < height; py++) {
      for (let px = 0; px < width; px++) {
        const nx = (px / width) * 16;
        const ny = (py / height) * 16;
        const v = fbm(sample, nx, ny, 5);
        const t = (v - 0.5) * strength;
        const idx = (py * width + px) * 4;
        if (t >= 0) {
          data[idx] += (lr - data[idx]) * t;
          data[idx + 1] += (lg - data[idx + 1]) * t;
          data[idx + 2] += (lb - data[idx + 2]) * t;
        } else {
          const neg = -t;
          data[idx] += (dr - data[idx]) * neg;
          data[idx + 1] += (dg - data[idx + 1]) * neg;
          data[idx + 2] += (db - data[idx + 2]) * neg;
        }
      }
    }
    ctx.putImageData(imageData, 0, 0);
  }

  function addPixelNoise(ctx, width, height, intensity, rng) {
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;
    for (let i = 0; i < data.length; i += 4) {
      const n = (rng() - 0.5) * 255 * intensity;
      data[i] = Math.max(0, Math.min(255, data[i] + n));
      data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + n));
      data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + n));
    }
    ctx.putImageData(imageData, 0, 0);
  }

  /**
   * Directional lighting gradient — darkens the bottom-right corner so
   * the whole canvas reads as a floor lit from the top-left.
   */
  function applyDirectionalLighting(ctx, width, height) {
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, 'rgba(255, 255, 255, 0.18)');
    gradient.addColorStop(0.45, 'rgba(255, 255, 255, 0)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0.2)');
    ctx.save();
    ctx.globalCompositeOperation = 'soft-light';
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
    ctx.restore();
  }

  /* ---------------- Wood generator ---------------- */
  function drawWood(canvas, options) {
    const ctx = canvas.getContext('2d');
    const rng = mulberry32(hashString('wood|' + JSON.stringify(options)));
    const { baseColor, lightColor, darkColor, grooveColor } = options;

    const W = canvas.width;
    const H = canvas.height;

    // Dark groove background.
    ctx.fillStyle = grooveColor;
    ctx.fillRect(0, 0, W, H);

    // Planks run vertically, 8 across the canvas.
    const NUM_PLANKS = 8;
    const plankWidth = W / NUM_PLANKS;
    const plankLength = H;

    for (let p = 0; p < NUM_PLANKS; p++) {
      const ox = p * plankWidth;
      const drift = (rng() - 0.5) * 0.34;
      const plankBase =
        drift >= 0
          ? lerpColor(baseColor, lightColor, drift * 2)
          : lerpColor(baseColor, darkColor, -drift * 2);

      const bodyGradient = ctx.createLinearGradient(ox, 0, ox + plankWidth, 0);
      bodyGradient.addColorStop(0, lerpColor(plankBase, lightColor, 0.16));
      bodyGradient.addColorStop(0.3, plankBase);
      bodyGradient.addColorStop(0.7, plankBase);
      bodyGradient.addColorStop(1, lerpColor(plankBase, darkColor, 0.22));
      ctx.fillStyle = bodyGradient;
      ctx.fillRect(ox + 1.5, 0, plankWidth - 3, plankLength);

      // Many, many grain strokes.
      const numGrains = 60;
      for (let g = 0; g < numGrains; g++) {
        const grainY = (g / numGrains) * plankLength + (rng() - 0.5) * 6;
        const goDark = rng() > 0.4;
        ctx.strokeStyle = goDark
          ? lerpColor(plankBase, darkColor, 0.22 + rng() * 0.22)
          : lerpColor(plankBase, lightColor, 0.1 + rng() * 0.14);
        ctx.globalAlpha = 0.12 + rng() * 0.32;
        ctx.lineWidth = 0.5 + rng() * 1.2;
        ctx.beginPath();
        const segments = 36;
        const phase = rng() * Math.PI * 2;
        const amplitude = 0.6 + rng() * 2.2;
        for (let s = 0; s <= segments; s++) {
          const fx = ox + (s / segments) * plankWidth;
          const fy = grainY + Math.sin(s * 0.35 + phase) * amplitude;
          if (s === 0) ctx.moveTo(fx, fy);
          else ctx.lineTo(fx, fy);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // Knots — 0-3 per plank.
      const numKnots = Math.floor(rng() * 3.5);
      for (let k = 0; k < numKnots; k++) {
        const kx = ox + plankWidth * (0.2 + rng() * 0.6);
        const ky = plankLength * (0.1 + rng() * 0.8);
        const kr = 4 + rng() * 9;
        const knotGradient = ctx.createRadialGradient(kx, ky, 0, kx, ky, kr);
        knotGradient.addColorStop(0, grooveColor);
        knotGradient.addColorStop(0.4, lerpColor(darkColor, grooveColor, 0.4));
        knotGradient.addColorStop(0.85, lerpColor(plankBase, darkColor, 0.3));
        knotGradient.addColorStop(1, plankBase);
        ctx.fillStyle = knotGradient;
        ctx.beginPath();
        ctx.arc(kx, ky, kr, 0, Math.PI * 2);
        ctx.fill();
        // Darker grain ring.
        ctx.strokeStyle = lerpColor(plankBase, darkColor, 0.5);
        ctx.globalAlpha = 0.55;
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.arc(kx, ky, kr + 2, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Left-edge chamfer highlight.
      ctx.fillStyle = lerpColor(plankBase, lightColor, 0.6);
      ctx.globalAlpha = 0.6;
      ctx.fillRect(ox + 1.5, 0, 1.5, plankLength);
      ctx.globalAlpha = 1;

      // Right-edge deep groove.
      ctx.fillStyle = grooveColor;
      ctx.fillRect(ox + plankWidth - 1.5, 0, 1.5, plankLength);
    }

    // Global fBm mottle pass across every plank.
    applyFbmMottle(
      ctx,
      W,
      H,
      lerpColor(darkColor, grooveColor, 0.3),
      lerpColor(lightColor, baseColor, 0.3),
      0.22,
      rng
    );

    // Global directional lighting.
    applyDirectionalLighting(ctx, W, H);

    // Fine photograph-grade noise.
    addPixelNoise(ctx, W, H, 0.05, rng);
  }

  /* ---------------- Tile generator ---------------- */
  function drawTile(canvas, options) {
    const ctx = canvas.getContext('2d');
    const rng = mulberry32(hashString('tile|' + JSON.stringify(options)));
    const { baseColor, highlightColor, shadowColor, groutColor, tileCount } = options;

    const W = canvas.width;
    const H = canvas.height;

    // Soft grout background.
    ctx.fillStyle = lerpColor(baseColor, groutColor, 0.4);
    ctx.fillRect(0, 0, W, H);

    const tilePx = W / tileCount;
    const groutPx = 2;

    for (let ty = 0; ty < tileCount; ty++) {
      for (let tx = 0; tx < tileCount; tx++) {
        const ox = tx * tilePx;
        const oy = ty * tilePx;
        const inner = tilePx - groutPx * 2;
        const ix = ox + groutPx;
        const iy = oy + groutPx;

        // Per-tile drift (±5%).
        const drift = (rng() - 0.5) * 0.1;
        const tileBase =
          drift >= 0
            ? lerpColor(baseColor, highlightColor, drift * 2)
            : lerpColor(baseColor, shadowColor, -drift);

        // Per-tile diagonal lighting.
        const gradient = ctx.createLinearGradient(ix, iy, ix + inner, iy + inner);
        gradient.addColorStop(0, lerpColor(tileBase, highlightColor, 0.15));
        gradient.addColorStop(0.5, tileBase);
        gradient.addColorStop(1, lerpColor(tileBase, shadowColor, 0.12));
        ctx.fillStyle = gradient;
        ctx.fillRect(ix, iy, inner, inner);
      }
    }

    // Full-canvas fBm mottle — the stone/marble drift that makes the
    // floor look like one continuous polished slab.
    applyFbmMottle(
      ctx,
      W,
      H,
      lerpColor(baseColor, shadowColor, 0.35),
      lerpColor(baseColor, highlightColor, 0.4),
      0.3,
      rng
    );

    // Second, finer fBm pass for close-up detail.
    applyFbmMottle(
      ctx,
      W,
      H,
      lerpColor(baseColor, shadowColor, 0.2),
      lerpColor(baseColor, highlightColor, 0.2),
      0.12,
      rng
    );

    // Global directional lighting.
    applyDirectionalLighting(ctx, W, H);

    // Subtle photograph-grade noise.
    addPixelNoise(ctx, W, H, 0.03, rng);
  }

  /* ---------------- Shadow helper ---------------- */
  function castShadow(ctx, drawFn) {
    ctx.save();
    ctx.shadowColor = 'rgba(10, 14, 20, 0.45)';
    ctx.shadowBlur = 14;
    ctx.shadowOffsetX = 4;
    ctx.shadowOffsetY = 6;
    drawFn();
    ctx.restore();
  }

  /* ---------------- Furniture: bed ---------------- */
  function drawBed(canvas) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;

    // Transparent background.
    ctx.clearRect(0, 0, W, H);

    // Bed is drawn in local coordinates 0..1; scale at the end via unit = W.
    const u = W / 2.5; // one "tile" worth of pixels (bed spans 1.5 tiles wide, 1 tile tall)
    const ox = u * 0.5; // left margin
    const oy = u * 0.4; // top margin
    const bedW = u * 1.55;
    const bedH = u * 0.8;

    // Cast shadow on the floor beneath the bed.
    castShadow(ctx, () => {
      ctx.fillStyle = '#000';
      const r = u * 0.12;
      roundedRect(ctx, ox, oy, bedW, bedH, r);
      ctx.fill();
    });

    // Head rail — dark, metallic-ish
    const headW = u * 0.16;
    const headGradient = ctx.createLinearGradient(ox, oy, ox + headW, oy);
    headGradient.addColorStop(0, '#0F141B');
    headGradient.addColorStop(0.5, '#2A3240');
    headGradient.addColorStop(1, '#11171F');
    ctx.fillStyle = headGradient;
    roundedRect(ctx, ox, oy, headW, bedH, [u * 0.12, 0, 0, u * 0.12]);
    ctx.fill();

    // Frame body (mattress base)
    const frameX = ox + headW;
    const frameW = bedW - headW;
    const frameGradient = ctx.createLinearGradient(
      frameX,
      oy,
      frameX + frameW,
      oy + bedH
    );
    frameGradient.addColorStop(0, '#F7F4EA');
    frameGradient.addColorStop(0.55, '#E8E3D3');
    frameGradient.addColorStop(1, '#CDC6B1');
    ctx.fillStyle = frameGradient;
    roundedRect(ctx, frameX, oy, frameW, bedH, [0, u * 0.1, u * 0.1, 0]);
    ctx.fill();

    // Frame outline
    ctx.strokeStyle = '#2A2418';
    ctx.lineWidth = 1.5;
    roundedRect(ctx, frameX, oy, frameW, bedH, [0, u * 0.1, u * 0.1, 0]);
    ctx.stroke();

    // Mattress top highlight — thin warm lit strip along the head-end edge
    ctx.save();
    ctx.globalCompositeOperation = 'soft-light';
    const topHighlight = ctx.createLinearGradient(frameX, oy, frameX, oy + bedH);
    topHighlight.addColorStop(0, 'rgba(255,255,255,0.4)');
    topHighlight.addColorStop(0.4, 'rgba(255,255,255,0)');
    ctx.fillStyle = topHighlight;
    ctx.fillRect(frameX, oy, frameW, bedH);
    ctx.restore();

    // Pillow — large rectangular with a radial gradient for softness
    const pillowX = frameX + u * 0.06;
    const pillowY = oy + u * 0.1;
    const pillowW = u * 0.42;
    const pillowH = bedH - u * 0.2;
    const pillowCx = pillowX + pillowW * 0.4;
    const pillowCy = pillowY + pillowH * 0.4;
    const pillowGradient = ctx.createRadialGradient(
      pillowCx,
      pillowCy,
      0,
      pillowCx,
      pillowCy,
      pillowW
    );
    pillowGradient.addColorStop(0, '#FFFFFF');
    pillowGradient.addColorStop(0.5, '#F3F0E6');
    pillowGradient.addColorStop(1, '#BFB7A0');
    ctx.fillStyle = pillowGradient;
    roundedRect(ctx, pillowX, pillowY, pillowW, pillowH, u * 0.08);
    ctx.fill();
    ctx.strokeStyle = '#817762';
    ctx.lineWidth = 1;
    roundedRect(ctx, pillowX, pillowY, pillowW, pillowH, u * 0.08);
    ctx.stroke();

    // Sheet fold line
    ctx.strokeStyle = '#A7A08A';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    const foldX = frameX + u * 0.72;
    ctx.moveTo(foldX, oy + u * 0.08);
    ctx.lineTo(foldX, oy + bedH - u * 0.08);
    ctx.stroke();

    // Second sheet fold (slightly lighter) closer to foot end
    ctx.strokeStyle = '#CDC6B1';
    ctx.lineWidth = 1;
    ctx.beginPath();
    const foldX2 = frameX + u * 1.0;
    ctx.moveTo(foldX2, oy + u * 0.1);
    ctx.lineTo(foldX2, oy + bedH - u * 0.1);
    ctx.stroke();

    // Foot rail — thin dark upright
    const footX = ox + bedW + u * 0.02;
    const footGradient = ctx.createLinearGradient(footX, oy, footX + u * 0.05, oy);
    footGradient.addColorStop(0, '#1A1F27');
    footGradient.addColorStop(0.5, '#2E3440');
    footGradient.addColorStop(1, '#1A1F27');
    ctx.fillStyle = footGradient;
    roundedRect(ctx, footX, oy + u * 0.1, u * 0.06, bedH - u * 0.2, u * 0.03);
    ctx.fill();

    // Small wheel dots at each corner of the frame base
    ctx.fillStyle = '#0D1218';
    for (const cx of [ox + u * 0.08, ox + bedW - u * 0.08]) {
      for (const cy of [oy + u * 0.06, oy + bedH - u * 0.06]) {
        ctx.beginPath();
        ctx.arc(cx, cy, u * 0.035, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  /* ---------------- Furniture: medical cart ---------------- */
  function drawMedicalCart(canvas) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const u = W;
    const ox = u * 0.22;
    const oy = u * 0.1;
    const cw = u * 0.56;
    const ch = u * 0.78;

    // Cast shadow beneath the cart.
    castShadow(ctx, () => {
      ctx.fillStyle = '#000';
      roundedRect(ctx, ox, oy, cw, ch, u * 0.06);
      ctx.fill();
    });

    // Cart body — white panel with a soft diagonal gradient for 3D feel
    const bodyGradient = ctx.createLinearGradient(ox, oy, ox + cw, oy + ch);
    bodyGradient.addColorStop(0, '#FCFCFB');
    bodyGradient.addColorStop(0.45, '#E2E4E5');
    bodyGradient.addColorStop(1, '#B7BAC0');
    ctx.fillStyle = bodyGradient;
    roundedRect(ctx, ox, oy, cw, ch, u * 0.06);
    ctx.fill();
    ctx.strokeStyle = '#1A1E25';
    ctx.lineWidth = 1.5;
    roundedRect(ctx, ox, oy, cw, ch, u * 0.06);
    ctx.stroke();

    // Cart top highlight
    ctx.save();
    ctx.globalCompositeOperation = 'soft-light';
    const topHighlight = ctx.createLinearGradient(ox, oy, ox, oy + ch);
    topHighlight.addColorStop(0, 'rgba(255,255,255,0.5)');
    topHighlight.addColorStop(0.3, 'rgba(255,255,255,0)');
    ctx.fillStyle = topHighlight;
    ctx.fillRect(ox, oy, cw, ch);
    ctx.restore();

    // Monitor panel (darker screen)
    const sx = ox + u * 0.07;
    const sy = oy + u * 0.08;
    const sw = cw - u * 0.14;
    const sh = u * 0.26;
    const screenGradient = ctx.createLinearGradient(sx, sy, sx, sy + sh);
    screenGradient.addColorStop(0, '#263443');
    screenGradient.addColorStop(0.4, '#324358');
    screenGradient.addColorStop(1, '#1A2431');
    ctx.fillStyle = screenGradient;
    roundedRect(ctx, sx, sy, sw, sh, u * 0.02);
    ctx.fill();
    ctx.strokeStyle = '#0B1118';
    ctx.lineWidth = 1.2;
    roundedRect(ctx, sx, sy, sw, sh, u * 0.02);
    ctx.stroke();

    // Screen specular reflection
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    const spec = ctx.createLinearGradient(sx, sy, sx + sw, sy);
    spec.addColorStop(0, 'rgba(120,160,200,0.4)');
    spec.addColorStop(0.3, 'rgba(120,160,200,0)');
    ctx.fillStyle = spec;
    roundedRect(ctx, sx, sy, sw, sh, u * 0.02);
    ctx.fill();
    ctx.restore();

    // ECG trace (green glowing line)
    ctx.strokeStyle = '#8CE0A8';
    ctx.lineWidth = 1.6;
    ctx.shadowColor = '#5FB07A';
    ctx.shadowBlur = 4;
    ctx.beginPath();
    const tracePoints = [
      [0.08, 0.5],
      [0.22, 0.5],
      [0.26, 0.25],
      [0.32, 0.8],
      [0.4, 0.5],
      [0.52, 0.5],
      [0.58, 0.3],
      [0.66, 0.78],
      [0.72, 0.5],
      [0.92, 0.5]
    ];
    tracePoints.forEach(([tx, ty], idx) => {
      const fx = sx + tx * sw;
      const fy = sy + ty * sh;
      if (idx === 0) ctx.moveTo(fx, fy);
      else ctx.lineTo(fx, fy);
    });
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Indicator LEDs
    ctx.fillStyle = '#8CE0A8';
    ctx.beginPath();
    ctx.arc(sx + sw * 0.1, sy + sh * 0.14, u * 0.015, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#EFC97A';
    ctx.beginPath();
    ctx.arc(sx + sw * 0.2, sy + sh * 0.14, u * 0.015, 0, Math.PI * 2);
    ctx.fill();

    // Control panel strip beneath the screen
    const cpY = sy + sh + u * 0.04;
    const cpH = u * 0.14;
    const panelGradient = ctx.createLinearGradient(sx, cpY, sx, cpY + cpH);
    panelGradient.addColorStop(0, '#E0E2E5');
    panelGradient.addColorStop(1, '#BEC2C7');
    ctx.fillStyle = panelGradient;
    roundedRect(ctx, sx, cpY, sw, cpH, u * 0.015);
    ctx.fill();
    ctx.strokeStyle = '#1A1E25';
    ctx.lineWidth = 0.9;
    roundedRect(ctx, sx, cpY, sw, cpH, u * 0.015);
    ctx.stroke();

    // Three knob circles on the control panel
    for (let k = 0; k < 3; k++) {
      const kx = sx + sw * (0.18 + 0.3 * k);
      const ky = cpY + cpH * 0.5;
      const kr = u * 0.028;
      const knobGradient = ctx.createRadialGradient(
        kx - kr * 0.3,
        ky - kr * 0.3,
        0,
        kx,
        ky,
        kr
      );
      knobGradient.addColorStop(0, '#A0A6AE');
      knobGradient.addColorStop(0.7, '#4E555E');
      knobGradient.addColorStop(1, '#1F262E');
      ctx.fillStyle = knobGradient;
      ctx.beginPath();
      ctx.arc(kx, ky, kr, 0, Math.PI * 2);
      ctx.fill();
    }

    // Wheels
    for (const wx of [ox + u * 0.08, ox + cw - u * 0.08]) {
      const wy = oy + ch - u * 0.06;
      const wheelGradient = ctx.createRadialGradient(
        wx - u * 0.02,
        wy - u * 0.02,
        0,
        wx,
        wy,
        u * 0.05
      );
      wheelGradient.addColorStop(0, '#4A5360');
      wheelGradient.addColorStop(1, '#0C1218');
      ctx.fillStyle = wheelGradient;
      ctx.beginPath();
      ctx.arc(wx, wy, u * 0.05, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  /* ---------------- Furniture: chair ---------------- */
  function drawChair(canvas, options) {
    const { seatColor, trimColor } = options;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const u = W;
    ctx.clearRect(0, 0, W, W);

    // Cast shadow
    castShadow(ctx, () => {
      ctx.fillStyle = '#000';
      roundedRect(ctx, u * 0.22, u * 0.28, u * 0.56, u * 0.54, u * 0.12);
      ctx.fill();
    });

    // Chair seat — radial gradient for softness
    const cx = u * 0.5;
    const cy = u * 0.55;
    const seatGradient = ctx.createRadialGradient(
      cx - u * 0.1,
      cy - u * 0.1,
      0,
      cx,
      cy,
      u * 0.34
    );
    seatGradient.addColorStop(0, lerpColor(seatColor, '#FFFFFF', 0.25));
    seatGradient.addColorStop(0.7, seatColor);
    seatGradient.addColorStop(1, lerpColor(seatColor, '#000000', 0.25));
    ctx.fillStyle = seatGradient;
    roundedRect(ctx, u * 0.22, u * 0.3, u * 0.56, u * 0.52, u * 0.1);
    ctx.fill();
    ctx.strokeStyle = trimColor;
    ctx.lineWidth = 1.4;
    roundedRect(ctx, u * 0.22, u * 0.3, u * 0.56, u * 0.52, u * 0.1);
    ctx.stroke();

    // Backrest strip (visible as a darker strip along the top edge)
    const backGradient = ctx.createLinearGradient(u * 0.22, u * 0.3, u * 0.22, u * 0.37);
    backGradient.addColorStop(0, lerpColor(seatColor, '#000000', 0.45));
    backGradient.addColorStop(1, seatColor);
    ctx.fillStyle = backGradient;
    roundedRect(ctx, u * 0.22, u * 0.3, u * 0.56, u * 0.1, [u * 0.1, u * 0.1, 0, 0]);
    ctx.fill();
    ctx.strokeStyle = trimColor;
    ctx.lineWidth = 1;
    roundedRect(ctx, u * 0.22, u * 0.3, u * 0.56, u * 0.1, [u * 0.1, u * 0.1, 0, 0]);
    ctx.stroke();
  }

  /* ---------------- Furniture: wheelchair ---------------- */
  function drawWheelchair(canvas) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const u = W;
    ctx.clearRect(0, 0, W, W);

    const cx = u * 0.5;
    const cy = u * 0.5;

    // Cast shadow
    castShadow(ctx, () => {
      ctx.fillStyle = '#000';
      ctx.beginPath();
      ctx.arc(cx, cy, u * 0.32, 0, Math.PI * 2);
      ctx.fill();
    });

    // Seat body
    const seatGradient = ctx.createRadialGradient(
      cx - u * 0.08,
      cy - u * 0.08,
      0,
      cx,
      cy,
      u * 0.32
    );
    seatGradient.addColorStop(0, '#E2E6EC');
    seatGradient.addColorStop(0.7, '#8C929C');
    seatGradient.addColorStop(1, '#353A45');
    ctx.fillStyle = seatGradient;
    ctx.beginPath();
    ctx.arc(cx, cy, u * 0.32, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#0E131A';
    ctx.lineWidth = 1.4;
    ctx.stroke();

    // Wheels — two large dark circles at the sides
    for (const wx of [cx - u * 0.36, cx + u * 0.36]) {
      const wheelGradient = ctx.createRadialGradient(
        wx,
        cy,
        0,
        wx,
        cy,
        u * 0.14
      );
      wheelGradient.addColorStop(0, '#34404E');
      wheelGradient.addColorStop(1, '#0A0F16');
      ctx.fillStyle = wheelGradient;
      ctx.beginPath();
      ctx.arc(wx, cy, u * 0.14, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#1A1F26';
      ctx.lineWidth = 1.2;
      ctx.stroke();
      // Spoke suggestion — a thin ring.
      ctx.strokeStyle = '#586275';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(wx, cy, u * 0.09, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Armrests (thin dark strips)
    ctx.fillStyle = '#1E252E';
    ctx.fillRect(cx - u * 0.22, cy - u * 0.3, u * 0.44, u * 0.04);
  }

  /* ---------------- Furniture: computer / workstation ---------------- */
  function drawComputer(canvas) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const u = W;
    ctx.clearRect(0, 0, W, W);

    castShadow(ctx, () => {
      ctx.fillStyle = '#000';
      roundedRect(ctx, u * 0.18, u * 0.18, u * 0.64, u * 0.56, u * 0.04);
      ctx.fill();
    });

    // Desk surface
    const deskGradient = ctx.createLinearGradient(
      u * 0.18,
      u * 0.18,
      u * 0.82,
      u * 0.74
    );
    deskGradient.addColorStop(0, '#EEE9DF');
    deskGradient.addColorStop(1, '#C8BFA8');
    ctx.fillStyle = deskGradient;
    roundedRect(ctx, u * 0.18, u * 0.18, u * 0.64, u * 0.56, u * 0.04);
    ctx.fill();
    ctx.strokeStyle = '#49402C';
    ctx.lineWidth = 1.2;
    roundedRect(ctx, u * 0.18, u * 0.18, u * 0.64, u * 0.56, u * 0.04);
    ctx.stroke();

    // Monitor
    const mx = u * 0.26;
    const my = u * 0.22;
    const mw = u * 0.48;
    const mh = u * 0.26;
    const monGradient = ctx.createLinearGradient(mx, my, mx, my + mh);
    monGradient.addColorStop(0, '#24323F');
    monGradient.addColorStop(0.5, '#3C5061');
    monGradient.addColorStop(1, '#192631');
    ctx.fillStyle = monGradient;
    roundedRect(ctx, mx, my, mw, mh, u * 0.015);
    ctx.fill();
    ctx.strokeStyle = '#0B1118';
    ctx.lineWidth = 1;
    roundedRect(ctx, mx, my, mw, mh, u * 0.015);
    ctx.stroke();

    // Monitor specular sheen
    ctx.save();
    ctx.globalCompositeOperation = 'screen';
    const sheen = ctx.createLinearGradient(mx, my, mx + mw, my);
    sheen.addColorStop(0, 'rgba(140,180,210,0.5)');
    sheen.addColorStop(0.4, 'rgba(140,180,210,0)');
    ctx.fillStyle = sheen;
    roundedRect(ctx, mx, my, mw, mh, u * 0.015);
    ctx.fill();
    ctx.restore();

    // Keyboard
    const kx = u * 0.3;
    const ky = my + mh + u * 0.05;
    const kw = u * 0.4;
    const kh = u * 0.14;
    const keyGradient = ctx.createLinearGradient(kx, ky, kx, ky + kh);
    keyGradient.addColorStop(0, '#F7F3E8');
    keyGradient.addColorStop(1, '#C9C1AE');
    ctx.fillStyle = keyGradient;
    roundedRect(ctx, kx, ky, kw, kh, u * 0.02);
    ctx.fill();
    ctx.strokeStyle = '#49402C';
    ctx.lineWidth = 0.9;
    roundedRect(ctx, kx, ky, kw, kh, u * 0.02);
    ctx.stroke();

    // Key row suggestion
    ctx.strokeStyle = 'rgba(73,64,44,0.5)';
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(kx + u * 0.03, ky + kh * 0.5);
    ctx.lineTo(kx + kw - u * 0.03, ky + kh * 0.5);
    ctx.stroke();
  }

  /* ---------------- Furniture: diagnostic table ---------------- */
  function drawDiagnosticTable(canvas) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const u = W;
    ctx.clearRect(0, 0, W, W);

    castShadow(ctx, () => {
      ctx.fillStyle = '#000';
      roundedRect(ctx, u * 0.08, u * 0.32, u * 0.84, u * 0.36, u * 0.12);
      ctx.fill();
    });

    // Long padded exam table
    const bodyGradient = ctx.createLinearGradient(
      u * 0.08,
      u * 0.32,
      u * 0.92,
      u * 0.68
    );
    bodyGradient.addColorStop(0, '#E6F1F2');
    bodyGradient.addColorStop(0.5, '#C8D8DA');
    bodyGradient.addColorStop(1, '#7FA0A4');
    ctx.fillStyle = bodyGradient;
    roundedRect(ctx, u * 0.08, u * 0.32, u * 0.84, u * 0.36, u * 0.12);
    ctx.fill();
    ctx.strokeStyle = '#0F3136';
    ctx.lineWidth = 1.5;
    roundedRect(ctx, u * 0.08, u * 0.32, u * 0.84, u * 0.36, u * 0.12);
    ctx.stroke();

    // Segment line near head
    ctx.strokeStyle = '#2F5C61';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(u * 0.22, u * 0.34);
    ctx.lineTo(u * 0.22, u * 0.66);
    ctx.stroke();

    // Highlight rim
    ctx.save();
    ctx.globalCompositeOperation = 'soft-light';
    const rim = ctx.createLinearGradient(u * 0.08, u * 0.32, u * 0.08, u * 0.68);
    rim.addColorStop(0, 'rgba(255,255,255,0.5)');
    rim.addColorStop(0.3, 'rgba(255,255,255,0)');
    ctx.fillStyle = rim;
    ctx.fillRect(u * 0.08, u * 0.32, u * 0.84, u * 0.36);
    ctx.restore();
  }

  /* ---------------- Helpers ---------------- */
  function roundedRect(ctx, x, y, w, h, r) {
    // r can be a scalar or [tl, tr, br, bl]
    const radii = Array.isArray(r) ? r : [r, r, r, r];
    const [tl, tr, br, bl] = radii;
    ctx.beginPath();
    ctx.moveTo(x + tl, y);
    ctx.lineTo(x + w - tr, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + tr);
    ctx.lineTo(x + w, y + h - br);
    ctx.quadraticCurveTo(x + w, y + h, x + w - br, y + h);
    ctx.lineTo(x + bl, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - bl);
    ctx.lineTo(x, y + tl);
    ctx.quadraticCurveTo(x, y, x + tl, y);
    ctx.closePath();
  }

  /* ---------------- Dispatch ---------------- */
  const results = {};
  for (const job of jobs) {
    const canvas = document.createElement('canvas');
    canvas.width = job.size;
    canvas.height = job.size;
    switch (job.kind) {
      case 'wood':
        drawWood(canvas, job.options);
        break;
      case 'tile':
        drawTile(canvas, job.options);
        break;
      case 'bed':
        drawBed(canvas);
        break;
      case 'medical_cart':
        drawMedicalCart(canvas);
        break;
      case 'chair':
      case 'waiting_chair':
        drawChair(canvas, job.options);
        break;
      case 'wheelchair':
        drawWheelchair(canvas);
        break;
      case 'computer':
        drawComputer(canvas);
        break;
      case 'diagnostic_table':
        drawDiagnosticTable(canvas);
        break;
    }
    results[job.name] = canvas.toDataURL('image/png');
  }
  return results;
}

/* -------------------------------------------------------------------------- */
/* Node driver                                                                */
/* -------------------------------------------------------------------------- */

/** List of every asset to generate. */
const jobs = [
  // Floors
  {
    name: 'textures/wood.png',
    kind: 'wood',
    size: 512,
    options: {
      baseColor: '#A47A4A',
      lightColor: '#D0A16B',
      darkColor: '#6D4B24',
      grooveColor: '#2C1C0A'
    }
  },
  {
    name: 'textures/tile_clinical.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 6,
      baseColor: '#D9DBDE',
      highlightColor: '#F2F4F6',
      shadowColor: '#A4A8AE',
      groutColor: '#8E9298'
    }
  },
  {
    name: 'textures/tile_hallway.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 5,
      baseColor: '#D6D8DC',
      highlightColor: '#EEF0F3',
      shadowColor: '#959AA1',
      groutColor: '#7F848B'
    }
  },
  {
    name: 'textures/tile_triage.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 6,
      baseColor: '#C9D6E6',
      highlightColor: '#E9EFF6',
      shadowColor: '#8FA3BC',
      groutColor: '#7B8A9E'
    }
  },
  {
    name: 'textures/tile_minor_injuries.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 6,
      baseColor: '#CADECC',
      highlightColor: '#E7F0E8',
      shadowColor: '#8FA892',
      groutColor: '#788B7A'
    }
  },
  {
    name: 'textures/tile_major_injuries.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 6,
      baseColor: '#E3C8BF',
      highlightColor: '#F3E0D6',
      shadowColor: '#A4867A',
      groutColor: '#8E7367'
    }
  },
  {
    name: 'textures/tile_trauma.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 6,
      baseColor: '#DFC1CB',
      highlightColor: '#F0D7DF',
      shadowColor: '#A07C8B',
      groutColor: '#8A6877'
    }
  },
  {
    name: 'textures/tile_diagnostic.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 6,
      baseColor: '#D2C5DE',
      highlightColor: '#E6DAED',
      shadowColor: '#958AA4',
      groutColor: '#80748F'
    }
  },
  {
    name: 'textures/tile_exit.png',
    kind: 'tile',
    size: 512,
    options: {
      tileCount: 5,
      baseColor: '#C2C7CD',
      highlightColor: '#D6DCE2',
      shadowColor: '#7B8189',
      groutColor: '#6C7279'
    }
  },
  // Furniture
  { name: 'furniture/bed.png', kind: 'bed', size: 320 },
  { name: 'furniture/medical_cart.png', kind: 'medical_cart', size: 256 },
  {
    name: 'furniture/chair.png',
    kind: 'chair',
    size: 256,
    options: { seatColor: '#EADFC9', trimColor: '#2F2415' }
  },
  {
    name: 'furniture/waiting_chair.png',
    kind: 'waiting_chair',
    size: 256,
    options: { seatColor: '#D9C9AA', trimColor: '#2F2415' }
  },
  { name: 'furniture/wheelchair.png', kind: 'wheelchair', size: 256 },
  { name: 'furniture/computer.png', kind: 'computer', size: 256 },
  { name: 'furniture/diagnostic_table.png', kind: 'diagnostic_table', size: 256 }
];

async function main() {
  console.log('Generating %d assets…', jobs.length);
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext({
      viewport: { width: 1024, height: 1024 }
    });
    const page = await context.newPage();
    await page.goto('about:blank');
    const dataUrls = await page.evaluate(runInBrowser, jobs);
    for (const [name, dataUrl] of Object.entries(dataUrls)) {
      const base64 = dataUrl.split(',')[1];
      const buffer = Buffer.from(base64, 'base64');
      const outPath = join(OUTPUT_ROOT, name);
      mkdirSync(dirname(outPath), { recursive: true });
      writeFileSync(outPath, buffer);
      console.log('  wrote %s (%d KB)', name, Math.round(buffer.byteLength / 1024));
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
