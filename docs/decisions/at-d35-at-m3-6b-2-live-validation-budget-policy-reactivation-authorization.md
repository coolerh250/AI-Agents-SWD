# AT-D35 — AT-M3.6B.2 Live Validation Budget Policy Reactivation Authorization

> **Product Owner decision record. Authorizes ONE bounded action: transitioning the existing AT-D33
> budget-policy row (policy_id `d29ad073-9f7c-48b4-876d-cd3cb1343b40`) from `status='inactive'` to
> `status='active'`, changing no other column. It authorizes NO new policy, NO change to scope,
> provider, limits, or enforcement, NO Anthropic call, and NO live-gate enablement.
> `production_executed_true_count: 0`.**

```text
AT-D35:                      RESOLVED / BINDING
Recorded_on:                 2026-09-09
Recorded_by:                 Product Owner
Canonical_main_at_decision:  58ec92acca7a96684b0c28d7f6f5d973bf8d50d7
Branch:                      (docs-only, direct to main)
Depends_on:                  AT-D32 (docs/decisions/at-d32-at-m3-6b-2-live-validation-authorization.md)
                             AT-D33 (docs/decisions/at-d33-at-m3-6b-2-live-validation-budget-policy-provisioning-authorization.md)
                             AT-D34 (docs/decisions/at-d34-at-m3-6b-2-test-runtime-database-migration-alignment-authorization.md)

BUDGET POLICY REACTIVATION:              AUTHORIZED
THIS SLICE:                              AUTHORIZED
ANTHROPIC CALLS AUTHORIZED BY THIS RECORD: 0
REASONING_LIVE_NETWORK_ENABLED:          false throughout -- not touched by this record
AT-M4:                                   NOT AUTHORIZED
Production:                              NOT GRANTED
production_executed_true_count:          0
```

## 1. What this record is for

The AT-M3.6B.2 Test Runtime Database Migration Alignment stage found, as part of its own final
safety checks, that the AT-D33 budget policy (created `active`, and required for a Live Validation
execution attempt to reach the Anthropic wire at all) had its `status` changed to `inactive` at some
point outside this project's own conversation history, roughly 23 minutes after creation. Direct
inspection confirmed zero `llm_budget_events` and zero `anthropic`-provider `reasoning_invocations`
exist — no real call or spend occurred — but the cause of the status change could not be established
from that evidence alone. This record authorizes reversing exactly that one status change so a Live
Validation execution attempt can proceed, without resolving or needing to resolve who changed it.

## 2. Verification performed before this record

```text
Policy identity/immutable properties:  confirmed unchanged and matching AT-D33 exactly -- policy_id
                                          d29ad073-9f7c-48b4-876d-cd3cb1343b40, scope_type=provider,
                                          provider=anthropic, max_cost_per_day_usd=5.00,
                                          max_cost_per_month_usd=5.00, enforcement_mode=block
Row count:                               exactly ONE row exists in llm_budget_policies, total, across
                                          every provider and scope -- no conflicting or overlapping
                                          policy of any kind
Usage/reservation baseline:              zero llm_budget_events for provider=anthropic, anywhere --
                                          full US$5.00/US$5.00 daily/monthly headroom remains
                                          available, unreset and unaltered
Deactivation-cause search:                every script in this repository that ever issues an UPDATE
                                          against llm_budget_policies.status (scripts/verify_llm_cost
                                          _governance.sh, scripts/verify_real_llm_plan_only_pilot.sh)
                                          targets only its own dynamically-generated policy_name or
                                          policy_id created earlier in the same script run --
                                          confirmed by reading both WHERE clauses and their variable
                                          definitions -- and could not have matched this policy's name
                                          or id. No crontab exists on the test host. No
                                          BudgetPolicyStore method deactivates a policy at all (no
                                          such method exists in the store). No automated or scheduled
                                          control in this codebase can explain, or could recur against,
                                          this specific row.
Conclusion:                              DEACTIVATION_CAUSE_UNRESOLVED, but NON_BLOCKING -- no active
                                          automated mechanism exists that would race against, or
                                          re-trigger, this reactivation
```

## 3. Authorized scope

```text
Action:                        exactly one UPDATE against llm_budget_policies, predicated on
                                policy_id = 'd29ad073-9f7c-48b4-876d-cd3cb1343b40' AND
                                status = 'inactive', setting status = 'active' and no other column;
                                a fail-closed row-count assertion (exactly 1) guards it
Environment:                    internal non-production test runtime only
Not authorized:                 a new policy; any change to scope_type, provider, max_cost_per_day_usd,
                                max_cost_per_month_usd, or enforcement_mode; deleting policy rows or
                                history; resetting usage/reservations/settlements; any Anthropic call;
                                REASONING_LIVE_NETWORK_ENABLED=true anywhere; any application, store,
                                or migration code change
Lifecycle:                      this reactivation exists only to permit the immediately-following
                                AT-M3.6B.2 Live Validation execution attempt. That execution session
                                must deactivate this same policy (status='inactive', never delete) on
                                reaching ANY terminal result -- PASS, FAIL, BLOCKED, ABORT, or
                                DESIGN_REVIEW_REQUIRED. If that execution does not start at all
                                following this reactivation, the session that discovers that must
                                deactivate the policy before stopping rather than leave standing
                                spending authority active indefinitely.
```

## 4. AT-D32 remains independently binding, unchanged and unconsumed by this record

This reactivation does not reset, expand, or pre-consume any part of AT-D32's envelope (12 requests
max, US$5.00 total, US$0.50/attempt, US$1.50/correlation, 3 attempts/correlation,
anthropic/claude-sonnet-5 only, ephemeral live-gate only, allowed verbs
propose/critique/summarize_decision/decompose_plan). This stage itself consumes 0 calls and $0 of
that envelope.

## 5. What is NOT authorized

```text
Any Anthropic call, real or diagnostic                                    NOT AUTHORIZED
REASONING_LIVE_NETWORK_ENABLED=true (any process)                         NOT AUTHORIZED
A new or modified budget policy beyond this one status transition         NOT AUTHORIZED
Credential validation, model-list call, health/pricing probe              NOT AUTHORIZED
BudgetPolicyStore / ReasoningService / AnthropicReasoningProvider code or schema change  NOT AUTHORIZED
M3.5 dispatch, AT-M4, HumanApproval mutation, production action           NOT AUTHORIZED / NOT GRANTED
```

## 6. What this decision does NOT do

```text
Does NOT authorize any Anthropic call -- a separate Live Validation execution session, still bounded
   by AT-D32, performs that
Does NOT amend AT-D32, AT-D33, or AT-D34
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4 or any real work execution
Does NOT resolve, or claim to resolve, who or what deactivated the policy previously
Does NOT modify application code, migrations, or BudgetPolicyStore/ReasoningService semantics
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
