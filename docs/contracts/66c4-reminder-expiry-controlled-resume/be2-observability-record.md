# Step 66C.4-BE2 Observability Record

> **Implementation record. NOT deployed. No raw payload in any metric or log.**

## Metrics

`shared/sdk/tasks/lifecycle_metrics.py` (prometheus_client, kept out of the broad
`shared/sdk/observability/metrics.py` so the two workers share one isolated definition module).

Poller:

```text
clarification_poll_cycles_total{poller}
clarification_poll_cycle_failures_total{poller}
clarification_reminder_claims_total
clarification_expiry_claims_total
clarification_duplicate_suppressed_total{poller}
clarification_reconciliation_failures_total{poller}
clarification_poll_duration_seconds{poller}         (histogram)
clarification_last_successful_poll_timestamp{poller} (gauge)
```

Relay:

```text
clarification_outbox_publish_success_total{event_type}
clarification_outbox_publish_failure_total{event_type}
clarification_outbox_retry_scheduled_total{event_type}
clarification_outbox_dead_total{event_type}
clarification_outbox_replay_total
clarification_outbox_pending_count                      (gauge)
clarification_outbox_oldest_pending_age_seconds         (gauge, stuck-event detection)
clarification_outbox_last_successful_publish_timestamp  (gauge)
clarification_outbox_relay_cycle_failures_total
```

All labels are bounded, safe values (poller kind, canonical event_type). No metric label carries a
clarification body, a payload, a secret, or a token.

## Health

Each worker entrypoint exposes `/health` (process alive) and `/status` (running flag, counters,
poll/relay interval). The relay's `_sample_backlog` populates the pending-count and
oldest-pending-age gauges each cycle, which are the backlog / stuck-event and dead-row signals a
health check would threshold on. A transient Redis/DB error is counted and retried, not surfaced as
a process crash (the run loop keeps running and persisted retry state means nothing is lost) -- so
an upstream outage does not look like a dead worker.

Health distinguishes, at least:

```text
process alive                 -> /health
database reachable            -> a failing poll/relay cycle increments *_cycle_failures_total
Redis/destination reachable   -> outbox_publish_failure_total + last_successful_publish_timestamp age
poll/relay last-success age   -> last_successful_poll_timestamp / last_successful_publish_timestamp
dead/backlog threshold        -> outbox_dead_total / outbox_pending_count / oldest_pending_age
```

## Logging and privacy

Structured logs (Python `logging`) carry only bounded, safe fields: event_id, clarification_id,
task_id, event_type, attempt, status, a bounded safe reason code, and durations. They NEVER carry a
raw clarification body, a raw answer/question, a payload dump, a token/secret, an external
notification body, or a full DSN. Error logging obeys the same `last_error` safety policy (exception
class name only). Verified by the bounded-error unit test and by inspection: no `print`, no payload
dump, no DSN in the two worker modules.

## Statement

Implementation record only. No deployment. No metrics/log emission in any shared runtime (the
workers are not served). No external notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
