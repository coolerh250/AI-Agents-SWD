# Step 66C.4-BE2 Implementation Record

> **Implementation record. NOT deployed. NOT runtime validated. No shared-runtime activation. No
> shared migration. No existing producer cutover. No dispatch/resume. No external notification.**
>
> **Superseded in part by Step 66C.4-BE2-R1** (see be2-r1-remediation-record.md): the independent
> Step 66C.4-BE2-R review returned `BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED` for two blocking
> findings — B-1 expiry parent-task consistency and B-2 unbounded Redis publish — both since closed.
> The retry schedule was also corrected to reach all four backoffs (dead on the 5th attempt). This
> record's original text is retained as history; where it differs, the BE2-R1 records govern.

## Scope

Built, but not activated, on top of the merged BE1 foundation (main `ab3c6cc`):

```text
1. Clarification lifecycle poller (reminder + expiry DB claim/transition).
2. Atomic lifecycle state update + clarification_lifecycle_outbox insert (one transaction).
3. Transactional outbox relay (single durable destination + persisted retry).
4. Persisted retry/backoff, published/dead terminal transitions.
5. Internal operator replay foundation (dead -> pending), no public endpoint.
6. Metrics, health, structured privacy-safe logging.
```

## Files added

```text
shared/sdk/tasks/lifecycle_poller.py    -- ClarificationLifecyclePoller
shared/sdk/tasks/outbox_relay.py        -- ClarificationOutboxRelay
shared/sdk/tasks/lifecycle_metrics.py   -- Prometheus metrics for both workers
apps/clarification-lifecycle-worker/src/{__init__.py,main.py}  -- poller entrypoint (NOT activated)
apps/clarification-outbox-relay/src/{__init__.py,main.py}      -- relay entrypoint (NOT activated)
tests/test_step66c4_be2_reminder_expiry_outbox_relay.py
scripts/verify_step66c4_be2_reminder_expiry_outbox_relay.py
```

No existing runtime file was modified. No migration was added or changed. The BE1 outbox schema
(migration 031, already on main) is sufficient; BE2 required NO schema change.

## Disclosed change to three prior-stage tests (zero-caller assertions)

Three BE1-era regression tests asserted that NO module outside `lifecycle_outbox.py` references the
outbox — the correct invariant while the foundation was disabled with zero callers:

```text
tests/test_step66c4_be1_data_model_deadline_outbox.py::test_outbox_module_has_no_live_producer_import
tests/test_step66c4_be1_merge.py::test_no_live_outbox_producer_on_main
tests/test_step66c4_be1_r1_remediation.py::test_no_relay_scheduler_or_live_producer_exists
```

BE2 is the PO-authorized stage that introduces the first outbox callers (the poller PRODUCES rows;
the relay CONSUMES them), so that specific invariant is intentionally superseded. Each test was
updated MINIMALLY to allow-list exactly the two authorized modules
(`shared/sdk/tasks/lifecycle_poller.py`, `shared/sdk/tasks/outbox_relay.py`) and nothing else. The
SAFETY invariant they protect is preserved and strengthened, not weakened: no OTHER module may
reference the outbox, and neither worker is ACTIVATED in any shared runtime (no compose/k8s/helm/cron
reference, no orchestrator import) — asserted by the BE2 no-activation tests and the BE2 verifier.
The `while True`/`FOR UPDATE`/`XREADGROUP` bans that the R1 test applies to `lifecycle_outbox.py`
itself are unchanged and still pass (BE2 did not touch that module). This change is disclosed here
and in the review handoff so the independent reviewer scrutinizes it directly.

## Architecture

Two separated execution units in one shared package, with separate entrypoints, separate
health/metrics, separate failure domains, and no import coupling (verified by test). Each supports
a one-shot cycle (`run_once` / `publish_one`) for tests and a `run(stop_event)` loop for a
separately-invoked entrypoint. Neither starts anything on import.

- **Poller** claims one clarification row at a time with `SELECT ... FOR UPDATE SKIP LOCKED`,
  performs the lifecycle state UPDATE(s), and inserts the outbox row through the BE1
  transaction-aware `insert_lifecycle_outbox_event`, all in ONE transaction. Expiry additionally
  moves the task to the existing `clarification_expired` status, guarded so a terminal/canceled
  task is not clobbered.
- **Relay** claims one pending, eligible outbox row (`status='pending' AND available_at <=
  statement_timestamp()`) with `FOR UPDATE SKIP LOCKED`, publishes it to the single canonical
  durable destination, and applies BE1's `plan_retry_state`/`plan_replay_state` for
  retry/dead/replay.

## Delivery model

At-least-once with a deterministic idempotency identity (idempotency_key + event_id). Exactly-once
is explicitly NOT claimed and NOT achievable. Single durable destination: the canonical audit
stream via the existing `publish_audit_event` (returns the XADD id / None -> a reliable per-publish
success/failure signal); the existing audit-worker produces the durable projection downstream. See
be2-outbox-relay-record.md.

## Authorization posture

```text
Deployment:                     NO (nothing served in any shared runtime)
Shared DB migration 031:        NO
Existing producer cutover:      NO (audit/event transport unchanged)
Runtime outbox writes:          NO (only tests invoke the workers)
Scheduler/relay activation:     NO (entrypoints registered in no compose/k8s/helm/cron/orchestrator)
Resume/dispatch/workflow resume: NO
External notification:          NO
Step 66C.4-BE3:                 NOT authorized, NOT started
Codex / Claude Design:          NOT authorized
Independent review:             REQUIRED (Step 66C.4-BE2-R) before merge/deploy
production_executed_true_count: 0
```

## Statement

Implementation record only. No deployment. No shared-runtime migration. No scheduler/relay
activation in any shared runtime. No live producer cutover. No dispatch/resume. No external
notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
