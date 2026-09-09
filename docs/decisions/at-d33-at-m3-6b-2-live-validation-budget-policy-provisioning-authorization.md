# AT-D33 — AT-M3.6B.2 Live Validation Budget Policy Provisioning Authorization

> **Product Owner decision record. Authorizes ONE bounded action: provisioning the single
> `llm_budget_policies` row that `AnthropicReasoningProvider.preflight()` requires to exist before
> any AT-D32 Live Validation call can proceed. It authorizes NO Anthropic call, NO live-gate
> enablement, NO implementation change, and NO provider/model diagnostic. `production_executed_true_count: 0`.**

```text
AT-D33:                      RESOLVED / BINDING
Recorded_on:                 2026-09-09
Recorded_by:                 Product Owner
Canonical_main_at_decision:  009b1dcbfca36c1020dcfe3f3c077ccf16ffa25f
Branch:                      (docs-only, direct to main)
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)

BUDGET POLICY PROVISIONING:              AUTHORIZED
THIS SLICE:                              AUTHORIZED
ANTHROPIC CALLS AUTHORIZED BY THIS RECORD: 0
REASONING_LIVE_NETWORK_ENABLED:          false throughout -- not touched by this record
AT-M4:                                   NOT AUTHORIZED
Production:                              NOT GRANTED
production_executed_true_count:          0
```

## 1. What this record is for

AT-D32 authorized one bounded AT-M3.6B.2 Live Validation execution session but did not itself make
the runtime capable of succeeding. A first attempt at that execution session found, before any
network gate consideration and before any credential resolution, that `AnthropicReasoningProvider
.preflight()` (`shared/sdk/agent_reasoning/anthropic_provider.py`) hard-requires an active
`llm_budget_policies` row carrying both `max_cost_per_day_usd` and `max_cost_per_month_usd` before a
live call is authorized to proceed, and that the internal non-production test runtime's
`llm_budget_policies` table held zero rows for any provider or scope. `BudgetPolicyStore
.get_active_policy()` has no fallback or default policy; an empty table means `None` unconditionally.

That session correctly declined to insert the missing row on its own initiative and stopped
`BLOCKED`, on the same principle this project's execution standard applies throughout: fixing a
control by way of an authority nobody granted is not fixing the control. This record supplies that
missing authority, scoped to exactly the one prerequisite row, and nothing beyond it.

## 2. Authorized scope

```text
Action authorized:            provisioning exactly ONE `llm_budget_policies` row via the canonical
                                `BudgetPolicyStore.create_policy()` path (no new operational API, no
                                schema change, no application code change)
Environment:                   internal non-production test runtime only -- this table exists only
                                inside that runtime's own Postgres; no production instance shares it
Policy scope_type:              `provider` (`SCOPE_PROVIDER`), the narrowest scope canonically
                                matched by `AnthropicReasoningProvider.preflight()`'s exact lookup
                                (`get_active_policy(provider="anthropic")`, no task/workflow/user id).
                                `global` was rejected as broader than necessary: it would additionally
                                govern every other provider, not only anthropic.
Provider:                       anthropic (matches AT-D32's provider-only scope; no fallback)
Daily ceiling:                  US$5.00 (`max_cost_per_day_usd`)
Monthly ceiling:                US$5.00 (`max_cost_per_month_usd`)
Enforcement:                    `block` -- the schema's only hard-deny value (the alternative,
                                `warn_only`, is not hard-deny and is not used)
Status:                         `active`
Purpose:                        satisfy the canonical budget-policy preflight for AT-M3.6B.2 Live
                                Validation only -- not a standing operational budget
```

## 3. AT-D32 remains independently binding

This record does not replace, widen, or supersede AT-D32. AT-D32's own ceilings (12 requests max,
US$5.00 total, US$0.50/attempt, US$1.50/correlation, 3 attempts/correlation, anthropic/claude-sonnet-5
only, ephemeral live-gate only, no Git mutation during the execution session) continue to bound any
future Live Validation execution session exactly as before. This policy row makes the runtime capable
of reaching AT-D32's ceilings; it is not itself a wider grant.

## 4. What is NOT authorized

```text
Any Anthropic call, real or diagnostic                  NOT AUTHORIZED
REASONING_LIVE_NETWORK_ENABLED=true (any process)         NOT AUTHORIZED
Credential validation, model-list call, health/pricing probe  NOT AUTHORIZED
AnthropicReasoningProvider / ReasoningService / BudgetPolicyStore code or schema change  NOT AUTHORIZED
A default or fallback budget policy applicable beyond this one row  NOT AUTHORIZED
M3.5 dispatch, AT-M4, HumanApproval mutation, production action  NOT AUTHORIZED / NOT GRANTED
```

## 5. Lifecycle requirement

This policy is not standing spending authority. After the AT-M3.6B.2 Live Validation execution
session this row exists to unblock reaches any terminal result (PASS, FAIL, BLOCKED, or ABORT), the
row must be set `status='inactive'` -- never deleted. Usage events, reservations, settlements, and
audit evidence tied to it must be preserved unchanged. A future execution session must verify or
perform this deactivation, or stop rather than proceed without it.

## 6. What this decision does NOT do

```text
Does NOT authorize any Anthropic call -- a separate Live Validation execution session, still bounded
   by AT-D32, performs that
Does NOT amend AT-D32 or any earlier AT-D
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4 or any real work execution
Does NOT modify application code, migrations, or BudgetPolicyStore semantics
Does NOT create a standing or default budget policy -- one stage-scoped row only, deactivated after
   the stage's terminal result
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
