# Step 66C.4-BE3-P → Implementation Handoff

> **Handoff. Planning/contract only. BE3 implementation is NOT authorized by this handoff — each
> slice (BE3-A/B/C) requires its own explicit Product Owner authorization. No merge, deploy, or
> activation.**

## What is designed (read these, in order)

```text
be3-operator-resume-replay-authorization-contract.md  -- master contract + PO decisions D1-D5
be3-rbac-permission-matrix.md                          -- roles, 13 actions, matrix, separation rules
be3-resume-replay-state-machine.md                     -- resume + replay state machines
be3-api-event-contract.md                              -- durable authorization, API, events, concurrency
be3-security-and-threat-model.md                       -- security requirements + T1-T8 threats
be3-runtime-activation-gate.md                         -- 11 activation prerequisites + rollback
be3-implementation-slicing-plan.md                     -- BE3-A/B/C/R/M + verification policy
```

## Binding constraints carried into implementation

```text
- Reuse the six canonical TASK_ROLES; do NOT create a second RBAC.
- Preserve the flow: answer -> eligible -> request -> authorization -> durable evidence -> confirmed.
- Durable authorization: resource-bound, action-bound, single-use, time-bounded, state-version-bound.
- Replay: two-person control (requester != approver); only 'dead' rows; event_id/idempotency_key
  preserved; attempts never reset; internal adapter only (no public replay endpoint; no Admin Console
  direct repository access; service identity may execute but never authorize).
- Single durable destination per outbox row; at-least-once + state-bound idempotency; exactly-once NOT
  claimed.
- Dispatch GATED/DISABLED-BY-DEFAULT; enabling is a separate authorization.
- Production-effect tasks require the separate production approval gate; no role bypasses it.
- No raw clarification/answer content, no secret/DSN in any authorization record, audit payload, log,
  or health response; reason codes from a bounded allowlist.
```

## Verification policy for BE3

```text
- BE3-A + BE3-B + BE3-C by ONE implementation flow.
- ONE independent security/transaction review (BE3-R) over the whole; findings -> original reviewer
  focused closure (no default fresh reviewer).
- BE3-M non-squash merge only after PO authorization.
```

## Posture

```text
BE3 status:        DESIGNED (contract only) / NOT IMPLEMENTED / NOT MERGED / NOT DEPLOYED / NOT ACTIVATED
Replay exposure:   NONE (replay_dead internal-only)
Migration 031:     present in repo, NOT applied to a shared DB
Codex / Claude Design: NOT authorized
production_executed_true_count: 0
Next authorization required: explicit PO authorization of BE3-A (first implementation slice).
```

## Statement

Handoff only. No implementation, no merge, no deployment, no activation. No production or external
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
