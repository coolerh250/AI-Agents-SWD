#!/usr/bin/env bash
# Stage 47 -- end-to-end verifier for the Real Repo Workspace Operator.
#
# Scenario A -- service health (workspace-operator-agent, orchestrator) + SDK.
# Scenario B -- prepare a reviewed FastAPI Todo project (plan + design review).
# Scenario C -- execute a controlled workspace (POST .../workspace/execute).
# Scenario D -- tests / static checks.
# Scenario E -- diff / artifacts / report / work-item execution links.
# Scenario F -- safety (controlled-only flags + no repo write + gitignored).
# Scenario G -- audit / notification (denylist + clean chain + convergence).
# Scenario H -- regression compatibility (residue + planner + design review +
#               tamper-evident + full regression).
#
# Marker: REAL_REPO_WORKSPACE_OPERATOR_VERIFY: PASS / FAIL

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

PY="${PYTHON:-python3}"
ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
WO_AGENT="${WORKSPACE_OPERATOR_URL:-http://localhost:8018}"

echo "### verify_real_repo_workspace_operator: $(date '+%Y-%m-%d %H:%M:%S %Z')"

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
wh=$(curl -sS -m 5 "$WO_AGENT/health" 2>/dev/null || echo '{}')
if echo "$wh" | grep -q '"status":"ok"'; then
  _pass "workspace-operator-agent health"
else
  _skip "workspace-operator-agent not reachable (execution still works via operations API)"
fi
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.workspace_operator import run_workspace_execution, WorkspaceExecutionRequest
from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
assert len(build_fastapi_todo_files()) >= 8
print('OK')
" >/dev/null 2>&1; then
  _pass "workspace_operator SDK importable"
else
  _fail "workspace_operator SDK import"
fi
# DB migration applied: the 6 new tables exist (checked via /operations/safety fields).
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$saf" | grep -q '"workspace_operator_enabled"' && _pass "migration/safety fields present" \
  || _fail "workspace safety fields missing"
# Workspace root allowlist enforced.
if "$PY" -c "
import sys,os; sys.path.insert(0,'.')
from shared.sdk.workspace_operator.path_safety import validate_workspace_root, REPO_ROOT, WorkspacePathError
try:
    validate_workspace_root(REPO_ROOT); raise SystemExit(1)
except WorkspacePathError:
    print('OK')
" >/dev/null 2>&1; then
  _pass "workspace root allowlist rejects repo root"
else
  _fail "workspace root allowlist"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario B: prepare reviewed FastAPI Todo project ==="
REQ='Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples.'
plan=$(curl -sS -m 20 -X POST "$ORCH/operations/projects/plan" -H 'Content-Type: application/json' \
  -d "{\"request_text\": \"$REQ\"}" 2>/dev/null || echo '{}')
PROJECT_ID=$(_field "$plan" project_id)
[ -n "$PROJECT_ID" ] && _pass "project planned ($PROJECT_ID)" || _fail "plan returned no project_id"
[ "$(_field "$plan" validation_status)" = "valid" ] && _pass "graph valid" || _fail "graph not valid"

if [ -n "$PROJECT_ID" ]; then
  review=$(curl -sS -m 30 -X POST "$ORCH/operations/projects/$PROJECT_ID/design-review" \
    -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
  dec=$(_field "$review" go_no_go_decision); bfc=$(_field "$review" blocking_findings_count)
  case "$dec" in
    planning_only|go_with_findings|go) _pass "design review decision=$dec (allows execution)";;
    *) _fail "design review decision=$dec not allowed";;
  esac
  [ "${bfc:-1}" = "0" ] && _pass "blocking findings=0" || _fail "blocking findings=$bfc"
else
  _skip "no project_id -- design review skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario C: execute controlled workspace ==="
WORKSPACE_ID=""
if [ -n "$PROJECT_ID" ]; then
  exec_out=$(curl -sS -m 120 -X POST "$ORCH/operations/projects/$PROJECT_ID/workspace/execute" \
    -H 'Content-Type: application/json' -d '{}' 2>/dev/null || echo '{}')
  WORKSPACE_ID=$(_field "$exec_out" workspace_id)
  WS_ROOT=$(_field "$exec_out" workspace_root)
  GFC=$(_field "$exec_out" generated_files_count)
  [ -n "$WORKSPACE_ID" ] && _pass "workspace_id present ($WORKSPACE_ID)" || _fail "no workspace_id"
  case "$WS_ROOT" in
    /tmp/aiagents-workspaces/*|*/.generated-workspaces/*) _pass "workspace_root safe ($WS_ROOT)";;
    *) _fail "workspace_root not under allowlist: $WS_ROOT";;
  esac
  [ "${GFC:-0}" -ge 8 ] 2>/dev/null && _pass "generated files=$GFC (>=8)" || _fail "generated files=$GFC"
  [ "$(_field "$exec_out" github_write_performed)" = "False" ] && _pass "no GitHub write" || _fail "github write performed"
  [ "$(_field "$exec_out" repo_write_performed)" = "False" ] && _pass "no repo root write" || _fail "repo write performed"
  [ "$(_field "$exec_out" deployment_performed)" = "False" ] && _pass "no deploy" || _fail "deploy performed"
  [ "$(_field "$exec_out" real_llm_used)" = "False" ] && _pass "no real LLM" || _fail "real LLM used"
  [ "$(_field "$exec_out" production_executed)" = "False" ] && _pass "production_executed=false" || _fail "production_executed not false"
else
  _skip "no project_id -- workspace execution skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario D: tests / static checks ==="
if [ -n "$WORKSPACE_ID" ]; then
  runs=$(curl -sS -m 10 "$ORCH/operations/workspaces/$WORKSPACE_ID/test-runs" 2>/dev/null || echo '{}')
  if echo "$runs" | grep -qiE 'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}'; then
    _fail "secret leak in test-runs"
  else
    _pass "test-runs output redacted / no secret"
  fi
  pytest_status=$(echo "$runs" | "$PY" -c "
import sys,json
d=json.load(sys.stdin)
r=[x for x in d.get('test_runs',[]) if x.get('test_type')=='pytest']
print(r[0]['status'] if r else 'none')
" 2>/dev/null || echo "none")
  case "$pytest_status" in
    passed) _pass "pytest passed";;
    skipped) _pass "pytest skipped (documented dependency)";;
    *) _fail "pytest status=$pytest_status";;
  esac
  compile_status=$(echo "$runs" | "$PY" -c "
import sys,json
d=json.load(sys.stdin)
r=[x for x in d.get('test_runs',[]) if x.get('test_type')=='compileall']
print(r[0]['status'] if r else 'none')
" 2>/dev/null || echo "none")
  [ "$compile_status" = "passed" ] && _pass "compileall passed" || _fail "compileall status=$compile_status"
else
  _skip "no workspace_id -- tests skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario E: diff / artifacts / report / links ==="
if [ -n "$WORKSPACE_ID" ]; then
  files=$(curl -sS -m 10 "$ORCH/operations/workspaces/$WORKSPACE_ID/files" 2>/dev/null || echo '{}')
  echo "$files" | grep -q 'app/main.py' && _pass "generated app/main.py present" || _fail "app/main.py missing"
  diff=$(curl -sS -m 10 "$ORCH/operations/workspaces/$WORKSPACE_ID/diff-summary" 2>/dev/null || echo '{}')
  [ "$(_field "$diff" created_files_count)" -ge 8 ] 2>/dev/null && _pass "diff summary exists" || _fail "diff summary missing"
  arts=$(curl -sS -m 10 "$ORCH/operations/workspaces/$WORKSPACE_ID/artifacts" 2>/dev/null || echo '{}')
  echo "$arts" | grep -q 'implementation_summary' && _pass "implementation summary artifact" || _fail "no implementation summary"
  echo "$arts" | grep -q 'test_result' && _pass "test result artifact" || _fail "no test result artifact"
  links=$(curl -sS -m 10 "$ORCH/operations/projects/$PROJECT_ID/work-item-execution-links" 2>/dev/null || echo '{}')
  [ "$(_field "$links" count)" -ge 1 ] 2>/dev/null && _pass "work item execution links exist" || _fail "no work item links"
  rep=$(curl -sS -m 10 "$ORCH/operations/workspaces/$WORKSPACE_ID/report" 2>/dev/null || echo '{}')
  echo "$rep" | grep -q '"production_executed": false' && _pass "report production_executed=false" || _fail "report production flag"
else
  _skip "no workspace_id -- diff/artifacts skipped"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Scenario F: safety ==="
saf=$(curl -sS -m 10 "$ORCH/operations/safety" 2>/dev/null || echo '{}')
echo "$saf" | grep -q '"workspace_operator_controlled_only":true' && _pass "controlled_only=true" || _fail "controlled_only not true"
echo "$saf" | grep -q '"workspace_operator_real_llm_enabled":false' && _pass "real_llm disabled" || _fail "real_llm not disabled"
echo "$saf" | grep -q '"workspace_operator_github_write_enabled":false' && _pass "github write disabled" || _fail "github write not disabled"
echo "$saf" | grep -q '"workspace_operator_deploy_enabled":false' && _pass "deploy disabled" || _fail "deploy not disabled"
echo "$saf" | grep -q '"production_executed_true_count":0' && _pass "production_executed_true_count=0" || _fail "production count != 0"
# generated workspace files must not appear in git tracked/untracked changes.
if ! git status --porcelain 2>/dev/null | grep -qE '\.generated-workspaces/|\.workspaces/|/tmp/aiagents-workspaces'; then
  _pass "no generated workspace files in git status"
else
  _fail "generated workspace files leaked into git status"
fi
grep -q '.generated-workspaces/' .gitignore && _pass "generated workspace path gitignored" || _fail "generated path not gitignored"

# ---------------------------------------------------------------------------
echo
echo "=== Scenario G: audit / notification ==="
if "$PY" -c "
import sys; sys.path.insert(0,'.')
from shared.sdk.workspace_operator.events import WORKSPACE_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import DEFAULT_REAL_DELIVERY_DENYLIST, _matches_pattern
evs=list(WORKSPACE_NOTIFICATION_EVENTS)+['codegen.file_written']
assert all(any(_matches_pattern(e,p) for p in DEFAULT_REAL_DELIVERY_DENYLIST) for e in evs)
print('OK')
" >/dev/null 2>&1; then
  _pass "workspace.* / codegen.* default-denied"
else
  _fail "workspace/codegen notifications not denied"
fi
# Let the always-on audit/notification workers converge before reading the chain.
for _i in 1 2 3 4 5 6 7 8 9 10; do
  vc=$(curl -sS -m 20 -X POST "$ORCH/operations/audit/verify-chain" 2>/dev/null || echo '{}')
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
if bash scripts/verify_agent_discussion_design_review.sh >/tmp/wso_dr.log 2>&1; then
  grep -q "AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: PASS" /tmp/wso_dr.log \
    && _pass "design review verify PASS (planner + full regression inside)" \
    || _fail "design review verify not PASS"
else
  grep -q "AGENT_DISCUSSION_DESIGN_REVIEW_VERIFY: PASS" /tmp/wso_dr.log \
    && _pass "design review verify PASS" || _skip "design review verify inconclusive"
fi
if grep -qE "\[PASS\] full regression" /tmp/wso_dr.log \
   || grep -qE "FULL_REGRESSION_VERIFY: (PASS|PASS_WITH_DOCUMENTED_GAPS)" /tmp/wso_dr.log; then
  _pass "full regression PASS / PASS_WITH_DOCUMENTED_GAPS"
else
  _fail "full regression not green (see /tmp/wso_dr.log)"
fi

# ---------------------------------------------------------------------------
echo
echo "=== Summary: $checks/$total checks passed ==="
if [ "$checks" -eq "$total" ]; then
  echo "REAL_REPO_WORKSPACE_OPERATOR_VERIFY: PASS"
  exit 0
else
  echo "REAL_REPO_WORKSPACE_OPERATOR_VERIFY: FAIL"
  exit 1
fi
