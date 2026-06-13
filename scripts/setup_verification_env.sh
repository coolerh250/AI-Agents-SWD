#!/usr/bin/env bash
# Stage 41 -- set up the local verification virtual environment.
#
# Creates (or updates) .venv at the repo root and installs all packages
# required by the project and its verify scripts.
#
# Idempotent: safe to run multiple times.
# Does NOT install global packages.
# Does NOT output any secret values.
# Ends by running verify_environment_dependencies.sh.

set -uo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

echo "### setup_verification_env: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  repo_root: $REPO_ROOT"

step() { echo; echo "=== $1 ==="; }

# ---- 1. Find system Python 3.10+ ----------------------------------------
step "1. Locate system Python"
SYS_PY=""
for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major="${ver%%.*}"
        minor="${ver##*.}"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ] 2>/dev/null; then
            SYS_PY="$candidate"
            echo "  found: $candidate ($ver)"
            break
        fi
    fi
done
if [ -z "$SYS_PY" ]; then
    echo "SETUP_VERIFICATION_ENV: FAIL (no python >= 3.10 found)"
    exit 1
fi

# ---- 2. Create .venv --------------------------------------------------------
step "2. Create .venv"
if [ -d ".venv" ]; then
    echo "  .venv already exists — skipping creation"
else
    "$SYS_PY" -m venv .venv
    echo "  .venv created"
fi

# Resolve the venv python
if [ -f ".venv/bin/python3" ]; then
    VENV_PY=".venv/bin/python3"
    VENV_PIP=".venv/bin/pip"
elif [ -f ".venv/Scripts/python.exe" ]; then
    VENV_PY=".venv/Scripts/python.exe"
    VENV_PIP=".venv/Scripts/pip.exe"
else
    echo "SETUP_VERIFICATION_ENV: FAIL (.venv created but python not found)"
    exit 1
fi
echo "  venv_python: $("$VENV_PY" --version)"

# ---- 3. Upgrade pip ---------------------------------------------------------
step "3. Upgrade pip"
"$VENV_PY" -m pip install --quiet --upgrade pip

# ---- 4. Install project requirements ----------------------------------------
step "4. Install requirements.txt"
if [ -f "requirements.txt" ]; then
    "$VENV_PY" -m pip install --quiet -r requirements.txt
    echo "  requirements.txt: installed"
else
    echo "  requirements.txt: not found (skipping)"
fi

step "5. Install orchestrator requirements"
if [ -f "apps/orchestrator/requirements.txt" ]; then
    "$VENV_PY" -m pip install --quiet -r apps/orchestrator/requirements.txt
    echo "  apps/orchestrator/requirements.txt: installed"
fi

# ---- 5. Verify asyncpg is importable ----------------------------------------
step "6. Verify asyncpg importable"
if "$VENV_PY" -c "import asyncpg" >/dev/null 2>&1; then
    echo "  asyncpg: IMPORTABLE"
else
    echo "SETUP_VERIFICATION_ENV: FAIL (asyncpg not importable after install)"
    exit 1
fi

# ---- 6. Run dependency check ------------------------------------------------
step "7. Run verify_environment_dependencies.sh"
if ./scripts/verify_environment_dependencies.sh; then
    echo "  dependency check: PASS"
else
    echo "  dependency check: FAIL (see output above)"
    echo "SETUP_VERIFICATION_ENV: FAIL (dependency check)"
    exit 1
fi

echo
echo "SETUP_VERIFICATION_ENV: PASS"
