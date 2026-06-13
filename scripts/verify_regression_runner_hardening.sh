#!/usr/bin/env bash
# Stage 41 -- end-to-end verifier for verification environment hygiene
#             and regression runner hardening.
#
# Scenarios:
#   A) dependency check -- asyncpg importable, required tools present
#   B) runner dry-run / quick mode -- report exists, no ModuleNotFoundError
#   C) full regression -- PASS or PASS_WITH_DOCUMENTED_GAPS only
#   D) operations safety -- verification fields populated
#   E) no secret leak -- scan reports for token-like patterns
#
# Marker: REGRESSION_RUNNER_HARDENING_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh"

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"

echo "### verify_regression_runner_hardening: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }
_skip() { echo "  [SKIP] $1"; }

# ============================================================
echo
echo "=== Scenario A: dependency check ==="

dep_out=$(./scripts/verify_environment_dependencies.sh 2>&1)
echo "$dep_out" | tail -5

if echo "$dep_out" | grep -q "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY: PASS"; then
    _pass "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY"
else
    _fail "VERIFICATION_ENVIRONMENT_DEPENDENCIES_VERIFY"
fi

# asyncpg via resolved PYTHON
if require_python_module "asyncpg"; then
    _pass "asyncpg importable via \$PYTHON ($PYTHON)"
else
    _fail "asyncpg NOT importable via \$PYTHON ($PYTHON)"
fi

# Required shell tools
for cmd in curl jq docker; do
    if command -v "$cmd" >/dev/null 2>&1; then
        _pass "command: $cmd"
    else
        _fail "command: $cmd missing"
    fi
done

# ============================================================
echo
echo "=== Scenario B: regression runner quick mode ==="

if [ ! -f "scripts/run_full_regression.sh" ]; then
    _fail "run_full_regression.sh not found"
else
    _pass "run_full_regression.sh present"
fi

quick_out=$(bash scripts/run_full_regression.sh --quick --json-report 2>&1)
echo "$quick_out" | tail -8

if echo "$quick_out" | grep -qE "FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)"; then
    _pass "quick mode result: PASS or PASS_WITH_DOCUMENTED_GAPS"
else
    _fail "quick mode result: not PASS"
fi

if echo "$quick_out" | grep -q "ModuleNotFoundError\|No module named 'asyncpg'"; then
    _fail "quick mode: ModuleNotFoundError detected"
else
    _pass "quick mode: no ModuleNotFoundError"
fi

if [ -f "source/regression-reports/regression_latest_summary.json" ]; then
    _pass "regression_latest_summary.json written"
else
    _fail "regression_latest_summary.json not found after --json-report"
fi

# ============================================================
echo
echo "=== Scenario C: full regression ==="

full_out=$(bash scripts/run_full_regression.sh --full --json-report --continue-on-fail 2>&1)
# Only print summary lines
echo "$full_out" | grep -E "result_class|FULL_REGRESSION|environment_ready|PASS|FAIL" | tail -15 || true

if echo "$full_out" | grep -qE "FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)"; then
    _pass "FULL_REGRESSION_VERIFY: PASS or PASS_WITH_DOCUMENTED_GAPS"
else
    _fail "FULL_REGRESSION_VERIFY: FAIL (see output above)"
fi

# Ensure no environment_failure in full run
if echo "$full_out" | grep -q "environment_failure"; then
    _fail "full regression: environment_failure detected"
else
    _pass "full regression: no environment_failure"
fi

# Ensure no safety_failure
if echo "$full_out" | grep -q "safety_failure"; then
    _fail "full regression: safety_failure detected"
else
    _pass "full regression: no safety_failure"
fi

# Ensure no regression_failure
if echo "$full_out" | grep -q "regression_failure"; then
    _fail "full regression: regression_failure detected"
else
    _pass "full regression: no regression_failure"
fi

# Allowed gap: check runner's result_class= lines (not raw output which contains
# intermediate PASS_WITH_GAPS from nested scripts like check_migration_down_scripts)
gap_result_count=$(echo "$full_out" | grep -c "result_class=pass_with_gaps" || true)
if [ "$gap_result_count" -gt 1 ]; then
    _fail "multiple pass_with_gaps results; only backup_production_readiness is allowed"
elif [ "$gap_result_count" -eq 1 ]; then
    _pass "pass_with_gaps only for backup_production_readiness (documented)"
fi

# ============================================================
echo
echo "=== Scenario D: operations safety verification fields ==="

safety_body=$(curl -sS -m 10 "${ORCH}/operations/safety" 2>/dev/null || echo '{}')

for field in \
    verification_environment_ready \
    verification_runner_available \
    latest_full_regression_status \
    verification_host_dependency_caveat_closed
do
    if echo "$safety_body" | grep -q "\"${field}\""; then
        _pass "safety field: $field"
    else
        _fail "safety field missing: $field"
    fi
done

# host_dependency_caveat_closed must be true
if echo "$safety_body" | grep -q '"verification_host_dependency_caveat_closed":true'; then
    _pass "verification_host_dependency_caveat_closed=true"
else
    _fail "verification_host_dependency_caveat_closed not true"
fi

# ============================================================
echo
echo "=== Scenario E: no secret leak in reports ==="

secret_clean=1
for report in source/regression-reports/regression_*.json; do
    [ -f "$report" ] || continue
    # Scan for token-like patterns
    if grep -qE '"(DISCORD_BOT_TOKEN|GITHUB_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY|BACKUP_ENCRYPTION_KEY|AUDIT_HMAC_KEY)\s*":\s*"[^"]{8,}' "$report" 2>/dev/null; then
        echo "  WARN: potential secret in $report"
        secret_clean=0
    fi
    if grep -qE '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|discord\.[A-Za-z0-9._-]{20,})' "$report" 2>/dev/null; then
        echo "  WARN: token pattern in $report"
        secret_clean=0
    fi
done
if [ "$secret_clean" = "1" ]; then
    _pass "no secret patterns found in regression reports"
else
    _fail "potential secrets in regression reports"
fi

# ============================================================
echo
echo "passed ${checks}/${total}"
if [ "$checks" -ge "$total" ]; then
    echo "REGRESSION_RUNNER_HARDENING_VERIFY: PASS"
    exit 0
else
    echo "REGRESSION_RUNNER_HARDENING_VERIFY: FAIL"
    exit 1
fi
