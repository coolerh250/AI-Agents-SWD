#!/usr/bin/env bash
# Step 52.3 -- combined session hardening & role mapping baseline verifier.
#
# Chains the Step 52.1 + Step 52.2 baselines, then the session hardening / role
# mapping / unknown user / break-glass / authorization model / audit enrichment
# verifiers and the targeted tests. NO real IdP, NO OIDC network call, NO
# production auth, NO runtime write endpoint, NO production action, NO full
# regression.
#
# Marker: SESSION_ROLE_MAPPING_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 52.1 identity / auth boundary baseline"
bash scripts/verify_identity_auth_boundary_baseline.sh 2>&1 | tail -2; need ${PIPESTATUS[0]}

step "2. Step 52.2 OIDC disabled-production baseline"
bash scripts/verify_oidc_disabled_production_baseline.sh 2>&1 | tail -2; need ${PIPESTATUS[0]}

step "3. session hardening verify"
"$PY" scripts/verify_session_hardening.py | tail -3; need ${PIPESTATUS[0]}

step "4. role mapping policy verify"
"$PY" scripts/verify_role_mapping_policy.py | tail -3; need ${PIPESTATUS[0]}

step "5. unknown user policy verify"
"$PY" scripts/verify_unknown_user_policy.py | tail -3; need ${PIPESTATUS[0]}

step "6. break-glass model verify"
"$PY" scripts/verify_break_glass_model.py | tail -3; need ${PIPESTATUS[0]}

step "7. identity authorization model verify"
"$PY" scripts/verify_identity_authorization_model.py | tail -3; need ${PIPESTATUS[0]}

step "8. identity audit enrichment verify"
"$PY" scripts/verify_identity_audit_enrichment.py | tail -3; need ${PIPESTATUS[0]}

step "9. session cleanup verify"
"$PY" scripts/verify_session_cleanup.py | tail -3; need ${PIPESTATUS[0]}

step "10. targeted Step 52.3 tests"
"$PY" -m pytest -q \
  tests/test_session_hardening_catalog.py tests/test_session_cleanup_model.py \
  tests/test_session_concurrency_policy.py tests/test_forced_logout_model.py \
  tests/test_session_key_rotation_model.py tests/test_role_mapping_engine.py \
  tests/test_role_mapping_policy.py tests/test_role_mapping_safe_fixture.py \
  tests/test_role_mapping_unsafe_fixtures.py tests/test_unknown_user_policy.py \
  tests/test_break_glass_model.py tests/test_identity_authorization_decision_model.py \
  tests/test_identity_audit_enrichment.py tests/test_identity_runtime_config_fail_closed.py \
  tests/test_session_role_mapping_no_secret_leak.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "11. secret / credential scan of identity files"
if grep -rEi '(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.|(client_secret|signing_secret|refresh_token|access_token|id_token|password)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+=._-]{6,})' infra/identity >/dev/null 2>&1; then
  echo "  [FAIL] secret-like value in identity files"; FAIL=1
else
  echo "  [PASS] no secret-like values in identity files"
fi

step "12. no real OIDC endpoint value / no network-call code"
if grep -rEi '(issuer|jwks_uri|jwksuri|authorization_endpoint|token_endpoint)[[:space:]]*[:=][[:space:]]*https?://' infra/identity >/dev/null 2>&1; then
  echo "  [FAIL] identity files reference a real OIDC endpoint value"; FAIL=1
elif grep -rEn '^\s*(import|from)\s+(requests|httpx|aiohttp|urllib)\b' shared/sdk/identity >/dev/null 2>&1; then
  echo "  [FAIL] identity SDK imports an HTTP client"; FAIL=1
else
  echo "  [PASS] no real OIDC endpoint value; identity SDK performs no HTTP import"
fi

step "13. safety posture: production auth disabled; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('admin_console_production_auth_enabled'), d.get('admin_console_oidc_enabled'), d.get('production_executed_true_count'))" 2>/dev/null || echo "unknown unknown unknown")
case "$pa" in
  "False False 0"|"None None 0"|"False None 0"|"None False 0")
    echo "  [PASS] production auth + OIDC disabled; production_executed_true_count=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "SESSION_ROLE_MAPPING_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "SESSION_ROLE_MAPPING_BASELINE_VERIFY: PASS"
