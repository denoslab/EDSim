# Running Tests

## Unit tests (vitest)

```bash
cd environment/react_frontend
npm test
```

42 tests across 3 test files:

| File | Tests | What it covers |
|---|---|---|
| `csv.test.ts` | 7 | CSV decoders for arena, game-object, and spawning block files |
| `parseTiledJSON.test.ts` | 33 | Zone extraction, wall compression, equipment/spawning extraction, fixture-pinned counts for both seed maps |
| `loadMapLayout.test.ts` | 2 | Browser-side fetch helper with mocked HTTP responses |

### Running with coverage

```bash
npm run test:coverage
```

Coverage report is written to `coverage/` (HTML + JSON summary).

## End-to-end tests (Playwright)

```bash
npm run test:e2e
```

6 tests in Chromium:

| Test | What it verifies |
|---|---|
| Renders small ED layout | Three.js canvas present, parsed counts match (8 zones, 42 equipment, 18 spawning) |
| Switches to Foothills | Stats update (219 equipment, 70 spawning, 122 × 123) |
| URL persistence | Map selection survives page reload |
| Toggle spawning overlay | Checkbox toggles without crashing WebGL |
| Toggle zone labels | Same |
| Navigation controls visible | All 5 nav buttons present in the DOM |

### Installing Playwright browsers

First e2e run requires a one-time browser download:

```bash
npx playwright install --with-deps chromium
```

### Capturing screenshots

```bash
CAPTURE_SCREENSHOTS=1 npx playwright test capture-screenshots
```

Outputs PNG files to `test-results/screenshots/` for visual QA. Gated behind the environment variable so it doesn't run in CI.

## CI

The `test-react-frontend` job in `.github/workflows/ci.yml` runs on every PR and push to `main`:

1. `npm ci` (install)
2. `npm run typecheck`
3. `npm run lint`
4. `npm test` (vitest)
5. `npm run build` (production bundle)
6. `npx playwright install --with-deps chromium`
7. `npm run test:e2e` (Playwright)
8. Upload Playwright report on failure
