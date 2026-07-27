# Step 66C.4-BE3-B → BE3-C Handoff

> **Handoff. BE3-B operator-controlled resume foundation is complete on the shared BE3 feature
> branch (Draft PR #20, NOT FOR MERGE). BE3-C is NOT authorized by this handoff — it requires a
> separate, explicit Product Owner authorization.**

## What BE3-A + BE3-B provide

```text
migrations/032_be3_resume_replay_authorization.sql   -- durable resume/replay authorization (BE3-A)
migrations/033_be3_resume_requests.sql               -- durable resume request entity (BE3-B)
shared/sdk/tasks/authorization_*.py                  -- authorization model/repo/policy/service (BE3-A)
shared/sdk/tasks/resume_request_model.py             -- resume request states/gates/projections (BE3-B)
shared/sdk/tasks/resume_request_repository.py        -- resume request CAS + locks + confirmation (BE3-B)
shared/sdk/tasks/resume_service.py                   -- resume request/authorize/gated-execution flow (BE3-B)
apps/orchestrator/src/operations_resume_api.py       -- resume-request API (DISABLED-BY-DEFAULT) (BE3-B)
```

## What BE3-C must build (dead-event replay)

```text
- /operations/replay-requests (create/get/authorize/reject/cancel) per be3-api-event-contract.md,
  reusing the BE3-A authorization model with action_type='replay' and resource_type='outbox_event'.
- Two-person control (requester != approver) at the authorize step (D2) -- already enforced by the
  DB chk_rra_replay_two_person constraint + authorization_policy two_person_required.
- A GATED/DISABLED-BY-DEFAULT internal Service-Identity path that consumes the replay authorization
  and calls the internal replay_dead adapter (dead -> pending, event_id + idempotency_key preserved,
  attempts NOT reset). replay_dead stays internal-only; NO public endpoint calls it directly.
- Reuse the replay state machine in be3-resume-replay-state-machine.md.
```

## Binding constraints carried forward

```text
- Consuming an authorization does NOT execute; execution is a separate, gated step.
- Single durable destination per outbox row; at-least-once + state-bound idempotency; exactly-once NOT claimed.
- Production-effect requires the separate production approval; no role bypasses it.
- Exact null-safe NOT NULL scope (BE3-A-C2); NULL is never a wildcard; policy + repository dual-layer.
- No shared activation, no producer cutover, no deployment, no migration applied to a shared DB.
```

## Verification policy

```text
BE3-A + BE3-B + BE3-C are one implementation flow on this feature branch (distinct commits + markers).
After BE3-A+B+C complete, ONE independent security/transaction review (BE3-R) runs over the whole;
findings -> a focused closure. BE3-M merges only after PO authorization.
```

## Posture

```text
BE3-A: complete (self-verified)  |  BE3-B: complete (self-verified)  |  BE3-C: NOT authorized, NOT started
PR: Draft / NOT FOR MERGE  |  Combined BE3-R: REQUIRED  |  Codex / Claude Design: NOT authorized
replay_dead: internal-only (BE3-C)  |  production_executed_true_count: 0
Next authorization required: explicit Product Owner authorization of Step 66C.4-BE3-C.
```

## Statement

Handoff only. No resume/replay execution, no orchestrator call, no public replay endpoint, no merge,
no deployment, no activation. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
