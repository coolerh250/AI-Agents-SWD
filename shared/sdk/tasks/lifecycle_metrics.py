"""Step 66C.4-BE2 -- Prometheus metrics for the clarification lifecycle poller and outbox relay.

Kept in shared/sdk/tasks so the two workers share one definition module without importing the
broad shared/sdk/observability/metrics module (which other services register their own collectors
in). Counters/histograms follow the prometheus_client convention already used across the repo.

No metric here ever carries a raw payload, a clarification body, a secret, or a token -- only
bounded, safe labels (event_type, outcome, kind).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---- Lifecycle poller -----------------------------------------------------------------

POLL_CYCLES_TOTAL = Counter(
    "clarification_poll_cycles_total",
    "Clarification lifecycle poll cycles run, labelled by poller kind",
    ["poller"],  # reminder | expiry
)
POLL_CYCLE_FAILURES_TOTAL = Counter(
    "clarification_poll_cycle_failures_total",
    "Clarification lifecycle poll cycles that raised before completing",
    ["poller"],
)
REMINDER_CLAIMS_TOTAL = Counter(
    "clarification_reminder_claims_total",
    "Reminder transitions committed (state + outbox in one transaction)",
)
EXPIRY_CLAIMS_TOTAL = Counter(
    "clarification_expiry_claims_total",
    "Expiry transitions committed (clarification + task + outbox in one transaction)",
)
DUPLICATE_SUPPRESSED_TOTAL = Counter(
    "clarification_duplicate_suppressed_total",
    "Lifecycle transitions skipped because the row no longer matched its claim guard",
    ["poller"],
)
RECONCILIATION_FAILURES_TOTAL = Counter(
    "clarification_reconciliation_failures_total",
    "Lifecycle transitions rolled back on an unexpected outbox idempotency collision",
    ["poller"],
)
POLL_DURATION_SECONDS = Histogram(
    "clarification_poll_duration_seconds",
    "Duration of one lifecycle poll cycle",
    ["poller"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
LAST_SUCCESSFUL_POLL_TIMESTAMP = Gauge(
    "clarification_last_successful_poll_timestamp",
    "Unix timestamp of the last poll cycle that completed without raising",
    ["poller"],
)

# ---- Outbox relay ---------------------------------------------------------------------

OUTBOX_PUBLISH_SUCCESS_TOTAL = Counter(
    "clarification_outbox_publish_success_total",
    "Outbox rows published to the canonical durable destination",
    ["event_type"],
)
OUTBOX_PUBLISH_FAILURE_TOTAL = Counter(
    "clarification_outbox_publish_failure_total",
    "Outbox publish attempts that failed and were scheduled for retry or dead-lettered",
    ["event_type"],
)
OUTBOX_RETRY_SCHEDULED_TOTAL = Counter(
    "clarification_outbox_retry_scheduled_total",
    "Outbox rows whose next attempt was scheduled with a persisted backoff",
    ["event_type"],
)
OUTBOX_DEAD_TOTAL = Counter(
    "clarification_outbox_dead_total",
    "Outbox rows moved to the terminal dead state after exhausting bounded retries",
    ["event_type"],
)
OUTBOX_REPLAY_TOTAL = Counter(
    "clarification_outbox_replay_total",
    "Dead outbox rows returned to pending by the operator replay foundation",
)
OUTBOX_PENDING_COUNT = Gauge(
    "clarification_outbox_pending_count",
    "Current count of pending outbox rows (sampled by the relay)",
)
OUTBOX_OLDEST_PENDING_AGE_SECONDS = Gauge(
    "clarification_outbox_oldest_pending_age_seconds",
    "Age of the oldest pending outbox row in seconds (sampled by the relay)",
)
LAST_SUCCESSFUL_PUBLISH_TIMESTAMP = Gauge(
    "clarification_outbox_last_successful_publish_timestamp",
    "Unix timestamp of the last successful outbox publish",
)
RELAY_CYCLE_FAILURES_TOTAL = Counter(
    "clarification_outbox_relay_cycle_failures_total",
    "Relay cycles that raised before completing",
)
