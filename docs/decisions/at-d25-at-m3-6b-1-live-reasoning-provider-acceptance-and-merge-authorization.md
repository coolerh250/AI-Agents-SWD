# AT-D25 — AT-M3.6B.1 Live Reasoning Provider Adapter + Limits product acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.6B.1 (the Anthropic live reasoning adapter, its
> safety/durability/cost/output boundaries, its retry authority and its budget reservation model)
> and authorizes merging the exact independently validated candidate into `main`. It accepts a
> runtime that is STRUCTURALLY READY for live provider use; it does not accept, and cannot accept,
> any evidence about real Anthropic connectivity, credentials or billing — that is AT-M3.6B.2, which
> remains NOT AUTHORIZED. Authorizes no real external LLM call, no diagnostic external call, no
> live-gate enablement, no real work execution (AT-M4), no production action, no live consumer for
> the M3.5 dispatch namespace, no authenticated execution ingress, no HumanApproval mutation, no PCP
> remediation and no P3 backlog work. `production_executed_true_count: 0`.**

```text
AT-D25:                      RESOLVED / BINDING
Recorded_on:                 2026-09-07
Recorded_by:                 Product Owner
Canonical_main_at_decision:  e50d42294119db4c561ea07ebe42a9382b8e3f68
Validated_candidate:         14c3820b616b4ef2ceacb2dde9c37e5371ec147f
Implementation_end:          14c3820b616b4ef2ceacb2dde9c37e5371ec147f
Branch:                      at-m3.6b.1-live-reasoning-adapter-1
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
                             AT-D18 (docs/decisions/at-d18-project-governance-reset.md)
                             AT-D23 (docs/decisions/at-d23-at-m3-6a-acceptance-and-merge-authorization.md)
                             AT-D24 (docs/decisions/at-d24-at-m3-6b-1-live-reasoning-provider-implementation-authorization.md)
```

`Implementation_end` is the exact byte state that was independently validated. This record and the
PM/progress reconciliation it authorizes create a later branch tip; `Implementation_end` does not
move with it. Acceptance attaches to a commit, not to a branch name.

## 1. What this record is for

AT-D14 authorized AT-M3.1 through AT-M3.6A and explicitly did **not** authorize AT-M3.6B. AT-D24 is
where the Product Owner authorized the AT-M3.6B.1 *implementation* — vendor, model, credential path,
egress boundary and every approved limit — while stating that a live validation would need its own
separate authorization. This record is the third and separate decision: the Product Owner accepts
the resulting capability as independently validated, and approves canonicalizing the exact validated
candidate.

Same shape as AT-D13 for AT-M2, AT-D15 for AT-M3.1, AT-D19 for AT-M3.2, AT-D20 for AT-M3.3, AT-D21
for AT-M3.4, AT-D22 for AT-M3.5 and AT-D23 for AT-M3.6A: implementation authority and merge
authority are separate decisions, and the second one names the commit. It is the only place the
AT-M3.6B.1 acceptance and merge authorization is recorded.

**What this acceptance is, and what it is not.** AT-M3.6B.1 proves the runtime is structurally ready
for a live provider: the adapter exists, it sits behind the one reasoning authority, its limits are
enforced, its retries are bounded and real, its spend is claimed before the wire, and its network
gate is closed. It proves nothing about real Anthropic connectivity, credential validity, latency,
model behaviour or billing, because **zero real external calls were made** — that was the condition
under which the work was authorized, and it was kept. Reading this record as "live reasoning works"
would be the single most expensive misreading available, and section 4 says so in the register.

## 2. Accepted product capability

Accepted exactly as validated, and no wider:

```text
PROVIDER AND AUTHORITY
one Anthropic adapter behind the EXISTING ReasoningProvider protocol, driven by the EXISTING
    ReasoningService -- no AnthropicReasoningService, no second reasoning store, no second
    invocation table, no competing reasoning authority of any kind
provider_mode = mock | disabled | live -- the provider CLASS; the vendor stays in
    requested_provider_name and the model in model_name, as migrations 037 and 040 already provide
the actual provider and model are CONFIGURATION-owned, never request-owned
one allowlisted model: claude-sonnet-5; an unlisted model refuses before any credential is read
the live adapter is unreachable BY NAME in both directions -- a request naming "anthropic" gets the
    refusing provider, and a request naming "mock" on a live runtime does not get the mock
no automatic fallback of any kind -- not to another model, not to another provider, not to the mock

LIVE GATE AND REPLAY
REASONING_LIVE_NETWORK_ENABLED, separate from REASONING_PROVIDER, DEFAULT FALSE
canonical replay happens BEFORE provider resolution, credential resolution, budget evaluation and
    any network path -- an already-succeeded invocation replays with the gate closed, no credential
    available and zero provider resolution
a refusal is RECORDED as a durable failed invocation, not thrown as a new exception type

SECRETS AND EGRESS
the EXISTING SecretProvider -> Vault KV v2 -> ANTHROPIC_API_KEY; no new secret framework
the credential is resolved LAST, held as a SecretRef until a header is built, never persisted,
    logged, audited, returned or placed in an exception
an explicit per-verb egress projection -- only the fields M3.3 and M3.4 actually build leave the
    boundary; anything else FAILS the call rather than being silently dropped, and the error names
    keys, never values
reasoning context <= 32 KiB serialized

GENERATION AND OUTPUT BOUNDS
max output tokens: propose 1500, critique 1500, summarize_decision 1500, decompose_plan 4000
generation profile fixed per verb, configuration-owned, never caller-supplied
typed durable artifact <= 256 KiB
PlanContent <= 40 steps; per step depends_on / required_capabilities / expected_outputs /
    constraints <= 10 each
strict JSON parsing -- no fence stripping, no regex extraction, no partial objects, no repair
closed Pydantic schemas; the outbound schema is derived from the canonical model so what is asked
    for and what is enforced cannot drift
the EXISTING content-safety validation, unchanged; no second policy engine
NO raw provider completion persistence, anywhere

EXECUTION PATH
async / non-blocking provider path -- the event loop stays free while a provider call is in flight
httpx transport constructed with retries=0; no adapter-level retry, no Retry-After internal recall

RETRY (ReasoningService-owned)
a KNOWN transient failure advances the SAME invocation immediately: attempt 1 -> 2 -> 3
same correlation_id, same invocation row, rotated attempt_token, fresh DATABASE-clock lease
provider_timeout, rate_limited and provider_unavailable are RETRYABLE IN BEHAVIOUR, not in name
max 3 attempts; there is no attempt 4
deterministic failures remain terminal after one call and replay as failures
crash / zombie recovery remains lease-and-takeover based and is NOT used for known answers
at-least-once external attempt semantics, stated truthfully and never claimed as exactly-one call
exactly-one canonical durable artifact per correlation_id

BUDGET
a DURABLE reservation is written BEFORE any provider-shaped call; a reservation that cannot be
    persisted means ZERO provider calls
reservation identity = invocation_id:attempt, enforced by a unique index; never attempt_token
an UNSETTLED reservation counts against the daily and monthly budget from the moment it is written
settlement REPLACES the conservative reservation with actual usage -- one row per attempt, so
    counting reservations and settlements together cannot double-count
a settlement failure RETAINS the counted conservative reservation; it can leave a charge
    conservative, it can no longer leave it at zero
malformed, unsafe, oversized, transient and zombie attempts all remain cost-accounted
a provably no-call pre-wire failure may release its reservation, idempotently; an ambiguous window
    always retains it
per-call hard cap US$0.50; max 3 attempts; per-correlation envelope US$1.50
llm_budget remains the sole cost authority; nothing reconstructs spend from reasoning_invocations

SCHEMA
migration 044 -- live provider mode + a bounded live failure vocabulary, fail-closed DOWN
migration 045 -- budget reservation / settlement identity semantics, fail-closed DOWN

SURFACES AND BOUNDARIES
/operations/safety truthfully distinguishes CONFIGURED provider/model from LIVE NETWORK ENABLED;
    naming a provider is not permission to call it
AT-M3.6A remains read-only; no new observability endpoint was added
no M3.5 dispatch consumer
no AT-M4 execution capability
HumanApproval unchanged
ZERO real Anthropic calls and ZERO diagnostic external calls during the whole of AT-M3.6B.1
no production action
```

This list is the acceptance boundary. Capability not named here is not accepted by this record,
whether or not code for it happens to exist.

## 3. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the exact validated candidate
                               14c3820 into main
Documentation-only authority:  this record and the bounded PM/progress reconciliation commit it
                               authorizes
Post-merge verification:       bounded product and source-of-truth checks only, with zero external
                               network and fake transports where a provider-shaped check is needed
```

## 4. What is NOT authorized

```text
AT-M3.6B.2 / live validation   NOT AUTHORIZED. This is the boundary that matters most in this
                                  record. AT-M3.6B.1 accepts a runtime that is structurally ready
                                  for live use; it establishes NOTHING about real Anthropic
                                  connectivity, credential validity, latency, model behaviour or
                                  billing, because zero real calls were made. Any prior discussion
                                  of a call-count or cost envelope is DISCUSSION, not authorization
Live network gate enablement   NOT AUTHORIZED. REASONING_LIVE_NETWORK_ENABLED stays false
Real external model credential NOT AUTHORIZED for use. ANTHROPIC_API_KEY may not be fetched,
                                  validated, or exercised against Anthropic by any step this
                                  record authorizes
Diagnostic external calls      NOT AUTHORIZED -- the Step 65F-C guardrail is unchanged: every
                                  external call counts, diagnostic ones included
AT-M4 implementation           NOT AUTHORIZED -- real work execution, DebugAttempt and the
                                  debug -> replan back-edge all remain out of scope
Live M3.5 dispatch consumer    NOT AUTHORIZED -- the namespace still has no reader
Authenticated execution ingress NOT AUTHORIZED -- mTLS, JWT, API keys, signed callbacks and bearer
                                  completion tokens all remain out of scope
Production action              NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization       NOT GRANTED -- unchanged
Frontend / Admin Console work  NOT AUTHORIZED by this record
P3 backlog remediation         NOT AUTHORIZED by this record -- see section 6
PCP remediation                NOT AUTHORIZED by this record
Step 66 stage-freeze guards    NOT AUTHORIZED for repair by this record -- see section 7
Unrelated runtime changes      NOT AUTHORIZED -- this record covers AT-M3.6B.1 acceptance and its
                                  merge only
```

## 5. Validation evidence — recorded here, not re-run by this decision

AT-M3.6B.1 used the bounded remediation policy AT-M1 established and AT-D18 restated, and it needed
it. The chain is recorded as it happened:

```text
AT-M3.6B-PRODUCT-ARCHITECTURE-AUTHORIZATION-REVIEW-1: AUTHORIZED_FOR_IMPLEMENTATION.

  A read-only architecture review that decided how a live provider should attach to the existing
  reasoning architecture and which boundaries had to become implementation acceptance requirements.
  It chose no vendor and authorized no call; AT-D24 did both.

AT-M3.6B.1-LIVE-PROVIDER-ADAPTER-LIMITS-1 (implementation, d1d7bc6):
  READY_FOR_INDEPENDENT_VALIDATION.

  One adapter behind the AT-M3.1 provider protocol, driven by the AT-M3.1 service, changing WHO
  authors a typed artifact and nothing else. The two PRE-M3.6B backlog items AT-D23 section 6
  carried -- the unbounded reasoning artifact column and the unbounded PlanContent step count --
  were closed as application-level bounds on NEW writes, with no database constraint added, because
  a limit that makes stored history unreadable destroys the evidence it exists to protect.

AT-M3.6B.1-INDEPENDENT-VALIDATION-1: FAIL. Two load-bearing findings.

  1  RETRY_AUTHORITY_CLAIM_FALSE. provider_timeout, rate_limited and provider_unavailable were
     documented as retryable and behaved terminally: the first transient failure wrote a FAILED row,
     and the next call for that correlation_id replayed it. There was never an attempt 2. The
     public claim was false.

  2  BUDGET_LEDGER_FAILURE. A provider call could land, the post-call usage write could fail, the
     failure was swallowed, and the daily and monthly totals understated that charge permanently --
     so a later pre-flight would authorize spend the account could not afford.

AT-M3.6B.1-IMPLEMENTATION-REMEDIATION-1 (14c3820): READY_FOR_VALIDATION_2.

  One bounded remediation, and exactly one. Both defects were ordering problems wearing the costume
  of error handling, and both were fixed by changing WHEN something happens rather than by adding a
  layer that watches it -- no scheduler, no queue, no daemon, no reconciliation job, no caller-side
  retry framework and no second authority.

  Retry: ReasoningService advances the same invocation to its next attempt on a known transient
  answer, in the same invoke, via one atomic compare-and-swap guarded on the current owner's token,
  the still-started status and the attempt budget. Lease takeover was deliberately NOT reused --
  takeover recovers a worker that has gone silent, and a provider that answered "429" has not.

  Budget: the spend is claimed before the wire, keyed on invocation_id:attempt with a unique index,
  and one ledger row carries an attempt from reservation to settlement -- so the totals can count
  reservations and settlements together with no way to count an attempt twice, and the worst a
  settlement failure can do is leave a charge conservative.

AT-M3.6B.1-INDEPENDENT-VALIDATION-2 / 2 FINAL: PASS. No Validation 3.
```

**Independent Validation 1 was a FAIL and is recorded here as a FAIL.** It is not restated as a pass
because a later remediation succeeded; the value of the record is that it says what happened. This
record states the results of validations performed independently, before this decision, and does not
re-derive them.

## 6. Retained non-blocking backlog

Recorded here so they are not rediscovered as if new. None blocks AT-M3.6B.1 acceptance or this
merge, and none is authorized for remediation by this record.

```text
1  Historical stage-freeze / meta test failures.
   Disposition: P3 / HISTORICAL_ONLY / NON_BLOCKING (see section 7)

2  HAZARD_AT_M3_LIVE_DENYLIST -- open since the AT-M3.1 canonical merge, tracked in
   AI_AGENTS_PM_STATE section 8 as a separate Product Owner item. It does not block this
   acceptance and this record does not dispose of it.
   Disposition: SEPARATELY TRACKED PO ITEM / NON_BLOCKING

3  AutonomyReadStore._session() recurses into itself instead of opening a private connection when
   no shared connection is open. Unreachable on every shipped product path, all six AT-M3.6A
   endpoints open store.session() first. Carried unchanged from AT-D23 section 6 item 1.
   Disposition: P3 / PRODUCT_HARDENING / CURRENT_PRODUCT_PATH_UNREACHABLE / NON_BLOCKING

4  A privileged raw-SQL DELETE of goal_execution_lineage can discard the plan-step mapping that
   migration 042's fail-closed DOWN exists to protect. The product API exposes no such path.
   Carried unchanged from AT-D23 section 6 item 2 and AT-D22 section 6.
   Disposition: P3 / DB_HARDENING / OUTSIDE_PRODUCT_API_CONTRACT / NON_BLOCKING
```

**The two PRE-M3.6B items are CLOSED by this acceptance.** AT-D23 section 6 item 3 (the unbounded
`reasoning_invocations.artifact` column) and item 4 (the unbounded `PlanContent` step count) are
answered by the accepted implementation: 256 KiB and 40 steps respectively, plus per-step list
bounds of 10, enforced on new writes at the adapter, the service and the store. They are not carried
forward.

Under AT-D18-R05 the four items above remain `NON-BLOCKING` by default. Item 2 touches an
external-model control and is therefore *tracked* rather than dismissed; it is a Product Owner
disposition item, and this record neither closes it nor lets it block a merge of work that does not
depend on it. Items 1, 3 and 4 reach no production-authorization, human-approval, external-model,
secret-handling, destructive-action, audit-integrity or security-boundary control exposed through
the product API. They become blocking only on concrete P0/P1 evidence, which does not exist today.

The AT-M3.6A observation in AT-D23 section 6, the six AT-M3.3 observations in AT-D20 section 7, the
four AT-M3.2 observations in AT-D19 section 6 and the one AT-M3.1 observation in AT-D15 are
unchanged and are not restated here.

## 7. Governance drift, and a class of failure deliberately left alone

AT-M3.6B.1 raised **two** `GOVERNANCE_DRIFT_ALERT`s across its implementation and its remediation,
both the same defect and both recorded in full in `source/progress.md`. Together with AT-D23 section
7's alert, that makes **three occurrences of one pattern**, and the third was written by the same
hand that raised the second.

The pattern: a slice-scoped test asserting that its own migration is the last that will ever exist —
`max(numbers) == 43`, `max(numbers) == 44`, or an enumerated list of the files this slice added.
Every such assertion forbids every later authorized migration by construction, so the next slice's
first migration fails a previous slice's test. It has now been amended in AT-M3.4, AT-M3.5,
AT-M3.6A and twice in AT-M3.6B.1.

Each was amended in place to assert the property its own name claims — no migration at or below
canonical main's last is edited, the new number was derived from repository truth, exactly one file
claims it, and it follows the previous one — and the AT-M3.6B.1 remediation's own migration-045 test
was written that way from the start. Changing a canonical migration still fails all of them.

**No mechanism was added in response, at any point.** That is deliberate and it is the AT-D18 rule:
the fix for a recurring assertion defect is to stop writing the assertion, not to build a control
that watches for it. A reservation ledger extension is not a budget governance platform and one
explicit attempt transition inside `ReasoningService` is not a retry scheduler.

Separately, three tests fail on the candidate that do not fail on canonical main:
`test_design_66ui4_fe1c_overview_brief::test_no_runtime_paths_changed`,
`test_design66ui4_fe1d_navigation_microcopy::test_no_runtime_paths_changed` and
`test_stage_gate_compliance::test_verifier_marker_pass`. Each runs `git diff --name-only
origin/main...HEAD` and fails if any path under `apps/`, `shared/`, `migrations/`, `infra/`,
`services/` or `database/` appears, so on canonical main they pass vacuously and on any
implementation branch they fail. This was demonstrated rather than argued during AT-M3.6B.1: a
branch cut from `e50d422` whose only change is one empty `shared/sdk/probe_only/__init__.py` fails
precisely those three and nothing else. They carry no P0/P1 risk and are **not** repaired by this
record, for the reason AT-D23 section 7 gives: amending another stage's governance artifact from an
AT-M3 product slice would be reaching into that stage's authority to make this slice's number look
better.

## 8. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B.2, live validation, or any real external LLM/network call
Does NOT authorize enabling REASONING_LIVE_NETWORK_ENABLED
Does NOT authorize fetching, validating or exercising a real external model credential
Does NOT authorize any diagnostic external call, probe, smoke test or health check
Does NOT claim that real Anthropic connectivity, credentials, latency, model behaviour or billing
   have been established -- zero real calls were made, and no record in this repository says
   otherwise
Does NOT pre-authorize any previously DISCUSSED live-validation envelope. A call count, a total
   cost ceiling, a per-call ceiling, the allowed verbs, the environment, the gate enablement, the
   credential use and the abort conditions must all be named explicitly by a future Product Owner
   decision before the first real external call
Does NOT authorize AT-M4 or any real work execution
Does NOT authorize a live consumer for the stream.plan_delegation namespace
Does NOT authorize an authenticated agent execution ingress, an auth framework, a bearer completion
   token or a signed callback
Does NOT authorize any frontend or Admin Console implementation
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT modify, read for mutation, or bypass the HumanApproval boundary
Does NOT retire, reduce or reclassify PCP debt
Does NOT dispose of HAZARD_AT_M3_LIVE_DENYLIST
Does NOT amend AT-D14, AT-D20, AT-D21, AT-D22, AT-D23 or AT-D24
Does NOT amend or reopen AT-D18, and does not reopen AT-D16 or AT-D17
Does NOT add a verifier, registry, model registry, provider registry, budget governance platform,
   retry framework, exemption mechanism, reconciliation daemon, meta-verifier, approval hierarchy,
   decision-discovery or canonical-activation mechanism
Does NOT remediate any observation in section 6
Does NOT repair the Step 66 stage-freeze guards described in section 7
Does NOT decide what follows AT-M3.6B.1 -- AT-M3.6B.2 and AT-M4 are both separate Product Owner
   decisions and no record in this repository makes either
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
