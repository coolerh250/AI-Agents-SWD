# AT-D15 — AT-M3.1 acceptance & canonical merge authorization

> **Product Owner decision record. Accepts AT-M3.1 and authorizes merging the validated candidate
> into `main`. Authorizes no real external LLM call (M3.6B), no production action, no AT-M4
> execution and no PCP remediation. `production_executed_true_count: 0`.**

```text
AT-D15:                      RESOLVED / BINDING
Recorded_on:                 2026-08-24
Recorded_by:                 Product Owner
Canonical_main_at_decision:  44cdd6f14333915932428d190b0a3e117d033b6d
Validated_candidate:         1ba197a91867e77a9fa2256289b2766317b51b41
Branch:                      at-m3.1-reasoning-contract-provider-abstraction
Depends_on:                  AT-D14 (docs/decisions/at-d14-at-m3-live-reasoning-authorization.md)
```

## 1. What this record is for

AT-D14 authorized non-production, non-external-network implementation and mock/local validation of
AT-M3.1 through AT-M3.6A but said nothing about accepting a specific implementation or merging it
into `main`. This record is that separate authorization: the Product Owner accepts the AT-M3.1
capability (Reasoning Contract & Provider Abstraction) as validated, and approves canonicalizing
the validated candidate branch into `main`. It is the only place the AT-M3.1 acceptance and merge
authorization is recorded.

## 2. What is authorized

```text
Merge scope:                   fast-forward canonicalization of the validated candidate into main
Documentation-only authority:  this record and the reconciliation commit it authorizes
Post-merge verification:       bounded source-of-truth checks only
```

## 3. What is NOT authorized

```text
M3.6B / real external LLM calls  NOT AUTHORIZED -- unchanged from AT-D14, no path to one is added
External model credentials       NOT AUTHORIZED
Production action                NOT AUTHORIZED -- unchanged, no path to one is added
Production authorization         NOT GRANTED -- unchanged
AT-M4 implementation             NOT AUTHORIZED -- code/command/test/tool execution, DebugAttempt,
                                   debug -> replan back-edge all remain out of scope
AT-M3.2 .. AT-M3.6A implementation NOT STARTED by this record -- AT-D14 already authorizes their
                                   eventual implementation; each still needs its own implementation
                                   report and its own Validation 1/2 pass before acceptance, the
                                   same discipline this record now closes out for AT-M3.1
PCP remediation                   NOT AUTHORIZED by this record
Unrelated runtime changes         NOT AUTHORIZED -- this record covers AT-M3.1 acceptance and its
                                   merge only
```

## 4. Validation evidence — recorded here, not re-run by this decision

AT-M3.1 (reasoning contract, vendor-neutral provider protocol, deterministic mock provider,
durable `ReasoningInvocation` metadata, `ReasoningService`) went through two validation passes in
this session, per the bounded remediation policy AT-M1 established (Validation 1 -> at most one
remediation -> Validation 2, no Validation 3):

```text
AT-M3.1 Validation 1 (2026-08-21..24 session): FAIL -- 3 material blockers
  1. Durability/traceability: a provider invocation could leave zero durable evidence if
     terminal persistence failed after a successful call -- proven by a store whose
     record_invocation() raised after the provider had already produced an artifact.
  2. Replay/concurrency correctness: the check-then-act replay guard allowed concurrent callers
     to race past the check; proven under REAL PostgreSQL that 10 concurrent invoke() calls
     sharing one correlation_id invoked the provider 10/10 times, and a 6-caller attribution
     probe showed every racer receiving its OWN genuinely-computed artifact paired with the
     SAME (winning) invocation_id -- an artifact/evidence misattribution.
  3. failure_reason safety: forbidden-marker/secret-shaped text (chain_of_thought, API-key- and
     Bearer-token-shaped strings) could reach durable storage verbatim, both via direct store use
     (no store-layer content-safety check) and via an unredacted provider exception message in
     the normal service path.

AT-M3.1-REMEDIATION-1 (bounded, single pass):
  - Atomic execution ownership: migration 037 amended in place (never canonical on main) to add a
    'started' state; ReasoningInvocationStore.try_begin_invocation() claims a correlation_id via
    INSERT ... ON CONFLICT DO NOTHING BEFORE any provider call; complete_invocation() transitions
    started -> succeeded|failed via UPDATE ... WHERE status='started', so a terminal row can
    never be overwritten and a losing caller never invokes the provider.
  - Explicit ReasoningResult.disposition ("fresh" | "replay" | "in_progress") replaces the
    implicit succeeded+artifact=None shape; a terminal-persistence failure now raises
    ReasoningPersistenceError rather than returning the artifact as an authoritative success,
    with the durable 'started' row surviving as evidence.
  - sanitize_failure_reason() (reusing redact_text + the existing FORBIDDEN_CONTENT_KEY_MARKERS
    vocabulary) is applied at both the service and the store layer, mirroring
    TeamStore.post_message's established defense-in-depth precedent.

AT-M3.1 Validation 2 (final, this session): PASS
  - 20/20 independent repeated real-PostgreSQL runs of 10 concurrent invoke() calls sharing one
    correlation_id: exactly 1 provider call, exactly 1 fresh result, 0 misattributed artifacts,
    1 durable row, every run.
  - An independently-connected reader confirmed the 'started' row is visible on real Postgres
    BEFORE the provider is ever invoked; a durable-claim failure (simulated DB-unreachable)
    produced 0 provider calls.
  - Terminal-state immutability confirmed in both directions (succeeded->failed and
    failed->succeeded overwrite attempts both rejected, in-memory and on real Postgres);
    malformed terminal writes (invalid status, inconsistent succeeded+failure_category, missing
    completed_at) all rejected by the live database CHECK constraints, row left unchanged.
  - failure_reason sanitization re-confirmed closed on both the service-exception path and the
    direct-store path, on real Postgres, while an ordinary failure message survives unmodified.
  - Provider fail-closed behaviour, zero-network-import, metadata-only persistence, and existing
    task-LLM (224 passed) / AT-M2 (52 passed, 9 DB-skip) regression suites all re-confirmed with
    no new AT-M3.1 regression.
  - One non-blocking observation carried forward, explicitly NOT remediated in scope: an
    unvalidated, caller-supplied `request.provider_name` can flow into an AUDIT event's
    summary/refs when a client is configured. This does not touch `reasoning_invocations` (the
    metadata this slice governs), mirrors a pre-existing repo-wide audit-construction pattern
    shared by every other AT-M2 `_audit` caller, and is not one of the three blockers above --
    carried as backlog for a future observability/audit-hardening slice, not for AT-M3.2.

Validation 2 PASS. No blockers. No Validation 3 required or permitted. This record does not claim
Validation 2 was re-run by the merge/acceptance step itself -- it was performed earlier in the same
session, independently, before this acceptance decision.

## 5. What this decision does NOT do

```text
Does NOT authorize AT-M3.6B or any real external LLM/network call
Does NOT authorize AT-M3.2 .. AT-M3.6A implementation -- AT-D14 already authorizes it; this
   record accepts and merges AT-M3.1 only
Does NOT grant production authorization -- NOT GRANTED, unchanged
Does NOT authorize AT-M4
Does NOT relax TASK_ROLES, RBAC, policy or approval
Does NOT retire, reduce or reclassify PCP debt
Does NOT amend AT-D14
Does NOT remediate the non-blocking provider_name/audit observation above
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
