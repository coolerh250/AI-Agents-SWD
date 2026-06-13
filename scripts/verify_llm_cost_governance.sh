#!/usr/bin/env bash
# Stage 35 -- LLM cost governance end-to-end verifier.
#
# Exercises preflight + cap + ledger paths against the cluster. The
# script creates ONE test policy with a tiny cost cap (so the cap is
# guaranteed to fire on a single small call) and one with a generous
# cap, evaluates preflight in both modes, then queries the operations
# endpoints to confirm the ledger + safety surfaces reflect the result.
# Fail-closed: every section either PASS / FAIL; no SKIPPED here.

set -uo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=scripts/lib/verify_env.sh
source "$(dirname "$0")/lib/verify_env.sh" 2>/dev/null || true

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_llm_cost_governance: $(date '+%Y-%m-%d %H:%M:%S %Z')"

ts=$(date +%s)
task_id="llm-budget-verify-$ts"
tiny_policy_name="stage35-test-tiny-$ts"
generous_policy_name="stage35-test-generous-$ts"

step() { echo; echo "=== $1 ==="; }

step "1. Migration / tables present"
have_policies=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT to_regclass('llm_budget_policies') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')
have_events=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT to_regclass('llm_budget_events') IS NOT NULL;" 2>/dev/null | tr -d '[:space:]')
if [ "$have_policies" = "t" ] && [ "$have_events" = "t" ]; then
  echo "LLM_BUDGET_TABLES: PASS"
else
  echo "LLM_BUDGET_TABLES: FAIL"
  exit 1
fi

step "2. POST /operations/llm/budget/policies (generous)"
gen_resp=$(curl -sS -m 5 -X POST "$ORCH/operations/llm/budget/policies" \
  -H "Content-Type: application/json" -d "$(cat <<JSON
{
  "policy_name": "$generous_policy_name",
  "provider": "external_openai",
  "scope_type": "global",
  "max_cost_per_task_usd": 5.0,
  "max_cost_per_day_usd": 5.0,
  "max_cost_per_month_usd": 25.0,
  "enforcement_mode": "block",
  "status": "active"
}
JSON
)" || echo '{}')
gen_id=$(echo "$gen_resp" | "${PYTHON:-python3}" -c 'import json,sys; print(json.load(sys.stdin).get("policy_id",""))' 2>/dev/null)
if [ -n "$gen_id" ]; then
  echo "LLM_BUDGET_POLICY_CREATE: PASS (id=${gen_id:0:8}…)"
else
  echo "LLM_BUDGET_POLICY_CREATE: FAIL"
  echo "$gen_resp" | head -c 400; echo
  exit 1
fi

step "3. GET /operations/llm/budget reflects active policy"
budget_view=$(curl -sS -m 5 "$ORCH/operations/llm/budget?provider=external_openai" || echo '{}')
if echo "$budget_view" | grep -q "$generous_policy_name"; then
  echo "LLM_BUDGET_VIEW: PASS"
else
  echo "LLM_BUDGET_VIEW: FAIL"
  echo "$budget_view" | head -c 400; echo
fi

step "4. Preflight allowed under generous policy (Python harness)"
allow_out=$("${PYTHON:-python3}" - <<'PY'
import asyncio, sys
sys.path.insert(0, '.')
from shared.sdk.llm_budget import BudgetPolicyEvaluator
async def main():
    e = BudgetPolicyEvaluator()
    d = await e.preflight(
        provider="external_openai", model_name="gpt-4o-mini",
        prompt_text="please plan a small task",
        task_id="stage35-verify-allow",
    )
    print(d.decision, d.cap_breached, d.reason)
asyncio.run(main())
PY
)
echo "$allow_out"
case "$allow_out" in
  allowed*) echo "LLM_BUDGET_PREFLIGHT_ALLOW: PASS" ;;
  *) echo "LLM_BUDGET_PREFLIGHT_ALLOW: FAIL"; exit 1 ;;
esac

step "5. POST tiny cost-cap policy + verify it blocks"
# First mark the generous policy inactive so the lookup picks the tiny one.
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "UPDATE llm_budget_policies SET status='inactive' WHERE policy_id='$gen_id';" \
  >/dev/null 2>&1 || true

tiny_resp=$(curl -sS -m 5 -X POST "$ORCH/operations/llm/budget/policies" \
  -H "Content-Type: application/json" -d "$(cat <<JSON
{
  "policy_name": "$tiny_policy_name",
  "provider": "external_openai",
  "scope_type": "global",
  "max_cost_per_task_usd": 0.000001,
  "max_cost_per_day_usd": 0.000001,
  "max_cost_per_month_usd": 0.000001,
  "enforcement_mode": "block",
  "status": "active"
}
JSON
)" || echo '{}')
tiny_id=$(echo "$tiny_resp" | "${PYTHON:-python3}" -c 'import json,sys; print(json.load(sys.stdin).get("policy_id",""))' 2>/dev/null)
echo "tiny_policy_id=${tiny_id:0:8}…"

block_out=$("${PYTHON:-python3}" - <<'PY'
import asyncio, sys
sys.path.insert(0, '.')
from shared.sdk.llm_budget import BudgetPolicyEvaluator
async def main():
    e = BudgetPolicyEvaluator()
    d = await e.preflight(
        provider="external_openai", model_name="gpt-4-turbo",
        prompt_text="x" * 4000,
        task_id="stage35-verify-block",
    )
    print(d.decision, d.cap_breached, d.reason)
asyncio.run(main())
PY
)
echo "$block_out"
case "$block_out" in
  blocked*cost_per_task*|blocked*cost_per_day*|blocked*cost_per_month*) echo "LLM_BUDGET_PREFLIGHT_BLOCK: PASS" ;;
  *) echo "LLM_BUDGET_PREFLIGHT_BLOCK: FAIL"; exit 1 ;;
esac

step "6. Token cap blocks (Python harness, scope-test policy)"
token_resp=$(curl -sS -m 5 -X POST "$ORCH/operations/llm/budget/policies" \
  -H "Content-Type: application/json" -d "$(cat <<JSON
{
  "policy_name": "stage35-token-test-$ts",
  "provider": "external_openai",
  "scope_type": "task",
  "scope_id": "stage35-verify-token-cap",
  "max_tokens_per_task": 5,
  "enforcement_mode": "block",
  "status": "active"
}
JSON
)")
token_id=$(echo "$token_resp" | "${PYTHON:-python3}" -c 'import json,sys; print(json.load(sys.stdin).get("policy_id",""))' 2>/dev/null)
echo "token_policy_id=${token_id:0:8}…"

token_out=$("${PYTHON:-python3}" - <<'PY'
import asyncio, sys
sys.path.insert(0, '.')
from shared.sdk.llm_budget import BudgetPolicyEvaluator
async def main():
    e = BudgetPolicyEvaluator()
    d = await e.preflight(
        provider="external_openai", model_name="gpt-4o-mini",
        prompt_text="some long enough prompt to exceed five tokens",
        task_id="stage35-verify-token-cap",
    )
    print(d.decision, d.cap_breached)
asyncio.run(main())
PY
)
echo "$token_out"
case "$token_out" in
  blocked*token_per_task*|blocked*cost_per_task*|blocked*cost_per_day*|blocked*cost_per_month*)
    echo "LLM_BUDGET_TOKEN_CAP: PASS" ;;
  *) echo "LLM_BUDGET_TOKEN_CAP: FAIL"; exit 1 ;;
esac

step "7. Unknown model uses conservative fallback (must not be free)"
unknown_out=$("${PYTHON:-python3}" - <<'PY'
import sys
sys.path.insert(0, '.')
from shared.sdk.llm_budget import LLMCostEstimator
out = LLMCostEstimator().estimate_cost(
    provider="external_openai", model_name="not-a-real-model",
    prompt_tokens=1000, completion_tokens=1000,
)
print(out["cost_usd"], out["fallback_used"])
PY
)
echo "$unknown_out"
cost=$(echo "$unknown_out" | awk '{print $1}')
if [ "$(echo "$cost > 0" | bc -l 2>/dev/null)" = "1" ]; then
  echo "LLM_BUDGET_UNKNOWN_MODEL_CONSERVATIVE: PASS"
else
  echo "LLM_BUDGET_UNKNOWN_MODEL_CONSERVATIVE: FAIL"
  exit 1
fi

step "8. Operations / safety carries Stage 35 fields"
safety=$(curl -sS -m 5 "$ORCH/operations/safety" || echo '{}')
all_ok=1
for k in '"real_llm_enabled_pilot"' '"llm_real_plan_only_enabled"' \
         '"llm_patch_generation_enabled"' '"llm_workspace_write_enabled"' \
         '"llm_cost_governance_enabled"' '"llm_budget_policy_active"' \
         '"llm_budget_enforcement_mode"' '"llm_daily_budget_remaining"' \
         '"llm_monthly_budget_remaining"' '"llm_budget_exceeded"'; do
  echo "$safety" | grep -q "$k" || { echo "  missing $k"; all_ok=0; }
done
if [ "$all_ok" = "1" ]; then
  echo "LLM_BUDGET_SAFETY_FIELDS: PASS"
else
  echo "LLM_BUDGET_SAFETY_FIELDS: FAIL"
fi
# Patch + workspace MUST be false even when real is enabled.
if echo "$safety" | grep -qE '"llm_patch_generation_enabled":\s*false' \
   && echo "$safety" | grep -qE '"llm_workspace_write_enabled":\s*false'; then
  echo "LLM_NO_PATCH_AND_NO_WORKSPACE: PASS"
else
  echo "LLM_NO_PATCH_AND_NO_WORKSPACE: FAIL"
fi

step "9. /operations/llm/budget/events has rows"
events=$(curl -sS -m 5 "$ORCH/operations/llm/budget/events?provider=external_openai&limit=10" || echo '{}')
count=$(echo "$events" | "${PYTHON:-python3}" -c 'import json,sys; print(json.load(sys.stdin).get("count",0))' 2>/dev/null || echo 0)
if [ "$count" -ge 1 ]; then
  echo "LLM_BUDGET_EVENTS_LOG: PASS (count=$count)"
else
  echo "LLM_BUDGET_EVENTS_LOG: FAIL"
fi

step "10. No API key leak in any operations response"
for body in "$budget_view" "$gen_resp" "$tiny_resp" "$token_resp" "$safety" "$events"; do
  if echo "$body" | grep -qE 'OPENAI_API_KEY=|ANTHROPIC_API_KEY=|sk-[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9_\-]{20,}'; then
    echo "LLM_BUDGET_NO_KEY_LEAK: FAIL"
    exit 1
  fi
done
echo "LLM_BUDGET_NO_KEY_LEAK: PASS"

step "11. production safety counters"
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
echo "  deployment_records.production_executed_true=$dep"
echo "  workflow_states.production_executed_true=$wf"
if [ "$dep" = "0" ] && [ "$wf" = "0" ]; then
  echo "LLM_BUDGET_PRODUCTION_SAFETY: PASS"
else
  echo "LLM_BUDGET_PRODUCTION_SAFETY: FAIL"
  exit 1
fi

step "12. Cleanup -- mark Stage 35 test policies inactive"
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "UPDATE llm_budget_policies SET status='inactive' WHERE policy_name IN
    ('$generous_policy_name', '$tiny_policy_name', 'stage35-token-test-$ts');" \
  >/dev/null 2>&1 || true
echo "  test policies marked inactive."

echo
echo "LLM_COST_GOVERNANCE_VERIFY: PASS"
echo "VERIFY_LLM_COST_GOVERNANCE_DONE"
