# Step 66C.4 — Reminder / Expiry / Controlled Resume Product Decisions

**Decision status: APPROVED_BY_PRODUCT_OWNER**

Recorded at Step 66C.4-P-M (contract merge). These six product decisions were approved by the
Product Owner alongside the authorization to merge
`planning/66c4-reminder-expiry-controlled-resume @ f50dd05` into `main`, making the Step 66C.4
Reminder / Expiry / Controlled Resume contract set canonical.

These decisions are authoritative and supersede the "recommended default" framing in
`docs/contracts/66c4-reminder-expiry-controlled-resume/product-owner-decision-checklist.md` for the
six items below.

## Decision 1 — Authoritative expiry

```text
No late answer when authoritative PostgreSQL DB time >= due_at.
- The Answer API returns 409.
- Scheduler lag does not extend the answer window.
- due_at is an exclusive upper bound (answer exactly at due_at is rejected).
- PostgreSQL database time is the authoritative lifecycle clock.
```

## Decision 2 — User-facing expiry state

```text
UI wording: "Blocked — clarification expired".
Backend: retains the existing clarification_expired semantics unchanged.
No new global task status is introduced.
```

## Decision 3 — Controlled Resume model

```text
Explicit Operator-Controlled Resume.

Answer recorded
  -> Resume eligible
  -> Operator requests resume
  -> Policy/safety authorization
  -> Durable resume event
  -> Orchestrator confirms resumed

An answer does NOT automatically resume the workflow.
```

## Decision 4 — Human confirmation

```text
The Operator's explicit resume request IS the human confirmation for a normal task.
No second general confirmation step is added.
Production-effect tasks still require the existing production approval; the operator resume
  request does NOT replace or bypass it.
```

## Decision 5 — Reminder count

```text
One reminder per clarification.
reminder_at = created_at + 24 hours.
```

## Decision 6 — Expired clarification immutability

```text
An expired clarification cannot be reopened.
To continue the work, a new clarification request is created, preserving audit linkage to the
  original clarification.
```

## Authorization posture recorded at approval time

```text
Step 66C.4-BE1 remains UNAUTHORIZED and NOT STARTED.
Codex remains UNAUTHORIZED.
Claude Design remains UNAUTHORIZED.
```

## Binding BE1 runtime-compatibility constraint

These decisions are approved together with the binding BE1 runtime-compatibility gate recorded in
`docs/contracts/66c4-reminder-expiry-controlled-resume/contract-source-of-truth-record.md`
("BE1 Runtime Compatibility Gate"). No runtime producer cutover to the outbox may occur until an
active relay, retries, DLQ, metrics, rollback path, and runtime validation are ready together.

## Statement

Product decision record only. No backend/frontend runtime change. No API implementation change. No
database schema change. No migration created. No workflow change. No scheduler activated. No outbox
relay activated. No existing producer switched. No dispatch/resume executed. No deployment. No
external notification. No production/external action. Step 66C.4-BE1 not started. Codex and Claude
Design not authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=true image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
