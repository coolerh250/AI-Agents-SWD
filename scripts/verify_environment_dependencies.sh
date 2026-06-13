#!/usr/bin/env bash
# Stage 41 -- verify all verification environment dependencies are present.
#
# Mode A (project venv):   .venv/bin/python3 + asyncpg + full SDK
# Mode C (pure shell):     curl, jq, docker, docker compose, psql (via docker)
#
# Outputs VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS if everything
# needed for regression is available. Never auto-installs packages.

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh"

echo "### verify_environment_dependencies: $(date '+%Y-%m-%d %H:%M:%S %Z')"

fail_count=0
warn_count=0

_pass() { echo "  [PASS] $1"; }
_fail() { echo "  [FAIL] $1"; fail_count=$((fail_count + 1)); }
_warn() { echo "  [WARN] $1"; warn_count=$((warn_count + 1)); }

echo
echo "=== Python environment ==="

# .venv present
if [ -n "$VENV_PYTHON" ] && [ -f "$VENV_PYTHON" ]; then
    _pass ".venv python: $VENV_PYTHON"
    echo "       $($VENV_PYTHON --version 2>&1)"
else
    _fail ".venv python not found"
    echo "       Run: ./scripts/setup_verification_env.sh"
    echo "       Expected: ${REPO_ROOT}/.venv/bin/python3"
fi

# Required Python modules
for mod in asyncpg httpx pydantic redis pytest langgraph prometheus_client; do
    if require_python_module "$mod"; then
        _pass "import $mod"
    else
        _fail "import $mod (not importable via $PYTHON)"
        echo "       Remediation: run ./scripts/setup_verification_env.sh"
    fi
done

# yaml (PyYAML or ruamel.yaml)
if require_python_module "yaml"; then
    _pass "import yaml"
else
    _warn "import yaml (not critical — PyYAML not installed)"
fi

echo
echo "=== Shell tools ==="

for cmd in curl jq docker; do
    if command -v "$cmd" >/dev/null 2>&1; then
        _pass "command: $cmd"
    else
        _fail "command: $cmd (not in PATH)"
    fi
done

# docker compose (v2 plugin syntax)
if docker compose version >/dev/null 2>&1; then
    _pass "docker compose (v2)"
elif command -v docker-compose >/dev/null 2>&1; then
    _pass "docker-compose (v1 fallback)"
else
    _fail "docker compose not available"
fi

# psql via docker (acceptable in container-only environments)
COMPOSE_CMD="docker compose -f ${REPO_ROOT}/infra/docker-compose/docker-compose.yml"
if command -v psql >/dev/null 2>&1; then
    _pass "psql (host)"
elif $COMPOSE_CMD exec -T postgres psql --version >/dev/null 2>&1; then
    _pass "psql (via docker compose postgres service)"
else
    _warn "psql not available on host or via docker — DB-dependent scripts may fail"
fi

echo
echo "=== asyncpg caveat closure ==="

# The key caveat from Stage 39: asyncpg ModuleNotFoundError on host python.
# We check that it's importable via the RESOLVED $PYTHON (venv), not bare host python3.
if require_python_module "asyncpg"; then
    _pass "asyncpg importable via \$PYTHON ($PYTHON)"
    # Check if host python3 ALSO has asyncpg (leak detection, not a failure)
    if detect_host_dependency_leak; then
        _warn "asyncpg found on host python3 as well (unusual — check if intentional)"
    else
        _pass "asyncpg NOT on host python3 (correctly isolated to venv)"
    fi
else
    _fail "asyncpg not importable via \$PYTHON"
    echo "       HOST_DEPENDENCY_CAVEAT: OPEN"
    echo "       Remediation: ./scripts/setup_verification_env.sh"
fi

echo
echo "=== shared.sdk imports ==="

for mod in \
    "shared.sdk.audit_integrity" \
    "shared.sdk.approval_policy" \
    "shared.sdk.llm_budget" \
    "shared.sdk.incidents.alert_store" \
    "shared.sdk.notifications.real_delivery_policy"
do
    # Run from repo root with sys.path including repo root
    if (cd "${REPO_ROOT}" && "$PYTHON" -c "import sys; sys.path.insert(0,''); import ${mod}" >/dev/null 2>&1); then
        _pass "import $mod"
    else
        _fail "import $mod (check asyncpg + project path)"
    fi
done

echo
echo "=== Verification scripts present ==="

for script in \
    scripts/run_full_regression.sh \
    scripts/verify_environment_dependencies.sh \
    scripts/setup_verification_env.sh \
    scripts/lib/verify_env.sh \
    scripts/verify_regression_runner_hardening.sh
do
    if [ -f "${REPO_ROOT}/${script}" ]; then
        _pass "$script"
    else
        _fail "$script (not found)"
    fi
done

echo
if [ "$fail_count" -eq 0 ]; then
    if [ "$warn_count" -gt 0 ]; then
        echo "  $warn_count warning(s) — non-critical"
    fi
    echo "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS"
    exit 0
else
    echo "  FAIL: $fail_count dependency failure(s)"
    echo "  Remediation: ./scripts/setup_verification_env.sh"
    echo "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: FAIL"
    exit 1
fi
