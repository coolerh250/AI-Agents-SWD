#!/usr/bin/env bash
# Run the test suite (and optional linters) for the AI Agents SWD Platform.
# Run from the repository root, ideally inside an activated Python venv.
set -euo pipefail

echo "### run_tests start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "python: $(python3 --version 2>&1)"

if ! python3 -c "import pytest, httpx, langgraph" >/dev/null 2>&1; then
  echo "test dependencies missing - installing requirements"
  python3 -m pip install -r requirements.txt
  python3 -m pip install -r apps/orchestrator/requirements.txt
fi

echo
echo "=== pytest ==="
python3 -m pytest -q tests/

echo
echo "=== optional linters ==="
if command -v ruff >/dev/null 2>&1; then
  echo "-- ruff check --"
  ruff check . || true
else
  echo "ruff not installed - skipping"
fi
if command -v black >/dev/null 2>&1; then
  echo "-- black --check --"
  black --check . || true
else
  echo "black not installed - skipping"
fi
if command -v mypy >/dev/null 2>&1; then
  echo "-- mypy --"
  mypy shared/ || true
else
  echo "mypy not installed - skipping"
fi

echo
echo "RUN_TESTS_DONE"
