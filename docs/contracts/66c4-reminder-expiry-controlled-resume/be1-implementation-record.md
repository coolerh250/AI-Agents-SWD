# Step 66C.4-BE1 — Implementation Record

> **Backend foundation slice. Implementation complete, pending the mandatory independent review
> (Step 66C.4-BE1-R). NOT merged, NOT deployed, NOT production-validated. No scheduler, no outbox
> relay, no resume, no dispatch, no external notification, no deployment. Codex and Claude Design
> remain unauthorized. Step 66C.4-BE2 remains not started.**

Marker context: `STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS`

## What was implemented (branch `feature/66c4-be1-lifecycle-outbox-foundation`)

```text
1. Migration 031_clarification_lifecycle_outbox_foundation.sql (+ _down.sql):
   - Six additive NULLABLE lifecycle columns on operator_clarification_requests
     (reminder_sent_at, expired_at, resume_eligible_at, resume_requested_at,
     resume_requested_by, resume_authorized_at).
   - New durable clarification_lifecycle_outbox table (transactional-outbox foundation).
   - Partial indexes (idx_ocr_reminder_due, idx_ocr_expiry_due, idx_clo_pending_created,
     idx_clo_clarification_id), UNIQUE(idempotency_key), status/attempts/nonempty CHECK
     constraints, and a lifecycle-ordering CHECK
     (chk_ocr_resume_authorized_requires_eligible).
2. shared/sdk/tasks/workroom_store.py:
   - claim_clarification_answer gains the authoritative-deadline predicate
     `AND answered_at IS NULL AND due_at > now()` (PostgreSQL DB time; exclusive upper bound).
   - _clar_row serializes the six new lifecycle timestamps (additive, read-only).
3. shared/sdk/tasks/lifecycle_outbox.py (NEW, disabled foundation):
   - Transaction-aware insert (caller owns the txn; never commits/closes), payload-safety
     guard, event-type allowlist, and read-only helpers. No live producer imports it.
4. apps/orchestrator/src/workroom_api.py:
   - On a lost answer claim, re-reads authoritative row state and returns 409
     invalid_state_for_answer:expired when the loss was to the deadline (row still 'open').
     Reuses existing 409 shapes; the concurrent-answer case still returns
     clarification_already_answered. No new endpoint, no success-schema change.
```

## What was NOT done (by design / hard constraint)

```text
- No scheduler, no outbox relay, no background task, no application-startup registration.
- No live runtime producer writes to the outbox (verified statically).
- No resume request endpoint; no resume eligibility/authorization/dispatch/resume behavior.
- No new global task/clarification status value; clarification_expired is NOT materialized here.
- Existing audit publisher (shared/sdk/audit/**) and event bus (shared/sdk/event_bus/**) are
  unchanged (transport path untouched).
- No external notification. No deployment (test/staging/production). No production/external action.
- No Codex/Claude Design authorization. Step 66C.4-BE2 not started.
```

## Verification summary

```text
BE1 verifier: PASS. BE1 tests: 15 passed (10 DB-less/API + 5 real-Postgres integration incl.
concurrency), executed against an isolated ephemeral Postgres. Step 66C regression: 101 passed.
Ruff/black/mypy clean. Secret scan unchanged. production_executed_true_count: 0.
```

## Authorization posture

```text
Step 66C.4-BE1: implementation complete, pending independent review (Step 66C.4-BE1-R).
Step 66C.4-BE2: NOT STARTED / NOT AUTHORIZED.
Codex: NOT AUTHORIZED. Claude Design: NOT AUTHORIZED.
Merge: NOT authorized by this stage. Deployment: NOT authorized by this stage.
```

## Statement

Backend foundation implementation record. No scheduler activated. No outbox relay activated. No
existing producer switched to the outbox. No workflow dispatch/resume. No external notification. No
deployment. No production/external action. Independent review required before BE2/merge/deploy.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
