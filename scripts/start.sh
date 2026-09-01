#!/usr/bin/env bash
set -e

# Determine repository root directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=================================================="
echo "  Starting Kairos Ambient Action Agent System     "
echo "=================================================="

# 1. Start Infrastructure (PostgreSQL, Redis, Temporal)
echo "📦 [1/4] Starting Docker services (PostgreSQL 5435, Temporal 7234, Temporal UI 8234)..."
if command -v docker-compose &> /dev/null; then
  docker-compose up -d
else
  docker compose up -d
fi

echo "⏳ Waiting for Temporal Server to be ready on port 7234..."
for i in {1..30}; do
  if (echo > /dev/tcp/127.0.0.1/7234) 2>/dev/null || nc -z localhost 7234 2>/dev/null; then
    break
  fi
  sleep 1
done
echo "✓ Docker infrastructure is live and healthy."

# 2. Activate Python Virtual Environment
source "$ROOT_DIR/.venv/bin/activate"
export PYTHONPATH="$ROOT_DIR/backend"

# 2a. Apply database migrations (schema is owned by Alembic)
echo "🗄️  Applying database migrations..."
(cd "$ROOT_DIR/backend" && python -m alembic upgrade head) || {
  echo "❌ Migrations failed. Check POSTGRES_* settings and that Postgres is reachable on port 5435."
  exit 1
}

# 3. Start Temporal Worker in background
echo "⚡ [2/4] Starting Temporal Durable Worker..."
python -m app.temporal.worker &
WORKER_PID=$!
echo "✓ Temporal Worker running (PID $WORKER_PID)."

# 4. Start FastAPI Backend
echo "🚀 [3/4] Starting FastAPI Backend on http://0.0.0.0:8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --no-proxy-headers &
BACKEND_PID=$!
echo "✓ FastAPI Backend running (PID $BACKEND_PID)."

# 5. Start Next.js Frontend Dashboard
echo "💻 [4/4] Starting Next.js Frontend on http://localhost:3000..."
(cd "$ROOT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!
echo "✓ Next.js Frontend running (PID $FRONTEND_PID)."

echo ""
echo "=================================================="
echo "  🎉 Kairos System Ready!                         "
echo "  - Frontend: http://localhost:3000               "
echo "  - Backend API Docs: http://localhost:8000/docs  "
echo "  - Temporal UI: http://localhost:8234            "
echo "=================================================="

# Trap SIGINT / SIGTERM to gracefully kill all background processes
trap "kill $WORKER_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0" INT TERM EXIT
wait
