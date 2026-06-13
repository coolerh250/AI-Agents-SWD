#!/usr/bin/env bash
# scripts/lib/verify_env.sh — Stage 41: shared verification environment helper.
#
# Source this file at the top of any verify / regression script that needs
# the project Python (asyncpg, shared.sdk.*) or common helper functions:
#
#   source "$(dirname "$0")/lib/verify_env.sh"       # from scripts/
#   source "$(cd "$(dirname "$0")/.." && pwd)/scripts/lib/verify_env.sh"  # from other dirs
#
# After sourcing:
#   $REPO_ROOT     -- absolute repo root path
#   $VENV_PYTHON   -- path to venv python3 (or "" if no venv)
#   $PYTHON        -- resolved python3 to use (venv if available, else system)
#   PATH           -- .venv/bin prepended if venv exists (makes bare python3 resolve to venv)
#
# Helper functions (all safe under set -e):
#   require_venv_python          -- exits 1 with message if no .venv
#   require_command CMD          -- exits 1 if CMD not found
#   require_python_module MOD    -- exits 1 if module not importable
#   run_python ARGS...           -- runs $PYTHON with args
#   run_in_service SVC CMD...    -- docker compose exec -T SVC CMD...
#   print_verify_header SCRIPT   -- prints standardised header
#   print_verify_result MARKER   -- prints PASS/FAIL marker line
#   fail_with_marker MARKER MSG  -- prints failure + exits 1
#   skip_with_marker MARKER MSG  -- prints skip line + returns 0
#   detect_host_dependency_leak  -- checks if asyncpg importable without venv
#
# Safety: does NOT auto-install packages. Does NOT print secret values.
# This file must tolerate being sourced under set -e and set -uo pipefail.

# ---- locate repo root -------------------------------------------------------
_VERIFY_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${_VERIFY_ENV_DIR}/../.." && pwd)"

# ---- resolve venv python -----------------------------------------------------
if [ -f "${REPO_ROOT}/.venv/bin/python3" ]; then
    VENV_PYTHON="${REPO_ROOT}/.venv/bin/python3"
elif [ -f "${REPO_ROOT}/.venv/Scripts/python.exe" ]; then
    # Windows Git Bash / WSL hybrid
    VENV_PYTHON="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [ -f "${REPO_ROOT}/.venv/Scripts/python3.exe" ]; then
    VENV_PYTHON="${REPO_ROOT}/.venv/Scripts/python3.exe"
else
    VENV_PYTHON=""
fi

if [ -n "$VENV_PYTHON" ]; then
    # Prepend venv/bin so bare "python3" calls resolve to the venv interpreter.
    _VENV_BIN="$(dirname "$VENV_PYTHON")"
    case ":$PATH:" in
        *":${_VENV_BIN}:"*) : ;;  # already present
        *) export PATH="${_VENV_BIN}:${PATH}" ;;
    esac
    export PYTHON="$VENV_PYTHON"
else
    export PYTHON="${PYTHON:-python3}"
fi

# ---- helper functions --------------------------------------------------------

# Exits 1 with a clear message if no .venv is set up.
require_venv_python() {
    if [ -z "$VENV_PYTHON" ]; then
        echo "ERROR: no .venv found at ${REPO_ROOT}/.venv"
        echo "  Run: ./scripts/setup_verification_env.sh"
        echo "  Expected: ${REPO_ROOT}/.venv/bin/python3"
        return 1
    fi
}

# Exits 1 if the given command is not available in PATH.
require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd"
        return 1
    fi
}

# Checks whether a Python module can be imported by the resolved $PYTHON.
# Returns 0 if importable, 1 otherwise (does NOT exit).
require_python_module() {
    local module="$1"
    "$PYTHON" -c "import $module" >/dev/null 2>&1
}

# Runs $PYTHON with the given arguments. Forwards exit code.
run_python() {
    "$PYTHON" "$@"
}

# Runs a command inside a docker compose service container.
# Usage: run_in_service <service> <cmd> [args...]
run_in_service() {
    local svc="$1"
    shift
    docker compose -f "${REPO_ROOT}/infra/docker-compose/docker-compose.yml" \
        exec -T "$svc" "$@"
}

# Prints a standardised verify script header.
print_verify_header() {
    local script_name="$1"
    echo "### ${script_name}: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    if [ -n "$VENV_PYTHON" ]; then
        echo "  python: $PYTHON (venv)"
    else
        echo "  python: $PYTHON (system — WARNING: no .venv found)"
    fi
}

# Prints a result marker line.
print_verify_result() {
    local marker="$1"
    echo
    echo "$marker"
}

# Prints FAIL marker and exits 1.
fail_with_marker() {
    local marker="$1"
    local msg="${2:-}"
    echo
    [ -n "$msg" ] && echo "  REASON: $msg"
    echo "${marker}: FAIL"
    return 1
}

# Prints SKIP marker and returns 0.
skip_with_marker() {
    local marker="$1"
    local msg="${2:-}"
    [ -n "$msg" ] && echo "  SKIP: $msg"
    echo "${marker}: SKIPPED-PASS"
}

# Checks whether asyncpg is importable from the SYSTEM python3 (not the venv).
# Returns 0 if asyncpg is leaking onto the host, 1 if properly isolated.
detect_host_dependency_leak() {
    if command -v python3 >/dev/null 2>&1; then
        local sys_py
        sys_py="$(command -v python3)"
        # Only flag as a leak if it's NOT the venv python.
        if [ "$sys_py" != "$VENV_PYTHON" ]; then
            if "$sys_py" -c "import asyncpg" >/dev/null 2>&1; then
                echo "  WARN: asyncpg is importable on host python ($sys_py)"
                echo "  This is unusual — asyncpg should only live in .venv or containers."
                return 0  # leak detected
            fi
        fi
    fi
    return 1  # no leak (expected)
}

# Redacts values from environment for logging. Prints key=*** for each key.
redact_env_values() {
    for key in "$@"; do
        local val
        val="${!key:-}"
        if [ -n "$val" ]; then
            echo "  $key=***REDACTED***"
        else
            echo "  $key=(not set)"
        fi
    done
}

export REPO_ROOT VENV_PYTHON PYTHON
