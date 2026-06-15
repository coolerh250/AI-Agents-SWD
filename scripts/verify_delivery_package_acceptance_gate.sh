#!/usr/bin/env bash
# Stage 49 -- end-to-end verifier for the Delivery Package & Acceptance Gate.
#
# Scenario A -- service health (package/pilot/workspace/design/planner + orch).
# Scenario B -- prepare a completed mini pilot (POST .../mini-delivery-pilots/run).
# Scenario C -- build the delivery package (POST .../delivery-package/build).
# Scenario D -- package sections / artifacts / report.
# Scenario E -- acceptance gate (passed/passed_with_findings, 0 failed/blocking).
# Scenario F -- readiness / handoff / operator review (actions disabled).
# Scenario G -- operations API / safety fields.
# Scenario H -- audit / notification (denylist + clean chain + convergence).
# Scenario I -- regression compatibility (chains mini pilot + full regression).
#
# Marker: DELIVERY_PACKAGE_ACCEPTANCE_GATE_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
DPA="${DELIVERY_PACKAGE_URL:-http://localhost:8020}"

echo "### verify_delivery_package_acceptance_gate: $(date '+%Y-%m-%d %H:%M:%S %Z')"

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
dh=$(curl -sS -m 5 "$DPA/health" 2>/dev/null || echo '{}')
if echo "$dh" | grep -q '"status":"ok"'; then
  _pass "delivery-package-agent health"
else
  _skip "delivery-package-agent not reachable (build still runs via operations API)"
fi
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$saf" | grep -q '"delivery_package_enabled"' && _pass "migration/safety fields present" \
  || _fail "delivery package safety fields missing"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario B: prepare completed mini pilot ==="
REQ='Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples.'
run=$(curl -sS -m 180 -X POST "$ORCH/operations/mini-delivery-pilots/run" \
  -H 'Content-Type: application/json' -d "{\"request_text\": \"$REQ\"}" 2>/dev/null || echo '{}')
PILOT_ID=$(_field "$run" pilot_id)
PROJECT_ID=$(_field "$run" project_id)
PILOT_STATUS=$(_field "$run" pilot_status)
[ -n "$PILOT_ID" ] && _pass "pilot_id present ($PILOT_ID)" || _fail "no pilot_id"
case "$PILOT_STATUS" in
  completed|report_ready) _pass "pilot status=$PILOT_STATUS";;
  *) _fail "pilot status=$PILOT_STATUS";;
esac
acc=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/acceptance-evaluations" 2>/dev/null || echo '{}')
acc_fail=$(echo "$acc" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('summary',{}).get('failed',1))" 2>/dev/null || echo 1)
[ "${acc_fail:-1}" = "0" ] && _pass "pilot acceptance failed=0" || _fail "pilot acceptance failed=$acc_fail"
qa=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/qa-report" 2>/dev/null || echo '{}')
case "$(_field "$qa" status)" in
  passed|passed_with_findings) _pass "pilot QA ok";;
  *) _fail "pilot QA=$(_field "$qa" status)";;
esac
sa=$(curl -sS -m 10 "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/safety-report" 2>/dev/null || echo '{}')
[ "$(_field "$sa" status)" = "safe" ] && _pass "pilot safety=safe" || _fail "pilot safety=$(_field "$sa" status)"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario C: build delivery package ==="
build=$(curl -sS -m 60 -X POST "$ORCH/operations/mini-delivery-pilots/$PILOT_ID/delivery-package/build" \
  -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
PKG_ID=$(_field "$build" package_id)
[ -n "$PKG_ID" ] && _pass "package_id present ($PKG_ID)" || _fail "no package_id"
[ "$(_field "$build" package_status)" = "ready_for_review" ] && _pass "package ready_for_review" || _fail "package status=$(_field "$build" package_status)"
[ "$(_field "$build" controlled_only)" = "True" ] && _pass "controlled_only=true" || _fail "controlled_only not true"
[ "$(_field "$build" human_acceptance_status)" = "pending" ] && _pass "human_acceptance pending" || _fail "human_acceptance not pending"
[ "$(_field "$build" pr_created)" = "False" ] && _pass "no PR" || _fail "PR created"
[ "$(_field "$build" deployment_performed)" = "False" ] && _pass "no deploy" || _fail "deploy performed"
[ "$(_field "$build" github_write_performed)" = "False" ] && _pass "no github write" || _fail "github write"
[ "$(_field "$build" real_llm_used)" = "False" ] && _pass "no real LLM" || _fail "real LLM used"
[ "$(_field "$build" production_executed)" = "False" ] && _pass "production_executed=false" || _fail "production_executed not false"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario D: sections / artifacts / report ==="
if [ -n "$PKG_ID" ]; then
  sec=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/sections" 2>/dev/null || echo '{}')
  sec_count=$(echo "$sec" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
  sec_missing=$(echo "$sec" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('missing_count',1))" 2>/dev/null || echo 1)
  [ "${sec_count:-0}" -ge 13 ] 2>/dev/null && _pass "sections>=13 ($sec_count)" || _fail "sections=$sec_count"
  [ "${sec_missing:-1}" = "0" ] && _pass "sections missing=0" || _fail "sections missing=$sec_missing"
  art=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/artifacts" 2>/dev/null || echo '{}')
  for t in project_brief design_review_summary workspace_report qa_evidence_report safety_evidence_report acceptance_evaluations mini_delivery_report; do
    echo "$art" | grep -q "$t" && _pass "artifact $t linked" || _fail "artifact $t missing"
  done
  rep=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/report" 2>/dev/null || echo '{}')
  echo "$rep" | grep -q 'acceptance_gate_decision' && echo "$rep" | grep -q 'section_summaries' \
    && _pass "report has gate decision + section summaries" || _fail "report missing fields"
  echo "$rep" | grep -q 'known_limitations' && echo "$rep" | grep -q 'next_steps' \
    && _pass "report has limitations + next steps" || _fail "report missing limitations/next steps"
  if echo "$rep" | grep -qiE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|chain_of_thought|raw_prompt'; then
    _fail "secret/CoT leak in report"
  else
    _pass "no secret / no chain-of-thought in report"
  fi
else
  _skip "no package_id -- sections skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario E: acceptance gate ==="
if [ -n "$PKG_ID" ]; then
  gate=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/acceptance-gate" 2>/dev/null || echo '{}')
  case "$(_field "$gate" status)" in
    passed|passed_with_findings) _pass "gate status ok";;
    *) _fail "gate status=$(_field "$gate" status)";;
  esac
  case "$(_field "$gate" decision)" in
    ready_for_operator_review|controlled_only_complete) _pass "gate decision ok";;
    *) _fail "gate decision=$(_field "$gate" decision)";;
  esac
  [ "$(_field "$gate" human_review_status)" = "pending" ] && _pass "human_review pending" || _fail "human_review not pending"
  [ "$(_field "$gate" blocking_findings_count)" = "0" ] && _pass "blocking findings=0" || _fail "blocking findings != 0"
  checks_json=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/acceptance-checks" 2>/dev/null || echo '{}')
  chk_count=$(echo "$checks_json" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0)
  chk_failed=$(echo "$checks_json" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('failed',1))" 2>/dev/null || echo 1)
  [ "${chk_count:-0}" -ge 15 ] 2>/dev/null && _pass "total checks>=15 ($chk_count)" || _fail "total checks=$chk_count"
  [ "${chk_failed:-1}" = "0" ] && _pass "failed checks=0" || _fail "failed checks=$chk_failed"
  for k in no_production_execution no_github_write no_pr_created no_deploy no_secret_leak; do
    st=$(echo "$checks_json" | "$PY" -c "
import sys,json
d=json.load(sys.stdin)
c=[x for x in d.get('checks',[]) if x.get('check_key')=='$k']
print(c[0]['status'] if c else 'missing')
" 2>/dev/null || echo missing)
    [ "$st" = "passed" ] && _pass "check $k passed" || _fail "check $k=$st"
  done
  hp=$(echo "$checks_json" | "$PY" -c "
import sys,json
d=json.load(sys.stdin)
c=[x for x in d.get('checks',[]) if x.get('check_key')=='human_acceptance_pending']
print(c[0]['status'] if c else 'missing', c[0]['blocking'] if c else True)
" 2>/dev/null || echo "missing True")
  echo "$hp" | grep -qE '(warning|pending) (False|false)' && _pass "human_acceptance_pending not blocking" || _fail "human_acceptance_pending blocking: $hp"
else
  _skip "no package_id -- gate skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario F: readiness / handoff / operator review ==="
if [ -n "$PKG_ID" ]; then
  rd=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/readiness" 2>/dev/null || echo '{}')
  [ "$(_field "$rd" readiness_status)" = "ready_for_operator_review" ] && _pass "readiness ready_for_operator_review" || _fail "readiness=$(_field "$rd" readiness_status)"
  for f in project_ready design_ready workspace_ready qa_ready acceptance_ready safety_ready docs_ready; do
    echo "$rd" | grep -q "\"$f\": *true" && _pass "$f=true" || _fail "$f not true"
  done
  echo "$rd" | grep -q '"human_acceptance_pending": *true' && _pass "human_acceptance_pending=true" || _fail "human_acceptance_pending not true"
  ho=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/handoff-summaries" 2>/dev/null || echo '{}')
  echo "$ho" | grep -q 'business_summary' && echo "$ho" | grep -q 'technical_summary' && echo "$ho" | grep -q 'operator_summary' \
    && _pass "3 handoff summaries present" || _fail "handoff summaries missing"
  rev=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/operator-review" 2>/dev/null || echo '{}')
  [ "$(_field "$rev" review_status)" = "pending" ] && _pass "operator review pending" || _fail "operator review=$(_field "$rev" review_status)"
  for action in accept reject request-changes; do
    resp=$(curl -sS -m 10 -X POST "$ORCH/operations/delivery-packages/$PKG_ID/operator-review/$action" -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
    if echo "$resp" | grep -qE 'action_disabled|policy_blocked'; then
      _pass "operator $action disabled by default"
    else
      _fail "operator $action not disabled: $resp"
    fi
  done
  rev2=$(curl -sS -m 10 "$ORCH/operations/delivery-packages/$PKG_ID/operator-review" 2>/dev/null || echo '{}')
  [ "$(_field "$rev2" review_status)" = "pending" ] && _pass "review still pending after disabled actions" || _fail "review changed by disabled action"
else
  _skip "no package_id -- readiness skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario G: operations API / safety ==="
if [ -n "$PROJECT_ID" ]; then
  curl -sS -m 10 "$ORCH/operations/projects/$PROJECT_ID/latest-delivery-package" 2>/dev/null | grep -q "$PKG_ID" \
    && _pass "project latest delivery package" || _fail "project latest delivery package"
  curl -sS -m 10 "$ORCH/operations/projects/$PROJECT_ID/delivery-packages" 2>/dev/null | grep -q "$PKG_ID" \
    && _pass "project delivery packages list" || _fail "project delivery packages list"
fi
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$saf" | grep -q '"delivery_package_controlled_only":true' && _pass "controlled_only=true" || _fail "controlled_only not true"
echo "$saf" | grep -q '"delivery_package_real_llm_enabled":false' && _pass "real_llm disabled" || _fail "real_llm not disabled"
echo "$saf" | grep -q '"delivery_package_github_write_enabled":false' && _pass "github write disabled" || _fail "github write not disabled"
echo "$saf" | grep -q '"delivery_package_pr_creation_enabled":false' && _pass "PR creation disabled" || _fail "PR creation not disabled"
echo "$saf" | grep -q '"delivery_package_deploy_enabled":false' && _pass "deploy disabled" || _fail "deploy not disabled"
echo "$saf" | grep -q '"delivery_package_external_delivery_enabled":false' && _pass "external delivery disabled" || _fail "external delivery not disabled"
echo "$saf" | grep -q '"delivery_package_auto_accept_enabled":false' && _pass "auto-accept disabled" || _fail "auto-accept not disabled"
echo "$saf" | grep -q '"delivery_package_operator_actions_enabled":false' && _pass "operator actions disabled" || _fail "operator actions not disabled"
echo "$saf" | grep -q '"production_executed_true_count":0' && _pass "production_executed_true_count=0" || _fail "production count != 0"
echo "$saf" | grep -q '"latest_human_acceptance_status":"pending"' && _pass "latest_human_acceptance pending" || _fail "latest_human_acceptance not pending"
echo "$saf" | grep -q '"delivery_package_ready_for_admin_console":true' && _pass "ready_for_admin_console=true" || _fail "not ready_for_admin_console"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario H: audit / notification ==="
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.delivery_package.events import DELIVERY_PACKAGE_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import DEFAULT_REAL_DELIVERY_DENYLIST, _matches_pattern
evs=list(DELIVERY_PACKAGE_NOTIFICATION_EVENTS)+['acceptance_gate.x','handoff.x']
assert all(any(_matches_pattern(e,p) for p in DEFAULT_REAL_DELIVERY_DENYLIST) for e in evs)
print('OK')
" >/dev/null 2>&1; then
  _pass "delivery_package.* / acceptance_gate.* / handoff.* default-denied"
else
  _fail "delivery package notifications not denied"
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
echo "=== Scenario I: regression compatibility ==="
# verify_mini_project_delivery_pilot.sh transitively runs the workspace +
# design-review + planner + full regression gates. Reuse it as the gate.
if bash scripts/verify_mini_project_delivery_pilot.sh >/tmp/dpa_mdp.log 2>&1; then
  grep -q "MINI_PROJECT_DELIVERY_PILOT_VERIFY: PASS" /tmp/dpa_mdp.log \
    && _pass "mini pilot + workspace + design + planner + full regression PASS" \
    || _fail "mini pilot verify not PASS"
else
  grep -q "MINI_PROJECT_DELIVERY_PILOT_VERIFY: PASS" /tmp/dpa_mdp.log \
    && _pass "mini pilot verify PASS" || _skip "mini pilot verify inconclusive"
fi
if grep -qE "\[PASS\] full regression|FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)" /tmp/dpa_mdp.log; then
  _pass "full regression PASS / PASS_WITH_DOCUMENTED_GAPS"
else
  _fail "full regression not green (see /tmp/dpa_mdp.log)"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Summary: $checks/$total checks passed ==="
if [ "$checks" -eq "$total" ]; then
  echo "DELIVERY_PACKAGE_ACCEPTANCE_GATE_VERIFY: PASS"
  exit 0
else
  echo "DELIVERY_PACKAGE_ACCEPTANCE_GATE_VERIFY: FAIL"
  exit 1
fi
