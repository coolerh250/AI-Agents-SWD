# Step 66C.4-BE2-R — Review Result Handoff

> **Independent review result. Reviewer did not implement the code. Evidence on an isolated ephemeral
> PostgreSQL 16 + Redis 7 stack on the internal test runtime. Nothing deployed; PR #18 untouched.**

## Markers (separate — do not conflate)

```
STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS
BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

The process marker means the review's own artifacts, verifier, and tests are complete and green. The
technical verdict is recorded SEPARATELY and is `REMEDIATION_REQUIRED`.

- Reviewed commit: `319123b`
- Review branch: `review/66c4-be2-poller-relay-transaction-recovery`

## Outcome

`REMEDIATION_REQUIRED`. Two blocking findings; BE2 must NOT merge, activate, deploy, or start BE3
until they are remediated and re-reviewed.

### Blocking

- **B-1 (§6.3) Silent partial consistency.** Expiry commits clarification=`expired` + outbox
  `clarification.expired` while a task in an unexpected state is left unchanged (the guarded task
  UPDATE matches 0 rows and its result is not inspected), with no reconciliation metric/log.
  Reproduced on PG16.
- **B-2 (§9) Unbounded Redis publish inside the open DB transaction.** XADD is awaited while the DB
  transaction is open and the outbox row is locked, with no bounded timeout
  (`socket_timeout=None`, no `asyncio.wait_for`). `docker pause` reproduction: `publish_one` blocked
  >14s holding the transaction and row lock. Pool-exhaustion risk under many workers.

### Non-blocking (Product Owner)

- LOW (§11): `RETRY_BACKOFF_SECONDS[3]=3600` is dead code; effective schedule `30/120/600 → dead`;
  attempt budget 4 correct, no off-by-one. Confirm intended schedule.
- MEDIUM future-tied (§16): `replay_dead` has no auth boundary; safe only while unexposed — BE3 must
  add RBAC when wiring a replay control.
- Observations: dead rows not routed to `stream.deadletter` (deferred per contract); audit-worker
  dedupes by `source_message_id` not `idempotency_key` (at-least-once, downstream dedupe available).

## Suggested remediation (for the BE owner — NOT performed by the reviewer)

1. Inspect the expiry task-update rowcount; make a clarification/task mismatch an observable
   reconciliation event (metric + bounded log) and decide, with the PO, whether `clarification.expired`
   should be emitted for a terminal/unexpected-state task.
2. Bound the Redis publish (client `socket_timeout`/`socket_connect_timeout` or `asyncio.wait_for`)
   so a hung broker rolls back and persists a retry instead of pinning the transaction, row lock, and
   DB connection.

## Gate posture

`merge_allowed:false`, `deployment_allowed:false`, `producer_cutover_allowed:false`,
`be3_authorized:false`, `product_owner_review_required:true`, `status: review-complete`. Product
Owner acceptance is required; the reviewer does not self-confirm human validation.

## What the reviewer verified independently

Vendor BE2 suite 28 passed / 0 skipped; vendor verifier PASS; BE1 regression 69 passed; audit/retry/
workroom sample 52 passed / 3 pre-existing skips; ruff/black/mypy/`git diff --check` clean on affected
files. Own reproductions on the ephemeral stack confirmed reminder/expiry predicates, atomic
rollback, two-worker single claim, retry→dead (4 attempts, no off-by-one), ack-loss same-identity
resend, audit-worker envelope compatibility, and the two blocking findings above. Ephemeral containers
were destroyed and the worktree removed after commit.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
