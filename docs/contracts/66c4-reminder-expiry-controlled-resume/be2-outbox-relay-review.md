# Step 66C.4-BE2-R — Outbox Relay & Single-Destination Review

> **Independent review. Reviewer did not implement the code. Evidence gathered on an isolated
> ephemeral PostgreSQL 16 + Redis 7 stack on the internal test runtime. Nothing deployed.**

Reviewed commit: `319123b`. Module: `shared/sdk/tasks/outbox_relay.py`;
entrypoint `apps/clarification-outbox-relay`.

## 8. Single durable destination — PASS (path is complete and executable)

The relay publishes each outbox row through `shared/sdk/audit/publisher.py::publish_audit_event`
onto `stream.audit`, consumed by the existing `audit-worker`, projected into `audit_logs`. This is a
single durable destination with a downstream projection — the model §8 prefers. Verified end-to-end:
a relay publish produces a real `stream.audit` XADD that the audit-worker path accepts.

### 8.1 Publisher contract

`publish_audit_event` returns the XADD id on success and `None` on drop; a raised transport exception
is caught by the relay's `_publish` and mapped to a definite failure. The relay's `PublishResult.ok`
is therefore a definite per-publish success/failure signal. `None` is treated uniformly as failure
→ persisted retry, which is correct for a relay (a false-negative only causes an at-least-once resend
with the same identity). The one caveat is timeout classification — see the transaction review §9.

### 8.2 Downstream compatibility — PASS

Independently reproduced (real relay → real `stream.audit` → normalizer path):

```
clarification.reminder_recorded: echo_skip=False norm_dt=clarification.reminder_recorded
    agent=clarification-outbox-relay idem=<cid>:reminder event_id=<outbox id>
clarification.expired:           echo_skip=False norm_dt=clarification.expired
    agent=clarification-outbox-relay idem=<cid>:expired event_id=<outbox id>
```

- The stream entry parses; `normalize_audit_event` preserves `decision_type` verbatim for both new
  event types.
- `event_id` (outbox row id) and `idempotency_key` survive in `artifact_refs`.
- `is_audit_recorded_echo` returns False for both → not skipped as a self-echo.
- `AuditStore.write_audit_log` inserts `decision_type` as free text (no enum/CHECK), so an unknown
  lifecycle type does **not** permanently fail the projection.
- The consumer group has pending/retry/deadletter recovery (un-acked on failure → redelivery;
  deadletter after 3 failures) — projection failure is recoverable/observable.

Correctly, the relay marks a row `published` only on a durable XADD success — NOT on projection
completion. One at-least-once caveat: the audit-worker deduplicates by `source_message_id` (the XADD
id), not by the relay's `idempotency_key`; a re-sent outbox row gets a NEW XADD id and therefore
produces a SECOND `audit_logs` row. This is consistent with the stated at-least-once model, and the
`idempotency_key` is carried in `artifact_refs` so a downstream reconciler can dedupe. Recorded as an
observation, not a defect.

### 8.3 No hidden fan-out — PASS

The relay calls only `publish_audit_event`. It does not also publish to the event bus directly, does
not call an external notification, and does not route dead rows onward. One outbox row → one durable
destination.

Observation (deferred contract item, not blocking): the canonical `api-and-event-contract.md` §11.3 /
`data-model-contract.md` describe a dead row as *"routed to the existing stream.deadletter /
retry-scheduler DLQ."* The relay marks the row `dead` in the outbox table but does **not** publish to
`stream.deadletter`. The BE2 record acknowledges this routing as deferred beyond BE2; it is consistent
with the §8.3 single-destination decision (routing onward would be a second destination). Flagged so
the Product Owner tracks it as an open contract item for a later stage, not lost.

## 10. At-least-once & acknowledgment-loss — PASS

Reproduced: XADD succeeds, the DB commit that marks `published` fails → row stays `pending`, `id` and
`idempotency_key` unchanged, `attempts` unchanged; a later publish re-sends with the same identity:

```
before: id=<X> key=<cid>:expired attempts=0
after : id=<X> key=<cid>:expired attempts=0 status=pending
identity preserved: id=True key=True still_pending=True
re-publish outcome (redis up): published
```

No new `event_id` is minted, payload semantics are unchanged, and exactly-once is neither claimed nor
implied (`AT-LEAST-ONCE` / `EXACTLY-ONCE is NOT claimed` are asserted in the module and by tests).

## 12. Replay foundation — PASS (safe, not activated)

`replay_dead(event_id)` accepts only a `status='dead'` row (`FOR UPDATE`), preserves `event_id` and
`idempotency_key`, does NOT reset `attempts`, sets `status='pending'`,
`available_at=statement_timestamp()`, clears `dead_at` and `last_error`. Reproduced: a dead row
replays to pending with `attempts=4` preserved and identity unchanged; a non-dead row is a no-op
(returns False). It is an internal method with no API route, no Admin Console control, no startup
invocation, no automatic loop. The BE2 record correctly frames the replay audit trail as a future
contract produced by the normal publication path once the row is pending again — not a completed
operator audit trail.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
