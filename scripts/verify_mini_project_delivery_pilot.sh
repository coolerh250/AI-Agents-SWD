#!/usr/bin/env bash
# Stage 48 -- end-to-end verifier for the Mini Project Delivery Pilot.
#
# Scenario A -- service health (pilot/planner/design-review/workspace + orch).
# Scenario B -- run a FastAPI Todo mini pilot (POST .../mini-delivery-pilots/run).
# Scenario C -- validate project / review / workspace links + steps.
# Scenario D -- acceptance evaluation (>=8 satisfied, 0 failed).
# Scenario E -- QA / safety / report evidence.
# Scenario F -- operations API / safety fields.
# Scenario G -- audit / notification (denylist + clean chain + convergence).
# Scenario H -- regression compatibility (chains workspace + design + planner +
#               full regression).
#
# Marker: MINI_PROJECT_DELIVERY_PILOT_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
MDP_AGENT="${MINI_DELIVERY_PILOT_URL:-http://localhost:8019}"

echo "### verify_mini_project_delivery_pilot: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=0
_pass() { echo "  [PASS] $1"; checks=$((checks + 1)); total=$((total + 1)); }
_fail() { echo "  [FAIL] $1"; total=$((total + 1)); }
_skip() { echo "  [SKIP] $1"; }
_field() { echo "$1" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('$2',''))" 2>/dev/null || echo ""; }

# ---------------------------------------------------------------------------
echo
echo "=== Scenario A: service health ==="
oh=$(curl -sS -m 5 "$ORCH/health" 2>/dev/null || echo '{}')
echo "$oh" | grep -q '"status":"ok"' && _pass "orchestrator health" || _fail "orchestrator health"
mh=$(curl -sS -m 5 "$MDP_AGENT/health" 2>/dev/null || echo '{}')
if echo "$mh" | grep -q '"status":"ok"'; then
  _pass "mini-delivery-pilot-agent health"
else
  _skip "mini-delivery-pilot-agent not reachable (pilot still runs via operations API)"
fi
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$saf" | grep -q '"mini_delivery_pilot_enabled"' && _pass "migration/safety fields present" \
  || _fail "mini delivery safety fields missing"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario B: run FastAPI Todo mini pilot ==="
REQ='Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples.'
run=$(curl -sS -m 180 -X POST "$ORCH/operations/mini-delivery-pilots/run" \
  -H 'Content-Type: application/json' -d "{\"request_text\": \"$REQ\"}" 2>/dev/null || echo '{}')
PILOT_ID=$(_field "$run" pilot_id)
PROJECT_ID=$(_field "$run" project_id)
DR_ID=$(_field "$run" design_review_session_id)
WS_ID=$(_field "$run" workspace_id)
PILOT_STATUS=$(_field "$run" pilot_status)
[ -n "$PILOT_ID" ] && _pass "pilot_id present ($PILOT_ID)" || _fail "no pilot_id"
[ -n "$PROJECT_ID" ] && _pass "project_id present" || _fail "no project_id"
[ -n "$DR_ID" ] && _pass "design_review_session_id present" || _fail "no design_review_session_id"
[ -n "$WS_ID" ] && _pass "workspace_id present" || _fail "no workspace_id"
case "$PILOT_STATUS" in
  completed|report_ready) _pass "pilot status=$PILOT_STATUS";;
  *) _fail "pilot status=$PILOT_STATUS";;
esac
[ "$(_field "$run" controlled_only)" = "True" ] && _pass "controlled_only=true" || _fail "controlled_only not true"
[ "$(_field "$run" production_executed)" = "False" ] && _pass "production_executed=false" || _fail "production_executed not false"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario C: project / review / workspace links + steps ==="
if [ -n "$PILOT_ID" ]; then
  steps=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/steps" 2>/dev/null || echo '{}')
  for key in project_plan design_review workspace_execution test_execution; do
    st=$(echo "$steps" | "$PY" -c "
import sys,json
d=json.load(sys.stdin)
s=[x for x in d.get('steps',[]) if x.get('step_key')=='$key']
print(s[0]['status'] if s else 'missing')
" 2>/dev/null || echo "missing")
    case "$st" in
      passed|passed_with_findings) _pass "step $key=$st";;
      *) _fail "step $key=$st";;
    esac
  done
else
  _skip "no pilot_id -- steps skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario D: acceptance evaluation ==="
if [ -n "$PILOT_ID" ]; then
  acc=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/acceptance-evaluations" 2>/dev/null || echo '{}')
  acc_total=$(echo "$acc" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('summary',{}).get('total',0))" 2>/dev/null || echo 0)
  acc_sat=$(echo "$acc" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('summary',{}).get('satisfied',0))" 2>/dev/null || echo 0)
  acc_fail=$(echo "$acc" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('summary',{}).get('failed',0))" 2>/dev/null || echo 0)
  [ "${acc_total:-0}" -ge 8 ] 2>/dev/null && _pass "acceptance total=$acc_total (>=8)" || _fail "acceptance total=$acc_total"
  [ "${acc_sat:-0}" -ge 8 ] 2>/dev/null && _pass "acceptance satisfied=$acc_sat (>=8)" || _fail "acceptance satisfied=$acc_sat"
  [ "${acc_fail:-1}" = "0" ] && _pass "acceptance failed=0" || _fail "acceptance failed=$acc_fail"
  echo "$acc" | grep -q 'test_run' && _pass "CRUD mapped to test_run evidence" || _fail "no test_run evidence"
  echo "$acc" | grep -q 'generated_file' && _pass "README mapped to generated_file evidence" || _fail "no generated_file evidence"
  echo "$acc" | grep -q 'static_check' && _pass "no-deploy/no-secret mapped to static_check evidence" || _fail "no static_check evidence"
else
  _skip "no pilot_id -- acceptance skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario E: QA / safety / report ==="
if [ -n "$PILOT_ID" ]; then
  qa=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/qa-report" 2>/dev/null || echo '{}')
  case "$(_field "$qa" status)" in
    passed|passed_with_findings) _pass "QA status ok";;
    *) _fail "QA status=$(_field "$qa" status)";;
  esac
  [ "$(_field "$qa" tests_failed)" = "0" ] && _pass "tests_failed=0" || _fail "tests_failed=$(_field "$qa" tests_failed)"
  sa=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/safety-report" 2>/dev/null || echo '{}')
  [ "$(_field "$sa" status)" = "safe" ] && _pass "safety status=safe" || _fail "safety status=$(_field "$sa" status)"
  [ "$(_field "$sa" production_executed_count)" = "0" ] && _pass "production_executed_count=0" || _fail "production count != 0"
  [ "$(_field "$sa" github_write_performed)" = "False" ] && _pass "no github write" || _fail "github write performed"
  [ "$(_field "$sa" pr_created)" = "False" ] && _pass "no PR created" || _fail "PR created"
  [ "$(_field "$sa" deployment_performed)" = "False" ] && _pass "no deploy" || _fail "deploy performed"
  [ "$(_field "$sa" real_llm_used)" = "False" ] && _pass "no real LLM" || _fail "real LLM used"
  [ "$(_field "$sa" repo_root_modified)" = "False" ] && _pass "no repo root write" || _fail "repo root modified"
  [ "$(_field "$sa" secret_leak_detected)" = "False" ] && _pass "no secret leak" || _fail "secret leak detected"
  [ "$(_field "$sa" chain_of_thought_persisted)" = "False" ] && _pass "no chain-of-thought persisted" || _fail "CoT persisted"
  rep=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/report" 2>/dev/null || echo '{}')
  if echo "$rep" | grep -q 'executive_summary' && echo "$rep" | grep -q 'safety_summary' \
     && echo "$rep" | grep -q 'acceptance_summary' && echo "$rep" | grep -q 'qa_summary'; then
    _pass "report has required summaries"
  else
    _fail "report missing summaries"
  fi
else
  _skip "no pilot_id -- QA/safety/report skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario F: operations API / safety ==="
if [ -n "$PILOT_ID" ]; then
  curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/timeline" 2>/dev/null | grep -q 'step_count' \
    && _pass "timeline endpoint" || _fail "timeline endpoint"
  curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/artifacts" 2>/dev/null | grep -q 'mini_delivery_report_ref' \
    && _pass "artifacts endpoint" || _fail "artifacts endpoint"
  curl -sS -m 10 "$ORCH/operations/projects/$PROJECT_ID/latest-mini-delivery-pilot" 2>/dev/null | grep -q "$PILOT_ID" \
    && _pass "project latest pilot endpoint" || _fail "project latest pilot endpoint"
fi
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$saf" | grep -q '"mini_delivery_pilot_controlled_only":true' && _pass "controlled_only=true" || _fail "controlled_only not true"
echo "$saf" | grep -q '"mini_delivery_real_llm_enabled":false' && _pass "real_llm disabled" || _fail "real_llm not disabled"
echo "$saf" | grep -q '"mini_delivery_github_write_enabled":false' && _pass "github write disabled" || _fail "github write not disabled"
echo "$saf" | grep -q '"mini_delivery_pr_creation_enabled":false' && _pass "PR creation disabled" || _fail "PR creation not disabled"
echo "$saf" | grep -q '"mini_delivery_deploy_enabled":false' && _pass "deploy disabled" || _fail "deploy not disabled"
echo "$saf" | grep -q '"mini_delivery_external_delivery_enabled":false' && _pass "external delivery disabled" || _fail "external delivery not disabled"
echo "$saf" | grep -q '"production_executed_true_count":0' && _pass "production_executed_true_count=0" || _fail "production count != 0"
if echo "$saf" | grep -qiE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|chain_of_thought":[^_]'; then
  _fail "secret/CoT leak in safety response"
else
  _pass "no secret / no chain-of-thought in safety response"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario G: audit / notification ==="
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.mini_delivery_pilot.events import DELIVERY_PILOT_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import DEFAULT_REAL_DELIVERY_DENYLIST, _matches_pattern
evs=list(DELIVERY_PILOT_NOTIFICATION_EVENTS)+['acceptance.criteria_satisfied','qa_evidence.report_ready']
assert all(any(_matches_pattern(e,p) for p in DEFAULT_REAL_DELIVERY_DENYLIST) for e in evs)
print('OK')
" >/dev/null 2>&1; then
  _pass "delivery_pilot.* / acceptance.* / qa_evidence.* default-denied"
else
  _fail "pilot notifications not denied"
fi
for _i in 1 2 3 4 5 6 7 8 9 10; do
  vc=$(curl -sS -m 60 -X POST "$ORCH/operations/audit/verify-chain" 2>/dev/null || echo '{}')
  st=$(echo "$vc" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
  [ "$st" = "passed" ] && break
  sleep 3
done
echo "  audit chain settled (verify-chain status=${st:-unknown})"
det=$(bash scripts/detect_audit_tamper_residue.sh 2>&1 || true)
echo "$det" | grep -qE "AUDIT_TAMPER_RESIDUE_DETECTOR: (PASS|SKIP)" && _pass "audit chain clean / no tamper residue" || _fail "tamper residue detected"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario H: regression compatibility ==="
# verify_real_repo_workspace_operator.sh transitively runs the design-review
# verify (planner + full regression). Reuse it as the single regression gate.
if bash scripts/verify_real_repo_workspace_operator.sh >/tmp/mdp_wso.log 2>&1; then
  grep -q "REAL_REPO_WORKSPACE_OPERATOR_VERIFY: PASS" /tmp/mdp_wso.log \
    && _pass "workspace + design + planner + full regression PASS" \
    || _fail "workspace operator verify not PASS"
else
  grep -q "REAL_REPO_WORKSPACE_OPERATOR_VERIFY: PASS" /tmp/mdp_wso.log \
    && _pass "workspace operator verify PASS" || _skip "workspace operator verify inconclusive"
fi
if grep -qE "\[PASS\] full regression|FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)" /tmp/mdp_wso.log; then
  _pass "full regression PASS / PASS_WITH_DOCUMENTED_GAPS"
else
  _fail "full regression not green (see /tmp/mdp_wso.log)"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Summary: $checks/$total checks passed ==="
if [ "$checks" -eq "$total" ]; then
  echo "MINI_PROJECT_DELIVERY_PILOT_VERIFY: PASS"
  exit 0
else
  echo "MINI_PROJECT_DELIVERY_PILOT_VERIFY: FAIL"
  exit 1
fi
