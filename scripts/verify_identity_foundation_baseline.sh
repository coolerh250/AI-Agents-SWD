#!/usr/bin/env bash
# Step 52.4 -- combined identity foundation (Step 52) integrated baseline.
#
# Chains the Step 52.1 + 52.2 + 52.3 baselines, then the identity operations
# visibility / Admin Console identity / identity safety-fields verifiers, the
# targeted tests, and the read-only / no-IdP / no-production-auth / no-mutation
# guards. NO real IdP, NO OIDC network call, NO production auth, NO production
# action.
#
# Marker: IDENTITY_FOUNDATION_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")"

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 52.1 identity / auth boundary baseline"
bash scripts/verify_identity_auth_boundary_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "2. Step 52.2 OIDC disabled-production baseline"
bash scripts/verify_oidc_disabled_production_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "3. Step 52.3 session hardening & role mapping baseline"
bash scripts/verify_session_role_mapping_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "4. identity operations visibility verify"
"$PY" scripts/verify_identity_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "5. Admin Console identity posture verify"
"$PY" scripts/verify_admin_console_identity_posture.py | tail -3; need ${PIPESTATUS[0]}

step "6. identity safety fields verify"
"$PY" scripts/verify_identity_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "7. targeted identity foundation tests"
"$PY" -m pytest -q tests/test_identity_posture_*.py tests/test_identity_operations_*.py \
  tests/test_identity_safety_fields.py tests/test_admin_console_identity_*.py \
  tests/test_identity_foundation_combined_verify.py tests/test_identity_no_mutation_actions.py \
  tests/test_identity_no_secret_leak_runtime.py tests/test_identity_production_not_ready.py \
  2>&1 | tail -4; need ${PIPESTATUS[0]}

step "8. secret / token scan of identity files + posture summary"
if grep -rEi '(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|(client_secret|signing_secret|refresh_token|access_token|id_token|password)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+=._-]{6,})' infra/identity >/dev/null 2>&1; then
  echo "  [FAIL] secret-like value in identity files"; FAIL=1
else
  echo "  [PASS] no secret-like values in identity files"
fi

step "9. no external IdP / discovery / JWKS call, no production auth, GET-only identity API"
if grep -rEn '^\s*(import|from)\s+(requests|httpx|aiohttp|urllib)\b' shared/sdk/identity shared/sdk/identity_posture >/dev/null 2>&1; then
  echo "  [FAIL] identity SDK imports an HTTP client"; FAIL=1
elif grep -rE '@router\.(post|put|patch|delete)' apps/orchestrator/src/identity_posture_api.py >/dev/null 2>&1; then
  echo "  [FAIL] identity API defines a mutation verb"; FAIL=1
else
  echo "  [PASS] no HTTP client import; identity API is GET-only"
fi

step "10. safety posture: identity + production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('identity_production_ready'), d.get('identity_oidc_enabled'), d.get('admin_console_production_auth_enabled'), d.get('production_executed_true_count'))" 2>/dev/null || echo "unknown unknown unknown unknown")
case "$pa" in
  "False False False 0"|"False False None 0")
    echo "  [PASS] identity production not ready; OIDC + production auth disabled; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "IDENTITY_FOUNDATION_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "IDENTITY_FOUNDATION_BASELINE_VERIFY: PASS"
