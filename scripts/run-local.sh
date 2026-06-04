#!/usr/bin/env bash
#
# run-local.sh — start all-thing-eye BACKEND + FRONTEND together (local dev).
#
# Usage:
#   ./scripts/run-local.sh                      # DEFAULT: backend -> PROD DB (MONGODB_URI in .env)
#   FRONTEND_PORT=3002 ./scripts/run-local.sh   # if :3000 is taken (e.g. another project)
#   BACKEND_PORT=8001  ./scripts/run-local.sh
#   LOCAL_DB=1 ./scripts/run-local.sh           # opt-in: use local mongo (mongodb://localhost:27017/ati)
#
# Stop BOTH:  Ctrl+C
#
# Notes:
#   - The unified current+retired export lives on branch `feature/unified-member-export`.
#   - .env MONGODB_URI currently points at the PROD DB and is directly reachable;
#     browsing/exporting is read-only-safe, but don't trigger data-collection/mutations.
#
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Pick a Python that ACTUALLY has the backend deps (.venv may be empty).
# Prefer .venv only if it can import the deps; otherwise fall back to system python3.
PY="python3"
if [ -x "$ROOT/.venv/bin/python" ] && "$ROOT/.venv/bin/python" -c "import pymongo, fastapi, uvicorn" >/dev/null 2>&1; then
  PY="$ROOT/.venv/bin/python"
fi
if ! "$PY" -c "import pymongo, fastapi, uvicorn, motor, strawberry" >/dev/null 2>&1; then
  echo "❌ Backend Python deps are missing in '$PY'."
  echo "   Install them, e.g.:"
  echo "     python3 -m pip install -r requirements.txt"
  echo "   (or set up the venv:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)"
  exit 1
fi

busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
if busy "$BACKEND_PORT";  then echo "❌ backend port $BACKEND_PORT is in use  →  set BACKEND_PORT=..."; exit 1; fi
if busy "$FRONTEND_PORT"; then echo "❌ frontend port $FRONTEND_PORT is in use →  try: FRONTEND_PORT=3002 $0"; exit 1; fi

# DB selection. DEFAULT = PRODUCTION DB (from .env MONGODB_URI).
# Opt in to the local mongo with: LOCAL_DB=1 ./scripts/run-local.sh
LOCAL_DB="${LOCAL_DB:-0}"
if [ "$LOCAL_DB" = "1" ]; then
  export MONGODB_URI="mongodb://localhost:27017/ati"
  DB_DESC="LOCAL mongo (mongodb://localhost:27017/ati)"
else
  # default → production DB; show host:port (credentials masked)
  _host="$(grep -m1 '^MONGODB_URI=' .env 2>/dev/null | sed -E 's#^MONGODB_URI=##; s#.*@##; s#[/?].*##')"
  DB_DESC="PROD DB (${_host:-from .env})"
fi

echo "▶ backend    http://localhost:$BACKEND_PORT     [$DB_DESC]"
echo "▶ frontend   http://localhost:$FRONTEND_PORT"
echo "  git branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null)   (unified export → feature/unified-member-export)"
echo "  Ctrl+C to stop both"
echo

# --- start backend ---
"$PY" -m uvicorn backend.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" 2>&1 \
  | sed -u 's/^/[backend]  /' &
BACK=$!

# --- start frontend ---
( cd "$ROOT/frontend" && npm run dev -- -p "$FRONTEND_PORT" 2>&1 | sed -u 's/^/[frontend] /' ) &
FRONT=$!

cleanup() {
  trap - EXIT INT TERM
  echo
  echo "⏹  stopping backend + frontend..."
  # kill the job subtrees (sed pipeline, uvicorn reloader, npm/next)
  for pid in "$BACK" "$FRONT"; do
    pkill -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
  done
  # belt-and-suspenders: free the ports
  { lsof -ti tcp:"$BACKEND_PORT"  -sTCP:LISTEN 2>/dev/null; lsof -ti tcp:"$FRONTEND_PORT" -sTCP:LISTEN 2>/dev/null; } | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
