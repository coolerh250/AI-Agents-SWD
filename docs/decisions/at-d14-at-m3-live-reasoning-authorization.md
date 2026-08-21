# AT-D14 — AT-M3 live-reasoning architecture and implementation authorization

> **Product Owner decision record. Authorizes non-production, non-external-network AT-M3
> implementation (M3.1 through M3.6A) and mock/local deterministic validation of it. Authorizes no
> real external LLM call, no production action, and no AT-M4 execution.
> `production_executed_true_count: 0`.**

```text
AT-D14:                      RESOLVED / BINDING
Recorded_on:                 2026-08-21
Recorded_by:                 Product Owner
Canonical_main_at_decision:  44cdd6f14333915932428d190b0a3e117d033b6d
```

## 1. What this record is for

`AI_AGENTS_PM_STATE.md` records `NEXT_PERMITTED_STAGE: AT-M3 PLANNING` and
`AT_M3_TO_AT_M8: NOT AUTHORIZED`. The AT-M3-LIVE-REASONING-PLANNING-1 planning report (this
session, prior turn) surfaced the AT-M3 implementation slices -- M3.1 through M3.6 -- and the open
questions each depends on. This record is the Product Owner's authorization for the
non-production, no-external-network portion of that work: M3.1 through M3.6A, and the schema
evolution each of them needs. It does not authorize M3.6B (a real external model call), and it
does not authorize AT-M4.

**Authorization scope is not the same thing as implementation state.** AT-D14 authorizes six
slices to be built; as of this record, exactly one -- AT-M3.1 -- has been. The other five remain
authorized-but-not-yet-implemented: each still needs its own implementation, its own test proof,
and its own Validation 1 (-> one bounded remediation -> Validation 2, no Validation 3), the same
per-slice discipline AT-M3.1 itself follows. Authorization is not a claim of completion, and this
record must not be read as one.

```text
AT_M3:                       PARTIALLY AUTHORIZED (M3.1-M3.6A); M3.6B and beyond NOT AUTHORIZED
AT_M3_AUTHORIZED_SLICES:     M3.1, M3.2, M3.3, M3.4, M3.5, M3.6A
AT_M3_CURRENT_IMPLEMENTATION_SLICE: AT-M3.1
AT_M3_1:                     IMPLEMENTED / AWAITING VALIDATION 1
AT_M3_2_THROUGH_M3_6A:       AUTHORIZED / NOT YET IMPLEMENTED
AT_M3_6B:                    NOT AUTHORIZED
```

## 2. What is authorized

Non-production, non-external-network implementation and mock/local deterministic validation of:

```text
M3.1  Reasoning contract & provider abstraction
      propose / critique / summarize_decision artifacts; vendor-neutral provider protocol;
      ReasoningInvocation durable call metadata
      STATUS: IMPLEMENTED (this branch), AWAITING VALIDATION 1

M3.2  Goal + immutable PlanRevision
      the Goal entity; PlanRevision as a versioned, historically-immutable, supersedable,
      diffable, traceable planning entity (planning-and-plan-revision-model.md)
      STATUS: AUTHORIZED, NOT YET IMPLEMENTED

M3.3  Bounded, capability-aware team discussion
      propose/challenge/converge over the existing ConversationThread/TeamMessage schema;
      max-rounds/timeout/budget bounds; fail-closed terminal states
      STATUS: AUTHORIZED, NOT YET IMPLEMENTED

M3.4  Goal decomposition / PlanRevision generation
      the planner producing a draft PlanRevision's work items and dependencies from a Goal and a
      discussion outcome, reusing the existing dependency validator
      STATUS: AUTHORIZED, NOT YET IMPLEMENTED

M3.5  Plan-driven dynamic delegation
      replacing the orchestrator's single hard-coded pre-dispatch routing call with a
      per-work-item dispatcher over the active PlanRevision, reusing the existing AT-M2 capability
      router unchanged
      STATUS: AUTHORIZED, NOT YET IMPLEMENTED

M3.6A Observability / read surfaces
      backend read APIs for participation, tokens/cost/latency, round count, active PlanRevision,
      delegation reasons -- exercised in mock mode; no frontend, no live model required
      STATUS: AUTHORIZED, NOT YET IMPLEMENTED
```

Schema evolution authorized for the above includes the migrations M3.1-M3.5 each need for
Goal/PlanRevision lineage, explicitly including the FK this decision pre-clears:
`team_decisions.resulting_plan_revision_id -> plan_revisions.plan_revision_id` -- the first
migration to alter an AT-M2 table rather than only add to one, which the AT-M3-LIVE-REASONING-
PLANNING-1 report flagged as needing explicit sign-off. This record is that sign-off, scoped to
exactly that FK and to the Goal/PlanRevision schema M3.2 introduces; it authorizes no other
alteration of an AT-M2 table.

## 3. What is explicitly NOT authorized

```text
M3.6B / real external LLM calls   no Anthropic, OpenAI, or other vendor network request, under
                                    any flag combination -- this is the live-model wiring split out
                                    of M3.6A specifically because it is NOT covered by this record
External model credentials         no API key is read, stored, or wired to a live path
Production                         no production authorization, no production data, no production
                                    action -- unchanged from every prior AT-M* record
AT-M4                               no code/command/test/tool execution; no DebugAttempt; no
                                    debug -> replan back-edge
PCP remediation                     out of scope; PCP-V2.1-RM5 stays open and unaffected
```

No prior historical Anthropic sandbox authorization is treated as still valid. M3.6B requires its
own future decision naming vendor, model, cost ceiling and key-provisioning path explicitly --
restated from the AT-M3-LIVE-REASONING-PLANNING-1 report's `AUTHORIZATION` section.

## 4. Safety invariants this decision restates, not creates

```text
Fail closed on refusal          a refused or unavailable provider never substitutes a
                                  mock-authored result for a live one; it raises, and the failure
                                  is durable
No hidden reasoning              no chain-of-thought, scratchpad, raw prompt, or raw completion is
                                  ever persisted
No secret persistence            no credential, API key, or token value is ever persisted
TeamDecision boundary             a TeamDecision (M3.3+) remains what AT-ADR-06 / INV-03 already
                                  establish -- a team coordination artifact, never a substitute for
                                  human Approval or ProductOwnerDecision
```

These are not new rules; they apply identically to every slice this record authorizes, not only to
M3.1. AT-M3.1's `assert_content_is_safe` reuse (`shared/sdk/agent_team/models.py`) and its closed
(`extra="forbid"`) artifact schemas are the first mechanical enforcement of them; each later slice
is expected to enforce them the same way, not invent a separate mechanism.

## 5. Scope boundary: authorization versus implementation

What AT-D14 authorizes (M3.1-M3.6A) and what exists on `main` today (nothing from AT-M3; AT-M3.1
exists only on its own unmerged branch, awaiting Validation 1) are different questions, and this
record answers only the first one.

```text
AUTHORIZED BY THIS RECORD, in the sense of "may be implemented and mock/local-validated":
  M3.1, M3.2, M3.3, M3.4, M3.5, M3.6A

IMPLEMENTED as of this record (branch at-m3.1-reasoning-contract-provider-abstraction, unmerged):
  M3.1 only -- shared/sdk/agent_reasoning/, migrations/037_..., tests/test_at_m3_1_*

NOT AUTHORIZED by this record under any circumstance:
  M3.6B, production, AT-M4, PCP remediation
```

A future slice (M3.2, ..., M3.6A) implementing against this authorization still requires: its own
branch, its own implementation report, its own test proof, and its own Validation 1/2 pass -- AT-D14
authorizes the WORK, not a merge, and not a skip of the per-slice proof discipline.

## 6. Statement

Decision record only, covering M3.1 through M3.6A as scoped above. No production action is
implied or performed. This decision does not modify AT-M1, AT-M2, or any prior binding decision.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
