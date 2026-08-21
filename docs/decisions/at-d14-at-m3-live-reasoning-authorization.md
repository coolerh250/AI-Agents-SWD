# AT-D14 — AT-M3 live-reasoning architecture and implementation authorization

> **Product Owner decision record. Authorizes non-production AT-M3 implementation and mock/local
> validation only. Authorizes no real external LLM call, no production action, and no AT-M4
> execution. `production_executed_true_count: 0`.**

```text
AT-D14:                      RESOLVED / BINDING
Recorded_on:                 2026-08-21
Recorded_by:                 Product Owner
Canonical_main_at_decision:  44cdd6f14333915932428d190b0a3e117d033b6d
```

## 1. What this record is for

`AI_AGENTS_PM_STATE.md` records `NEXT_PERMITTED_STAGE: AT-M3 PLANNING` and
`AT_M3_TO_AT_M8: NOT AUTHORIZED`. The AT-M3-LIVE-REASONING-PLANNING-1 planning report (this
session, prior turn) surfaced the concrete AT-M3.1 slice -- a reasoning contract and provider
abstraction -- and the open questions it depends on. This record is the authorization that moves
AT-M3.1 from planned to implementable. It authorizes AT-M3.1 only; it is not a blanket AT-M3
authorization, and it authorizes no later AT-M3.x slice by itself.

```text
AT_M3:                       PLANNING CONTINUES; NOT FULLY AUTHORIZED
AT_M3_1:                     AUTHORIZED / NON-PRODUCTION / MOCK-LOCAL ONLY
```

## 2. What is authorized

```text
Reasoning contract           propose / critique / summarize_decision structured artifacts
Provider abstraction         vendor-neutral protocol; mock + disabled provider modes only
ReasoningInvocation           durable call-metadata persistence (migration 037, additive only)
Mock/local validation         deterministic MockReasoningProvider, no network
Schema evolution               the migration above, and future AT-M3 migrations this decision's
                               successors authorize individually
Forward-looking scaffolding    reserving (not implementing) the shape a future Goal, PlanRevision,
                               bounded discussion loop, and plan-driven routing slice will use
```

## 3. What is explicitly NOT authorized

```text
Real external LLM calls        no Anthropic, OpenAI, or other vendor network request, under any
                                 flag combination
External model credentials     no API key is read, stored, or wired to a live path
Production                     no production authorization, no production data, no production
                                 action -- unchanged from every prior AT-M* record
AT-M4                           no code/command/test/tool execution; no DebugAttempt; no
                                 debug -> replan back-edge
PCP remediation                 out of scope; PCP-V2.1-RM5 stays open and unaffected
```

No prior historical Anthropic sandbox authorization is treated as still valid. A real external
call requires its own future decision naming vendor, model, cost ceiling and key-provisioning path
explicitly -- restated from the AT-M3-LIVE-REASONING-PLANNING-1 report's `AUTHORIZATION` section.

## 4. Safety invariants this decision restates, not creates

```text
Fail closed on refusal          a refused or unavailable provider never substitutes a
                                  mock-authored result for a live one; it raises, and the failure
                                  is durable
No hidden reasoning              no chain-of-thought, scratchpad, raw prompt, or raw completion is
                                  ever persisted -- ReasoningInvocation stores call METADATA only
No secret persistence            no credential, API key, or token value is ever persisted
TeamDecision boundary             nothing in this slice creates a TeamDecision; when a later slice
                                  does, it remains what AT-ADR-06 / INV-03 already establish -- a
                                  team coordination artifact, never a substitute for human Approval
                                  or ProductOwnerDecision
```

These are not new rules. AT-M3.1's `assert_content_is_safe` reuse
(`shared/sdk/agent_team/models.py`) and its closed (`extra="forbid"`) artifact schemas are the
mechanical enforcement; this record states that the mechanism is authorized to exist, not that the
prohibition is new.

## 5. Scope boundary

AT-M3.1 implements exactly:

```text
shared/sdk/agent_reasoning/    reasoning contract, provider protocol, mock provider, store, service
migrations/037_...             one additive table, reasoning_invocations
tests/test_at_m3_1_*            focused + DB-backed + static-SQL proof
```

It does not implement, and this decision does not authorize:

```text
Goal entity                     AT-M3.2
PlanRevision                    AT-M3.2
Bounded team discussion          AT-M3.3
Plan-driven dynamic delegation   AT-M3.5
Any orchestrator/workflow change AT-M3.5
Any frontend/Admin Console change AT-M3.6+
```

## 6. Statement

Decision record only, covering AT-M3.1 as scoped above. No production action is implied or
performed. This decision does not modify AT-M1, AT-M2, or any prior binding decision; where a
prior record and this one could be read as disagreeing, the narrower, later, explicitly-scoped
statement here governs AT-M3.1 only.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
