# Step 66C.4-BE1-R1 Outbox Durability Remediation Record (B-2)

> **Remediation record. No relay implemented. No relay activated. No claim loop. No live producer.
> No deployment. No merge.**

## The defect

Binding `api-and-event-contract.md` 11.3 failure mode 1 requires that a publisher outage cause NO
LOSS, while failure mode 7 requires bounded retries to end in `dead`. With no PERSISTED next-attempt
time, both cannot hold: a relay polling every few seconds exhausts its bounded attempts budget
within seconds of an outage and dead-letters healthy, non-poison rows. In-memory backoff does not
close the gap -- it dies with the worker and is not shared between the multiple relay workers the
contract permits.

Additionally, `status='dead'` existed with no `dead_at`, so the time of death was unrecoverable
(DLQ age, alert thresholds and reconciliation SLAs were not computable), and there was no
`last_error`, so an operator-reconciliation item carried no diagnosis.

Step 66C.4-BE1 flagged these three columns honestly as a forward contract-refinement item. The
independent review agreed with the finding and disagreed with the classification: because the
missing columns are what make the BINDING 11.3 failure modes implementable at all, they are
merge-blocking rather than a BE2 concern.

## The correction

```text
Previous outbox schema: id, clarification_id, task_id, event_type, idempotency_key, payload,
                        status, attempts, created_at, published_at

Added (BINDING, now part of the canonical data-model-contract.md):
  available_at  TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()
  dead_at       TIMESTAMPTZ NULL
  last_error    TEXT NULL, bounded to 500 characters

Added constraints:
  chk_clo_last_error_bounded   CHECK (last_error IS NULL OR length(last_error) <= 500)
  chk_clo_status_timestamps    CHECK (status/timestamp coherence, see below)

Added indexes:
  idx_clo_pending_available    ON (available_at, created_at) WHERE status='pending'
  idx_clo_dead_at              ON (dead_at)                  WHERE status='dead'

No synonym column was introduced: published_at, attempts and status already existed and are reused.
No claim-owner and no lease-expiry column was added -- unnecessary while the relay claims with
FOR UPDATE SKIP LOCKED inside its own transaction. That is now a BINDING constraint recorded in the
contract for BE2, rather than an unwritten precondition.
```

Migration 031 was amended IN PLACE rather than adding a 032, because 031 has never been merged to
main and has never been applied to any shared runtime. A note in the migration records that anyone
who applied the pre-R1 031 to a scratch database must run the down script once before re-applying,
since `CREATE TABLE IF NOT EXISTS` is a no-op on an existing table.

## Status semantics (binding)

```text
pending    published_at IS NULL     AND dead_at IS NULL     AND available_at IS NOT NULL
published  published_at IS NOT NULL AND dead_at IS NULL
dead       dead_at      IS NOT NULL AND published_at IS NULL
```

## Retry semantics (binding)

```text
Claim eligibility : status='pending' AND available_at <= statement_timestamp()
Transient failure : attempts+1; available_at := next backoff time; last_error := bounded reason
Exhausted         : status := 'dead'; dead_at := statement_timestamp(); last_error retained
Success           : status := 'published'; published_at := statement_timestamp(); last_error cleared
Backoff schedule  : 30s, 120s, 600s, 3600s (RETRY_BACKOFF_SECONDS); budget = 4 attempts
```

The schedule is expressed as a PURE mapping function (`plan_retry_state`) with no I/O and no loop.
It is the model a future relay would apply; no relay exists in this stage.

## Operator replay semantics (binding, contract only)

```text
dead -> pending, preserving id and the deterministic idempotency_key.
  status       := 'pending'
  available_at := statement_timestamp()
  dead_at      := NULL
  last_error   := NULL (the reason moves into the audit evidence for the replay action)
  attempts     NOT reset -- full delivery-attempt history is preserved as evidence.
                A replay_count column may be added by a FUTURE stage if a per-replay budget is
                needed; BE1-R1 adds no unauthorized column.
```

`plan_replay_state` expresses this mapping. No replay endpoint and no runtime replay path exist.

## Evidence (isolated ephemeral PostgreSQL 16)

```text
available_at persisted on insert; row immediately claim-eligible        : PASS
pending row with future available_at is NOT claim-eligible              : PASS
transient-failure update persists a future available_at + bounded error : PASS
dead state records dead_at, published_at stays NULL                     : PASS
published state records published_at, dead_at stays NULL                : PASS
published + dead simultaneously rejected by the coherence CHECK         : PASS (CheckViolationError)
last_error above the bound rejected at the DB boundary                  : PASS (CheckViolationError)
last_error above the bound rejected at the repository boundary          : PASS (ValueError)
duplicate idempotency_key rejected                                      : PASS (UniqueViolationError)
replay mapping representable; attempts and idempotency_key preserved    : PASS
transaction rollback removes the outbox insert AND the state mutation   : PASS
commit persists both (atomic state + outbox)                            : PASS
migration up / down / reapply deterministic                             : PASS
no table rewrite for the additive columns (relfilenode unchanged)       : PASS
existing rows unmutated across up, down and reapply                     : PASS
no runtime caller of the outbox exists                                  : PASS (0 offenders)
```

## Statement

Remediation record only. No relay implemented. No relay activated. No scheduler. No claim loop. No
live producer cutover. No runtime outbox write. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
