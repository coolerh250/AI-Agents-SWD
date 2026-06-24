#!/usr/bin/env bash
# Step 52.1 -- combined identity / auth boundary baseline verifier.
#
# Chains the Step 50 Admin Console v1 + Step 51 integrated baseline verifications,
# then the identity boundary / auth-RBAC / identity-audit verifiers and the
# targeted identity tests. NO real OIDC, NO production auth, NO IdP connection,
# NO cluster, NO production action.
#
# Marker: IDENTITY_AUTH_BOUNDARY_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")" || exit 0

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 50 Admin Console v1 operator actions verify"
bash scripts/verify_admin_console_v1_operator_actions.sh 2>&1 | tail -3; need ${PIPESTATUS[0]}

step "2. Step 51 integrated baseline verify"
bash scripts/verify_kubernetes_helm_argocd_baseline.sh 2>&1 | tail -2; need ${PIPESTATUS[0]}

step "3. identity boundary inventory verify"
"$PY" scripts/verify_identity_boundary_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "4. auth / RBAC boundary verify"
"$PY" scripts/verify_auth_rbac_boundary.py | tail -3; need ${PIPESTATUS[0]}

step "5. identity audit boundary verify"
"$PY" scripts/verify_identity_audit_boundary.py | tail -3; need ${PIPESTATUS[0]}

step "6. targeted identity tests"
"$PY" -m pytest -q tests/test_identity_*.py tests/test_auth_rbac_boundary_static.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "7. secret / credential scan of identity files"
if grep -rEi '(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|(client_secret|signing_secret|refresh_token|password)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+=._-]{6,})' infra/identity >/dev/null 2>&1; then
  echo "  [FAIL] secret-like value in identity files"; FAIL=1
else
  echo "  [PASS] no secret-like values in identity files"
fi

step "8. no production auth / OIDC connection / production action"
# Detect a REAL OIDC connection (an actual URL VALUE), not the unconfigured
# prerequisite field names (jwksUri/issuerUrl with configured:false).
if grep -rEi '(jwks_uri|jwksuri|issuer|issuerurl|authorization_endpoint)[[:space:]]*[:=][[:space:]]*https?://' infra/identity >/dev/null 2>&1; then
  echo "  [FAIL] identity files reference a real OIDC endpoint value"; FAIL=1
else
  echo "  [PASS] no real OIDC connection referenced (prerequisites unconfigured only)"
fi
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('admin_console_production_auth_enabled'), d.get('production_executed_true_count'))" 2>/dev/null || echo "unknown unknown")
if [ "$pa" = "False 0" ] || [ "$pa" = "None 0" ]; then
  echo "  [PASS] production auth disabled; production_executed_true_count=0"
else
  echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "IDENTITY_AUTH_BOUNDARY_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "IDENTITY_AUTH_BOUNDARY_BASELINE_VERIFY: PASS"
