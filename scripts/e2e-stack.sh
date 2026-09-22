#!/usr/bin/env bash
# Kairos E2E stack runner: boots the worker + backend + frontend
# standalone on dedicated e2e ports, then runs the Playwright suite
# against them. Re-runnable: kills any previous e2e leftovers first.
#
# Environment overrides:
#   E2E_FRONTEND_PORT     default 3200 (3000 is the user's dev app and
#                         3100 is reserved by the OTHER app's e2e suite —
#                         both are off-limits; 3200 keeps us clear)
#   E2E_BACKEND_PORT     default 8100
#   POSTGRES_HOST/PORT    default localhost/5435 (shared dev container)
#   TEMPORAL_HOST         default localhost:7234 (shared dev container)
#   SKIP_FRONTEND_BUILD   1 = reuse frontend/.next/standalone as-is
#   FORCE_FRONTEND_BUILD  1 = rebuild even when .next looks fresh
#
# Contract: exit code is Playwright's exit code; the stack is always
# torn down on exit (trap INT/TERM/EXIT). CI invokes: bash scripts/e2e-stack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

E2E_FRONTEND_PORT="${E2E_FRONTEND_PORT:-3200}"
E2E_BACKEND_PORT="${E2E_BACKEND_PORT:-8100}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5435}"
TEMPORAL_HOST="${TEMPORAL_HOST:-localhost:7234}"
SKIP_FRONTEND_BUILD="${SKIP_FRONTEND_BUILD:-0}"
FORCE_FRONTEND_BUILD="${FORCE_FRONTEND_BUILD:-0}"

# Dedicated Temporal queue: the e2e worker must never pick up (or miss)
# activities belonging to other suites' workers on the shared server.
# Both worker and backend dispatch through settings.TEMPORAL_TASK_QUEUE.
TEMPORAL_TASK_QUEUE="${TEMPORAL_TASK_QUEUE:-kairos-e2e-queue}"

# Repo-root venv with backend requirements (python 3.14).
log() { printf '[e2e-stack] %s\n' "$*" >&2; }
if [ -x "$ROOT/.venv/bin/python" ]; then
  VENV_PY="$ROOT/.venv/bin/python"
else
  VENV_PY="$(command -v python3 || command -v python)"
  log "WARNING: .venv/bin/python not found — falling back to $VENV_PY"
fi

SCRATCH="$ROOT/scratch"
mkdir -p "$SCRATCH"

WORKER_PID=""
BACKEND_PID=""
FRONTEND_PID=""
TEST_EXIT=0

cleanup() {
  local code=$?
  trap - EXIT INT TERM
  for pid in "$FRONTEND_PID" "$BACKEND_PID" "$WORKER_PID"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  # Reap any stragglers started outside this invocation's recorded PIDs.
  pkill -f "app.temporal.worker" 2>/dev/null || true
  wait 2>/dev/null || true
  exit "$code"
}
trap cleanup EXIT INT TERM

# ── 0. Idempotency: kill leftovers from a previous e2e-stack run ────
# (recorded pidfiles from this script; the shared dev worker is also
# swept because a non-e2e worker without SANDBOX_MODE steals activities
# when it shares the queue name — ours is dedicated, but a stale e2e
# worker on the same queue would double-execute items.)
kill_pidfile() {
  local pf="$1" pid
  if [ -f "$pf" ]; then
    pid="$(cat "$pf" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      log "stopping stale process (pid $pid, $(basename "$pf"))"
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.25
      done
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  fi
}
kill_pidfile "$SCRATCH/e2e-frontend.pid"
kill_pidfile "$SCRATCH/e2e-backend.pid"
kill_pidfile "$SCRATCH/e2e-worker.pid"
pkill -f "app.temporal.worker" 2>/dev/null || true

# Port sanity: our e2e ports must be free (the other app owns 3000 and
# must never be touched). Anything still listening after the pidfile
# sweep is a foreign process — abort rather than disturb it.
port_listening() {
  ss -tlnH "sport = :$1" 2>/dev/null | grep -q LISTEN
}
for p in "$E2E_BACKEND_PORT" "$E2E_FRONTEND_PORT"; do
  if port_listening "$p"; then
    log "FATAL: port $p is still occupied; refusing to start (another e2e run?)"
    exit 78
  fi
done

# ── 1. Dev infra: postgres + temporal (reuse, never re-create) ───────
wait_for() { # wait_for <seconds> <check-cmd...>
  local deadline=$((SECONDS + $1)); shift
  while (( SECONDS < deadline )); do
    if "$@" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}
pg_ok() { timeout 3 bash -c "</dev/tcp/$POSTGRES_HOST/$POSTGRES_PORT"; }
temporal_ok() { timeout 3 bash -c "</dev/tcp/${TEMPORAL_HOST%%:*}/${TEMPORAL_HOST##*:}"; }
if ! wait_for 30 pg_ok; then
  log "postgres not reachable — starting dev containers"
  docker compose -f docker-compose.dev.yml up -d
  wait_for 60 pg_ok || { log "FATAL: postgres never became reachable"; exit 1; }
fi
if ! wait_for 30 temporal_ok; then
  log "temporal not reachable — starting dev containers"
  docker compose -f docker-compose.dev.yml up -d
  wait_for 60 temporal_ok || { log "FATAL: temporal never became reachable"; exit 1; }
fi
log "dev infra up (pg $POSTGRES_HOST:$POSTGRES_PORT, temporal $TEMPORAL_HOST)"

# ── 2. Migrations ───────────────────────────────────────────────────
(
  cd "$ROOT/backend"
  PYTHONPATH="$ROOT/backend" "$VENV_PY" -m alembic upgrade head
)
log "database migrated to head"

# ── 3. Worker (dedicated e2e task queue, sandbox execution) ─────────
# setsid: without it the process dies with this shell's session.
E2E_ENV=(
  APP_ENV=test
  SANDBOX_MODE=true
  TEMPORAL_TASK_QUEUE="$TEMPORAL_TASK_QUEUE"
  TEMPORAL_HOST="$TEMPORAL_HOST"
  POSTGRES_HOST="$POSTGRES_HOST"
  POSTGRES_PORT="$POSTGRES_PORT"
  KAIROS_DB_APP_NAME=kairos-e2e-worker
  PYTHONPATH="$ROOT/backend"
)
setsid env "${E2E_ENV[@]}" \
  "$VENV_PY" -m app.temporal.worker \
  >"$SCRATCH/e2e-worker.log" 2>&1 &
WORKER_PID=$!
echo "$WORKER_PID" > "$SCRATCH/e2e-worker.pid"
log "worker started (pid $WORKER_PID, queue $TEMPORAL_TASK_QUEUE) -> scratch/e2e-worker.log"

# ── 4. Backend (test env: no API key, deterministic extraction) ─────
setsid env "${E2E_ENV[@]}" KAIROS_DB_APP_NAME=kairos-e2e-backend \
  "$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$E2E_BACKEND_PORT" --no-proxy-headers \
  >"$SCRATCH/e2e-backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$SCRATCH/e2e-backend.pid"
log "backend started (pid $BACKEND_PID, port $E2E_BACKEND_PORT) -> scratch/e2e-backend.log"

backend_ok() { curl -sf "http://127.0.0.1:$E2E_BACKEND_PORT/api/health" >/dev/null; }
if ! wait_for 60 backend_ok; then
  log "FATAL: backend did not become healthy; tail of scratch/e2e-backend.log:"
  tail -n 40 "$SCRATCH/e2e-backend.log" >&2 || true
  exit 1
fi
log "backend healthy"

# Sandbox must be ON for executions to succeed without credentials
# (persists in operator_settings, applies to new batches).
curl -s -X POST "http://127.0.0.1:$E2E_BACKEND_PORT/api/connectors/sandbox-toggle" \
  -H "Content-Type: application/json" \
  -d '{"sandbox_mode": true}' >/dev/null
log "sandbox mode enabled"

# ── 5. Frontend standalone build ────────────────────────────────────
NEED_BUILD=0
if [ "$SKIP_FRONTEND_BUILD" = "1" ]; then
  log "SKIP_FRONTEND_BUILD=1 — reusing existing .next/standalone"
elif [ "$FORCE_FRONTEND_BUILD" = "1" ]; then
  NEED_BUILD=1
elif [ ! -f "$ROOT/frontend/.next/standalone/server.js" ] || \
     [ ! -f "$ROOT/frontend/.next/standalone/.next/BUILD_ID" ] || \
     [ "$ROOT/frontend/src" -nt "$ROOT/frontend/.next/standalone/.next/BUILD_ID" ]; then
  NEED_BUILD=1
fi
if [ "$NEED_BUILD" = "1" ]; then
  log "building frontend (standalone output)"
  (
    cd "$ROOT/frontend"
    npm run build
    # next build recreates .next/standalone; static assets must be copied
    # in AFTER the build or pages ship without JS/CSS.
    cp -r .next/static .next/standalone/.next/static
  )
  [ -f "$ROOT/frontend/.next/standalone/.next/BUILD_ID" ] || { log "FATAL: BUILD_ID missing after build"; exit 1; }
  log "frontend built"
fi

# ── 6. Frontend server ──────────────────────────────────────────────
setsid env \
  PORT="$E2E_FRONTEND_PORT" \
  HOSTNAME=127.0.0.1 \
  BACKEND_INTERNAL_URL="http://127.0.0.1:$E2E_BACKEND_PORT" \
  node "$ROOT/frontend/.next/standalone/server.js" \
  >"$SCRATCH/e2e-frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$SCRATCH/e2e-frontend.pid"
log "frontend started (pid $FRONTEND_PID, port $E2E_FRONTEND_PORT) -> scratch/e2e-frontend.log"

frontend_ok() { curl -sf "http://127.0.0.1:$E2E_FRONTEND_PORT/" >/dev/null; }
if ! wait_for 60 frontend_ok; then
  log "FATAL: frontend did not come up; tail of scratch/e2e-frontend.log:"
  tail -n 40 "$SCRATCH/e2e-frontend.log" >&2 || true
  exit 1
fi
log "frontend up at http://127.0.0.1:$E2E_FRONTEND_PORT"

# ── 7. Playwright ────────────────────────────────────────────────────
log "running: npx playwright test $*"
cd "$ROOT/frontend"
E2E_FRONTEND_PORT="$E2E_FRONTEND_PORT" E2E_BACKEND_PORT="$E2E_BACKEND_PORT" \
  npx playwright test "$@"
