# Step 66C.4-BE3-P — Operator-Controlled Resume and Replay Authorization Contract

> **Planning/contract document only. No backend, API, DB migration, frontend, or deployment code is
> written or authorized by this stage. BE3 implementation requires a separate, explicit Product
> Owner authorization. The BE1 Runtime Compatibility Gate and the disabled-by-default posture of the
> lifecycle poller, the outbox relay, and `replay_dead` remain in force.**

## 1. Scope

This contract defines, as design only, the binding model for ten capabilities:

```text
1. Operator-controlled resume request        6. Authorized dead-event replay
2. Resume eligibility                          7. Team/operator RBAC
3. Policy and safety authorization             8. Human confirmation and audit evidence
4. Durable authorization outcome               9. Idempotency, concurrency, failure handling
5. Orchestrator resume confirmation           10. Runtime activation and rollback boundary
```

It EXTENDS the existing `controlled-resume-contract.md` (Option A, recommended and assumed here),
`rbac-and-safety-contract.md`, `data-model-contract.md`, and `api-and-event-contract.md`; it does
NOT fork a second resume model. The companion BE3-P documents own the detail:

```text
be3-rbac-permission-matrix.md            -- roles, actions, permission matrix, separation rules
be3-resume-replay-state-machine.md       -- resume + replay state machines (per-transition contract)
be3-api-event-contract.md                -- API endpoints, event and audit contract
be3-security-and-threat-model.md         -- security requirements + threat analysis
be3-runtime-activation-gate.md           -- prerequisites before any activation
be3-implementation-slicing-plan.md       -- BE3-A/B/C/R/M slices
```

## 2. Binding product flow (preserved, never collapsed)

```text
answer recorded -> resume eligible -> operator requests resume -> policy/safety authorization
  -> durable event/evidence -> orchestrator confirms resumed
```

Each arrow is a separate, independently-observable, independently-audited transition. No step may be
collapsed into another (answering never implies resumed; requesting never implies resumed;
authorizing never implies resumed — only the orchestrator's confirmation establishes "resumed").

## 3. Product decisions already binding (carried forward, not re-litigated)

```text
- An operator's explicit resume request is a normal-task human confirmation, NOT a production
  approval; production-effect approval remains a separate, independent gate.
- An expired clarification can never be re-answered and never becomes resume-eligible; continuation
  after expiry requires a NEW linked clarification (not a resume of the expired one).
- replay_dead must NOT be exposed to any operator-facing surface until ALL of: team/operator RBAC,
  explicit human authorization, durable replay audit evidence, and authorization-outcome
  persistence exist (this contract designs exactly those prerequisites).
- Single durable destination: every resume/replay event uses one durable outbox destination with a
  downstream projection; no outbox row tracks multiple destinations.
- at-least-once command delivery + state-bound idempotency + durable authorization + orchestrator
  reconciliation. exactly-once is NOT claimed.
```

## 4. Product Owner decisions requested by this contract

The following are genuine PO decisions; this contract records a recommended default for each and
does NOT adopt any unilaterally. The detailed matrix lives in be3-rbac-permission-matrix.md §D.

```text
D1. May an Operator both request AND authorize their own resume?
    Recommended: for NORMAL non-production resume the "authorization" is the automated policy/safety
    check (no human authorizer), so self-request is fine; for DEAD-EVENT REPLAY, NO -- replay
    requires a distinct human Approver (two-person control; requester != approver).
D2. Does replay require two-person control?  Recommended: YES (requester != approver).
D3. May a Platform Administrator override policy?  Recommended: YES, only via an explicit,
    audited `override policy` permission (never silent), and NEVER for a production-effect task.
D4. Service Identity authority?  Recommended: a Service Identity may EXECUTE an already-authorized
    command only; it can never request or authorize.
D5. Production-effect resume/replay?  Recommended: Operator request + separate production approval +
    policy authorization (all three), unchanged from the existing production-effect gate.
```

Recommended authorization defaults (summary):

```text
Normal non-production resume:   Operator request + policy/safety authorization
Dead-event replay:              Operator request + Approver (human) authorization  [two-person]
Production-effect resume/replay: Operator request + production approval + policy authorization
```

## 5. Non-goals of this stage

```text
- No backend/API/migration/frontend/deployment code.
- No new runtime route registered; no public replay endpoint created.
- No activation of the lifecycle poller or outbox relay; no producer cutover; migration 031 not
  applied to any shared database.
- No second parallel RBAC system: the six canonical TASK_ROLES are reused verbatim.
```

## 6. Status

```text
Step 66C.4-BE3:  DESIGNED (contract only) / NOT IMPLEMENTED / NOT MERGED / NOT DEPLOYED / NOT ACTIVATED
Replay exposure: NONE (replay_dead remains internal-only)
Resume:          NOT ACTIVATED
production_executed_true_count: 0
Next authorization required: explicit Product Owner authorization of the first implementation slice
  (BE3-A), per be3-implementation-slicing-plan.md.
```

## Statement

Planning/contract document only. No implementation, no API, no migration, no frontend, no
deployment, no activation. No dispatch/resume/replay executed. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
