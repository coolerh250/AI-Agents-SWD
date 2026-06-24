#!/usr/bin/env bash
# Step 51.4 -- combined Kubernetes / Helm / ArgoCD runtime baseline verifier.
#
# Step 51 overall acceptance. Chains the entire 51.1 -> 51.3 baseline (via the
# GitOps baseline, which itself chains storage / network / security / foundation
# and renders the four environments), then runs the read-only runtime visibility
# / admin-console / safety-field checkers. NO cluster, NO kubectl, NO argocd CLI,
# NO helm install/upgrade, NO sync, NO deploy.
#
# Marker: KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY: PASS | FAIL
set -uo pipefail
cd "$(dirname "$0")/.."
source scripts/lib/baseline_run_guard.sh
baseline_run_once "$(basename "$0")" || exit 0

PY="${PYTHON:-python3}"
RENDER_DIR=".runtime/kubernetes-rendered"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAIL=0
step() { echo ""; echo "########## $1 ##########"; }
need() { if [ "$1" -ne 0 ]; then echo "  -> step FAILED"; FAIL=1; fi; }

step "1. Step 51.1 -> 51.3 baselines (GitOps baseline chains all 23 prior markers + renders envs)"
bash scripts/verify_gitops_argocd_baseline.sh | tail -3; need ${PIPESTATUS[0]}

step "2. runtime operations visibility verify (read-only API)"
"$PY" scripts/verify_runtime_operations_visibility.py | tail -3; need ${PIPESTATUS[0]}

step "3. runtime safety fields verify (/operations/safety)"
"$PY" scripts/verify_runtime_safety_fields.py | tail -3; need ${PIPESTATUS[0]}

step "4. admin console runtime baseline verify (read-only view)"
"$PY" scripts/verify_admin_console_runtime_baseline.py | tail -3; need ${PIPESTATUS[0]}

step "5. runtime baseline summary anti-drift (committed == collected)"
"$PY" -m pytest -q tests/test_runtime_baseline_collector.py 2>&1 | tail -3; need ${PIPESTATUS[0]}

step "6. secret / credential scan of runtime baseline summary"
if grep -rEi '(ghp_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16}|kubeconfig|(password|secret[_-]?key|token)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9/+=._-]{8,})' infra/kubernetes/runtime-baseline-summary.yaml >/dev/null 2>&1; then
  echo "  [FAIL] secret-like value in runtime baseline summary"; FAIL=1
else
  echo "  [PASS] no secret-like values in runtime baseline summary"
fi

step "7. no rendered manifests tracked by Git"
if git ls-files --error-unmatch "$RENDER_DIR" >/dev/null 2>&1; then
  echo "  [FAIL] rendered output tracked by Git"; FAIL=1
else
  echo "  [PASS] rendered output not tracked"
fi

step "8. production_executed_true_count == 0"
pe=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('production_executed_true_count'))" 2>/dev/null || echo "unknown")
if [ "$pe" = "0" ]; then
  echo "  [PASS] production_executed_true_count=0"
else
  echo "  [FAIL] production_executed_true_count=$pe"; FAIL=1
fi

step "9. no cluster / sync mutation commands in this verifier"
if grep -vE '^[[:space:]]*#' "$0" | grep -vE 'echo ' \
     | grep -nE '(kubectl|argocd|helm)[[:space:]]+(apply|install|upgrade|sync|delete|create)\b' >/dev/null 2>&1; then
  echo "  [FAIL] cluster/sync mutation command present"; FAIL=1
else
  echo "  [PASS] no kubectl/argocd/helm mutation commands"
fi

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY: FAIL"
  exit 1
fi
echo "KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY: PASS"
