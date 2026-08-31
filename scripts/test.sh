#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=================================================="
echo "  Running Kairos Full Battle Test Suite           "
echo "=================================================="

# Ensure infrastructure containers are up if down
if ! (echo > /dev/tcp/127.0.0.1/5435) 2>/dev/null; then
  echo "📦 Starting isolated Docker services (PostgreSQL, Redis, Temporal)..."
  if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.dev.yml up -d
  else
    docker compose -f docker-compose.dev.yml up -d
  fi
  echo "⏳ Waiting for database and Temporal to be ready..."
  for i in {1..30}; do
    if (echo > /dev/tcp/127.0.0.1/5435) 2>/dev/null && ((echo > /dev/tcp/127.0.0.1/7234) 2>/dev/null || nc -z localhost 7234 2>/dev/null); then
      break
    fi
    sleep 1
  done
  echo "✓ Infrastructure ready."
fi

# Activate Python environment
if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
fi
export PYTHONPATH="$ROOT_DIR/backend"
export APP_ENV=test

echo "🗄️  Applying database migrations..."
(cd "$ROOT_DIR/backend" && python -m alembic upgrade head)
echo "✓ Schema at head."

pytest "$ROOT_DIR/backend/tests/" -v --tb=short
