# Step 66C.4-BE1-R1 Context Receipt

```text
Stage: 66C.4-BE1-R1 -- Deadline CAS, Outbox Durability and Payload Safety Remediation
Partner: Claude Code (remediation implementation session)

Latest main reviewed:            e03c22d
Feature branch baseline:         d2467f5 (verified equal to HEAD before work began)
Independent review commit:       f5417f4 (read directly from the commit, not from a report)

Canonical contract reviewed: all docs under docs/contracts/66c4-reminder-expiry-controlled-resume/**
  including contract-source-of-truth-record.md and the BE1 Runtime Compatibility Gate.
PO decisions reviewed: docs/decisions/66c4-reminder-expiry-controlled-resume-product-decisions.md
  (six decisions APPROVED_BY_PRODUCT_OWNER) plus the eight-item BE1-R1 authorization in the stage
  prompt.
Independent review evidence read in full (not via the completion report):
  be1-independent-review.md, be1-deadline-semantics-review.md,
  be1-outbox-foundation-sufficiency-review.md, be1-security-review.md, be1-migration-review.md,
  be1-test-quality-review.md, be1-review-result-handoff.md.
BE1 implementation reviewed: migration 031 (+down), workroom_store.py, lifecycle_outbox.py,
  workroom_api.py, the BE1 test file and verifier, and the four BE1 records + handoff.

Blocking findings independently understood:
  B-1  now() IS transaction_timestamp(), frozen at BEGIN. The claim-execution-time requirement is
       not met, and the canonical contract's "now() is evaluated per statement" claim is factually
       wrong for PostgreSQL. Confirmed independently by re-running the cross-deadline scenario.
  B-2  Binding 11.3 failure modes 1 and 7 are mutually unsatisfiable without a persisted backoff
       schedule; dead_at and last_error are also absent, so a DLQ item has neither age nor
       diagnosis.
  M-1  The payload guard iterates only top-level keys with exact matching; nesting and near-miss
       names bypass it.

New information found:
  * The canonical event naming in api-and-event-contract.md 11.2 is DOTTED
    (clarification.reminder_recorded); BE1's ALLOWED_EVENT_TYPES used underscore names that appear
    nowhere in the contract. The allowlist rework aligned to the canonical dotted names rather than
    perpetuating the inconsistency.
  * Migration 031 has never been merged or applied to a shared runtime, so amending it in place is
    correct and no 032 is needed. Because CREATE TABLE IF NOT EXISTS is a no-op on an existing
    table, a note was added telling anyone holding the pre-R1 031 on a scratch DB to run the down
    script once first.
  * The BE1 verifier itself asserted the now-refuted `due_at > now()` predicate and had to be
    corrected, or it would have enforced the defect.
  * The environment has no local PostgreSQL; an isolated ephemeral PostgreSQL 16 container was
    created for this stage and destroyed afterwards. The shared test database was never touched.

Conflicts found:
  * Prompt section 9.3 illustrates the allowlist with dotted event names while BE1's code used
    underscore names. Resolved in favour of the canonical contract naming, as the prompt itself
    directs ("use repository canonical event naming, do not invent inconsistent names").
  * The prompt suggests a DB CHECK for payload size and event type as defence in depth. Only the
    last_error bound was added as a DB CHECK; payload-size/event-type CHECKs were judged weak
    against the stated threat and recorded as deferred L-1 rather than added silently.

Remediation impact:
  One CAS predicate and two timestamp expressions changed; behaviour under today's autocommit call
  shape is identical, and correct instead of silently widened once BE2 wraps the CAS. Three outbox
  columns, two CHECK constraints and two indexes added additively. The payload guard was inverted
  from deny list to positive allowlist. No runtime producer, relay or scheduler was created, and
  the existing audit/event transport was not touched.
```

## Statement

Context receipt only. No scheduler implemented or activated. No relay. No live producer. No
dispatch/resume. No external notification. No shared-runtime migration. No deployment. No merge.
Independent closure review required.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
