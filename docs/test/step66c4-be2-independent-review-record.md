# Step 66C.4-BE2-R — Independent Review Test Record

> **Independent review evidence. Reviewer did not implement the code. All PostgreSQL/Redis work ran
> against an isolated ephemeral PostgreSQL 16 + Redis 7 stack on the internal test runtime, created
> and destroyed for this review. Nothing deployed; PR #18 untouched.**

Reviewed commit: `319123b`. Review branch: `review/66c4-be2-poller-relay-transaction-recovery`.

## Environment

Isolated ephemeral PostgreSQL 16 container and Redis 7 container on the internal test runtime, reached
over dedicated host ports. Fail-closed guard `STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1` with an isolated
database name matching the `step66c4_*` pattern; `BE1_TEST_DATABASE_URL` (PG DSN) and
`BE2_TEST_REDIS_URL` (Redis URL) set to the ephemeral endpoints. The shared `aiagents-test` stack and
any shared datastore were NOT touched. Containers were destroyed at the end of the review.

## Vendor suites (green baseline)

| Suite | Result |
|-------|--------|
| `tests/test_step66c4_be2_reminder_expiry_outbox_relay.py` | 28 passed, 0 skipped |
| `scripts/verify_step66c4_be2_reminder_expiry_outbox_relay.py` | exit 0 — self-verify PASS |
| BE1 regression (data-model + merge + R1) | 69 passed |
| audit/retry/workroom sample | 52 passed, 3 pre-existing skips |
| ruff / black / mypy (affected files) | clean / clean / no issues |
| `git diff --check origin/main...HEAD` | clean |

## Independent reproductions (reviewer's own scripts)

### §6.3 unexpected NON-terminal task state (BLOCKING B-1)
```
committed cycle count      : 1
clarification.status       : expired  (expired_at set: True)
TASK.status (was 'running'): running   <-- UNCHANGED, task update matched 0 rows
outbox row emitted         : event_type=clarification.expired status=pending
reconciliation metric delta: 0   <-- NO observable reconciliation failure
```
Terminal (`canceled`) task: `clarification.expired` outbox row still committed (count=1) while task
stays `canceled`.

### §9 DB transaction across Redis publish — bounded timeout? (BLOCKING B-2)
```
redis socket_timeout        : None
redis socket_connect_timeout: None
first publish (redis up)    : published
redis PAUSED (hung broker on an established connection)
[t+2s] row B: {'row_status': 'pending', 'claimable_by_other_worker': False}
publish_one STILL BLOCKED after 14.1s holding the DB txn + row lock
=> NO bounded Redis timeout
redis UNPAUSED
blocked publish finally returned after 14.5s
```

### §11 retry / dead (no off-by-one)
```
cycle 0: retry -> pending attempts=1
cycle 1: retry -> pending attempts=2
cycle 2: retry -> pending attempts=3
cycle 3: dead  -> dead    attempts=4     (dead_at set, last_error='publish_dropped')
TOTAL real publish attempts before dead: 4
plan_retry_state: 0->30, 1->120, 2->600, 3->dead(None)
RETRY_BACKOFF_SECONDS=(30,120,600,3600)  MAX_DELIVERY_ATTEMPTS=4   # index 3 (3600) never reached
```

### §10 acknowledgment loss — same identity
```
before: id=<X> key=<cid>:expired attempts=0
after : id=<X> key=<cid>:expired attempts=0 status=pending
identity preserved: id=True key=True still_pending=True
re-publish outcome (redis up): published
```

### §8.2 audit-worker envelope compatibility
```
clarification.reminder_recorded: echo_skip=False norm_dt=clarification.reminder_recorded
    agent=clarification-outbox-relay idem=<cid>:reminder event_id=<outbox id>
clarification.expired:           echo_skip=False norm_dt=clarification.expired
    agent=clarification-outbox-relay idem=<cid>:expired  event_id=<outbox id>
both lifecycle types accepted (no skip): True
```
`AuditStore.write_audit_log` inserts `decision_type` as free text (no enum), so the projection does
not permanently fail on the new types; dedupe is by `source_message_id` (at-least-once).

## Markers

```
STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS
BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
