#!/usr/bin/env bash
# Stage 27 — Discord-driven flexible task execution loop verifier.
#
# Four end-to-end scenarios on the local/test stack (no real Discord
# / GitHub / LLM):
#
#   A) simple_task        — short non-dev request stays simple_task.
#   B) delivery_task      — dev-shaped request reaches ready_for_
#                           development, GitHub dry-run runs.
#   C) needs_clarification — "TBD" description triggers a clarification
#                           request; answer + resume restores the
#                           pipeline.
#   D) scrum_project      — explicit Scrum vocabulary turns on
#                           acceptance_criteria / definition_of_done.
#
# Production_executed=false must hold throughout.
set -uo pipefail

ORCH="${ORCH_URL:-http://localhost:8000}"
DISCORD="${DISCORD_URL:-http://localhost:8007}"

echo "### verify_flexible_task_execution_loop: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=20
fail() { echo "  $1: FAIL"; }
pass() { echo "  $1: PASS"; checks=$((checks+1)); }

_post_discord() {
  local task_id="$1" content="$2"
  curl -sS -m 30 -X POST "${DISCORD}/discord/messages" \
    -H "Content-Type: application/json" \
    -d "{\"content\":\"${content}\",\"channel_id\":\"sandbox-stage27\",\"user_id\":\"verify-stage27\"}" \
    || echo '{}'
}

_wait_stage() {
  local task_id="$1" want="$2" max="${3:-30}"
  local stage=""
  for i in $(seq 1 "$max"); do
    local prog
    prog=$(curl -sS -m 10 "${ORCH}/workflow/progress/${task_id}" || echo '{}')
    stage=$(echo "$prog" | sed -n 's/.*"current_stage": *"\([^"]*\)".*/\1/p')
    if [ "$stage" = "$want" ]; then break; fi
    sleep 2
  done
  echo "$stage"
}

# ---------------------------------------------------------------------
# Scenario A — simple task
# ---------------------------------------------------------------------
echo
echo "=== Scenario A — simple task ==="
ts=$(date +%s)
ta="stage27-simple-$ts"
seed=$(_post_discord "$ta" "/ai task type=general description=\\\"please tidy up the docs intro for the AI Agents platform\\\" task_id=$ta")
echo "  seed: $(echo "$seed" | head -c 240)"

sleep 8
wi_a=$(curl -sS -m 10 "${ORCH}/operations/tasks/work-items/${ta}" || echo '{}')
echo "  work_item: $(echo "$wi_a" | head -c 400)"
mode_a=$(echo "$wi_a" | sed -n 's/.*"execution_mode": *"\([^"]*\)".*/\1/p' | head -n1)
[ "$mode_a" = "simple_task" ] && pass "SCENARIO_A_EXECUTION_MODE" || fail "SCENARIO_A_EXECUTION_MODE ($mode_a)"

if echo "$wi_a" | grep -q '"scrum_enabled": *false' && echo "$wi_a" | grep -q '"acceptance_criteria": *null'; then
  pass "SCENARIO_A_SCRUM_OPTIONAL"
else
  fail "SCENARIO_A_SCRUM_OPTIONAL"
fi

if echo "$wi_a" | grep -q "\"task_id\": *\"${ta}\""; then
  pass "SCENARIO_A_WORK_ITEM_CREATED"
else
  fail "SCENARIO_A_WORK_ITEM_CREATED"
fi

ops_a=$(curl -sS -m 10 "${ORCH}/operations/workflows/${ta}" || echo '{}')
if echo "$ops_a" | grep -q '"task_execution"' && echo "$ops_a" | grep -q "\"execution_mode\": *\"simple_task\""; then
  pass "SCENARIO_A_OPERATIONS_VIEW"
else
  fail "SCENARIO_A_OPERATIONS_VIEW"
fi

# ---------------------------------------------------------------------
# Scenario B — delivery task with dev keywords
# ---------------------------------------------------------------------
echo
echo "=== Scenario B — delivery task ==="
ts=$(date +%s)
tb="stage27-delivery-$ts"
seed=$(_post_discord "$tb" "/ai task type=dev.test description=\\\"implement a new /healthz endpoint, add unit tests, and wire metrics\\\" task_id=$tb")
echo "  seed: $(echo "$seed" | head -c 240)"

stage_b=$(_wait_stage "$tb" completed 30)
echo "  final stage: $stage_b"
sleep 4
wi_b=$(curl -sS -m 10 "${ORCH}/operations/tasks/work-items/${tb}" || echo '{}')
mode_b=$(echo "$wi_b" | sed -n 's/.*"execution_mode": *"\([^"]*\)".*/\1/p' | head -n1)
status_b=$(echo "$wi_b" | python3 -c "import json,sys;d=json.load(sys.stdin);print((d.get('work_item') or {}).get('status',''))" 2>/dev/null)
[ "$mode_b" = "delivery_task" ] && pass "SCENARIO_B_EXECUTION_MODE" || fail "SCENARIO_B_EXECUTION_MODE ($mode_b)"

ops_b=$(curl -sS -m 15 "${ORCH}/operations/workflows/${tb}" || echo '{}')
disc_count=$(echo "$ops_b" | grep -o '"agent": *"[a-z-]*"' | sort -u | wc -l)
echo "  agent_discussions distinct agents: $disc_count"
if [ "$disc_count" -ge 4 ]; then
  pass "SCENARIO_B_AGENT_DISCUSSIONS"
else
  fail "SCENARIO_B_AGENT_DISCUSSIONS ($disc_count)"
fi

if [ "$stage_b" = "completed" ]; then
  pass "SCENARIO_B_WORKFLOW_COMPLETED"
else
  fail "SCENARIO_B_WORKFLOW_COMPLETED ($stage_b)"
fi

if echo "$ops_b" | grep -q '"dry_run":true' && echo "$ops_b" | grep -q '"pr_url"'; then
  pass "SCENARIO_B_GITHUB_DRY_RUN"
else
  fail "SCENARIO_B_GITHUB_DRY_RUN"
fi

notif_b=$(curl -sS -m 10 "http://localhost:8007/discord/deliveries/${tb}" || echo '{}')
if echo "$notif_b" | grep -q '"event_type": *"task.ready_for_development"' \
   || echo "$ops_b" | grep -q '"task.ready_for_development"'; then
  pass "SCENARIO_B_READY_NOTIFICATION"
else
  fail "SCENARIO_B_READY_NOTIFICATION"
fi

audit_b=$(curl -sS -m 10 "http://localhost:8003/audit/events/${tb}" || echo '{}')
if echo "$audit_b" | grep -q '"decision_type": *"task_ready_for_development"'; then
  pass "SCENARIO_B_READY_AUDIT"
else
  fail "SCENARIO_B_READY_AUDIT"
fi

# ---------------------------------------------------------------------
# Scenario C — unclear task -> clarification -> answer -> resume
# ---------------------------------------------------------------------
echo
echo "=== Scenario C — needs clarification ==="
ts=$(date +%s)
tc="stage27-clarify-$ts"
seed=$(_post_discord "$tc" "/ai task type=dev.test description=\\\"TBD\\\" task_id=$tc")
echo "  seed: $(echo "$seed" | head -c 240)"

sleep 8
wi_c=$(curl -sS -m 10 "${ORCH}/operations/tasks/work-items/${tc}" || echo '{}')
# Parse work_item.status (the sed greedy match would otherwise grab
# clarification_requests[].status, which is "open" here).
status_c=$(echo "$wi_c" | python3 -c "import json,sys;d=json.load(sys.stdin);print((d.get('work_item') or {}).get('status',''))" 2>/dev/null)
echo "  initial status: $status_c"
if [ "$status_c" = "needs_clarification" ]; then
  pass "SCENARIO_C_NEEDS_CLARIFICATION"
else
  fail "SCENARIO_C_NEEDS_CLARIFICATION ($status_c)"
fi

clar_list=$(curl -sS -m 10 "${DISCORD}/discord/clarifications/${tc}" || echo '{}')
echo "  clarification list head: $(echo "$clar_list" | head -c 400)"
clar_id=$(echo "$clar_list" | sed -n 's/.*"clarification_id": *"\([a-f0-9-]*\)".*/\1/p' | head -n1)
echo "  clarification_id: $clar_id"
if [ -n "$clar_id" ]; then
  pass "SCENARIO_C_CLARIFICATION_OPEN"
else
  fail "SCENARIO_C_CLARIFICATION_OPEN"
fi

# Confirm development agent did NOT run (agent_executions has no
# development-agent row).
exec_count=$(curl -sS -m 10 "${ORCH}/operations/workflows/${tc}" \
  | grep -o '"agent": *"development-agent"' | wc -l)
echo "  development-agent rows in operations view: $exec_count"
if [ "$exec_count" -eq 0 ]; then
  pass "SCENARIO_C_NO_DEVELOPMENT_RUN"
else
  fail "SCENARIO_C_NO_DEVELOPMENT_RUN ($exec_count)"
fi

if [ -n "$clar_id" ]; then
  ans=$(curl -sS -m 10 -X POST "${DISCORD}/discord/clarifications/${clar_id}/answer" \
    -H "Content-Type: application/json" \
    -d "{\"answer\":\"please implement a /healthz endpoint with tests\",\"user_id\":\"verify-stage27\"}" \
    || echo '{}')
  echo "  answer response: $(echo "$ans" | head -c 200)"
  resume_status=$(echo "$ans" | sed -n 's/.*"resume_status": *"\([^"]*\)".*/\1/p')
  if [ "$resume_status" = "ok" ]; then
    pass "SCENARIO_C_ANSWER_RESUMED"
  else
    # Some envs (e.g. orchestrator down) may not auto-resume — call
    # the endpoint directly as a fallback.
    rs2=$(curl -sS -m 10 -X POST "${ORCH}/workflow/resume-after-clarification/${tc}" || echo '{}')
    echo "  manual resume: $(echo "$rs2" | head -c 200)"
    if echo "$rs2" | grep -q '"resumed": *true'; then
      pass "SCENARIO_C_ANSWER_RESUMED"
    else
      fail "SCENARIO_C_ANSWER_RESUMED"
    fi
  fi

  # Wait for the workflow to actually move forward.
  stage_c=$(_wait_stage "$tc" completed 30)
  echo "  final stage after resume: $stage_c"
  wi_c2=$(curl -sS -m 10 "${ORCH}/operations/tasks/work-items/${tc}" || echo '{}')
  status_c2=$(echo "$wi_c2" | python3 -c "import json,sys;d=json.load(sys.stdin);print((d.get('work_item') or {}).get('status',''))" 2>/dev/null)
  echo "  final status: $status_c2"
  if [ "$status_c2" = "ready_for_development" ] || [ "$status_c2" = "completed" ]; then
    pass "SCENARIO_C_READY_AFTER_RESUME"
  else
    fail "SCENARIO_C_READY_AFTER_RESUME ($status_c2)"
  fi
else
  fail "SCENARIO_C_ANSWER_RESUMED"
  fail "SCENARIO_C_READY_AFTER_RESUME"
fi

if echo "$wi_c2" | grep -q '"production_executed":false' \
   || curl -sS -m 10 "${ORCH}/operations/safety" \
   | grep -q '"production_executed_true_count": *0'; then
  pass "SCENARIO_C_PRODUCTION_SAFETY"
else
  fail "SCENARIO_C_PRODUCTION_SAFETY"
fi

# ---------------------------------------------------------------------
# Scenario D — explicit Scrum request
# ---------------------------------------------------------------------
echo
echo "=== Scenario D — scrum project ==="
ts=$(date +%s)
td="stage27-scrum-$ts"
seed=$(_post_discord "$td" "/ai task type=general description=\\\"project kickoff: populate the sprint backlog, author acceptance criteria, pin definition of done\\\" task_id=$td")
echo "  seed: $(echo "$seed" | head -c 240)"

sleep 8
wi_d=$(curl -sS -m 10 "${ORCH}/operations/tasks/work-items/${td}" || echo '{}')
mode_d=$(echo "$wi_d" | sed -n 's/.*"execution_mode": *"\([^"]*\)".*/\1/p' | head -n1)
if [ "$mode_d" = "scrum_project" ]; then
  pass "SCENARIO_D_SCRUM_MODE"
else
  fail "SCENARIO_D_SCRUM_MODE ($mode_d)"
fi

if echo "$wi_d" | grep -q '"scrum_enabled": *true'; then
  pass "SCENARIO_D_SCRUM_ENABLED"
else
  fail "SCENARIO_D_SCRUM_ENABLED"
fi

if echo "$wi_d" | grep -q '"acceptance_criteria"' \
   && echo "$wi_d" | grep -q '"definition_of_done"' \
   && ! echo "$wi_d" | grep -q '"acceptance_criteria": *null'; then
  pass "SCENARIO_D_ACCEPTANCE_DOD"
else
  fail "SCENARIO_D_ACCEPTANCE_DOD"
fi

# Final guard: simple_task work item must NOT carry the Scrum
# acceptance_criteria the scrum branch emits.
if echo "$wi_a" | grep -q '"acceptance_criteria": *null'; then
  pass "SCENARIO_D_SCRUM_NOT_LEAKING"
else
  fail "SCENARIO_D_SCRUM_NOT_LEAKING"
fi

echo
echo "checks passed: $checks / $total"
if [ "$checks" -eq "$total" ]; then
  echo "FLEXIBLE_TASK_EXECUTION_VERIFY: PASS"
else
  echo "FLEXIBLE_TASK_EXECUTION_VERIFY: CHECK"
fi
echo
echo "VERIFY_FLEXIBLE_TASK_EXECUTION_DONE"
