#!/usr/bin/env bash
# Step 51.2C2 -- combined Migration / Backup / Restore Job baseline verifier.
#
# Chains the 51.1 + 51.2A + 51.2B + 51.2C1 verifiers, renders the four standard
# environments + the restore fixture, then runs the batch inventory / migration
# / backup / restore / policy checkers and the targeted pytest suite.
# NO cluster connection, NO kubectl, NO helm install/upgrade, NO job execution.
#
# Marker: KUBERNETES_BATCH_JOBS_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")" || exit 0

PY="${PYTHON:-python3}"
RENDER_DIR=".runtime/kubernetes-rendered"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51.1 + 51.2A + 51.2B + 51.2C1 storage baseline (chains earlier markers, renders envs)"
bash scripts/verify_kubernetes_storage_baseline.sh | tail -3; need ${PIPESTATUS[0]}

step "2. batch operation inventory verify"
"$PY" scripts/verify_kubernetes_batch_operation_inventory.py | tail -3; need ${PIPESTATUS[0]}

step "3. migration Job verify"
"$PY" scripts/verify_kubernetes_migration_job.py | tail -3; need ${PIPESTATUS[0]}

step "4. backup CronJob verify"
"$PY" scripts/verify_kubernetes_backup_cronjob.py | tail -3; need ${PIPESTATUS[0]}

step "5. restore Job verify (fixture)"
"$PY" scripts/verify_kubernetes_restore_job.py | tail -3; need ${PIPESTATUS[0]}

step "6. batch job policy verify"
"$PY" scripts/verify_kubernetes_batch_job_policy.py | tail -3; need ${PIPESTATUS[0]}

step "7. targeted pytest (batch jobs)"
"$PY" -m pytest -q \
  tests/test_kubernetes_batch_operation_inventory.py \
  tests/test_kubernetes_batch_command_catalog.py \
  tests/test_kubernetes_migration_job.py \
  tests/test_kubernetes_migration_locking.py \
  tests/test_kubernetes_migration_no_hooks.py \
  tests/test_kubernetes_backup_cronjob.py \
  tests/test_kubernetes_backup_target_isolation.py \
  tests/test_kubernetes_backup_secret_references.py \
  tests/test_kubernetes_restore_job_disabled.py \
  tests/test_kubernetes_restore_target_isolation.py \
  tests/test_kubernetes_batch_job_security.py \
  tests/test_kubernetes_batch_job_serviceaccounts.py \
  tests/test_kubernetes_batch_job_network_policy.py \
  tests/test_kubernetes_batch_jobs_environment_rules.py \
  tests/test_kubernetes_batch_jobs_prod_fail_closed.py \
  tests/test_kubernetes_batch_jobs_no_execution.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "8. secret-like pattern scan of rendered output"
if grep -rEi '(password|secret[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,})\s*[:=]\s*[^"'"'"' ]' "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] secret-like value in rendered output"; FAIL=1
else
  echo "  [PASS] no secret-like values in rendered output"
fi

step "9. no rendered files tracked by Git"
if git ls-files --error-unmatch "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output tracked by Git"; FAIL=1
else
  echo "  [PASS] rendered output not tracked"
fi

step "10. no Helm/ArgoCD hook annotations in rendered batch output"
if grep -rnE '(helm\.sh/hook|argocd\.argoproj\.io/hook)' "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] Helm/ArgoCD hook annotation in rendered output"; FAIL=1
else
  echo "  [PASS] no Helm/ArgoCD hook annotations"
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
  echo "KUBERNETES_BATCH_JOBS_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "KUBERNETES_BATCH_JOBS_BASELINE_VERIFY: PASS"
