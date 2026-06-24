#!/usr/bin/env bash
# Step 53 -- combined secret management foundation baseline.
#
# Chains the Step 51 + Step 52 integrated baselines, then the secret inventory /
# reference / store / no-inline / rotation / redaction / operations / Admin
# Console / safety verifiers and the targeted tests. NO secret store connection,
# NO secret value, NO read/write/rotate endpoint, NO production auth/action, NO
# full regression.
#
# Marker: SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")" || exit 0

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51 Kubernetes/Helm/ArgoCD integrated baseline"
bash scripts/verify_kubernetes_helm_argocd_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "2. Step 52 identity foundation integrated baseline"
bash scripts/verify_identity_foundation_baseline.sh 2>&1 | tail -1; need ${PIPESTATUS[0]}

step "3. secret inventory verify"
"$PY" scripts/verify_secret_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "4. secret reference schema verify"
"$PY" scripts/verify_secret_reference_schema.py | tail -3; need ${PIPESTATUS[0]}

step "5. secret store abstraction verify"
"$PY" scripts/verify_secret_store_abstraction.py | tail -3; need ${PIPESTATUS[0]}

step "6. no inline secret values verify"
"$PY" scripts/verify_secret_no_inline_values.py | tail -3; need ${PIPESTATUS[0]}

step "7. secret rotation model verify"
"$PY" scripts/verify_secret_rotation_model.py | tail -3; need ${PIPESTATUS[0]}

step "8. secret redaction policy verify"
"$PY" scripts/verify_secret_redaction_policy.py | tail -3; need ${PIPESTATUS[0]}

step "9. secret operations visibility verify"
"$PY" scripts/verify_secret_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "10. Admin Console secret posture verify"
"$PY" scripts/verify_admin_console_secret_posture.py | tail -3; need ${PIPESTATUS[0]}

step "11. secret safety fields verify"
"$PY" scripts/verify_secret_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "12. targeted secret foundation tests"
"$PY" -m pytest -q tests/test_secret_*.py tests/test_production_secret_store_disabled_config.py \
  tests/test_identity_secret_references.py tests/test_runtime_secret_references.py \
  tests/test_backup_secret_references.py tests/test_gitops_secret_references.py \
  tests/test_admin_console_secret_posture.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "13. safety posture: secret foundation + production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('secrets_production_ready'), d.get('secrets_production_store_enabled'), d.get('secrets_read_value_enabled'), d.get('secrets_inline_values_detected'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x")
case "$pa" in
  "False False False False 0")
    echo "  [PASS] secret production not ready; store disabled; no value read; no inline; production_executed=0 ($pa)" ;;
  *)
    echo "  [FAIL] unexpected safety posture: $pa"; FAIL=1 ;;
esac

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY: PASS"
