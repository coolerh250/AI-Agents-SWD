# Real LLM Plan-Only Pilot (Stage 35)

Stage 35 ships a deliberately narrow real-LLM capability:

* the platform may call OpenAI or Anthropic to generate a
  **development plan** (no code),
* every call must clear an active budget policy first,
* the response is parsed, redacted, safety-checked, then persisted
  as an `llm_proposal_artifacts` row of type `development_plan_only`,
* nothing in this path creates a workspace, a code-change artifact,
  a PR draft, or any wire-level change.

The Stage 30 hard rail (`HARD_SAFETY_ACTIONS.real_llm_network_call`)
is unchanged. The plan-only path is the FIRST opt-in opportunity to
exercise that rail; everything else still refuses.

## Required operator inputs

The pilot is opt-in at every layer. The full input set:

| Variable | Required when | Purpose |
|---|---|---|
| `LLM_PROVIDER` | always | one of `mock`, `disabled`, `external_openai_placeholder`, `external_anthropic_placeholder`, `external_openai`, `external_anthropic`. |
| `RUN_REAL_LLM_TEST` | real run | literal string `"true"`. |
| `ENABLE_REAL_LLM_NETWORK_CALL` | real run | literal string `"true"`. |
| `OPENAI_API_KEY` | OpenAI real | bearer key. NEVER logged. |
| `OPENAI_MODEL` | optional | default `gpt-4o-mini`. |
| `ANTHROPIC_API_KEY` | Anthropic real | API key. NEVER logged. |
| `ANTHROPIC_MODEL` | optional | default `claude-3-5-haiku`. |
| `LLM_MAX_TOKENS_PER_TASK` | recommended | mirror of an active policy's cap. |
| `LLM_MAX_COST_PER_TASK_USD` | recommended | likewise. |
| `LLM_MAX_COST_PER_DAY_USD` | required | the day cap. |
| `LLM_MAX_COST_PER_MONTH_USD` | required | the month cap. |
| `LLM_BUDGET_POLICY_MODE` | optional | `block` (default) or `warn_only`. |

Use `scripts/check_llm_runtime_inputs.sh` to confirm the env is
complete WITHOUT printing any key value. The script emits
`REAL_LLM_INPUTS: PRESENT` or `REAL_LLM_TEST_SKIPPED: PASS`
depending on what's set.

## Hard guarantees

The plan-only path enforces six invariants. Each is exercised by
either a unit test or the verify script:

1. **No patch.** `RealLLMPlanOnlyProvider.generate_patch_proposal`
   raises `LLMProviderError` unconditionally.
2. **No test plan.** Same for `generate_test_plan`.
3. **No workspace.** The plan-only operations endpoint does NOT call
   `CodeWorkspaceStore`. The provider module does not import it.
4. **No code change artifact.** No reference to
   `code_change_artifacts` exists in the plan-only path.
5. **No PR draft.** No reference to `pr_draft_artifacts` or
   `PRDraftStore` exists in the plan-only path.
6. **Human review required.** The plan dataclass forces
   `requires_human_review=True` in `__post_init__`; the operations
   endpoint pins the same field to `True`.

## Wire-call sequence

```
operator -> orchestrator (development_plan request)
  -> BudgetPolicyEvaluator.preflight(...)   [llm_budget_events row]
       decision != allowed  ->  abort + audit `llm_budget_exceeded` /
                                `llm_real_test_skipped` /
                                `llm_plan_blocked_by_policy`
  -> RealLLMPlanOnlyProvider.generate_development_plan(...)
       guard ok -> httpx.post to provider URL
       response parsed via _parse_openai_plan / _parse_anthropic_plan
       response text run through prompt_contract.redact_text BEFORE
       it enters the plan's summary / risks / assumptions fields.
  -> apply_llm_safety_policy(plan)
       blocked  -> abort + audit `llm_plan_blocked_by_policy`
  -> LLMInteractionStore.create_interaction(...)
  -> LLMInteractionStore.create_proposal(
         proposal_type="development_plan_only",
         status="proposed",
         requires_human_review=True,
         linked_workspace_id=None,
     )
  -> LLMInteractionStore.record_usage(prompt_tokens, completion_tokens,
                                      estimated_cost)
  -> BudgetPolicyEvaluator.record_usage(...)
  -> audit decision_type = `llm_real_plan_created`
  -> notification event_type = `llm.plan_ready_for_review`
```

The notification event is default-blocked by the Stage 33 real
Discord delivery policy. Operators can widen the allowlist if they
want a Discord ping, but the platform's primary surfacing is via
`/operations/llm/plan-only/{task_id}`.

## Operations surfaces

* `GET /operations/llm/plan-only/{task_id}` returns:
  * `real_llm_used: bool` (true when any interaction.provider starts
    with `external_`),
  * `plan_only: true`,
  * `interactions`: every Stage 30 `llm_interactions` row (with
    redacted previews),
  * `plan_only_proposals`: every proposal with
    `proposal_type=development_plan_only`,
  * `usage_records`: `llm_usage_records` rows,
  * `budget_events`: every `llm_budget_events` row for the task,
  * `requires_human_review: true`,
  * `production_executed: false`.
* `GET /operations/safety` -- see `llm-cost-governance.md` for the
  per-field meaning.
* `GET /operations/llm/budget` + sibling endpoints expose the policy
  + usage view.

## How to verify

```bash
# Inputs presence check -- never prints any key value.
./scripts/check_llm_runtime_inputs.sh

# Budget governance verifier -- runs in both mock + real modes.
./scripts/verify_llm_cost_governance.sh

# Plan-only pilot verifier -- SKIPPED when real env is absent.
./scripts/verify_real_llm_plan_only_pilot.sh

# Runtime smokes from check_runtime_state.sh:
./scripts/check_runtime_state.sh | grep -E 'LLM_BUDGET|REAL_LLM_PLAN|LLM_NO_'
```

## Cleanup / disable

To stop using a real provider, unset the four env variables:

```
unset RUN_REAL_LLM_TEST ENABLE_REAL_LLM_NETWORK_CALL \
      OPENAI_API_KEY ANTHROPIC_API_KEY
```

then `docker compose up -d --force-recreate orchestrator
development-agent` (orchestrator + development-agent are the two
services that hold real env). The integrity chain and budget ledger
remain intact -- past events keep their `llm_budget_events` rows.
