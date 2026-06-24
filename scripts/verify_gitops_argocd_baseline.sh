#!/usr/bin/env bash
# Step 51.3 -- combined ArgoCD & Environment GitOps baseline verifier.
#
# Chains the Step 51.1 -> 51.2C2 baselines (via the batch-jobs baseline, which
# itself chains the storage / network / security / foundation verifiers and
# renders the four environments), then runs the ArgoCD manifest / environment
# mapping / production isolation checkers and the targeted pytest suite.
# NO cluster connection, NO kubectl, NO argocd CLI, NO sync, NO helm install.
#
# Marker: GITOPS_ARGOCD_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")" || exit 0

PY="${PYTHON:-python3}"
RENDER_DIR=".runtime/kubernetes-rendered"
GITOPS_DIR="infra/gitops"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51.1 -> 51.2C2 baselines (batch-jobs baseline chains all earlier markers + renders envs)"
bash scripts/verify_kubernetes_batch_jobs_baseline.sh | tail -3; need ${PIPESTATUS[0]}

step "2. ArgoCD manifests verify"
"$PY" scripts/verify_argocd_manifests.py | tail -3; need ${PIPESTATUS[0]}

step "3. GitOps environment mapping verify"
"$PY" scripts/verify_gitops_environment_mapping.py | tail -3; need ${PIPESTATUS[0]}

step "4. GitOps production isolation verify"
"$PY" scripts/verify_gitops_production_isolation.py | tail -3; need ${PIPESTATUS[0]}

step "5. targeted pytest (gitops)"
"$PY" -m pytest -q \
  tests/test_gitops_environment_catalog.py \
  tests/test_argocd_project.py \
  tests/test_argocd_applications.py \
  tests/test_argocd_app_of_apps.py \
  tests/test_argocd_sync_disabled.py \
  tests/test_argocd_destination_safety.py \
  tests/test_argocd_source_repo_restriction.py \
  tests/test_argocd_resource_scope.py \
  tests/test_argocd_no_credentials.py \
  tests/test_gitops_environment_mapping.py \
  tests/test_gitops_production_isolation.py \
  tests/test_gitops_no_real_cluster.py \
  tests/test_gitops_no_production_activation.py 2>&1 | tail -4; need ${PIPESTATUS[0]}

step "6. secret / credential pattern scan of GitOps manifests"
if grep -rEi '(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|ssh-rsa |AKIA[0-9A-Z]{16}|(password|token|bearer)[[:space:]]*[:=][[:space:]]*[^ ])' "$GITOPS_DIR/argocd" >/dev/null 2>&1; then
  echo "  [FAIL] credential-like value in GitOps manifests"; FAIL=1
else
  echo "  [PASS] no credential-like values in GitOps manifests"
fi

step "7. no real cluster endpoint / no Secret in GitOps manifests"
# A Secret RESOURCE has `kind: Secret` at column 0 (top-level). The Project's
# namespaceResourceBlacklist legitimately names an INDENTED `kind: Secret` to
# DENY it -- that must not trip this scan, so anchor at line start.
if grep -rnE '^kind:[[:space:]]*Secret' "$GITOPS_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] Secret resource present in GitOps manifests"; FAIL=1
elif grep -rnE 'server:[[:space:]]*https://([0-9]{1,3}\.){3}[0-9]{1,3}' "$GITOPS_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] real IP cluster endpoint in GitOps manifests"; FAIL=1
else
  echo "  [PASS] no Secret resource / real IP endpoint in GitOps manifests"
fi

step "8. no rendered manifests tracked by Git"
if git ls-files --error-unmatch "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output tracked by Git"; FAIL=1
else
  echo "  [PASS] rendered output not tracked"
fi

step "9. no cluster / sync commands in this verifier"
if grep -vE '^[[:space:]]*#' "$0" | grep -vE 'echo ' \
     | grep -nE '(kubectl|argocd|helm)[[:space:]]+(apply|install|upgrade|sync|delete|create)\b' >/dev/null 2>&1; then
  echo "  [FAIL] cluster/sync command present"; FAIL=1
else
  echo "  [PASS] no kubectl/argocd/helm mutation commands"
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "GITOPS_ARGOCD_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "GITOPS_ARGOCD_BASELINE_VERIFY: PASS"
