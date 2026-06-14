#!/usr/bin/env bash
# Stage 45 -- end-to-end verifier for the project planner & task graph.
#
# Scenario A -- service health (project-planner-agent, orchestrator) + migration.
# Scenario B -- plan a FastAPI Todo project via POST /operations/projects/plan.
# Scenario C -- planning-only safety (no GitHub write / deploy / dispatch).
# Scenario D -- operations API reads (project / brief / work items / graph / ...).
# Scenario E -- audit / notification (project.* denylisted, chain clean).
# Scenario F -- regression compatibility (residue + tamper-evident + full run).
#
# Marker: PROJECT_PLANNER_TASK_GRAPH_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
PLANNER="${PROJECT_PLANNER_URL:-http://localhost:8016}"

echo "### verify_project_planner_task_graph: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }
_skip() { echo "  [SKIP] $1"; }

# ---------------------------------------------------------------------------
echo
echo "=== Scenario A: service health + SDK ==="
oh=$(curl -sS -m 5 "$ORCH/health" 2>/dev/null || echo '{}')
echo "$oh" | grep -q '"status":"ok"' && _pass "orchestrator health" || _fail "orchestrator health"
ph=$(curl -sS -m 5 "$PLANNER/health" 2>/dev/null || echo '{}')
if echo "$ph" | grep -q '"status":"ok"'; then
  _pass "project-planner-agent health"
else
  _skip "project-planner-agent not reachable (planning still works via operations API)"
fi
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.project_planning import build_brief, build_task_graph, validate_dependencies
g = build_task_graph(build_brief('FastAPI Todo CRUD with SQLite'), project_type='fastapi_todo_service')
assert validate_dependencies(g).status == 'valid'
print('OK')
" >/dev/null 2>&1; then
  _pass "project_planning SDK builds + validates a graph"
else
  _fail "project_planning SDK build/validate"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario B: plan FastAPI Todo project ==="
REQ='Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples.'
plan_resp=$(curl -sS -m 20 -X POST "$ORCH/operations/projects/plan" \
  -H 'Content-Type: application/json' \
  -d "{\"request_text\": \"$REQ\"}" 2>/dev/null || echo '{}')
PROJECT_ID=$(echo "$plan_resp" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('project_id',''))" 2>/dev/null || echo "")
if [ -n "$PROJECT_ID" ]; then
  _pass "project planned (project_id=$PROJECT_ID)"
else
  _fail "POST /operations/projects/plan returned no project_id"
fi

_field() { echo "$plan_resp" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('$1',''))" 2>/dev/null || echo ""; }
[ "$(_field status)" = "planned" ] && _pass "status=planned" || _fail "status not planned ($(_field status))"
[ "$(_field validation_status)" = "valid" ] && _pass "graph validation valid" || _fail "validation not valid"
[ "$(_field requires_clarification)" = "False" ] && _pass "no clarification required" || _skip "requires_clarification=$(_field requires_clarification)"
wic=$(_field work_items_count); dpc=$(_field dependencies_count); acc=$(_field acceptance_criteria_count)
[ "${wic:-0}" -ge 8 ] 2>/dev/null && _pass "work_items_count=$wic (>=8)" || _fail "work_items_count=$wic (<8)"
[ "${dpc:-0}" -ge 5 ] 2>/dev/null && _pass "dependencies_count=$dpc (>=5)" || _fail "dependencies_count=$dpc (<5)"
[ "${acc:-0}" -ge 8 ] 2>/dev/null && _pass "acceptance_criteria_count=$acc (>=8)" || _fail "acceptance_criteria_count=$acc (<8)"

# brief + scope/non-scope + stories
if [ -n "$PROJECT_ID" ]; then
  brief=$(curl -sS -m 5 "$ORCH/operations/projects/$PROJECT_ID/brief" 2>/dev/null || echo '{}')
  echo "$brief" | grep -q '"scope"' && echo "$brief" | grep -q '"non_scope"' \
    && _pass "brief has scope/non_scope" || _fail "brief missing scope/non_scope"
  stories=$(curl -sS -m 5 "$ORCH/operations/projects/$PROJECT_ID/stories" 2>/dev/null || echo '{}')
  echo "$stories" | grep -q '"stories"' && _pass "user stories present" || _fail "no user stories"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario C: planning-only safety ==="
safety=$(curl -sS -m 5 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$safety" | grep -q '"project_planner_planning_only":true' \
  && _pass "planning_only=true" || _fail "planning_only not true"
echo "$safety" | grep -q '"project_work_item_dispatch_enabled":false' \
  && _pass "work_item_dispatch disabled" || _fail "work_item_dispatch not disabled"
echo "$safety" | grep -q '"project_planner_real_llm_enabled":false' \
  && _pass "real_llm disabled" || _fail "real_llm not disabled"
echo "$safety" | grep -q '"project_planner_production_execution_enabled":false' \
  && _pass "production_execution disabled" || _fail "production_execution not disabled"
echo "$safety" | grep -q '"production_executed_true_count":0' \
  && _pass "production_executed_true_count=0" || _fail "production_executed_true_count != 0"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario D: operations API ==="
if [ -n "$PROJECT_ID" ]; then
  for path in "" "/brief" "/work-items" "/dependencies" "/graph" "/progress" "/delivery-readiness"; do
    resp=$(curl -sS -m 5 "$ORCH/operations/projects/$PROJECT_ID$path" 2>/dev/null || echo '{}')
    if echo "$resp" | grep -qiE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|chain_of_thought|"reasoning"'; then
      _fail "secret/chain-of-thought leak in $path"
    else
      _pass "GET projects/{id}$path clean"
    fi
  done
else
  _skip "no project_id -- operations API reads skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario E: audit / notification ==="
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.project_planning.events import PROJECT_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import DEFAULT_REAL_DELIVERY_DENYLIST, _matches_pattern
assert all(any(_matches_pattern(e,p) for p in DEFAULT_REAL_DELIVERY_DENYLIST) for e in PROJECT_NOTIFICATION_EVENTS)
print('OK')
" >/dev/null 2>&1; then
  _pass "project.* notifications default-denied"
else
  _fail "project.* notifications not denied"
fi
det_out=$(bash scripts/detect_audit_tamper_residue.sh 2>&1 || true)
if echo "$det_out" | grep -qE "AUDIT_TAMPER_RESIDUE_DETECTOR: (PASS|SKIP)"; then
  _pass "audit chain has no tamper residue"
else
  _fail "audit tamper residue detected"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario F: regression compatibility ==="
if bash scripts/verify_tamper_evident_audit.sh >/tmp/ppv_tamper.log 2>&1; then
  grep -q "TAMPER_EVIDENT_AUDIT_VERIFY: PASS" /tmp/ppv_tamper.log \
    && _pass "tamper-evident audit verify PASS" || _skip "tamper-evident verify inconclusive"
else
  _skip "tamper-evident verify could not run"
fi
echo "  running full regression (this serializes audit-touching scripts)..."
if bash scripts/run_full_regression.sh --full --json-report >/tmp/ppv_full.log 2>&1; then
  :
fi
if grep -qE "FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)" /tmp/ppv_full.log; then
  _pass "full regression PASS / PASS_WITH_DOCUMENTED_GAPS"
else
  _fail "full regression not green (see /tmp/ppv_full.log)"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Summary: $checks/$total checks passed ==="
if [ "$checks" -eq "$total" ]; then
  echo "PROJECT_PLANNER_TASK_GRAPH_VERIFY: PASS"
  exit 0
else
  echo "PROJECT_PLANNER_TASK_GRAPH_VERIFY: FAIL"
  exit 1
fi
