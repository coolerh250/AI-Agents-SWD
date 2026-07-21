# Observability and Audit Plan — Step 66C.4-P

> **Planning document only. No metrics/logging/audit code implemented. No Admin Console UI built.
> This document defines a read-only evidence contract for a later implementation stage to build.**

## Metrics

```text
poll_cycle_count               -- total poll cycles executed by the clarification-timeout worker.
poll_cycle_duration_seconds    -- histogram, per cycle.
reminder_claims_total          -- count of rows successfully claimed for reminder, per cycle.
expiry_claims_total            -- count of rows successfully claimed for expiry, per cycle.
claim_conflict_total           -- count of CAS attempts that matched zero rows (a losing race) --
  expected to be near-zero; a sustained nonzero rate would indicate an unexpected contention
  pattern worth investigating, not itself an error.
reminder_count                 -- cumulative count of clarification_reminder_sent events.
expiry_count                   -- cumulative count of clarification_expired events.
resume_eligible_count          -- cumulative count of clarification_resume_eligible events.
resume_success_count           -- cumulative count of clarification_resume_authorized events
  (renamed from the prompt's "success" framing since "dispatched" is out of scope -- "authorized"
  is the furthest state this stage's implementation scope reaches).
resume_failure_count           -- count of resume-request attempts that failed the eligibility/
  policy check (with a "reason" label matching the reason codes in
  api-and-event-contract.md's resume-eligibility response).
duplicate_suppression_count    -- count of CAS attempts blocked by an already-set guard column
  (e.g. resume_requested_at IS NOT NULL) -- a normal, expected occurrence from duplicate UI clicks,
  not an error.
dlq_count                      -- reused directly from the EXISTING retry-scheduler DLQ metrics
  (stream.deadletter depth) -- no new DLQ concept introduced by this stage.
```

## Logs

```text
Structured log per poll cycle: cycle start/end timestamp, rows evaluated, rows claimed
  (reminder/expiry split), any error encountered.
Structured log per resume-request: clarification_id, requesting role, outcome
  (authorized/rejected + reason), timestamp.
No raw clarification question/answer body ever logged -- matches the existing
  safe_workroom_refs (hash/length-only) convention.
```

## Audit events (all follow the existing `audit_events.py` allowlist-projection pattern —
reachable only via the existing, unmodified `GET /tasks/{id}/audit-evidence` endpoint)

```text
clarification_reminder_sent
clarification_expired
clarification_resume_eligible
clarification_resume_requested   (Option A only)
clarification_resume_authorized
```

Each audit event carries only: `task_id`, `clarification_id`, `occurred_at`, `actor` (for
resume-requested only), and a safe status/reason string — never raw message content, matching
every existing audit event type in this system.

## Health checks

```text
Standard container healthcheck for the new clarification-timeout worker (matches every other
  service in this project's docker-compose definition).
"Last successful poll cycle timestamp" gauge -- if this timestamp falls too far behind "now"
  (threshold: 5x the poll interval, i.e. 5 minutes at the recommended 60s interval), it signals a
  stalled worker requiring operator attention. This is a NEW metric this stage proposes (no
  existing precedent for "worker liveness beyond container healthcheck" in this repo, since every
  existing background worker is event-driven and has no natural "am I keeping up" signal the way
  a poller does).
```

## Stuck clarification detection

```text
A clarification whose reminder_at has passed but reminder_sent_at remains NULL for longer than
  one poll interval is, by definition, evidence of a stalled worker (covered by the health-check
  gauge above) -- no SEPARATE per-clarification "stuck" detector is proposed, since the worker-
  liveness gauge already covers this at the aggregate level, more efficiently than a per-row check.
```

## Overdue scheduler lag

```text
Derivable directly from poll_cycle_duration_seconds and the "last successful poll cycle" gauge
  above -- no separate metric needed.
```

## Prohibited from being logged/recorded anywhere in this contract

```text
- Secrets, tokens.
- Raw sensitive clarification question/answer content (only hash/length-safe references, per the
  existing safe_workroom_refs pattern).
- Full external payload (moot for this stage -- no external channel integration is proposed at
  all).
```

## Admin Console read-only evidence contract (future UI, NOT built by this stage)

```text
A future Admin Console surface (out of this stage's implementation scope; see
  frontend-ux-boundary.md and implementation-stage-slicing-plan.md's 66C.4-FE slice) could read:
  - the new GET .../lifecycle endpoint (api-and-event-contract.md) for a per-clarification
    lifecycle banner.
  - the new GET .../resume-eligibility endpoint for the resume-readiness state.
  - the EXISTING GET /tasks/{id}/audit-evidence endpoint for the new audit event types, with zero
    change to that endpoint's own shape.
No new UI is built by this planning stage.
```

## Statement

Planning document only. No metrics/logging/audit code implemented. No Admin Console UI built. This
document defines a read-only evidence contract for a later implementation stage to build.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
