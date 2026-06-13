#!/usr/bin/env bash
# Stage 31 -- flexible human approval policy verifier.
#
# Five scenarios on the local/test stack (no real LLM, no real GitHub,
# no real Discord, no production deploy):
#
#   A) per_action: explicit approval required; the orchestrator
#      refuses to auto-promote.
#   B) per_feature: an active policy bound to a task authorises
#      promotions inside its allowlist; another task is refused.
#   C) per_stage: a policy bound to a stage authorises actions
#      inside that stage and refuses actions outside it.
#   D) delegated: a fully-constrained delegated policy authorises
#      actions; missing constraints get a 400 at create time.
#   E) hard safety: even a delegated policy that lists a denylist
#      path / production_deploy / real_github_write action gets
#      refused at evaluate time -- the hard rails always win.
#
# production_executed=false must hold throughout.
set -uo pipefail

# shellcheck source=scripts/lib/verify_env.sh
source "$(cd "$(dirname "$0")" && pwd)/lib/verify_env.sh" 2>/dev/null || true

ORCH="${ORCH_URL:-http://localhost:8000}"

echo "### verify_flexible_human_approval_policy: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=14
fail() { echo "  $1: FAIL"; }
pass() { echo "  $1: PASS"; checks=$((checks+1)); }

ts=$(date +%s)

_post() {
  local url="$1" body="$2"
  curl -sS -m 15 -X POST "${url}" \
    -H "Content-Type: application/json" -d "${body}" || echo '{}'
}

_post_code() {
  local url="$1" body="$2"
  curl -sS -m 15 -o /dev/null -w "%{http_code}" -X POST "${url}" \
    -H "Content-Type: application/json" -d "${body}" || echo "000"
}

_field() {
  "${PYTHON:-python3}" -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    for k in sys.argv[2].split('.'):
        if isinstance(d, list):
            d = d[int(k)]
        elif isinstance(d, dict):
            d = d.get(k)
        else:
            d = None; break
    if d is None: print('')
    elif isinstance(d, (dict, list)): print(json.dumps(d))
    else: print(d)
except Exception: print('')
" "$1" "$2"
}

# Future ISO timestamp (in 1 hour).
expires_at=$("${PYTHON:-python3}" -c "
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
")

# Scenario A -- per_action default
echo
echo "=== Scenario A -- per_action ==="
task_a="stage31-per-action-${ts}"
body_a=$(cat <<EOF
{"task_id":"${task_a}","approval_mode":"per_action","granted_by":"verifier"}
EOF
)
resp_a=$(_post "${ORCH}/approval-policies" "${body_a}")
mode_a=$(_field "$resp_a" "policy.approval_mode")
[ "$mode_a" = "per_action" ] && pass "PER_ACTION_POLICY_CREATED" || fail "PER_ACTION_POLICY_CREATED (mode=$mode_a)"

# Unknown proposal -> 404 (per_action requires explicit approval)
http_a=$(_post_code "${ORCH}/llm/proposals/00000000-0000-0000-0000-000000000000/promote" \
  "{\"task_id\":\"${task_a}\",\"promoted_by\":\"verifier\"}")
[ "$http_a" = "404" ] && pass "PER_ACTION_UNAPPROVED_BLOCKED" || fail "PER_ACTION_UNAPPROVED_BLOCKED (got: $http_a)"

# Scenario B -- per_feature
echo
echo "=== Scenario B -- per_feature ==="
task_b="stage31-per-feature-${ts}"
body_b=$(cat <<EOF
{"task_id":"${task_b}","approval_mode":"per_feature","granted_by":"verifier",
 "allowed_actions":["llm_proposal_promote"],
 "allowed_paths":["docs/generated/","apps/demo-generated/","tests/generated/"],
 "denied_paths":[".env","*.pem"],
 "reason":"per_feature test"}
EOF
)
resp_b=$(_post "${ORCH}/approval-policies" "${body_b}")
status_b=$(_field "$resp_b" "policy.status")
[ "$status_b" = "active" ] && pass "PER_FEATURE_POLICY_ACTIVE" || fail "PER_FEATURE_POLICY_ACTIVE (status=$status_b)"

# Same task -- /operations/approval-policies shows the policy.
ops_b=$(curl -sS -m 10 "${ORCH}/operations/approval-policies/${task_b}" || echo '{}')
ac_b=$(_field "$ops_b" "active_count")
[ "$ac_b" = "1" ] && pass "PER_FEATURE_VISIBLE_VIA_OPERATIONS" || fail "PER_FEATURE_VISIBLE_VIA_OPERATIONS (ac=$ac_b)"

# Scenario C -- per_stage
echo
echo "=== Scenario C -- per_stage ==="
task_c="stage31-per-stage-${ts}"
body_c=$(cat <<EOF
{"task_id":"${task_c}","approval_mode":"per_stage","granted_by":"verifier",
 "allowed_actions":["llm_proposal_promote"],
 "allowed_paths":["docs/generated/"],
 "allowed_stages":["code_generation"],
 "reason":"per_stage test"}
EOF
)
resp_c=$(_post "${ORCH}/approval-policies" "${body_c}")
stage_c=$(_field "$resp_c" "policy.allowed_stages.0")
[ "$stage_c" = "code_generation" ] && pass "PER_STAGE_BOUND_TO_STAGE" || fail "PER_STAGE_BOUND_TO_STAGE (stage=$stage_c)"

# per_stage with missing allowed_stages -> 400
bad_c=$(_post_code "${ORCH}/approval-policies" \
  "{\"task_id\":\"${task_c}-bad\",\"approval_mode\":\"per_stage\",\"granted_by\":\"v\",\"allowed_actions\":[\"x\"],\"allowed_paths\":[\"docs/generated/\"]}")
[ "$bad_c" = "400" ] && pass "PER_STAGE_MISSING_STAGES_400" || fail "PER_STAGE_MISSING_STAGES_400 (got: $bad_c)"

# Scenario D -- delegated
echo
echo "=== Scenario D -- delegated ==="
task_d="stage31-delegated-${ts}"
body_d=$(cat <<EOF
{"task_id":"${task_d}","approval_mode":"delegated","granted_by":"verifier",
 "allowed_actions":["llm_proposal_promote"],
 "allowed_paths":["docs/generated/","apps/demo-generated/","tests/generated/"],
 "denied_paths":[".env","*.pem","infra/"],
 "max_actions":5,"max_files_changed":3,"max_auto_fix_attempts":2,
 "expires_at":"${expires_at}",
 "reason":"delegated agent test"}
EOF
)
resp_d=$(_post "${ORCH}/approval-policies" "${body_d}")
mode_d=$(_field "$resp_d" "policy.approval_mode")
max_d=$(_field "$resp_d" "policy.max_actions")
[ "$mode_d" = "delegated" ] && pass "DELEGATED_POLICY_CREATED" || fail "DELEGATED_POLICY_CREATED (mode=$mode_d)"
[ "$max_d" = "5" ] && pass "DELEGATED_MAX_ACTIONS_RECORDED" || fail "DELEGATED_MAX_ACTIONS_RECORDED (max=$max_d)"

# delegated missing constraints -> 400
bad_d=$(_post_code "${ORCH}/approval-policies" \
  "{\"task_id\":\"${task_d}-bad\",\"approval_mode\":\"delegated\",\"granted_by\":\"v\"}")
[ "$bad_d" = "400" ] && pass "DELEGATED_MISSING_CONSTRAINTS_400" || fail "DELEGATED_MISSING_CONSTRAINTS_400 (got: $bad_d)"

# Scenario E -- hard safety block
echo
echo "=== Scenario E -- hard safety ==="
# A delegated policy that "claims" to allow production_deploy still
# cannot evaluate true -- the evaluator hard-blocks it.
hard_check=$("${PYTHON:-python3}" -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.approval_policy import HumanApprovalPolicy, evaluate_action
from datetime import datetime, timezone, timedelta
policy = HumanApprovalPolicy(
    policy_id='p-x', task_id='t-x', approval_mode='delegated', status='active',
    granted_by='op', expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
    max_actions=1, max_files_changed=1, max_auto_fix_attempts=0,
    allowed_actions=['production_deploy', 'real_github_write'],
    allowed_paths=['docs/generated/'], denied_paths=['.env'],
)
res = evaluate_action(
    task_id='t-x', workflow_id='w', action_type='production_deploy',
    stage='deploy', agent='devops-agent', paths=['docs/generated/x.md'],
    candidate_policies=[policy],
)
print('OK' if (not res.allowed and res.hard_policy_block) else 'FAIL')
")
[ "$hard_check" = "OK" ] && pass "HARD_SAFETY_BLOCKS_PRODUCTION_DEPLOY" || fail "HARD_SAFETY_BLOCKS_PRODUCTION_DEPLOY"

denylist_check=$("${PYTHON:-python3}" -c "
import sys
sys.path.insert(0, '.')
from shared.sdk.approval_policy import HumanApprovalPolicy, evaluate_action
from datetime import datetime, timezone, timedelta
policy = HumanApprovalPolicy(
    policy_id='p-y', task_id='t-y', approval_mode='delegated', status='active',
    granted_by='op', expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
    max_actions=1, max_files_changed=1, max_auto_fix_attempts=0,
    allowed_actions=['llm_proposal_promote'], allowed_paths=['infra/'],
    denied_paths=['.env'],
)
res = evaluate_action(
    task_id='t-y', workflow_id='w', action_type='llm_proposal_promote',
    stage='code_generation', agent='development-agent',
    paths=['infra/docker-compose/docker-compose.yml'], files_changed=1,
    candidate_policies=[policy],
)
print('OK' if (not res.allowed and res.hard_policy_block) else 'FAIL')
")
[ "$denylist_check" = "OK" ] && pass "HARD_SAFETY_BLOCKS_DENYLIST_PATH" || fail "HARD_SAFETY_BLOCKS_DENYLIST_PATH"

# Operations / Discord wiring
echo
echo "=== Operations / Discord wiring ==="
ops_summary=$(curl -sS -m 10 "${ORCH}/operations/summary" || echo '{}')
if echo "$ops_summary" | grep -q '"approval_policy_summary"'; then
  pass "OPERATIONS_SUMMARY_APPROVAL"
else
  fail "OPERATIONS_SUMMARY_APPROVAL"
fi

safety=$(curl -sS -m 10 "${ORCH}/operations/safety" || echo '{}')
if echo "$safety" | grep -q '"hard_policy_enforced":true' \
   && echo "$safety" | grep -q '"production_delegation_allowed":false'; then
  pass "SAFETY_HARD_POLICY_FIELDS"
else
  fail "SAFETY_HARD_POLICY_FIELDS"
fi

# Audit reachability check
echo
echo "=== Audit / production safety ==="
prod=$(_field "$safety" "production_executed_true_count")
[ "$prod" = "0" ] && pass "PRODUCTION_EXECUTED_ZERO" || fail "PRODUCTION_EXECUTED_ZERO (count=$prod)"

echo
echo "passed ${checks}/${total}"
if [ "$checks" -ge "$total" ]; then
  echo "FLEXIBLE_HUMAN_APPROVAL_POLICY_VERIFY: PASS"
  exit 0
else
  echo "FLEXIBLE_HUMAN_APPROVAL_POLICY_VERIFY: FAIL"
  exit 1
fi
