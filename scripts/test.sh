#!/usr/bin/env bash
set -e

echo "=================================================="
echo "  Running Kairos Full Battle Test Suite           "
echo "=================================================="

source .venv/bin/activate
export PYTHONPATH=backend
export APP_ENV=test

pytest backend/tests/ -v --tb=short
