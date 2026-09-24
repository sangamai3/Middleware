#!/usr/bin/env bash
# Start SangamMW for local development: Postgres (Docker if needed) + API + Vite.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8100}"
PYTHON="${PYTHON:-python3}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "→ Ensuring database (SANGAM_POSTGRES=${SANGAM_POSTGRES:-auto})…"
cd "$ROOT/backend"
"$PYTHON" -m sangam_mw.dev.db_bootstrap

echo "→ API http://127.0.0.1:${API_PORT}/docs"
"$PYTHON" -m uvicorn sangam_mw.api.main:app --reload --reload-exclude '.venv/*' --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$ROOT/frontend"
echo "→ UI http://127.0.0.1:5173"
npm run dev
