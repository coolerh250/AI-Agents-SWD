#!/usr/bin/env bash
# Step 58 (Stage 60A) -- combined Admin Console v2 operational metrics baseline.
#
# Generates the metrics snapshot, runs the Step 52-57 baselines (via the deduped
# Step 57 combined) + the tenant strategy-note verifier, the 6 metrics verifiers, the
# targeted tests, and the safety posture check. Read-only: NO ArgoCD sync, NO
# Kubernetes mutation, NO GitHub write, NO external send, NO production action.
#
# Final marker: ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY: PASS | BLOCKED | FAIL
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
  echo "$out" | tail -3
  marker="$(echo "$out" | grep -E "^${name}: " | tail -1)"
  case "$marker" in
    *": PASS") : ;;
    *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> classified BLOCKED" ;;
    *) FAILS=$((FAILS+1)); echo "  -> classified FAIL ($marker)" ;;
  esac
}

step "0. generate operational metrics snapshot"
runv OPERATIONAL_METRICS_SNAPSHOT_RUN "$PY" scripts/generate_operational_metrics_snapshot.py

step "1-6. Step 52-57 baselines (deduped via Step 57 combined)"
s57="$(bash scripts/verify_multi_project_delivery_dispatch_baseline.sh 2>&1)"
echo "$s57" | grep -E "MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY|classification" | tail -2
case "$(echo "$s57" | grep -E '^MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY: ' | tail -1)" in
  *": PASS") echo "  -> Step 52-57 PASS" ;;
  *BLOCKED*) BLOCKED=$((BLOCKED+1)); echo "  -> Step 57 chain BLOCKED" ;;
  *) FAILS=$((FAILS+1)); echo "  -> Step 52-57 not PASS" ;;
esac

step "7. tenant strategy note";        runv TENANT_WORKSPACE_STRATEGY_NOTE_VERIFY "$PY" scripts/verify_tenant_workspace_strategy_note.py
step "8. metrics model";               runv OPERATIONAL_METRICS_MODEL_VERIFY "$PY" scripts/verify_operational_metrics_model.py
step "9. metrics sources";             runv OPERATIONAL_METRICS_SOURCES_VERIFY "$PY" scripts/verify_operational_metrics_sources.py
step "10. metrics snapshot";           runv OPERATIONAL_METRICS_SNAPSHOT_VERIFY "$PY" scripts/verify_operational_metrics_snapshot.py
step "11. metrics API";                runv OPERATIONAL_METRICS_API_VERIFY "$PY" scripts/verify_operational_metrics_api.py
step "12. Admin Console v2";           runv ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_VERIFY "$PY" scripts/verify_admin_console_v2_operational_metrics.py
step "13. safety fields (live)";       runv OPERATIONAL_METRICS_SAFETY_FIELDS_VERIFY "$PY" scripts/verify_operational_metrics_safety_fields.py

step "14. targeted Step 58 tests"
"$PY" -m pytest -q \
  tests/test_operational_metrics_model.py \
  tests/test_operational_metrics_sources.py \
  tests/test_operational_metrics_aggregator.py \
  tests/test_operational_metrics_snapshot.py \
  tests/test_operational_metrics_api.py \
  tests/test_operational_metrics_api_read_only.py \
  tests/test_admin_console_v2_operational_metrics.py \
  tests/test_operational_metrics_safety_fields.py \
  tests/test_operational_metrics_no_production_actions.py \
  tests/test_operational_metrics_redaction.py 2>&1 | tail -4
if [ "${PIPESTATUS[0]}" -ne 0 ]; then echo "  -> tests FAILED"; FAILS=$((FAILS+1)); fi

step "15. safety posture: metrics fields + no production action"
pa=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null | "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d.get('admin_console_v2_metrics_enabled'), d.get('operational_metrics_production_action_enabled'), d.get('operational_metrics_gitops_sync_enabled'), d.get('operational_metrics_production_ready'), d.get('production_executed_true_count'))" 2>/dev/null || echo "x x x x x")
case "$pa" in
  "True False False False 0") echo "  [PASS] metrics enabled; no production action/sync; not production ready; production_executed=0 ($pa)" ;;
  *) echo "  [FAIL] unexpected metrics safety posture: $pa"; FAILS=$((FAILS+1)) ;;
esac

echo ""
echo "=== classification: FAILS=$FAILS BLOCKED=$BLOCKED ==="
if [ "$FAILS" -ne 0 ]; then echo "ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY: FAIL"; exit 1; fi
if [ "$BLOCKED" -ne 0 ]; then echo "ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY: BLOCKED"; exit 0; fi
echo "ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY: PASS"
exit 0
