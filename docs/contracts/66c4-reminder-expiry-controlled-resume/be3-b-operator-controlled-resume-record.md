# Step 66C.4-BE3-B — Operator-Controlled Resume Request, Authorization and Gated Execution Command

> **Implementation record. Operator-controlled resume request/authorize/gated-execution FOUNDATION
> on the shared BE3 feature branch (Draft PR #20, NOT FOR MERGE). No orchestrator call, no resume
> execution, no event publish, no deployment, no activation. BE3-C NOT started.**

Marker: `STEP66C4_BE3_B_OPERATOR_RESUME_VERIFY: PASS` (self-verification only; the combined
independent **BE3-R** review over BE3-A+B+C is still the required gate before any merge/activation).

## What BE3-B adds

```text
migrations/033_be3_resume_requests.sql (+ _down)     -- durable resume_requests table (additive)
shared/sdk/tasks/resume_request_model.py             -- states, reason codes, gates, projections, safe command payload
shared/sdk/tasks/resume_request_repository.py        -- transaction-aware CAS repo + row locks + confirmation ops
shared/sdk/tasks/resume_service.py                   -- eligibility + BE3-A authorization + outbox/audit orchestration
apps/orchestrator/src/operations_resume_api.py       -- /operations/resume-requests API (DISABLED-BY-DEFAULT)
shared/sdk/tasks/lifecycle_outbox.py                 -- + resume.* audit events and the resume.execution_requested command
```

## Design decisions

1. **Durable request entity vs. clarification markers (no parallel conflicting fields).** The
   authoritative clarification-level markers `resume_eligible_at` / `resume_requested_at` /
   `resume_requested_by` / `resume_authorized_at` stay on `operator_clarification_requests`
   (migration 031). `resume_requests` (033) is the durable REQUEST entity with its own lifecycle
   (`execution_requested_at`/`resumed_at`/`failed_at`/`canceled_at`/`expired_at`, `command_id`,
   `state`) which has no clarification-column equivalent. The "one active request per clarification"
   invariant is enforced BOTH by the `resume_requested_at IS NULL` CAS (create transaction) and by
   the `uq_rr_active_per_clarification` partial unique index. A terminal, non-resumed request
   (cancel/reject/expire/fail) RELEASES the clarification markers so a NEW request is possible
   (recovery is always a new request); a `resumed` request keeps them.
2. **not_eligible / eligible are pre-request projections.** They are derived from authoritative DB
   state at request time; no durable request row exists until `authorization_pending`. `eligible` is
   not a stored request state.
3. **Scope.** `resume_requests.team_id` / `.project_id` are UUID **NOT NULL** (BE3-A-C2 parity); a
   resume request is always team- and project-bound and NULL is never a scope wildcard. `team_id` is
   the actor-declared scope (no team entity upstream yet); `project_id` is additionally cross-checked
   against `operator_tasks.project_id` when the task has one (mismatch → `not_found_masked`).
   `workflow_id` is nullable (no separate workflow entity yet; the task is the resume anchor).
4. **Execution command = the canonical durable outbox.** The `resume.execution_requested` command is
   a single `clarification_lifecycle_outbox` row (one destination → orchestrator); `command_id` is
   that row's id, persisted on `resume_requests`. Identifiers only — never a raw clarification/answer
   body. The resume audit events (`resume.requested/authorized/rejected/canceled/resumed/failed`) are
   also durable outbox rows written in the SAME transaction as their state change.
5. **Actors.** Operators authenticate via the existing fail-closed test auth. The POLICY/SAFETY
   AUTHORITY is a server-configured capability (`BE3_RESUME_POLICY_AUTHORITY_CAPABILITY` + header),
   never a client-asserted role/body/query; `is_policy_authority` is set server-side only. A plain
   operator (incl. the requester) cannot human-authorize a resume (`policy_authority_required`).
   Execution preparation is Service-Identity-only and internal (NO endpoint); it consumes the
   single-use authorization via the BE3-A `authorization_service.consume`, so the production-effect
   gate is unchanged.

## Transaction boundaries

Create / authorize / reject / cancel / prepare-execution each run in ONE transaction that locks the
clarification + task rows (`FOR UPDATE`), re-validates eligibility/scope/state-version, applies the
authorization transition (BE3-A) and the resume-request transition, and writes the durable evidence
row — all atomically. In `prepare_execution` the authorization consume + `execution_pending`
transition + `resume.execution_requested` outbox insert commit together; an outbox failure rolls
back the consume (no consumed authorization is ever left without its command).

## Feature gates (disabled-by-default, env-only)

```text
BE3_RESUME_API_ENABLED=false       -- the whole /operations/resume-requests router 503s when off; no DB access
BE3_RESUME_COMMAND_ENABLED=false   -- prepare_execution does NOTHING when off (no consume, no outbox)
```

Gate state is read from the process environment only — never from a request body/query/header.

## Verification

```text
STEP66C4_BE3_B_OPERATOR_RESUME_VERIFY: PASS
Tests: see docs/test/step66c4-be3-b-operator-controlled-resume-record.md (isolated ephemeral
PostgreSQL 16; 0 failed / 0 skipped). ruff / black / mypy clean.
No orchestrator call, no resume execution, no replay_dead, no BE3-C, no shared migration/deployment/
activation. production_executed_true_count = 0. Draft PR #20 NOT merged. Combined BE3-R required.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
