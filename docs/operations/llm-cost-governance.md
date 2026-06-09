# LLM Cost Governance (Stage 35)

Stage 35 makes every LLM call pay attention to a budget. Two new
tables sit beside the existing `llm_*` tables (which are not
modified):

* `llm_budget_policies` -- per-scope cost / token caps (global, task,
  workflow, user, provider).
* `llm_budget_events` -- one row per preflight / recorded usage /
  budget_exceeded / budget_warning decision.

The mock provider is exempt (always $0 / 0 tokens), but every
**real** LLM call now MUST clear an active policy before it touches
the wire. No active policy = blocked. This is the contract that makes
Step 34's plan-only pilot safe to run.

## Decision flow

```
caller -> BudgetPolicyEvaluator.preflight(task_id, workflow_id,
                                          provider, model,
                                          prompt_text / token_count)
    1. estimate tokens (4-chars-per-token heuristic) + cost (per-1K
       USD from DEFAULT_PRICING; unknown model -> most expensive
       fallback)
    2. lookup active policy (task > workflow > user > provider > global)
    3. evaluate caps in order: token_per_task, cost_per_task,
       cost_per_day, cost_per_month
    4. decision: allowed | blocked | warning
    5. INSERT llm_budget_events.event_type=preflight
    -> return BudgetDecision
```

After the LLM call lands:

```
caller -> BudgetPolicyEvaluator.record_usage(provider, model,
                                            prompt_tokens, completion_tokens,
                                            task_id, policy_id,
                                            actual_cost_usd)
    1. INSERT llm_budget_events.event_type=recorded_usage
    2. if cumulative usage breached a cap, ALSO INSERT
       event_type=budget_exceeded so operators see the breach
       without scanning the whole ledger.
```

## Default pricing (per 1K tokens, USD)

Conservative defaults; an operator can override the table by
constructing `LLMCostEstimator(pricing=...)`. Unknown models fall
back to the MOST expensive entry in the provider's table so a
misconfiguration cannot silently approve a $0 estimate.

| Provider             | Model                | Prompt   | Completion |
|----------------------|----------------------|----------|------------|
| external_openai      | gpt-4o               | $0.005   | $0.015     |
| external_openai      | gpt-4o-mini          | $0.00015 | $0.0006    |
| external_openai      | gpt-4-turbo          | $0.01    | $0.03      |
| external_openai      | gpt-3.5-turbo        | $0.0005  | $0.0015    |
| external_anthropic   | claude-3-5-sonnet    | $0.003   | $0.015     |
| external_anthropic   | claude-3-5-haiku     | $0.0008  | $0.004     |
| external_anthropic   | claude-3-opus        | $0.015   | $0.075     |
| external_anthropic   | claude-3-sonnet      | $0.003   | $0.015     |
| external_anthropic   | claude-3-haiku       | $0.00025 | $0.00125   |
| mock                 | mock-deterministic   | $0       | $0         |

## Budget policy schema

```sql
llm_budget_policies (
  policy_id            UUID PRIMARY KEY,
  policy_name          TEXT NOT NULL,
  scope_type           TEXT NOT NULL,           -- global|task|workflow|user|provider
  scope_id             TEXT,
  provider             TEXT NOT NULL,
  model_name           TEXT,
  max_tokens_per_task  INTEGER,
  max_cost_per_task_usd  NUMERIC(12,6),
  max_cost_per_day_usd   NUMERIC(12,6),
  max_cost_per_month_usd NUMERIC(12,6),
  enforcement_mode     TEXT NOT NULL DEFAULT 'block',  -- block|warn_only
  status               TEXT NOT NULL DEFAULT 'active', -- active|inactive|expired
  created_by           TEXT,
  created_at           TIMESTAMPTZ,
  updated_at           TIMESTAMPTZ,
  metadata             JSONB
)
```

Each `llm_budget_events` row carries the decision + reason +
remaining budget (where defined) + the estimated / actual tokens and
cost; the row never contains a prompt body, response body, or API key.

## Operations endpoints

| Endpoint                              | Returns                                                                |
|---------------------------------------|------------------------------------------------------------------------|
| `GET /operations/llm/budget`          | active policies + usage summary for an optional `?provider=` filter    |
| `GET /operations/llm/budget/policies` | list policies (status / provider filter)                               |
| `POST /operations/llm/budget/policies`| create a new policy                                                    |
| `GET /operations/llm/budget/usage`    | daily + monthly usage summary; per-task usage when `?task_id=` is set  |
| `GET /operations/llm/budget/events`   | list budget events (provider / task / event_type / decision filter)    |
| `GET /operations/llm/plan-only/{task_id}` | the Stage 35 per-task plan-only summary (interactions, proposals, usage, budget events) |

`GET /operations/safety` now carries:

* `real_llm_enabled_pilot`
* `llm_real_plan_only_enabled`
* `llm_patch_generation_enabled` -- **always `false`** in Stage 35
* `llm_workspace_write_enabled`  -- **always `false`** in Stage 35
* `llm_cost_governance_enabled`
* `llm_budget_policy_active`
* `llm_budget_enforcement_mode`
* `llm_daily_budget_remaining`
* `llm_monthly_budget_remaining`
* `llm_budget_exceeded`

None of these fields carries an API key value.

## Audit decision types

The orchestrator + audit pipeline reserve these `decision_type`
strings for Stage 35:

* `llm_budget_policy_created`
* `llm_budget_preflight_allowed`
* `llm_budget_exceeded`
* `llm_real_plan_created`
* `llm_plan_blocked_by_policy`
* `llm_real_test_skipped`

`artifact_refs` for each audit row carries: `provider`, `model_name`,
`token_usage` (tokens in / out / total), `estimated_cost`,
`actual_cost`, `budget_policy_id`, `budget_decision`, `real_llm_used`,
`plan_only=true`, `production_executed=false`. **It never carries a
prompt body, response body, or API key.**

## Notification events

Stage 35 reserves these `event_type` values:

* `llm.plan_ready_for_review`
* `llm.budget_exceeded`
* `llm.real_test_skipped`
* `llm.plan_blocked_by_policy`

These events live in `stream.notifications`. The Stage 33 default-deny
policy denies `llm.*` -- meaning these notifications are **not** sent
to real Discord by default. An operator who wants to surface them on
Discord must add the event_type to `REAL_DISCORD_ALLOWLIST` and
restart the notification-worker. The Stage 32 endpoint guard remains
in force on the explicit `/discord/real/*` routes.

## Metrics

Stage 35 adds these Prometheus counters (audit-worker /
orchestrator):

| Counter                          | Labels                       | Meaning                                |
|----------------------------------|------------------------------|----------------------------------------|
| `llm_budget_preflight_total`     | provider, decision, reason   | per preflight evaluation               |
| `llm_budget_allowed_total`       | provider, model              | preflights returning allowed           |
| `llm_budget_blocked_total`       | provider, reason             | preflights returning blocked           |
| `llm_real_plan_calls_total`      | provider, model, result      | real plan-only calls attempted         |
| `llm_real_plan_blocked_total`    | provider, reason             | real plan-only calls blocked           |
| `llm_cost_usd_total`             | provider, model              | cumulative USD spent                   |
| `llm_tokens_total`               | provider, model, kind        | tokens consumed (prompt/completion/total) |

Stage 35 spans: `llm_budget.preflight`, `llm_budget.record_usage`,
`llm_provider.real_plan_call`, `llm_provider.plan_schema_validate`,
`llm_provider.plan_policy_validate`, `llm_provider.plan_persist`.
Span attributes: `task_id`, `workflow_id`, `provider`, `model`,
`estimated_cost`, `actual_cost`, `budget_decision`,
`real_llm=true|false`.

## Limitations

* The estimator uses a coarse 4-chars-per-token heuristic. This is
  intentionally a slight over-estimate for English; budget caps stay
  on the conservative side. Operators with very different prompt
  shapes should override the pricing table.
* Pricing is static. The DEFAULT_PRICING table must be updated when a
  provider revises its rates. Until then, the platform errs on the
  side of "old prices" which today are usually higher than current --
  again, conservative.
* The default-deny on `llm.*` notifications means operators won't see
  a Discord ping when a budget exceeds. The `/operations/safety` +
  `/operations/llm/budget` endpoints + Prometheus alerts are the
  designated discovery surfaces.
* HMAC + multi-key audit chain rotation (carry-forward from Step 33)
  is still future work -- see
  [`tamper-evident-audit.md`](tamper-evident-audit.md).
* The audit-service direct-POST `/audit/events` path (carry-forward
  from Step 33) does not write integrity records inline; the backfill
  cadence is the operator's recovery tool until that path is moved
  through `stream.audit`.
