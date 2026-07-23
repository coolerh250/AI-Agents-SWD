# Step 66C.4-BE2-R — Independent Poller, Relay, Transaction & Failure-Recovery Review

> **Independent review. A fresh reviewer who did NOT implement the code. Judged from the canonical
> contract, Product Owner decisions, the exact commit, the committed records, the code, and the
> tests. Evidence gathered on an isolated ephemeral PostgreSQL 16 + Redis 7 stack on the internal
> test runtime. Nothing deployed; PR #18 untouched.**

- Reviewed commit (feature tip): `319123b`
- Feature branch: `feature/66c4-be2-reminder-expiry-outbox-relay`
- Review branch: `review/66c4-be2-poller-relay-transaction-recovery`

## Markers (recorded separately — never conflated)

- Process/artifacts: `STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS`
- Technical verdict: `BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED`

## Verdict basis (§19)

Technical PASS requires ALL 15 conditions. Two fail:

- **(3) unexpected task states cause no partial consistency** — FAILS. Expiry commits
  clarification=`expired` + outbox `clarification.expired` while a task in an unexpected state is left
  unchanged, with no observable reconciliation (§6.3).
- **(6)/(7) bounded Redis timeout / DB transaction & row locks do not wait indefinitely** — FAILS.
  The Redis XADD is awaited inside the open DB transaction while the outbox row is locked, and there
  is no bounded publish timeout; a hung broker pins the transaction, row lock, and DB connection (§9).

All other conditions hold (predicates, atomicity on the happy path and injected-failure paths, single
durable destination, audit-worker/envelope/projection compatibility, ack-loss same-identity resend,
retry/dead with no off-by-one, replay foundation safe & not activated, metrics/health real, historical
guard not weakened, no shared activation/cutover/deployment, no critical/high security issue, mandatory
PG/Redis tests 0 skipped / 0 failed). Per §19 the two failures make the verdict
**REMEDIATION_REQUIRED**; PASS_WITH_GAPS is NOT used to mask them.

## Blocking findings

### B-1 (§6.3) — Silent partial consistency on an unexpected task state
Expiry sets clarification→`expired` and inserts the outbox event unconditionally; the task UPDATE is
guarded `WHERE status='clarification_needed'` and its 0-row result is never inspected. Reproduced:
task=`running` → clarification=`expired` + outbox committed + task unchanged + reconciliation metric
delta 0. Terminal (`canceled`) task: the `clarification.expired` row is still committed. No metric/log
surfaces the divergence. Detail in `be2-lifecycle-poller-review.md` §6.3.

### B-2 (§9) — Unbounded Redis publish inside the open DB transaction / row lock
`publish_one` does BEGIN → FOR UPDATE SKIP LOCKED → await XADD → UPDATE → COMMIT. The Redis client is
built with `socket_timeout=None`/`socket_connect_timeout=None` and the publish is not wrapped in
`asyncio.wait_for`. Reproduced with `docker pause`: `publish_one` blocked >14s holding the DB
transaction and row lock (a second worker could not claim the locked row). No bound during normal
running; all workers share one Redis, so a real hang can pin every worker's DB connection →
pool-exhaustion risk. Detail in `be2-transaction-and-concurrency-review.md` §9.

## Non-blocking (recorded for the Product Owner)

- **LOW (§11):** `RETRY_BACKOFF_SECONDS[3]=3600` is dead code — effective schedule is `30/120/600 →
  dead`, not `30/120/600/3600`. Attempt budget (4) is correct and there is no off-by-one; but the
  declared schedule and the module comment do not match behavior. PO to confirm intended semantics.
- **MEDIUM, future-tied (§16):** `replay_dead` has no authorization boundary — safe only because it
  is unexposed; BE3 must add RBAC when wiring an operator replay control. Flagged openly.
- **Observation (§8.3):** dead rows are not routed to `stream.deadletter` (contract mentions it as
  the eventual DLQ); consistent with the single-destination decision and marked deferred by the BE2
  record. Tracked as an open contract item.
- **Observation (§8.2):** audit-worker deduplicates by `source_message_id`, not by the relay
  `idempotency_key`; a resend creates a second `audit_logs` row. Consistent with at-least-once; the
  `idempotency_key` is in `artifact_refs` for downstream dedupe.

## Sub-reviews

- `be2-lifecycle-poller-review.md` — §6.1/6.2/6.3/6.4
- `be2-outbox-relay-review.md` — §8/8.1/8.2/8.3, §10, §12
- `be2-transaction-and-concurrency-review.md` — §7, §9
- `be2-failure-recovery-review.md` — §11, relay §17
- `be2-observability-and-security-review.md` — §13, §16
- `be2-test-quality-review.md` — §14, §18

## Scope & safety (§3, §5, §15)

Diff `origin/main...319123b` adds two disabled worker entrypoints, three `shared/sdk/tasks` modules,
docs, a verifier, a new BE2 test, three widened historical guards, and `source/progress.md`. **No**
migration/schema change, **no** frontend, **no** infra/helm/k8s/.github change, **no** shared compose
activation, **no** orchestrator startup activation, **no** producer cutover, **no** resume/dispatch,
**no** external notification. `shared/sdk/audit/**`, `shared/sdk/event_bus/**`,
`apps/communication-gateway/**`, `infra/**`, `helm/**`, `k8s/**`, `.github/workflows/**` are UNCHANGED
vs main. `git grep` confirms the only references to the worker modules are the two disabled
entrypoints themselves — shared runtime activation = 0, live producer cutover = 0, runtime outbox
write in a shared environment = 0.

The reviewer modified ZERO implementation files (added only docs/scripts/tests/progress) and left
PR #18 untouched.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
