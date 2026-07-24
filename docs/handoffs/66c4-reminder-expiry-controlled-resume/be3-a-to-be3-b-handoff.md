# Step 66C.4-BE3-A → BE3-B Handoff

> **Handoff. BE3-A durable authorization foundation is complete on the shared BE3 feature branch
> (Draft PR, NOT FOR MERGE). BE3-B is NOT authorized by this handoff — it requires a separate,
> explicit Product Owner authorization.**

## What BE3-A provides

```text
migrations/032_be3_resume_replay_authorization.sql  -- resume_replay_authorizations (durable, additive)
shared/sdk/tasks/authorization_model.py             -- enums, reason codes, state projection, safe payload
shared/sdk/tasks/authorization_repository.py        -- CAS: create_request/approve/reject/cancel/revoke/consume/expire
shared/sdk/tasks/authorization_policy.py            -- RBAC + isolation + two-person + production gate
shared/sdk/tasks/authorization_service.py           -- internal orchestration -> safe structured outcome
```

## What BE3-B must build (resume request/authorize/execution command)

```text
- /operations/resume-requests (create/get/authorize/reject/cancel) endpoints, per be3-api-event-contract.md,
  with RBAC (403), 404-masking, 409/idempotency, audit evidence, one transaction per state change.
- The resume execution command is GATED/DISABLED-BY-DEFAULT (dispatch_enabled hardcoded false) and
  publishes a single durable outbox row consumed by the orchestrator; the orchestrator confirms resumed.
- Consume a resume authorization via authorization_service.consume (Service Identity), then publish the
  gated command; NEVER execute resume directly and NEVER bypass the authorization.
- Reuse the resume state machine in be3-resume-replay-state-machine.md; the authorization foundation
  here backs the authorization-bearing transitions.
```

## Binding constraints carried forward

```text
- Consuming an authorization does NOT execute resume; execution is a separate, gated step.
- Single durable destination per outbox row; at-least-once + state-bound idempotency; exactly-once NOT claimed.
- Production-effect resume requires the separate production approval; no role bypasses it.
- No public replay endpoint; replay_dead stays internal-only (that is BE3-C).
- No shared activation, no producer cutover, no deployment, no migration applied to a shared DB.
```

## Verification policy

```text
BE3-A + BE3-B + BE3-C are one implementation flow on this feature branch (distinct commits + markers).
After BE3-A+B+C complete, ONE independent security/transaction review (BE3-R) runs over the whole;
findings -> the original reviewer performs a focused closure. BE3-M merges only after PO authorization.
```

## Posture

```text
BE3-A: complete (self-verified)  |  BE3-B: NOT authorized, NOT started  |  BE3-C: NOT started
PR: Draft / NOT FOR MERGE  |  Combined BE3-R: REQUIRED  |  Codex / Claude Design: NOT authorized
replay_dead: internal-only  |  production_executed_true_count: 0
Next authorization required: explicit Product Owner authorization of Step 66C.4-BE3-B.
```

## Statement

Handoff only. No resume/replay execution, no public endpoint, no merge, no deployment, no activation.
No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
