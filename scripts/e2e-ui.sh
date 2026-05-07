#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/e2e-ui.sh — run the Playwright UI e2e suite
#
# Prerequisites (operator must set up before running):
#   1. A running Postgres instance (set ONTO_DATABASE_URL or use default dev DB)
#   2. Backend running on 127.0.0.1:8080 with:
#        ONTO_UI_SESSION_TTL=2        (enables session-expiry test)
#        ONTO_UI_COOKIE_SECURE=false  (allows cookie over HTTP on 127.0.0.1)
#   3. ONTO_BOOTSTRAP_TOKEN set to the bootstrap admin token for that backend
#      (printed by the backend on first run, or obtained via `make dev` logs)
#
# Quick-start (assumes `make dev` already running in another terminal):
#   export ONTO_BOOTSTRAP_TOKEN="op_..."
#   make e2e-ui
# ---------------------------------------------------------------------------
set -euo pipefail

export API_BASE_URL=${API_BASE_URL:-http://127.0.0.1:8080}
export ONTO_BOOTSTRAP_TOKEN=${ONTO_BOOTSTRAP_TOKEN:?must export the bootstrap token — see scripts/e2e-ui.sh for instructions}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$SCRIPT_DIR/../ui"

echo "==> Building UI..."
cd "$UI_DIR"
npm run build

echo "==> Installing Playwright browsers (chromium)..."
npx playwright install --with-deps chromium

echo "==> Running Playwright tests..."
npx playwright test
