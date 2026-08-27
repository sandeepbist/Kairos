#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=================================================="
echo "  Running Kairos Full Battle Test Suite           "
echo "=================================================="

source "$ROOT_DIR/.venv/bin/activate"
export PYTHONPATH="$ROOT_DIR/backend"
export APP_ENV=test

pytest "$ROOT_DIR/backend/tests/" -v --tb=short
