# Step 66C.4-BE2 Context Receipt

```text
Stage: 66C.4-BE2 -- Reminder / Expiry Poller and Transactional Outbox Relay
Partner: Claude Code

Latest main reviewed:          ab3c6cc (BE1 merged at 8080141)
Working tree reviewed:         clean before branching
Canonical contract reviewed:   docs/contracts/66c4-reminder-expiry-controlled-resume/** incl.
  lifecycle-and-time-contract.md (7.3A, statement_timestamp() deadline), api-and-event-contract.md
  (11.2 event names, 11.3 transactional-outbox atomicity model), data-model-contract.md (outbox
  durability columns + retry/replay semantics).
PO decisions reviewed:         docs/decisions/66c4-reminder-expiry-controlled-resume-product-decisions.md
BE1 Runtime Compatibility Gate reviewed: yes -- existing producers stay on current paths; BE2 may
  implement relay/retry/DLQ/metrics but may NOT deploy or cut over.
Migration 031 reviewed:        available_at/dead_at/last_error present; sufficient for BE2 -> no
  schema change needed.
Existing worker/retry/DLQ patterns reviewed: apps/retry-scheduler (run(stop_event) loop, status(),
  one-shot handle, manual replay), shared/sdk/event_bus/redis_streams (XADD/XREADGROUP/SKIP-LOCKED
  not used there), shared/sdk/observability/metrics (prometheus_client), worker main.py lifespan
  (FastAPI + install_metrics_endpoint).
Existing event/audit transport reviewed: shared/sdk/audit/publisher.publish_audit_event (best-effort,
  returns XADD id or None -> a usable success/failure signal), stream.audit -> audit-worker ->
  audit_logs.

New information found:
  * publish_audit_event's id-or-None return is the reliable per-publish success/failure signal a
    relay needs, so it is the single canonical durable destination (downstream audit-worker produces
    the projection). This resolves the stage-prompt §11 destination question WITHOUT a multi-
    destination fan-out and WITHOUT a schema that can track per-destination status.
  * clarification_expired is already a valid operator_tasks.status; expiry reuses it (no new status).
  * asyncpg Transaction has no is_active(); rollback is guarded with contextlib.suppress instead.

Conflicts found:
  None between the canonical contract, the BE1 schema, and this prompt. The contract's Option 1
  wording "produces the audit projection and the Redis event" is satisfied by the single audit-stream
  publication (the audit projection is the downstream audit_logs write); this is recorded as the BE2
  single-durable-destination decision rather than a fan-out.

Implementation impact:
  Two isolated workers added under shared/sdk/tasks + thin non-activated entrypoints; no runtime
  file modified; no migration; BE1 outbox schema sufficient; existing transport unchanged.
```

## Statement

Context receipt only. No deployment. No shared-runtime activation. No shared migration. No producer
cutover. No dispatch/resume. No external notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
