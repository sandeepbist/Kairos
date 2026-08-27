#!/usr/bin/env bash
set -e

echo "=================================================="
echo "  Starting Kairos Ambient Action Agent System     "
echo "=================================================="

# 1. Start Infrastructure (PostgreSQL, Redis, Temporal)
echo "📦 [1/4] Starting Docker services (PostgreSQL 5435, Redis 6381, Temporal 7234)..."
docker-compose up -d

echo "⏳ Waiting for Temporal Server to be ready on port 7234..."
until nc -z localhost 7234 2>/dev/null; do
  sleep 1
done
echo "✓ Docker infrastructure is live and healthy."

# 2. Activate Python Virtual Environment
source .venv/bin/activate
export PYTHONPATH=backend

# 3. Start Temporal Worker in background
echo "⚡ [2/4] Starting Temporal Durable Worker..."
python -m app.temporal.worker &
WORKER_PID=$!
echo "✓ Temporal Worker running (PID $WORKER_PID)."

# 4. Start FastAPI Backend
echo "🚀 [3/4] Starting FastAPI Backend on http://0.0.0.0:8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "✓ FastAPI Backend running (PID $BACKEND_PID)."

# 5. Start Next.js Frontend Dashboard
echo "💻 [4/4] Starting Next.js Frontend on http://localhost:3000..."
cd frontend && npm run dev &
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
