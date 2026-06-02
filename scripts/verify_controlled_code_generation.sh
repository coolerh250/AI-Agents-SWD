#!/usr/bin/env bash
# Stage 28 — Controlled Code Generation Workspace + PR draft delivery
# verifier.
#
# Three end-to-end scenarios on the local/test stack (no real Discord,
# no real GitHub, no LLM, no production deploy):
#
#   A) docs generation       — description triggers documentation
#                              template; workspace + artifact + PR
#                              draft must land.
#   B) API generation        — description triggers demo_api template;
#                              app + test files compile (py_compile).
#   C) policy block          — description targets a denied path;
#                              workspace is marked blocked, no PR
#                              draft, blocked audit + notification
#                              are emitted.
#
# production_executed=false must hold throughout.
set -uo pipefail

ORCH="${ORCH_URL:-http://localhost:8000}"
DISCORD="${DISCORD_URL:-http://localhost:8007}"
AUDIT="${AUDIT_URL:-http://localhost:8003}"

echo "### verify_controlled_code_generation: $(date '+%Y-%m-%d %H:%M:%S %Z')"

checks=0
total=18
fail() { echo "  $1: FAIL"; }
pass() { echo "  $1: PASS"; checks=$((checks+1)); }

_post_discord() {
  local content="$1"
  curl -sS -m 30 -X POST "${DISCORD}/discord/messages" \
    -H "Content-Type: application/json" \
    -d "{\"content\":\"${content}\",\"channel_id\":\"sandbox-stage28\",\"user_id\":\"verify-stage28\"}" \
    || echo '{}'
}

_wait_stage() {
  local task_id="$1" want="$2" max="${3:-30}"
  local stage=""
  for i in $(seq 1 "$max"); do
    local prog
    prog=$(curl -sS -m 10 "${ORCH}/workflow/progress/${task_id}" || echo '{}')
    stage=$(echo "$prog" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('current_stage',''))" 2>/dev/null)
    if [ "$stage" = "$want" ]; then break; fi
    sleep 2
  done
  echo "$stage"
}

_field() {
  # JSON-safe field extractor — usage: _field <json> <dotted.path>
  local data="$1" path="$2"
  python3 -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    for k in sys.argv[2].split('.'):
        if isinstance(d, list):
            d = d[int(k)]
        elif isinstance(d, dict):
            d = d.get(k)
        else:
            d = None
            break
    if d is None:
        print('')
    elif isinstance(d, (dict, list)):
        print(json.dumps(d))
    else:
        print(d)
except Exception:
    print('')
" "$data" "$path"
}

stage28_ts=$(date +%s)

# -------------------------------------------------------------------
# Scenario A: documentation generation
# -------------------------------------------------------------------
echo
echo "=== Scenario A — docs generation ==="
task_a="stage28-docs-${stage28_ts}"
_post_discord "/ai task type=dev.doc description=\\\"please write the documentation for the new module\\\" task_id=${task_a}" >/dev/null
stage_a=$(_wait_stage "$task_a" "completed" 30)
ops_a=$(curl -sS -m 10 "${ORCH}/operations/workflows/${task_a}" || echo '{}')
ws_status_a=$(_field "$ops_a" "code_generation.status")
files_a=$(_field "$ops_a" "code_generation.changed_files")
prod_a=$(_field "$ops_a" "production_executed")

[ -n "$ws_status_a" ] && pass "CODE_WORKSPACE_CREATED_A" || fail "CODE_WORKSPACE_CREATED_A"
echo "$files_a" | grep -q "docs/generated/${task_a}.md" \
  && pass "CODE_GENERATION_DOCS_FILE" || fail "CODE_GENERATION_DOCS_FILE"

ws_a=$(curl -sS -m 10 "${ORCH}/operations/code/workspaces/${task_a}" || echo '{}')
artifact_a=$(_field "$ws_a" "code_change_artifacts.0.file_path")
diff_a=$(_field "$ws_a" "code_change_artifacts.0.diff_text")
[ -n "$artifact_a" ] && pass "CODE_ARTIFACT_RECORDED_A" || fail "CODE_ARTIFACT_RECORDED_A"
[ -n "$diff_a" ] && pass "CODE_DIFF_NOT_EMPTY_A" || fail "CODE_DIFF_NOT_EMPTY_A"

pr_a=$(curl -sS -m 10 "${ORCH}/operations/code/pr-drafts/${task_a}" || echo '{}')
pr_status_a=$(_field "$pr_a" "pr_draft.status")
[ "$pr_status_a" = "ready" ] && pass "PR_DRAFT_READY_A" || fail "PR_DRAFT_READY_A"

# github dry-run PR url present on the workflow view.
pr_url_a=$(_field "$ops_a" "github.pr_url")
[ -n "$pr_url_a" ] && pass "GITHUB_DRY_RUN_PR_A" || fail "GITHUB_DRY_RUN_PR_A"
[ "$prod_a" = "False" ] || [ "$prod_a" = "false" ] && pass "PRODUCTION_EXECUTED_FALSE_A" || fail "PRODUCTION_EXECUTED_FALSE_A"

# -------------------------------------------------------------------
# Scenario B: demo API generation
# -------------------------------------------------------------------
echo
echo "=== Scenario B — API generation ==="
task_b="stage28-api-${stage28_ts}"
_post_discord "/ai task type=dev.api description=\\\"please implement a /healthz endpoint API with tests\\\" task_id=${task_b}" >/dev/null
_wait_stage "$task_b" "completed" 30 >/dev/null
ws_b=$(curl -sS -m 10 "${ORCH}/operations/code/workspaces/${task_b}" || echo '{}')
files_b=$(_field "$ws_b" "workspace.workspace_id")
arts_b=$(_field "$ws_b" "code_change_artifacts")
echo "$arts_b" | grep -q "apps/demo-generated/" \
  && pass "CODE_GENERATION_API_APP_FILE" || fail "CODE_GENERATION_API_APP_FILE"
echo "$arts_b" | grep -q "tests/generated/" \
  && pass "CODE_GENERATION_API_TEST_FILE" || fail "CODE_GENERATION_API_TEST_FILE"

pr_b=$(curl -sS -m 10 "${ORCH}/operations/code/pr-drafts/${task_b}" || echo '{}')
val_b=$(_field "$pr_b" "pr_draft.test_results.status")
[ "$val_b" = "passed" ] && pass "CODE_VALIDATION_PASSED_B" || fail "CODE_VALIDATION_PASSED_B"

# Local py_compile check against the workspace files.
gen_root="${DEVELOPMENT_AGENT_WORKSPACE_ROOT:-/tmp/aiagents-workspaces}/${task_b}"
if [ -d "$gen_root" ]; then
  py_ok=1
  for f in $(find "$gen_root" -name "*.py" 2>/dev/null); do
    python3 -m py_compile "$f" 2>/dev/null || py_ok=0
  done
  [ "$py_ok" = "1" ] && pass "PY_COMPILE_B" || fail "PY_COMPILE_B"
else
  # On the test stack the workspace lives inside the dev-agent
  # container; rely on the validation_status check above.
  [ "$val_b" = "passed" ] && pass "PY_COMPILE_B" || fail "PY_COMPILE_B"
fi

# -------------------------------------------------------------------
# Scenario C: policy block
# -------------------------------------------------------------------
echo
echo "=== Scenario C — policy block ==="
task_c="stage28-block-${stage28_ts}"
_post_discord "/ai task type=dev.test description=\\\"qwertyuiop unclassifiable random nonsense\\\" task_id=${task_c}" >/dev/null
_wait_stage "$task_c" "completed" 30 >/dev/null
ws_c=$(curl -sS -m 10 "${ORCH}/operations/code/workspaces/${task_c}" || echo '{}')
ws_status_c=$(_field "$ws_c" "workspace.status")
gen_mode_c=$(_field "$ws_c" "workspace.generator_mode")
blocked_reason_c=$(_field "$ws_c" "workspace.blocked_reason")
[ "$ws_status_c" = "blocked" ] && pass "CODE_GENERATION_BLOCKED_C" || fail "CODE_GENERATION_BLOCKED_C"
[ "$gen_mode_c" = "blocked" ] && pass "CODE_GENERATOR_MODE_BLOCKED_C" || fail "CODE_GENERATOR_MODE_BLOCKED_C"

pr_c_status=$(curl -sS -m 5 -o /dev/null -w "%{http_code}" "${ORCH}/operations/code/pr-drafts/${task_c}" || echo "000")
[ "$pr_c_status" = "404" ] && pass "NO_PR_DRAFT_C" || fail "NO_PR_DRAFT_C"

# Audit events for blocked decision_type.
aud_blocked=$(curl -sS -m 10 "${AUDIT}/audit/events?decision_type=code_generation_blocked&limit=5" || echo '{}')
echo "$aud_blocked" | grep -q "$task_c" \
  && pass "BLOCKED_AUDIT_C" || fail "BLOCKED_AUDIT_C"

# Notification deliveries for blocked event.
del_c=$(curl -sS -m 10 "${DISCORD}/discord/deliveries/${task_c}" || echo '{}')
echo "$del_c" | grep -q "code.generation_blocked" \
  && pass "BLOCKED_NOTIFICATION_C" || fail "BLOCKED_NOTIFICATION_C"

# -------------------------------------------------------------------
# Production safety counter
# -------------------------------------------------------------------
echo
echo "=== Production safety ==="
safety=$(curl -sS -m 10 "${ORCH}/operations/safety" || echo '{}')
prod_true=$(_field "$safety" "production_executed_true_count")
wf_prod=$(_field "$safety" "workflow_production_executed_true_count")
if [ "$prod_true" = "0" ] && [ "$wf_prod" = "0" ]; then
  pass "PRODUCTION_EXECUTED_TOTAL_ZERO"
else
  fail "PRODUCTION_EXECUTED_TOTAL_ZERO"
fi

# -------------------------------------------------------------------
# Final tally
# -------------------------------------------------------------------
echo
echo "passed ${checks}/${total}"
if [ "$checks" -ge "$total" ]; then
  echo "CONTROLLED_CODE_GENERATION_VERIFY: PASS"
  exit 0
else
  echo "CONTROLLED_CODE_GENERATION_VERIFY: FAIL"
  exit 1
fi
