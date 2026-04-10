# Getting Started

## Prerequisites

- **Node.js 18+** — `brew install node` on macOS
- **npm** — ships with Node.js

## Quick start

From the repository root:

```bash
./run_map_viewer.sh
```

This installs dependencies (first run), starts the Vite dev server, and opens the 3D floor plan viewer at [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Manual setup

```bash
cd environment/react_frontend
npm install
npm run dev
```

## Available scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server on `:5173` |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the production bundle on `:4173` |
| `npm run typecheck` | Run TypeScript type checking |
| `npm run lint` | Run ESLint |
| `npm test` | Run vitest unit tests |
| `npm run test:e2e` | Run Playwright end-to-end tests |
| `npm run generate-assets` | Regenerate floor texture PNGs |

## Project structure

```
environment/react_frontend/
├── src/
│   ├── main.tsx              # React entry point
│   ├── MapViewer.tsx         # Top-level page (sidebar + 3D canvas)
│   ├── styles.css            # Global stylesheet
│   ├── components/
│   │   └── ThreeFloorPlan.tsx   # Three.js 3D scene
│   ├── parser/               # Tiled JSON parser (pure functions)
│   ├── assets/               # Textures and sprite PNGs
│   ├── theme/                # Colour palette
│   └── data/                 # Map catalogue
├── public/
│   └── models/               # Kenney GLTF furniture models
├── tests/
│   ├── unit/                 # vitest (42 tests)
│   └── e2e/                  # Playwright (6 tests)
└── scripts/                  # Asset generation and debug utilities
```

## Environment setup for the full simulation

The 3D viewer is standalone — it only needs Node.js. To run the full simulation (backend + legacy frontend), see the [main README](https://github.com/denoslab/EDSim#installation).
