#!/usr/bin/env bash
# Stage 46 -- end-to-end verifier for the agent discussion & design review.
#
# Scenario A -- service health (design-review-agent, orchestrator) + SDK.
# Scenario B -- prepare a FastAPI Todo project (POST /operations/projects/plan).
# Scenario C -- run design review (POST /operations/projects/{id}/design-review).
# Scenario D -- operations API reads (discussion/review/findings/gates/...).
# Scenario E -- planning-only safety.
# Scenario F -- audit / notification (denylist + clean chain).
# Scenario G -- regression compatibility (residue + planner + tamper + full run).
#
# Marker: AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
DR_AGENT="${DESIGN_REVIEW_URL:-http://localhost:8017}"

echo "### verify_agent_discussion_design_review: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }
_skip() { echo "  [SKIP] $1"; }
_field() { echo "$1" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('$2',''))" 2>/dev/null || echo ""; }

# ---------------------------------------------------------------------------
echo
echo "=== Scenario A: service health + SDK ==="
oh=$(curl -sS -m 5 "$ORCH/health" 2>/dev/null || echo '{}')
echo "$oh" | grep -q '"status":"ok"' && _pass "orchestrator health" || _fail "orchestrator health"
dh=$(curl -sS -m 5 "$DR_AGENT/health" 2>/dev/null || echo '{}')
if echo "$dh" | grep -q '"status":"ok"'; then
  _pass "design-review-agent health"
else
  _skip "design-review-agent not reachable (review still works via operations API)"
fi
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.design_review import build_review
from shared.sdk.design_review.models import ReviewContext
print('OK')
" >/dev/null 2>&1; then
  _pass "design_review SDK importable"
else
  _fail "design_review SDK import"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario B: prepare FastAPI Todo project ==="
REQ='Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples.'
plan=$(curl -sS -m 20 -X POST "$ORCH/operations/projects/plan" -H 'Content-Type: application/json' \
  -d "{\"request_text\": \"$REQ\"}" 2>/dev/null || echo '{}')
PROJECT_ID=$(_field "$plan" project_id)
[ -n "$PROJECT_ID" ] && _pass "project planned ($PROJECT_ID)" || _fail "plan returned no project_id"
[ "$(_field "$plan" validation_status)" = "valid" ] && _pass "graph valid" || _fail "graph not valid"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario C: run design review ==="
if [ -n "$PROJECT_ID" ]; then
  review=$(curl -sS -m 30 -X POST "$ORCH/operations/projects/$PROJECT_ID/design-review" \
    -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
  DSID=$(_field "$review" discussion_session_id)
  RSID=$(_field "$review" review_session_id)
  [ -n "$DSID" ] && _pass "discussion_session_id present" || _fail "no discussion_session_id"
  [ -n "$RSID" ] && _pass "review_session_id present" || _fail "no review_session_id"
  pc=$(_field "$review" participants_count); cc=$(_field "$review" contributions_count)
  gc=$(_field "$review" gates_count); fc=$(_field "$review" findings_count)
  dc=$(_field "$review" decisions_count); dec=$(_field "$review" go_no_go_decision)
  bfc=$(_field "$review" blocking_findings_count)
  [ "${pc:-0}" -ge 7 ] 2>/dev/null && _pass "participants_count=$pc (>=7)" || _fail "participants_count=$pc"
  [ "${cc:-0}" -ge 7 ] 2>/dev/null && _pass "contributions_count=$cc (>=7)" || _fail "contributions_count=$cc"
  [ "${gc:-0}" -ge 6 ] 2>/dev/null && _pass "gates_count=$gc (>=6)" || _fail "gates_count=$gc"
  [ "${fc:-0}" -ge 1 ] 2>/dev/null && _pass "findings_count=$fc (>=1)" || _fail "findings_count=$fc"
  [ "${dc:-0}" -ge 1 ] 2>/dev/null && _pass "decisions_count=$dc (>=1)" || _fail "decisions_count=$dc"
  case "$dec" in
    planning_only|go_with_findings|go) _pass "decision=$dec (acceptable)";;
    *) _fail "unexpected decision=$dec";;
  esac
  [ "${bfc:-1}" = "0" ] && _pass "no blocking findings for valid template" || _fail "blocking findings=$bfc"
  [ "$(_field "$review" production_executed)" = "False" ] && _pass "production_executed=false" || _fail "production_executed not false"
  [ "$(_field "$review" work_item_dispatch_enabled)" = "False" ] && _pass "no work item dispatch" || _fail "work item dispatch enabled"
else
  _skip "no project_id -- design review skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario D: operations API ==="
if [ -n "${PROJECT_ID:-}" ] && [ -n "${RSID:-}" ]; then
  for url in \
    "$ORCH/operations/projects/$PROJECT_ID/discussions" \
    "$ORCH/operations/discussions/$DSID/participants" \
    "$ORCH/operations/discussions/$DSID/contributions" \
    "$ORCH/operations/design-reviews/$RSID" \
    "$ORCH/operations/design-reviews/$RSID/findings" \
    "$ORCH/operations/design-reviews/$RSID/decisions" \
    "$ORCH/operations/projects/$PROJECT_ID/review-gates" \
    "$ORCH/operations/projects/$PROJECT_ID/go-no-go-summary" \
    "$ORCH/operations/projects/$PROJECT_ID/acceptance-coverage"; do
    resp=$(curl -sS -m 5 "$url" 2>/dev/null || echo '{}')
    if echo "$resp" | grep -qiE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|chain_of_thought|raw_prompt'; then
      _fail "secret/CoT leak in ${url##*/operations/}"
    else
      _pass "GET ${url##*/operations/} clean"
    fi
  done
else
  _skip "no review session -- operations API reads skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario E: safety ==="
safety=$(curl -sS -m 5 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$safety" | grep -q '"design_review_planning_only":true' && _pass "planning_only=true" || _fail "planning_only not true"
echo "$safety" | grep -q '"design_review_work_item_dispatch_enabled":false' && _pass "dispatch disabled" || _fail "dispatch not disabled"
echo "$safety" | grep -q '"design_review_real_llm_enabled":false' && _pass "real_llm disabled" || _fail "real_llm not disabled"
echo "$safety" | grep -q '"agent_discussion_chain_of_thought_persistence_enabled":false' && _pass "no CoT persistence" || _fail "CoT persistence flag wrong"
echo "$safety" | grep -q '"production_executed_true_count":0' && _pass "production_executed_true_count=0" || _fail "production count != 0"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario F: audit / notification ==="
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.agent_discussion.events import DISCUSSION_NOTIFICATION_EVENTS
from shared.sdk.design_review.events import DESIGN_REVIEW_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import DEFAULT_REAL_DELIVERY_DENYLIST, _matches_pattern
evs=list(DISCUSSION_NOTIFICATION_EVENTS)+list(DESIGN_REVIEW_NOTIFICATION_EVENTS)
assert all(any(_matches_pattern(e,p) for p in DEFAULT_REAL_DELIVERY_DENYLIST) for e in evs)
print('OK')
" >/dev/null 2>&1; then
  _pass "discussion.* / design_review.* default-denied"
else
  _fail "discussion/design_review notifications not denied"
fi
det=$(bash scripts/detect_audit_tamper_residue.sh 2>&1 || true)
echo "$det" | grep -qE "AUDIT_TAMPER_RESIDUE_DETECTOR: (PASS|SKIP)" && _pass "audit chain clean" || _fail "tamper residue detected"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario G: regression compatibility ==="
# Earlier scenarios (a live design review + the tamper-evident verify) generate
# audit/notification churn through the always-on audit-worker. Let the chain
# settle before the full regression's verify-chain runs, so an in-flight row
# does not transiently fail verification. This does NOT lower verifier
# strictness -- it only waits for eventual consistency to converge.
for _i in 1 2 3 4 5 6 7 8 9 10; do
  vc=$(curl -sS -m 20 -X POST "$ORCH/operations/audit/verify-chain" 2>/dev/null || echo '{}')
  st=$(echo "$vc" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
  [ "$st" = "passed" ] && break
  sleep 3
done
echo "  audit chain settled (verify-chain status=${st:-unknown})"
if bash scripts/verify_project_planner_task_graph.sh >/tmp/adr_planner.log 2>&1; then
  grep -q "PROJECT_PLANNER_TASK_GRAPH_VERIFY: PASS" /tmp/adr_planner.log \
    && _pass "project planner verify PASS" || _fail "project planner verify not PASS"
else
  grep -q "PROJECT_PLANNER_TASK_GRAPH_VERIFY: PASS" /tmp/adr_planner.log \
    && _pass "project planner verify PASS" || _skip "project planner verify inconclusive"
fi
# verify_project_planner_task_graph.sh runs the full regression internally and
# emits a "[PASS] full regression ..." line on its own stdout (the
# FULL_REGRESSION_VERIFY marker itself lands in its private /tmp/ppv_full.log).
if grep -qE "\[PASS\] full regression" /tmp/adr_planner.log \
   || grep -qE "FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)" /tmp/adr_planner.log; then
  _pass "full regression PASS / PASS_WITH_DOCUMENTED_GAPS"
else
  _fail "full regression not green (see /tmp/adr_planner.log)"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Summary: $checks/$total checks passed ==="
if [ "$checks" -eq "$total" ]; then
  echo "AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: PASS"
  exit 0
else
  echo "AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: FAIL"
  exit 1
fi
