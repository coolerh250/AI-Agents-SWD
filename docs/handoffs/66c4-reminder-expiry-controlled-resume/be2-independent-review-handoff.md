# Step 66C.4-BE2 → Independent Review Handoff

> **Handoff. PR is Draft / NOT FOR MERGE. The implementation session does NOT review its own work,
> does NOT approve a merge, does NOT deploy, and does NOT start BE3.**

## What the reviewer reviews

```text
Branch:        feature/66c4-be2-reminder-expiry-outbox-relay
Base:          origin/main @ ab3c6cc (BE1 merged)
BE1 outbox schema: migration 031 (on main), UNCHANGED by BE2
```

Executed by Step 66C.4-BE2-R: a FRESH Claude Code review subagent, independent session, independent
worktree. Must judge only from the canonical contract, PO decisions, the exact commit, the committed
records, the code, and the tests; must NOT fix anything, merge, deploy, or start BE3.

## Markers (never conflate)

```text
STEP66C4_BE2_REMINDER_EXPIRY_OUTBOX_RELAY_VERIFY -- the implementation session's self-verification.
BE2_TECHNICAL_VERDICT (PASS | REMEDIATION_REQUIRED) -- only the independent reviewer may set this.
```

## What must be independently re-verified

```text
1. Reminder + expiry transitions match the canonical predicates (statement_timestamp(); past-due is
   expired not reminded; answered/canceled/expired skipped).
2. Lifecycle state UPDATE(s) + outbox INSERT are ONE transaction: a forced failure at any step
   rolls back ALL of clarification, task, and outbox (independently reproduce §19.8 and §19.9).
3. Concurrency: two workers -> exactly one claim, for both reminder and expiry; a crash before
   commit rolls back.
4. Relay: single durable destination via publish_audit_event; persisted backoff in available_at;
   bounded attempts -> dead with dead_at + bounded last_error; NOT exhausted in a tight loop;
   at-least-once with a stable event_id/idempotency_key on re-publish; exactly-once NOT claimed.
5. Replay foundation: dead -> pending, attempts preserved, idempotency_key preserved, no public
   endpoint (not wired to orchestrator/admin-console).
6. last_error and logs carry no raw payload/secret/DSN.
7. No migration/schema change; BE1 031 unchanged. No existing-producer cutover; audit/event
   transport unchanged vs main. No shared-runtime activation (no compose/k8s/helm/cron/orchestrator
   reference). No deployment. No resume/dispatch. No external notification.
8. Mandatory PostgreSQL 16 + Redis 7 suites run with 0 skipped / 0 failed on isolated ephemeral
   containers; the reviewer should re-run them on its own ephemeral containers.
```

## Disclosed change to three prior-stage tests (review directly)

BE2 updated three BE1-era zero-caller regression tests
(`test_outbox_module_has_no_live_producer_import`, `test_no_live_outbox_producer_on_main`,
`test_no_relay_scheduler_or_live_producer_exists`) to allow-list EXACTLY the two authorized
non-activated worker modules (`lifecycle_poller.py`, `outbox_relay.py`). This is because BE2 is the
PO-authorized stage that adds the first outbox callers. The reviewer should confirm: (a) only those
two modules are allow-listed and no other module references the outbox; (b) neither worker is
activated in any shared runtime (no compose/k8s/helm/cron reference, no orchestrator import); (c) the
`lifecycle_outbox.py`-scoped `while True`/`FOR UPDATE`/`XREADGROUP` bans are unchanged and still
pass. See be2-implementation-record.md "Disclosed change to three prior-stage tests".

## Known / deferred

```text
- Routing dead outbox rows onward to stream.deadletter / retry-scheduler is intentionally NOT done
  in BE2 (no external side effect); the persisted dead row is the durable reconciliation record.
- The BE1 deferred Low findings (be1-deferred-low-findings.md) remain deferred; BE2 does not touch
  them.
```

## Posture

```text
PR:              Draft / NOT FOR MERGE.
Step 66C.4-BE3:  NOT authorized, NOT started.
Codex / Claude Design: NOT authorized.
Deployment / shared migration / producer cutover: NOT performed, NOT authorized.
```

## Statement

Handoff only. No deployment. No shared-runtime activation. No shared migration. No producer cutover.
No dispatch/resume. No external notification. No merge. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
