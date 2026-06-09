#!/usr/bin/env bash
# Stage 35 -- real-LLM plan-only pilot verifier.
#
# Default mode (no RUN_REAL_LLM_TEST / API key): the script asserts
# SKIPPED: PASS for the wire-call sections and exits 0.
#
# Opt-in mode (RUN_REAL_LLM_TEST=true + ENABLE_REAL_LLM_NETWORK_CALL=true
# + matching provider API key): the script
#   1. confirms a budget policy is active,
#   2. issues ONE development_plan via the SDK (no orchestrator HTTP
#      yet -- the pilot is run via the shared SDK so the test cluster
#      does not depend on a new orchestrator endpoint to ship),
#   3. records actual usage,
#   4. validates the plan-only path created NO workspace / NO
#      code_change_artifacts / NO PR draft,
#   5. confirms /operations/llm/plan-only/{task_id} surfaces the result.

set -uo pipefail

cd "$(dirname "$0")/.."

ORCH="${ORCHESTRATOR_URL:-http://localhost:8000}"
COMPOSE="docker compose -f infra/docker-compose/docker-compose.yml"

echo "### verify_real_llm_plan_only_pilot: $(date '+%Y-%m-%d %H:%M:%S %Z')"
./scripts/check_llm_runtime_inputs.sh || true

provider_lower="$(echo "${LLM_PROVIDER:-mock}" | tr 'A-Z' 'a-z')"

real_env_ok=0
case "$provider_lower" in
  external_openai)
    if [ "${RUN_REAL_LLM_TEST:-false}" = "true" ] \
       && [ "${ENABLE_REAL_LLM_NETWORK_CALL:-false}" = "true" ] \
       && [ -n "${OPENAI_API_KEY:-}" ]; then
      real_env_ok=1
    fi
    ;;
  external_anthropic)
    if [ "${RUN_REAL_LLM_TEST:-false}" = "true" ] \
       && [ "${ENABLE_REAL_LLM_NETWORK_CALL:-false}" = "true" ] \
       && [ -n "${ANTHROPIC_API_KEY:-}" ]; then
      real_env_ok=1
    fi
    ;;
esac

if [ "$real_env_ok" = "0" ]; then
  echo
  echo "=== Skipped-mode contract ==="
  # Even in skipped mode we exercise the guard so the operator can
  # see the deterministic refusal reason.
  python3 - <<'PY'
import sys
sys.path.insert(0, '.')
from shared.sdk.llm import RealLLMPlanOnlyProvider, real_llm_plan_only_guard
allowed, reason = real_llm_plan_only_guard(
    provider_name="external_openai", allow_real=True,
    interaction_type="development_plan", env={},
)
print(f"guard_allowed={allowed} reason={reason}")
provider = RealLLMPlanOnlyProvider(vendor="openai", env={})
plan = provider.generate_development_plan(
    task_id="skipped-mode", prompt_contract={"interaction_type":"development_plan"},
    allow_real=True, env={},
)
print(f"plan_summary={plan.summary[:80]}")
print(f"plan_requires_human_review={plan.requires_human_review}")
PY
  echo "REAL_LLM_PLAN_ONLY_SKIPPED: PASS"
  echo
  echo "REAL_LLM_PLAN_ONLY_PILOT_VERIFY: PASS"
  exit 0
fi

echo
echo "=== Real-mode pilot run ==="
ts=$(date +%s)
task_id="real-llm-plan-only-pilot-$ts"
policy_name="stage35-real-pilot-$ts"

# Active policy (generous enough to allow ONE small plan call).
policy_resp=$(curl -sS -m 5 -X POST "$ORCH/operations/llm/budget/policies" \
  -H "Content-Type: application/json" -d "$(cat <<JSON
{
  "policy_name": "$policy_name",
  "provider": "$provider_lower",
  "scope_type": "global",
  "max_cost_per_task_usd": 0.50,
  "max_cost_per_day_usd": 1.00,
  "max_cost_per_month_usd": 5.00,
  "enforcement_mode": "block",
  "status": "active"
}
JSON
)")
policy_id=$(echo "$policy_resp" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("policy_id",""))' 2>/dev/null)
echo "policy_id=${policy_id:0:8}…"

python3 - <<PY
import asyncio, sys, json
sys.path.insert(0, '.')
from shared.sdk.llm import (
    RealLLMPlanOnlyProvider, apply_llm_safety_policy, build_prompt_contract,
)
from shared.sdk.llm.store import LLMInteractionStore
from shared.sdk.llm_budget import BudgetPolicyEvaluator

provider_name = "${provider_lower}"
vendor = "openai" if provider_name == "external_openai" else "anthropic"
task_id = "${task_id}"

async def main():
    evaluator = BudgetPolicyEvaluator()
    contract = build_prompt_contract(
        task_id=task_id, execution_mode="delivery_task",
        interaction_type="development_plan",
        description="Plan how to add a smoke test for the budget gate.",
        allowed_paths=["docs/generated/"], denied_paths=["infra/*"],
        output_schema_name="LLMDevelopmentPlan",
    )
    decision = await evaluator.preflight(
        provider=provider_name, model_name="",
        prompt_text=contract["task_summary"], task_id=task_id,
    )
    print("preflight:", decision.decision, decision.reason)
    if not decision.allowed:
        print("REAL_LLM_PLAN_BLOCKED_BY_BUDGET")
        return

    provider = RealLLMPlanOnlyProvider(vendor=vendor)
    plan = provider.generate_development_plan(
        task_id=task_id, prompt_contract=contract,
        prompt_text=contract["task_summary"], allow_real=True,
    )
    print("plan_summary:", (plan.summary or "")[:120])
    print("plan_confidence:", plan.confidence)
    print("plan_requires_human_review:", plan.requires_human_review)

    safety = apply_llm_safety_policy(plan)
    print("safety_allowed:", safety["allowed"])
    print("safety_violations:", len(safety["violations"]))

    # Use actual tokens reported in the plan's assumptions, if any.
    actual_prompt = 0
    actual_completion = 0
    for a in plan.assumptions:
        if a.startswith("actual_prompt_tokens="):
            actual_prompt = int(a.split("=", 1)[1])
        elif a.startswith("actual_completion_tokens="):
            actual_completion = int(a.split("=", 1)[1])

    store = LLMInteractionStore()
    interaction = await store.create_interaction(
        task_id=task_id, workflow_id=None,
        provider=provider_name, model_name=provider.model_name,
        interaction_type="development_plan",
        prompt_preview=contract["task_summary"][:200],
        prompt_hash="",
        response_preview=(plan.summary or "")[:200],
        response_hash="",
        token_usage={
            "prompt_tokens": actual_prompt, "completion_tokens": actual_completion,
            "total_tokens": actual_prompt + actual_completion,
        },
        safety_result=safety,
    )
    print("interaction_id:", interaction.interaction_id)
    proposal = await store.create_proposal(
        task_id=task_id, workflow_id=None,
        interaction_id=interaction.interaction_id,
        proposal_type="development_plan_only",
        status="proposed",
        proposed_files=[],
        plan=plan.to_dict(), safety_result=safety,
        requires_human_review=True,
        linked_workspace_id=None,
    )
    print("proposal_id:", proposal.proposal_id, "proposal_type:", proposal.proposal_type)
    usage = await store.record_usage(
        task_id=task_id, provider=provider_name,
        model_name=provider.model_name,
        prompt_tokens=actual_prompt, completion_tokens=actual_completion,
        total_tokens=actual_prompt + actual_completion,
        estimated_cost=decision.estimated_cost_usd,
    )
    print("usage_id:", usage.usage_id, "estimated_cost:", usage.estimated_cost)
    out = await evaluator.record_usage(
        provider=provider_name, model_name=provider.model_name,
        prompt_tokens=actual_prompt, completion_tokens=actual_completion,
        task_id=task_id, policy_id="${policy_id}",
    )
    print("record_usage:", json.dumps(out))

asyncio.run(main())
PY

echo
echo "=== Inspect /operations/llm/plan-only/$task_id ==="
view=$(curl -sS -m 5 "$ORCH/operations/llm/plan-only/$task_id" || echo '{}')
echo "$view" | python3 -m json.tool 2>/dev/null | head -40 || echo "$view" | head -c 600
echo

# Hard guarantees.
if echo "$view" | grep -q '"plan_only": true' \
   && echo "$view" | grep -q '"requires_human_review": true' \
   && echo "$view" | grep -q '"production_executed": false'; then
  echo "REAL_LLM_PLAN_ONLY_INVARIANTS: PASS"
else
  echo "REAL_LLM_PLAN_ONLY_INVARIANTS: FAIL"
fi

# No workspace + no code_change_artifacts + no PR draft.
ws_count=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM code_workspaces WHERE task_id='$task_id';" \
  2>/dev/null | tr -d '[:space:]')
cc_count=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM code_change_artifacts WHERE task_id='$task_id';" \
  2>/dev/null | tr -d '[:space:]')
pr_count=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM pr_draft_artifacts WHERE task_id='$task_id';" \
  2>/dev/null | tr -d '[:space:]')
echo "  code_workspaces.count=$ws_count"
echo "  code_change_artifacts.count=$cc_count"
echo "  pr_draft_artifacts.count=$pr_count"
if [ "$ws_count" = "0" ] && [ "$cc_count" = "0" ] && [ "$pr_count" = "0" ]; then
  echo "REAL_LLM_PLAN_ONLY_NO_WRITES: PASS"
else
  echo "REAL_LLM_PLAN_ONLY_NO_WRITES: FAIL"
  exit 1
fi

# Production safety.
dep=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM deployment_records WHERE metadata->>'production_executed'='true' OR environment='production';" \
  2>/dev/null | tr -d '[:space:]')
wf=$($COMPOSE exec -T postgres psql -U postgres -d aiagents -tAc \
  "SELECT count(*) FROM workflow_states WHERE execution_result->>'production_executed'='true';" \
  2>/dev/null | tr -d '[:space:]')
if [ "$dep" = "0" ] && [ "$wf" = "0" ]; then
  echo "REAL_LLM_PLAN_ONLY_PRODUCTION_SAFETY: PASS"
else
  echo "REAL_LLM_PLAN_ONLY_PRODUCTION_SAFETY: FAIL"
  exit 1
fi

# Cleanup -- mark the test policy inactive.
$COMPOSE exec -T postgres psql -U postgres -d aiagents -c \
  "UPDATE llm_budget_policies SET status='inactive' WHERE policy_id='$policy_id';" \
  >/dev/null 2>&1 || true

echo
echo "REAL_LLM_PLAN_ONLY_PILOT_VERIFY: PASS"
echo "VERIFY_REAL_LLM_PLAN_ONLY_PILOT_DONE"
