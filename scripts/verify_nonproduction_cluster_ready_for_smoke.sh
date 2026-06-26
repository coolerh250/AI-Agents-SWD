#!/usr/bin/env bash
# Step 55.1 (Stage 57B) -- combined "cluster ready for runtime smoke" verification.
#
# Chains: tooling -> kind cluster -> bootstrap -> cluster safety -> namespace plan
# -> (re)generate the live runtime smoke report -> Step 55 combined runtime smoke
# -> safety confirmations. NO production namespace/context, NO registry login, NO
# image push, NO ArgoCD sync, NO production action. production_executed stays 0.
#
# Final markers:
#   NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: PASS | BLOCKED | FAIL
#   (Step 55 combined emits NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY)
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
FAILS=0
BLOCKED=0
step() { echo ""; echo "########## $1 ##########"; }

runv() {
  local name="$1"; shift
  local out marker
  out="$("$@" 2>&1)"
  echo "$out" | tail -4
  marker="$(echo "$out" | grep -E "^${name}: " | tail -1)"
  case "$marker" in
    *": PASS") : ;;
    *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> classified BLOCKED" ;;
    *) FAILS=$((FAILS+1)); echo "  -> classified FAIL ($marker)" ;;
  esac
}

step "1. kubernetes tooling"
runv NONPROD_KUBERNETES_TOOLING_VERIFY "$PY" scripts/verify_nonproduction_kubernetes_tooling.py

step "2. kind non-production cluster"
runv KIND_NONPROD_CLUSTER_VERIFY "$PY" scripts/verify_kind_nonproduction_cluster.py

step "3. (re)generate live runtime smoke report"
runv NONPROD_RUNTIME_SMOKE_RUN "$PY" scripts/run_nonproduction_runtime_smoke.py

step "4. cluster bootstrap"
runv NONPROD_CLUSTER_BOOTSTRAP_VERIFY "$PY" scripts/verify_nonproduction_cluster_bootstrap.py

step "5. cluster safety"
runv NONPROD_CLUSTER_SAFETY_VERIFY "$PY" scripts/verify_nonproduction_cluster_safety.py

step "6. namespace plan"
runv NONPROD_NAMESPACE_PLAN_VERIFY "$PY" scripts/verify_nonproduction_namespace_plan.py

step "7. Step 55 combined non-production runtime smoke"
s55="$(bash scripts/verify_nonproduction_kubernetes_runtime_smoke.sh 2>&1)"
echo "$s55" | grep -E "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY|classification" | tail -2
case "$(echo "$s55" | grep -E '^NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 55 PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 55 BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 55 not PASS" ;;
esac

step "8. safety: no production deploy / ArgoCD sync; production_executed=0"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('nonprod_kubernetes_smoke_enabled'), d.get('nonprod_runtime_smoke_production_ready'), d.get('kubernetes_production_deploy_performed'), d.get('argocd_sync_performed'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x")
case "$pa" in
  "True False False False 0") echo "  [PASS] smoke enabled; not production ready; no deploy; no argocd sync; production_executed=0 ($pa)" ;;
  *) echo "  [FAIL] unexpected runtime safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then
  echo "NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: FAIL"
  exit 1
fi
if [ "$BLOCKED" -ne 0 ]; then
  echo "NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: BLOCKED"
  exit 0
fi
echo "NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: PASS"
exit 0
