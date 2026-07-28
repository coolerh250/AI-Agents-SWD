# Step 66C.4-BE3-A+B+C → Combined BE3-R Handoff

> **Handoff. BE3-A, BE3-B, and BE3-C are ALL complete (self-verified) on the shared BE3 feature
> branch (Draft PR #20, NOT FOR MERGE). This handoff does NOT authorize BE3-R, merge, deployment, or
> activation — the combined independent review requires a separate, explicit Product Owner
> authorization, as does everything after it.**

## What BE3-A + BE3-B + BE3-C provide (one implementation flow, distinct commits + markers)

```text
BE3-A  migrations/032 + authorization_model/repository/policy/service
       -- durable resume/replay authorization: single-use, time-bound, state-version-bound,
          revocable, two-person (replay), service-identity consume-only, production gate.
       (+ BE3-A-C1: dual-layer scope enforcement, policy-authority-only resume authorization,
          canonical UUID scope types)
       (+ BE3-A-C2: NULL-scope wildcard closure -- exact null-safe equality, NOT NULL scope columns)

BE3-B  migrations/033 + resume_request_model/repository/service + operations_resume_api.py
       -- operator-controlled resume request/authorize/gated-execution-command foundation.
       (+ BE3-B-C1: policy-authority trusted-principal binding [hmac.compare_digest + a
          server-configured principal id, never a client-asserted role]; command outbox
          destination routing [EVENT_DESTINATIONS classification; the BE2 audit relay can never
          claim/mis-publish an orchestrator-command row])

BE3-C  migrations/034 + replay_request_model/repository/service + operations_replay_api.py
       -- two-person-controlled dead-event replay request/authorize/gated-execution foundation.
       (includes a request_authorization savepoint composability fix in authorization_service.py,
       needed because replay has no pre-authorization claim gate like resume's clarification CAS)
```

## Markers (all self-verification only)

```text
STEP66C4_BE3_A_AUTHORIZATION_FOUNDATION_VERIFY: PASS
STEP66C4_BE3_A_CONTRACT_ALIGNMENT_VERIFY: PASS
STEP66C4_BE3_A_NULL_SCOPE_CLOSURE_VERIFY: PASS
STEP66C4_BE3_B_OPERATOR_RESUME_VERIFY: PASS
STEP66C4_BE3_B_AUTHORITY_ROUTING_ALIGNMENT_VERIFY: PASS
STEP66C4_BE3_C_AUTHORIZED_REPLAY_VERIFY: PASS
```

## What BE3-R must review

```text
- The full authorization model (single-use/time-bound/state-version-bound/revocable) across BOTH
  resume and replay usages, including the two request-side savepoint compositions.
- The dead-episode resource_state_version design (dead_at:attempts composite) for replay -- does it
  hold under every realistic concurrency/reconciliation scenario, not just the tested ones?
- The policy-authority trusted-principal + capability model (BE3-B) and the two-person Approver
  model (BE3-C) -- are these the right long-term shape, or does either need a real identity/secret
  management system before activation?
- Destination readiness and the runtime activation gate (be3-runtime-activation-gate.md) -- BOTH
  resume execution and replay execution are structurally blocked today (no consumer exists for
  either); confirm the activation gate's 11 items remain sufficient before any future activation.
- Rate-limit defaults (3 successful replays / 24h; 10 requests/actor/24h) -- product-level review of
  whether these conservative defaults are appropriate.
- Full security/threat-model re-check against be3-security-and-threat-model.md.
- Transaction/concurrency correctness across all three: request/authorize/reject/cancel/execute
  races, rollback completeness, idempotency identity stability under retry.
```

## Binding constraints carried forward (unchanged)

```text
- Consuming an authorization does NOT execute; execution is a separate, gated, internal-only step.
- Single durable destination per outbox row; at-least-once + state-bound idempotency; exactly-once
  NOT claimed.
- Production-effect (resume or replay) requires the separate production approval; no role bypasses it.
- Exact null-safe NOT NULL scope everywhere; NULL is never a wildcard; policy + repository dual-layer.
- No shared activation, no producer cutover, no deployment, no migration applied to a shared DB.
- No public execute/replay-now endpoint for either resume or replay.
```

## Verification policy (unchanged from be3-a-to-be3-b-handoff.md)

```text
After BE3-A+B+C complete (NOW), ONE independent security/transaction review (BE3-R) runs over the
WHOLE combined implementation; findings -> a focused closure by the original reviewer. BE3-M merges
only after explicit Product Owner authorization, separate from the BE3-R authorization itself.
```

## Posture

```text
BE3-A: complete (self-verified)  |  BE3-B: complete (self-verified)  |  BE3-C: complete (self-verified)
PR: Draft #20 / NOT FOR MERGE  |  Combined BE3-R: REQUIRED, NOT YET AUTHORIZED
Codex / Claude Design: NOT authorized  |  replay_dead: internal-only, never called in any shared runtime
production_executed_true_count: 0
Next authorization required: explicit Product Owner authorization of the combined BE3-R review.
```

## Statement

Handoff only. No resume/replay execution in any shared runtime, no public endpoint beyond what is
documented, no merge, no deployment, no activation. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
