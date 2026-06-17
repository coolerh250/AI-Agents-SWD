#!/usr/bin/env bash
# Step 51.2C1 -- combined Storage Ownership & Data Lifecycle baseline verifier.
#
# Chains the 51.1 + 51.2A + 51.2B verifiers, renders four envs, then runs the
# storage inventory / data lifecycle / storage manifest checkers and the
# targeted pytest suite. NO cluster connection, NO kubectl, NO helm install.
#
# Marker: KUBERNETES_STORAGE_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
RENDER_DIR=".runtime/kubernetes-rendered"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51.1 runtime inventory verify"
"$PY" scripts/verify_kubernetes_runtime_inventory.py | tail -2; need ${PIPESTATUS[0]}

step "2. Step 51.1 helm foundation verify (renders four envs)"
bash scripts/verify_helm_foundation.sh | tail -3; need ${PIPESTATUS[0]}

step "3. Step 51.2A security/RBAC baseline verify"
bash scripts/verify_kubernetes_security_rbac_baseline.sh | tail -3; need ${PIPESTATUS[0]}

step "4. Step 51.2B network baseline verify"
bash scripts/verify_kubernetes_network_baseline.sh | tail -3; need ${PIPESTATUS[0]}

step "5. storage inventory verify"
"$PY" scripts/verify_kubernetes_storage_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "6. data lifecycle verify"
"$PY" scripts/verify_kubernetes_data_lifecycle.py | tail -3; need ${PIPESTATUS[0]}

step "7. storage manifest verify (rendered four envs)"
"$PY" scripts/verify_kubernetes_storage_manifest.py | tail -4; need ${PIPESTATUS[0]}

step "8. targeted pytest (storage)"
"$PY" -m pytest -q \
  tests/test_kubernetes_storage_consumer_inventory.py \
  tests/test_kubernetes_storage_ownership_catalog.py \
  tests/test_kubernetes_data_lifecycle.py \
  tests/test_kubernetes_postgres_persistence.py \
  tests/test_kubernetes_redis_persistence.py \
  tests/test_kubernetes_workspace_storage.py \
  tests/test_kubernetes_artifact_storage.py \
  tests/test_kubernetes_pvc_template.py \
  tests/test_kubernetes_storage_access_modes.py \
  tests/test_kubernetes_storage_mount_safety.py \
  tests/test_kubernetes_storage_environment_rules.py \
  tests/test_kubernetes_storage_prod_fail_closed.py \
  tests/test_kubernetes_no_hostpath_storage.py \
  tests/test_kubernetes_no_fake_rwx.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

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

step "11. no PV / StorageClass / hostPath / NFS in rendered output"
if grep -rnE 'kind:[[:space:]]*(PersistentVolume|StorageClass)\b' "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output contains a PersistentVolume/StorageClass"; FAIL=1
elif grep -rnE '(hostPath:|[[:space:]]nfs:|[[:space:]]csi:)' "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output contains hostPath/NFS/CSI volume"; FAIL=1
else
  echo "  [PASS] no PV/StorageClass/hostPath/NFS/CSI in rendered output"
fi

step "12. no cluster mutation commands in this verifier"
if grep -vE '^[[:space:]]*#' "$0" | grep -vE 'echo ' \
     | grep -nE '(kubectl|helm)[[:space:]]+(apply|install|upgrade|delete|create)\b' >/dev/null 2>&1; then
  echo "  [FAIL] cluster mutation command present"; FAIL=1
else
  echo "  [PASS] no kubectl/helm install/upgrade/apply"
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "KUBERNETES_STORAGE_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "KUBERNETES_STORAGE_BASELINE_VERIFY: PASS"
