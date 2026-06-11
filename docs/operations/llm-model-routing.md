# LLM Model Routing & Agent Model Policy (Stage 38)

Stage 38 centralises every "which model do we use for this LLM
call?" decision. Agents no longer pick models. Agents submit a
standardised :class:`LLMCapabilityRequest` describing **what
capability** they need (classification / requirement_analysis /
development_plan / qa_review / ...), plus risk level, schema,
estimated tokens, and (optionally) a *preference* for a model
alias. The :class:`ModelRouter` consults three new tables and
returns an :class:`LLMRoutingDecision`.

> Stage 38 is NOT a real-LLM rollout. Real providers are still
> default-disabled. Patch generation and workspace write remain
> hard-disabled. The router gates real-LLM intent through the
> Stage 35 budget evaluator and the existing Stage 30 + Stage 35
> safety rails.

## Architecture

```
agent
  |
  +-- build_capability_request(agent_name, capability, risk, schema, ...)
  |
  v
ModelRouter.route(request, persist=True)
  |  1. hard safety rails (patch=False, workspace=False)
  |  2. agent_model_policies lookup (default-deny)
  |  3. requested_model_alias allowed by policy?
  |     -> if no => direct_model_rejected
  |  4. critical risk & not allow_real_llm
  |     -> human_approval_required
  |  5. candidate models from registry (preferred + fallbacks)
  |  6. model-side gates: status / provider / tier / capability / schema
  |  7. policy cost / token caps
  |  8. Stage 35 BudgetPolicyEvaluator (optional)
  |  9. selected | mock_selected | fallback_selected
  |  v
llm_routing_decisions (persisted)
audit_logs (decision_type=llm_model_routing_*)
notification deliveries (llm.routing_* events; default-blocked)
metrics (llm_model_routing_*)
spans (llm_routing.request / load_policy / ...)
```

## Agent capability request

Agents construct one of these per LLM call. Required fields:

| Field | Type | Notes |
|-------|------|-------|
| `agent_name` | string | one of the pipeline agents (intake-agent, requirement-agent, development-agent, qa-agent, devops-agent, ...) |
| `capability` | string | from the standard vocabulary (classification, summarization, requirement_analysis, clarification_question, development_plan, test_plan, qa_review, policy_review, documentation, delivery_risk_review, rollback_plan, code_patch_proposal, embedding) |
| `task_id` | string | optional but recommended; used by /operations/llm/routing-decisions/{task_id} |
| `workflow_id` | string | optional |
| `task_type` | string | default `default`; used by policy lookup |
| `risk_level` | string | `low` / `medium` / `high` / `critical` |
| `requested_schema` | string | e.g. `LLMDevelopmentPlan`, `QAReviewReport`. Optional. If supplied the model must declare it in `supported_schemas`. |
| `requested_model_alias` | string | **preference only**; the router rejects with `direct_model_rejected` when the alias is not in the policy's allowed set. **Agents may NOT bypass the router via this field.** |
| `estimated_input_tokens` | int | drives the policy cost cap. |
| `max_output_tokens` | int | optional. |
| `allow_real_llm_requested` | bool | request a real provider; the router still needs the policy + model to authorise it. |
| `allow_patch_generation_requested` | bool | **hard-disabled at the router. Always returns blocked.** |
| `allow_workspace_write_requested` | bool | **hard-disabled at the router. Always returns blocked.** |

The router accepts `LLMCapabilityRequest` only; bare provider /
model calls in agent code are flagged by
`tests/test_no_direct_model_selection.py`.

## Model registry

`llm_model_registry` is the catalogue of allowed providers + models
with capability declarations, schema support, cost, tier, status,
and hard-safety flags.

| Tier | Meaning |
|------|---------|
| `tier_1_critical_reasoning` | high-end reasoning; cost + risk both high; always requires_human_review=true |
| `tier_2_development_qa` | dev plan / qa review / requirement analysis. |
| `tier_3_documentation_classification` | docs / summarisation / triage. |
| `tier_4_lightweight_embedding` | embedding / smallest classification. |

| Status | Meaning |
|--------|---------|
| `active` | available to the router. |
| `inactive` | not picked by the router; operator-decided. |
| `deprecated` | still picked but emits a warning. |
| `blocked` | never picked. |

The default seed (`shared/sdk/llm_routing/registry.py::DEFAULT_MODEL_SEED`)
ships:

* `mock-default` (mock; active; all capabilities; plan_only_allowed=true)
* `mock-lightweight` (mock; active; classification / summarisation / embedding)
* `openai-plan-only` (external_openai; **inactive by default**; plan_only_allowed=true)
* `anthropic-plan-only` (external_anthropic; **inactive by default**; plan_only_allowed=true)

No seed entry has `patch_generation_allowed`,
`workspace_write_allowed`, or `production_use_allowed` set to
true. The store enforces False at the SQL boundary
(`ModelRouterStore.upsert_model`); the dataclass + validator reject
any attempt to flip these.

## Agent model policy

`agent_model_policies` is the per (agent_name, task_type,
capability, risk_level) policy. **Default-deny**: when the router
cannot find an active policy, it returns
`DECISION_POLICY_NOT_FOUND`.

The default seed
(`shared/sdk/llm_routing/policy.py::DEFAULT_AGENT_POLICY_SEED`)
covers:

* `intake-agent` -- `classification`, `summarization` (lightweight; allow_real_llm=false)
* `requirement-agent` -- `requirement_analysis`, `clarification_question`
* `development-agent` -- `development_plan` (medium risk; requires_human_review=true)
* `qa-agent` -- `qa_review`, `test_plan` (advisory only; requires_human_review=true)
* `devops-agent` -- `delivery_risk_review`, `rollback_plan` (high risk; requires_human_review=true)
* `documentation-agent` -- `documentation` (low risk; mock by default)

Every seeded policy sets `allow_real_llm=false`,
`allow_patch_generation=false`, `allow_workspace_write=false`.
Operators may flip `allow_real_llm` on a per-policy basis; the
hard-disabled patch + workspace flags are enforced at the SQL
boundary.

## Routing decision lifecycle

```
agent submits LLMCapabilityRequest
  |
  v
ModelRouter.route(request, persist=True)
  |
  v
LLMRoutingDecision
  decision = selected | mock_selected | fallback_selected |
             blocked | budget_blocked | schema_unsupported |
             provider_unavailable | policy_not_found |
             human_approval_required | direct_model_rejected
  selected_provider / selected_model_name / selected_model_alias /
  selected_model_tier
  fallback_used (bool)
  estimated_input_tokens / estimated_output_tokens / estimated_cost_usd
  requires_human_review
  real_llm_allowed
  patch_generation_allowed = False   (hard)
  workspace_write_allowed  = False   (hard)
  violations / warnings
  |
  v
llm_routing_decisions (persisted)
```

## Budget integration (Stage 35)

When the router is constructed with a `BudgetPolicyEvaluator`
(`Stage 35`), real-provider routes call
`evaluator.preflight(provider, model_name, prompt_text="", task_id,
workflow_id)` before selection. A `budget_blocked` decision is
returned if the evaluator refuses. Mock provider routes skip this
call (mock is always $0 / 0 tokens).

## Schema compatibility

The router refuses to select a model that does not declare the
requested schema:

* `requested_schema=None` -- no constraint.
* `requested_schema="LLMDevelopmentPlan"` -- the model's
  `supported_schemas` must contain that string.

## Fallback behavior

* Preferred model unavailable / mismatched -> attempt
  `policy.fallback_model_aliases` in order.
* Fallback selected -> `decision=fallback_selected`,
  `fallback_used=true`. Audit + metric counters both record the
  fallback.
* Fallback exhausted -> `blocked` (or the specific reason that
  pushed every candidate out: schema_unsupported,
  provider_unavailable, ...).

## Human review requirement

`requires_human_review=true` on the decision when ANY of:

* `policy.requires_human_review=true`.
* `model.requires_human_review=true`.
* `risk_level in ("high", "critical")`.

A `critical` risk with `policy.allow_real_llm=false` immediately
returns `human_approval_required`.

## Direct model selection rejection

`requested_model_alias` is a **preference**. If the requested
alias is not the policy's `preferred_model_alias` and not in
`policy.fallback_model_aliases`, the router returns
`direct_model_rejected` -- the agent is denied.

## No patch / no workspace guarantee

The router refuses to satisfy a request that asks for patch
generation or workspace write authority:

* `allow_patch_generation_requested=True` ->
  `blocked` with reason `patch_generation_hard_disabled`.
* `allow_workspace_write_requested=True` ->
  `blocked` with reason `workspace_write_hard_disabled`.

These rails are enforced **before** any policy / registry lookup,
so they cannot be circumvented by an operator misconfiguration.

## Operations endpoints

* `GET  /operations/llm/models?status=active`
* `GET  /operations/llm/model-policies?agent_name=...&status=active`
* `GET  /operations/llm/routing-decisions?task_id=...&agent_name=...&decision=...`
* `GET  /operations/llm/routing-decisions/{task_id}`
* `POST /operations/llm/routing/preview` -- runs the router without
  invoking a provider. Optional `persist=true` writes the decision
  to `llm_routing_decisions`.
* `POST /operations/llm/routing/seed-defaults` -- idempotent seed of
  the registry + agent policies.

`GET /operations/safety` gains:

* `llm_model_router_enabled`
* `agent_direct_model_selection_allowed=false`
* `llm_routing_policy_enforced=true`
* `llm_model_registry_active_count`
* `llm_routing_budget_enforced=true`
* `llm_routing_human_review_enforced=true`
* `llm_model_routing_active_policies`

`GET /operations/summary` carries an `llm_model_routing_summary`
block with `model_router_enabled`, `registry_active_count`,
`policy_active_count`,
`agent_direct_model_selection_allowed=false`,
`patch_generation_hard_disabled=true`,
`workspace_write_hard_disabled=true`.

`GET /operations/workflows/{task_id}` `llm_assistance` section
gains `routing_decisions[]`, `selected_model`,
`selected_provider`, `model_policy`, `fallback_used`,
`routing_blocked`, `routing_reason`, `model_cost_estimate`,
`model_requires_human_review`.

`GET /discord/tasks/{task_id}` gains:

* `llm_model_router_enabled=true`
* `agent_direct_model_selection_allowed=false`
* `selected_model_alias`, `selected_provider`,
  `selected_model_tier`
* `routing_decision`
* `routing_requires_human_review`
* `routing_fallback_used`

None of these surfaces expose an API key, provider secret, or
prompt / response body.

## Audit decision types

Stage 38 reserves the following `decision_type` values in
`audit_logs`:

* `llm_model_registry_seeded`
* `llm_agent_model_policy_created`
* `llm_model_routing_selected`
* `llm_model_routing_fallback_selected`
* `llm_model_routing_blocked`
* `llm_model_routing_budget_blocked`
* `llm_model_routing_human_approval_required`
* `llm_direct_model_selection_rejected`

`artifact_refs` may include `routing_decision_id`, `agent_name`,
`capability`, `selected_provider`, `selected_model_alias`,
`selected_model_tier`, `decision`, `reason`, `fallback_used`,
`budget_decision`, `requires_human_review`, and
`production_executed=false`. The records NEVER carry an API key
value, provider secret, prompt text, or response text.

## Notification events

The notification-worker reserves these event types:

* `llm.routing_selected`
* `llm.routing_blocked`
* `llm.routing_human_approval_required`
* `llm.routing_budget_blocked`

All four sit under the existing `llm.*` denylist namespace (Stage
33), so they are **default-blocked** from real Discord delivery.
An operator who wants any of them externalised must add the
specific event_type to the allowlist *and* the originating
publisher must include the `metadata.real_delivery=true` marker.

## Metrics

* `llm_model_routing_requests_total{agent_name, capability}`
* `llm_model_routing_selected_total{agent_name, provider, model_tier, decision}`
* `llm_model_routing_blocked_total{agent_name, reason}`
* `llm_model_routing_fallback_total{agent_name, model_tier}`
* `llm_model_routing_human_review_total{agent_name, capability}`
* `llm_model_routing_budget_blocked_total{agent_name, provider}`
* `llm_model_policy_missing_total{agent_name, capability}`
* `llm_model_direct_selection_rejected_total{agent_name, capability}`

Spans:

* `llm_routing.request`, `llm_routing.load_policy`,
  `llm_routing.load_registry`, `llm_routing.evaluate_capability`,
  `llm_routing.evaluate_schema`, `llm_routing.evaluate_budget`,
  `llm_routing.select_model`, `llm_routing.persist_decision`.

Span attributes carry `task_id`, `workflow_id`, `agent_name`,
`capability`, `selected_model_alias`, `decision`, `fallback_used`.

## Limitations (recorded explicitly)

* **Real LLM still default-off.** No platform agent is wired to
  call a real provider in Stage 38. Setting `allow_real_llm=true`
  on a policy and flipping the matching registry entry to
  `status=active` are required and operator-decided.
* **No human approval workflow yet.** When the router returns
  `human_approval_required`, the platform records the decision
  but does NOT yet ship a `/operations/llm/routing/approvals/...`
  approval endpoint. Operators must approve via the existing
  Stage 31 human approval policy.
* **No model usage feedback loop.** The router records intent +
  estimated cost; actual recorded usage stays in the Stage 35
  `llm_budget_events` ledger (recorded_usage event type).
* **Mock registry only.** Production deployments must add a real
  registry seed (operator-decided).
* **Step 33 carry-forward limitations still open.** HMAC key
  rotation / key map loader; audit-service direct POST integrity
  gap.
* **Stage 36 backup readiness gaps still open.**
  `encryption_no_key`, `storage_not_off_host`,
  `schedule_dry_run_only`, `migration_down_gaps`.

Stage 38 does NOT remediate the carry-forward items.
