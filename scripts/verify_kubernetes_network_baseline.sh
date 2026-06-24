#!/usr/bin/env bash
# Step 51.2B -- combined NetworkPolicy & Service Connectivity baseline verifier.
#
# Chains the 51.1 + 51.2A verifiers, renders four envs, then runs the network
# topology / policy / connectivity checkers and the targeted pytest suite.
# NO cluster connection, NO kubectl, NO helm install/upgrade.
#
# Marker: KUBERNETES_NETWORK_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")"

PY="${PYTHON:-python3}"
RENDER_DIR=".runtime/kubernetes-rendered"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51.1 runtime inventory verify"
"$PY" scripts/verify_kubernetes_runtime_inventory.py | tail -2; need ${PIPESTATUS[0]}

step "2. Step 51.1 helm foundation verify (renders four envs)"
bash scripts/verify_helm_foundation.sh | tail -3; need ${PIPESTATUS[0]}

step "3. Step 51.2A workload security verify"
"$PY" scripts/verify_kubernetes_workload_security.py | tail -3; need ${PIPESTATUS[0]}

step "4. Step 51.2A RBAC safety verify"
"$PY" scripts/verify_kubernetes_rbac_safety.py | tail -2; need ${PIPESTATUS[0]}

step "5. network topology verify"
"$PY" scripts/verify_kubernetes_network_topology.py | tail -3; need ${PIPESTATUS[0]}

step "6. NetworkPolicy verify"
"$PY" scripts/verify_kubernetes_network_policy.py | tail -3; need ${PIPESTATUS[0]}

step "7. service connectivity coverage verify"
"$PY" scripts/verify_kubernetes_service_connectivity.py | tail -9; need ${PIPESTATUS[0]}

step "8. targeted pytest (network)"
"$PY" -m pytest -q \
  tests/test_kubernetes_network_connectivity_catalog.py \
  tests/test_kubernetes_default_deny.py \
  tests/test_kubernetes_dns_policy.py \
  tests/test_kubernetes_component_ingress.py \
  tests/test_kubernetes_component_egress.py \
  tests/test_kubernetes_connectivity_coverage.py \
  tests/test_kubernetes_postgres_network_policy.py \
  tests/test_kubernetes_redis_network_policy.py \
  tests/test_kubernetes_external_egress_disabled.py \
  tests/test_kubernetes_ingress_controller_disabled.py \
  tests/test_kubernetes_observability_network_deferred.py \
  tests/test_kubernetes_network_prod_fail_closed.py \
  tests/test_kubernetes_no_unrestricted_cidr.py \
  tests/test_kubernetes_no_external_service_exposure.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "9. secret-like pattern scan of rendered output"
if grep -rEi '(password|secret[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,})\s*[:=]\s*[^"'"'"' ]' "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] secret-like value in rendered output"; FAIL=1
else
  echo "  [PASS] no secret-like values in rendered output"
fi

step "10. render output not tracked by Git"
if git ls-files --error-unmatch "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output tracked by Git"; FAIL=1
else
  echo "  [PASS] rendered output not tracked"
fi

step "11. no cluster mutation commands in this verifier"
if grep -vE '^[[:space:]]*#' "$0" | grep -vE 'echo ' \
     | grep -nE '(kubectl|helm)[[:space:]]+(apply|install|upgrade|delete|create)\b' >/dev/null 2>&1; then
  echo "  [FAIL] cluster mutation command present"; FAIL=1
else
  echo "  [PASS] no kubectl/helm install/upgrade/apply"
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "KUBERNETES_NETWORK_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "KUBERNETES_NETWORK_BASELINE_VERIFY: PASS"
