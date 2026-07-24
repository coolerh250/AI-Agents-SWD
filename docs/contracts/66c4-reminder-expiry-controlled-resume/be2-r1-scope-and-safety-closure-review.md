# Step 66C.4-BE2-R1-R — Scope & Safety Closure Review

> Independent review record. Not deployed. Not a merge authorization. No shared activation.

## R1 diff scope (`git diff --name-status 319123b..c2677f7`)

The R1 change touches ONLY: expiry consistency + guarded-rowcount/rollback + reconciliation
observability (`lifecycle_poller.py`, `lifecycle_metrics.py`, `models.py`); Redis client / publish
timeout (`outbox_relay.py`, `event_bus/redis_streams.py`); retry attempt semantics
(`lifecycle_outbox.py`); and directly-related tests / verifiers / records / contracts /
`source/progress.md`.

```text
NONE of the following are touched:
  migration / schema (no new migration, no edit to 029/030/031)
  deployment config, shared activation (infra/helm/k8s/.github/workflows unchanged)
  producer cutover (shared/sdk/audit/**, retry-scheduler, audit-worker, notification-worker unchanged)
  public replay endpoint (replay_dead stays internal, zero runtime callers)
  resume / dispatch, frontend, external notification
```

## Shared `RedisStreamEventBus` change — additive only

Independently confirmed the `shared/sdk/event_bus/redis_streams.py` change is a PURE ADDITIVE
timeout-config change:
- New kwargs `socket_timeout` / `socket_connect_timeout` are keyword-only and default None.
- With None, `client` builds `from_url(url, decode_responses=True)` exactly as before — existing
  caller defaults unchanged (verified: a default-constructed bus has both attrs None).
- `publish_event` / XADD / `ensure_group` / `consume_events` / `ack_event` bodies have ZERO diff.
Not a transport rewrite.

## Reviewer scope compliance

```text
Files added by this reviewer (allowed paths only):
  docs/contracts/66c4-reminder-expiry-controlled-resume/be2-r1-*-closure-review.md   (7)
  docs/handoffs/66c4-reminder-expiry-controlled-resume/be2-r1-closure-review-result-handoff.md
  docs/test/step66c4-be2-r1-independent-closure-review-record.md
  docs/stages/66c4-be2-r1-independent-closure-review/**                              (3)
  scripts/verify_step66c4_be2_r1_independent_closure_review.py
  tests/test_step66c4_be2_r1_independent_closure_review.py
  source/progress.md                                                                 (updated)
Implementation files modified by reviewer:  NONE (git diff --name-only HEAD over apps/shared/
  migrations/services/frontend/infra/helm/k8s/.github is empty).
Actions NOT taken: no fix of findings, no PR #18 merge, no deploy, no shared worker/relay
  activation, no producer cutover, no public replay endpoint, no resume/dispatch, no BE3 start.
```

## Test-environment safety

All independent tests ran on an isolated ephemeral PostgreSQL 16 + Redis 7 (private DB name
matching `^step66c4_[a-z0-9_]+$`, unused ports), created and destroyed for this review. The shared
internal test runtime's PostgreSQL container was left running and untouched. No internal IP, SSH
alias, username, or ephemeral password appears in any committed file.

## Verdict

**Scope & safety: COMPLIANT.**

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
