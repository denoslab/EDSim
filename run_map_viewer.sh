#!/usr/bin/env bash
#
# run_map_viewer.sh — One-command launcher for the Phase 1 EDSim Floor Plan
# Viewer (React + Three.js).
#
# Usage:
#   ./run_map_viewer.sh                # install (if needed) and start dev server
#   ./run_map_viewer.sh build          # produce a production build in dist/
#   ./run_map_viewer.sh preview        # serve the built bundle on :4173
#   ./run_map_viewer.sh test           # run vitest unit tests
#   ./run_map_viewer.sh test:e2e       # run Playwright end-to-end tests
#
# The viewer lives under environment/react_frontend and reads its map data
# directly from environment/frontend_server/static_dirs/assets/the_ed/, so the
# floor plan you see in the browser is exactly the one the legacy Phaser
# renderer (and the simulation backend) consumes.
#
# Requirements: Node.js 18+ and npm. Install via Homebrew: `brew install node`.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="${REPO_ROOT}/environment/react_frontend"
COMMAND="${1:-dev}"

if ! command -v node >/dev/null 2>&1; then
  echo "error: node is not installed. Install it with: brew install node" >&2
  exit 1
fi

cd "${FRONTEND_DIR}"

if [ ! -d "node_modules" ]; then
  echo "==> Installing JavaScript dependencies (first run)…"
  npm install
fi

case "${COMMAND}" in
  dev)
    echo "==> Starting Vite dev server on http://127.0.0.1:5173"
    echo "    (Press Ctrl-C to stop.)"
    npm run dev
    ;;
  build)
    echo "==> Building production bundle into ${FRONTEND_DIR}/dist"
    npm run build
    ;;
  preview)
    if [ ! -d "dist" ]; then
      npm run build
    fi
    echo "==> Serving built bundle on http://127.0.0.1:4173"
    npm run preview
    ;;
  test)
    echo "==> Running vitest unit tests"
    npm test
    ;;
  test:e2e)
    echo "==> Running Playwright end-to-end tests"
    if [ ! -d "$HOME/Library/Caches/ms-playwright" ] && [ ! -d "$HOME/.cache/ms-playwright" ]; then
      echo "    Installing Playwright Chromium (one-time)…"
      npx playwright install --with-deps chromium
    fi
    npm run test:e2e
    ;;
  *)
    echo "error: unknown command '${COMMAND}'" >&2
    echo "usage: $0 [dev|build|preview|test|test:e2e]" >&2
    exit 2
    ;;
esac
