---
name: all-thing-eye-local-dev-expertise
description: Three non-obvious traps when running all-thing-eye backend+frontend locally (.venv empty, prod DB reachable, uvicorn --reload hides import errors)
triggers:
  - run-local.sh
  - ModuleNotFoundError pymongo
  - backend not running localhost:8000
  - Make sure the backend API is running
  - uvicorn --reload port not binding
  - .venv empty deps
  - MONGODB_URI prod reachable
  - is the db firewalled
---

# all-thing-eye — Local Dev Gotchas

## The Insight
Running this repo locally has three traps that each LOOK like a different problem than they are. Diagnose them in this order before guessing.

## Why This Matters
Each one cost real time this session: a "backend not running" error that was actually a missing dep, and a wrong "the DB is firewalled, use an SSH tunnel" conclusion that was actually a broken connectivity test. Knowing these saves an hour.

## Recognition Pattern & The Approach

**1. `.venv` exists but is EMPTY — backend deps live in SYSTEM `python3`.**
- Symptom: a script that does `[ -x .venv/bin/python ] && PY=.venv/bin/python` fails; `uvicorn` exits with `ModuleNotFoundError: No module named 'pymongo'`.
- Rule: pick the interpreter that can actually `import pymongo, fastapi, uvicorn, motor, strawberry`. System `python3` has them; `.venv` does not. `scripts/run-local.sh` already auto-detects this — use it.

**2. `.env` `MONGODB_URI` points to PROD (`43.201.95.192:27017`) and is DIRECTLY reachable from local — it is NOT firewalled.**
- mongo binds `0.0.0.0:27017`, host `ufw` is inactive, so any IP with the password connects. The mongo user is `ale` (authSource=ati).
- Gotcha: do NOT test reachability with `timeout 3 bash -c "cat </dev/null >/dev/tcp/HOST/PORT"` — **macOS has no `timeout`**, so the command aborts and reads as "blocked" (a false negative). Verify with a real `socket.connect_ex` in python, or `pymongo` ping. There is no need for an SSH tunnel; a plain `uvicorn` reading `.env` connects to prod fine.

**3. `uvicorn --reload` MASKS startup import errors.**
- Symptom: the uvicorn process is alive (`pgrep` finds it) but `:8000` never starts LISTENING, and the frontend shows "Make sure the backend API is running."
- Rule: a running process + unbound port = the app failed to import, not a slow/hung startup. Reproduce on a throwaway port WITHOUT `--reload`, piping to a logfile, to surface the real traceback:
  `python3 -m uvicorn backend.main:app --port 8011 > /tmp/diag.log 2>&1 &` then read the log.

## Example
```bash
# one-command local run (backend :8000 -> PROD DB by default, frontend :3000)
./scripts/run-local.sh
# port busy (another project on :3000)?  ->  FRONTEND_PORT=3002 ./scripts/run-local.sh
# use the local mongo instead of prod   ->  LOCAL_DB=1 ./scripts/run-local.sh
```
Frontend pages are gated by AuthGuard; locally, `NEXT_PUBLIC_DEV_MODE=true` (in `frontend/.env.local`) bypasses login. A browser `ChunkLoadError: app/layout` after a dev-server restart is a stale-chunk client cache, not a server error — hard-refresh (Cmd+Shift+R), the server is fine.
