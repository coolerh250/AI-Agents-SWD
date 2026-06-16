#!/usr/bin/env bash
# Step 51.2A -- combined Workload Security & RBAC Safety baseline verifier.
#
# Orchestrates: Step 51.1 inventory + helm-foundation verifies, a four-env render
# into a gitignored runtime dir, the workload-security checker, the RBAC checker,
# and the targeted pytest suite. NO cluster connection, NO kubectl, NO helm
# install/upgrade. Production execution must remain false.
#
# Marker: KUBERNETES_SECURITY_RBAC_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
RENDER_DIR=".runtime/kubernetes-rendered"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. prerequisites (no cluster tools invoked)"
if command -v helm >/dev/null 2>&1 || command -v docker >/dev/null 2>&1; then
  echo "  helm/docker render tooling available"
else
  echo "  [FAIL] neither helm nor docker available to render"; FAIL=1
fi

step "2. Step 51.1 runtime inventory verify"
"$PY" scripts/verify_kubernetes_runtime_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "3. Step 51.1 helm foundation verify (renders four envs to $RENDER_DIR)"
bash scripts/verify_helm_foundation.sh | tail -4; need ${PIPESTATUS[0]}

step "4. workload security checker"
"$PY" scripts/verify_kubernetes_workload_security.py; need $?

step "5. RBAC safety checker"
"$PY" scripts/verify_kubernetes_rbac_safety.py | tail -8; need ${PIPESTATUS[0]}

step "6. targeted pytest"
"$PY" -m pytest -q \
  tests/test_kubernetes_workload_security_inventory.py \
  tests/test_kubernetes_pod_security_context.py \
  tests/test_kubernetes_container_security_context.py \
  tests/test_kubernetes_readonly_rootfs.py \
  tests/test_kubernetes_writable_path_model.py \
  tests/test_kubernetes_serviceaccount_safety.py \
  tests/test_kubernetes_rbac_safety.py \
  tests/test_kubernetes_resource_probe_completeness.py \
  tests/test_kubernetes_dangerous_features_absent.py \
  tests/test_kubernetes_security_prod_fail_closed.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "7. render output safety"
if git ls-files --error-unmatch "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output is tracked by Git"; FAIL=1
else
  echo "  [PASS] rendered output not tracked by Git"
fi

step "8. no cluster mutation commands in this verifier"
if grep -vE '^[[:space:]]*#' "$0" | grep -vE 'echo ' \
     | grep -nE '(kubectl|helm)[[:space:]]+(apply|install|upgrade|delete|create)\b' >/dev/null 2>&1; then
  echo "  [FAIL] cluster mutation command present"; FAIL=1
else
  echo "  [PASS] no kubectl/helm install/upgrade/apply"
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "KUBERNETES_SECURITY_RBAC_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "KUBERNETES_SECURITY_RBAC_BASELINE_VERIFY: PASS"
