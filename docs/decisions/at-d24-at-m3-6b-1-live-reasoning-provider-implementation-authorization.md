# AT-D24 — AT-M3.6B.1 live reasoning provider implementation authorization

> **Product Owner decision record. Authorizes the IMPLEMENTATION of a live Anthropic reasoning
> adapter behind the existing AT-M3.1 provider abstraction, together with the safety, cost and size
> boundaries it requires. Authorizes ZERO live external calls, no AT-M3.6B.2 live validation, no
> AT-M4, and no production action. `production_executed_true_count: 0`.**

```text
AT-D24:                      RESOLVED / BINDING
Recorded_on:                 2026-09-03
Recorded_by:                 Product Owner
Canonical_main_at_decision:  e50d42294119db4c561ea07ebe42a9382b8e3f68
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
                             AT-D23 (docs/decisions/at-d23-at-m3-6a-acceptance-and-merge-authorization.md)
Origin:                      AT-M3.6B-PRODUCT-ARCHITECTURE-AUTHORIZATION-REVIEW-1
Standard:                    docs/governance/AI_AGENTS_PROJECT_EXECUTION_STANDARD.md
```

## 1. What this record is for

AT-D14 section 3 named M3.6B as explicitly NOT authorized and stated the condition under which it
could become authorized: *"M3.6B requires its own future decision naming vendor, model, cost ceiling
and key-provisioning path explicitly."* AT-D23 closed AT-M3.6A and left
`PRODUCT_CRITICAL_PATH: NONE`, because AT-D14's authorized scope was fully consumed. The
AT-M3.6B-PRODUCT-ARCHITECTURE-AUTHORIZATION-REVIEW-1 report then assessed whether the existing
architecture could carry a live provider without a parallel reasoning authority, recommended
`AUTHORIZED_FOR_IMPLEMENTATION`, and recommended splitting the work so that writing the code and
spending money are separately authorized.

This record is that decision, for the first half only. It names the vendor, the model, the cost
ceiling and the key-provisioning path AT-D14 required, and it authorizes the code. It does not
authorize a single external call.

```text
AT_M3_6B_1:                  AUTHORIZED (implementation only)
AT_M3_6B_2:                  NOT AUTHORIZED (live validation)
LIVE_EXTERNAL_CALLS:         0
PAID_MODEL_CALLS:            0
AT_M4:                       NOT AUTHORIZED
PRODUCTION:                  NOT GRANTED
```

## 2. What is authorized

A live reasoning adapter, implemented behind the canonical
`shared/sdk/agent_reasoning/provider.py::ReasoningProvider` abstraction and driven by the canonical
`ReasoningService`, with the following package fixed by this decision.

```text
Provider                     Anthropic
Provider identity            name = "anthropic"
Provider class (mode)        "live"
Model allowlist              claude-sonnet-5, and nothing else
Secret path                  existing SecretProvider -> Vault KV v2 -> ANTHROPIC_API_KEY
Live network gate            REASONING_LIVE_NETWORK_ENABLED, default false, false for all of B.1
```

**Data egress.** Locally-authored, non-production, control-plane reasoning content required for a
reasoning call may be sent to Anthropic through the adapter. This is the data-egress statement the
architecture review flagged as an authorization prerequisite; the repository had no
data-classification policy, and this paragraph is the answer rather than a new policy subsystem.

Forbidden from leaving the local boundary under any circumstance: secrets, credentials, production
authorization material, unrelated-project data, raw audit history, and AT-M4 execution credentials.

**Approved limits.**

```text
Outbound reasoning context   <= 32 KiB serialized JSON
Output tokens per verb       propose 1500 / critique 1500 / summarize_decision 1500
                             decompose_plan 4000
Durable typed artifact       <= 256 KiB serialized safe artifact
PlanContent                  <= 40 steps
Per PlanStep                 depends_on <= 10, required_capabilities <= 10,
                             expected_outputs <= 10, constraints <= 10
Connect timeout              10 seconds
Provider attempt timeout     60 seconds total
Database lease               120 seconds, UNCHANGED and not to be raised
Cost per external call       <= US$0.50 (hard, pre-flight)
Cost per invocation          <= US$1.50 (per-call ceiling x the existing 3-attempt budget)
Max attempts                 3, the existing DEFAULT_MAX_ATTEMPTS
Budget policy                an ACTIVE LLMBudgetPolicy carrying both a daily and a monthly cost
                             cap is required for live mode to resolve at all
Model pricing                claude-sonnet-5 at US$2 / million input tokens and
                             US$10 / million output tokens
Provider fallback            NONE. No automatic fallback to another model, another provider, or
                             the mock, under any condition.
```

Schema evolution authorized for the above is exactly one additive migration widening
`reasoning_invocations.provider_mode` to admit `live` and `failure_category` to admit
`provider_timeout`, `rate_limited` and `budget_exceeded`. No AT-M2 table is touched — AT-D14's one
schema prohibition is unchanged.

## 3. What is explicitly NOT authorized

```text
AT-M3.6B.2 / live validation  no real external call, official or diagnostic, under any flag
                              combination. Enabling REASONING_LIVE_NETWORK_ENABLED requires its own
                              Product Owner decision naming call count and cost ceiling.
Diagnostic external calls     forbidden without their own authorization -- the Step 65F-C guardrail
                              (docs/staging/step65f-llm-guardrail-update.md), carried forward
                              verbatim: every external network call counts, not only the official
                              one.
Credential validation         the Anthropic key is never checked by calling Anthropic in B.1.
Multi-provider architecture   deferred. One provider, one model.
AT-M4                         no code/command/test/tool execution; no M3.5 dispatch consumer; no
                              authenticated completion ingress.
Production                    no production authorization, no production data, no production
                              action, no production credential.
```

## 4. The controls this authorization requires

Implementation acceptance is conditioned on these. They are requirements of the authorization, not
aspirations, and a missing one makes the slice unacceptable rather than merely weaker.

```text
R01  ReasoningService remains the ONLY reasoning authority. No LiveReasoningService, no
     AnthropicReasoningService, no second reasoning store or invocation table.
R02  Provider and model resolve from configuration. ReasoningRequest.provider_name and .model_name
     remain requested metadata and MUST NOT become routing authority in either direction -- a
     caller may neither route itself to a live model nor downgrade a live runtime to the mock.
R03  The live network gate defaults closed and refuses a NEW attempt before secret resolution and
     before any network use.
R04  Canonical replay of a SUCCEEDED invocation works with the gate closed, with no provider
     resolution, no credential read, no budget spend and no external call.
R05  Provider calls are genuinely non-blocking; the event loop is not held for the request timeout.
R06  ONE authoritative retry layer: the existing attempt/takeover state machine. Transport retries
     disabled.
R07  connect < attempt timeout << lease, with the lease unchanged at 120 seconds.
R08  Output is bounded BEFORE the durable write: strict JSON, closed Pydantic schema, semantic
     validation, content safety, artifact byte cap. No JSON repair of any kind.
R09  No raw prompt, completion, chain-of-thought or scratchpad is persisted, logged or audited.
R10  Usage and cost are recorded truthfully even for a call whose output was unusable or whose
     attempt lost an ownership race. A billable call that produced no canonical artifact is still a
     billable call.
R11  Migration 040's success/artifact atomicity, lease contract and terminal immutability apply to
     live rows unchanged. A live invocation is not a privileged invocation.
R12  Provider-specific errors are non-authoritative and sanitized; an unknown exception contributes
     its CLASS NAME only.
R13  /operations/safety reports the reasoning provider posture truthfully, distinguishing
     "configured for Anthropic" from "permitted to call Anthropic".
R14  AT-M3.6A remains read-only and gains no new endpoint; the live fields it already declares are
     populated rather than duplicated.
R15  Zero external calls are proven by test, not asserted by report.
```

## 5. Safety invariants this decision restates, not creates

```text
Fail closed on refusal        a refused, gated, unauthorized, over-budget or unavailable provider
                              never substitutes a mock-authored result for a live one. AT-D14
                              section 4's first invariant, and the specific behaviour
                              shared/sdk/agent_reasoning/provider.py has refused to inherit from
                              shared/sdk/llm/provider.py::ExternalLLMProviderGuard since AT-M3.1.
No hidden reasoning           no chain-of-thought, scratchpad, raw prompt or raw completion is ever
                              persisted.
No secret persistence         no credential, API key or token value is ever persisted, logged,
                              audited, returned or placed in an exception.
At-least-once attempts        external provider attempts remain at-least-once and the canonical
                              durable artifact remains exactly-once. No exactly-one-network-call
                              claim is made, and correctness does not depend on provider dedupe.
TeamDecision boundary         a TeamDecision remains a team coordination artifact, never a
                              substitute for human Approval or ProductOwnerDecision. HumanApproval
                              semantics are unchanged and this authorization creates no
                              HumanApproval row.
```

## 6. Non-blocking backlog

Recorded, not remediated by this authorization.

```text
1  Provider idempotency key (invocation_id + attempt) is NOT implemented. Canonical correctness
   does not depend on it; it would only reduce duplicate charges in the crash-between-wire-and-
   commit window.
   NON_BLOCKING / PRODUCT_HARDENING.

2  Migration 040's terminal-immutability trigger freezes latency_ms but not input_tokens,
   output_tokens or estimated_cost_usd, so a terminal row's recorded usage is editable by a
   privileged raw-SQL caller. Outside the product API contract.
   P3 / DB_HARDENING / OUTSIDE_PRODUCT_API_CONTRACT.

3  Retry-After is not honoured beyond mapping 429 to rate_limited; a bounded wait is deferred to
   the existing lease/takeover path.
   NON_BLOCKING / PRE-M3.6B.2.

4  prompt_profile_id / prompt_profile_version are not recorded. One fixed profile set ships and is
   pinned by the commit, so the traceability gap is currently empty.
   NON_BLOCKING / PRODUCT_HARDENING.

5  Carried unchanged from AT-D23 section 6: the AutonomyReadStore._session() recursion fallback
   (P3, unreachable on every shipped path) and the privileged raw-SQL DELETE of
   goal_execution_lineage (P3, outside the product API contract). Neither is touched by this slice.

The two PRE-M3.6B items AT-D23 section 6 recorded -- the unbounded reasoning artifact and the
unbounded PlanContent step count -- are CLOSED by this authorization's approved limits, because
AT-M3.6B.1 is the slice that makes untrusted output reach them.
```

## 7. Governance

Uses AT-D18's Minimal Governance Kernel and adds no mechanism. A configuration allowlist of one
model is not a model registry; a feature gate is not a governance platform. No verifier, exemption
system, meta-verifier, approval hierarchy, canonical activation framework or provider-governance
subsystem is created. This decision sits squarely on two of AT-D18-R04's eight blocking kernel
items — "external model / network / action authorization" and "secrets and credentials" — which is
why it exists as a Product Owner decision rather than as an engineering choice.

## 8. What this record does not do

It does not accept an implementation, authorize a merge, or replace the per-slice proof discipline.
AT-M3.6B.1 still requires its own implementation report, its own Independent Validation 1, and — if
that passes — its own Product Owner acceptance record before it may become canonical, the same way
AT-D15/AT-D19/AT-D20/AT-D21/AT-D22/AT-D23 each accepted one slice after AT-D14 authorized the work.
It does not modify AT-D14, AT-D18, AT-D23, or any other prior binding decision.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
