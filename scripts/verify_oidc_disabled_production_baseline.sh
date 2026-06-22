#!/usr/bin/env bash
# Step 52.2 -- combined OIDC disabled-production baseline verifier.
#
# Chains the Step 52.1 identity/auth boundary baseline, then the OIDC provider
# abstraction / fail-closed config / no-secret-leak verifiers and the targeted
# OIDC tests. NO real OIDC, NO discovery fetch, NO JWKS fetch, NO IdP connection,
# NO callback, NO token exchange, NO production action, NO full regression.
#
# Marker: OIDC_DISABLED_PRODUCTION_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 52.1 identity / auth boundary baseline"
bash scripts/verify_identity_auth_boundary_baseline.sh 2>&1 | tail -2; need ${PIPESTATUS[0]}

step "2. OIDC provider abstraction verify"
"$PY" scripts/verify_oidc_provider_abstraction.py | tail -3; need ${PIPESTATUS[0]}

step "3. OIDC fail-closed config verify"
"$PY" scripts/verify_oidc_fail_closed_config.py | tail -3; need ${PIPESTATUS[0]}

step "4. OIDC no-secret-leak verify"
"$PY" scripts/verify_oidc_no_secret_leak.py | tail -3; need ${PIPESTATUS[0]}

step "5. targeted OIDC tests"
"$PY" -m pytest -q tests/test_oidc_*.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "6. no OIDC network-call code in identity SDK"
# The abstraction must not import an HTTP client (no discovery/JWKS fetch).
if grep -rEn '^\s*(import|from)\s+(requests|httpx|aiohttp|urllib)\b' shared/sdk/identity >/dev/null 2>&1; then
  echo "  [FAIL] identity SDK imports an HTTP client"; FAIL=1
else
  echo "  [PASS] identity SDK performs no HTTP import (no discovery/JWKS fetch)"
fi

step "7. no real OIDC endpoint value in OIDC files"
if grep -rEi '(issuer|jwks_uri|jwksuri|authorization_endpoint|token_endpoint)[[:space:]]*[:=][[:space:]]*https?://' infra/identity/oidc-*.yaml infra/identity/production-oidc-disabled-config.yaml >/dev/null 2>&1; then
  echo "  [FAIL] OIDC files reference a real endpoint value"; FAIL=1
else
  echo "  [PASS] no real OIDC endpoint value (placeholders only)"
fi

step "8. safety posture: production auth disabled; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('admin_console_production_auth_enabled'), d.get('admin_console_oidc_enabled'), d.get('production_executed_true_count'))" 2>/dev/null || echo "unknown unknown unknown")
case "$pa" in
  "False False 0"|"None None 0"|"False None 0"|"None False 0")
    echo "  [PASS] production auth + OIDC disabled; production_executed_true_count=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "OIDC_DISABLED_PRODUCTION_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "OIDC_DISABLED_PRODUCTION_BASELINE_VERIFY: PASS"
