# Step 66C.4-BE3-P — Runtime Activation and Rollback Gate

> **Planning/contract document only. This stage authorizes NO activation and NO deployment. It
> defines the prerequisites that must ALL be satisfied, and explicitly Product-Owner-authorized,
> before any BE3 resume/replay capability is ever turned on.**

## A.0 BE3-R1 findings-closure evidence (added Step 66C.4-BE3-R1)

The BE3-R combined independent review recorded two Medium findings as **mandatory activation
preconditions** (not merge blockers for the disabled foundation itself). Both are now CLOSED at the
code level; this does not itself authorize activation -- items 1-11 below remain required in full.

```text
Finding M-1 (production approval reference resolution):
  IMPLEMENTED:              production_action_approvals registry (migration 035) + a
                             transaction-aware resolve_and_consume_approval resolver
                             (production_approval_repository.py), wired into the ONE shared
                             authorization_service.consume() integration point used by BOTH the
                             resume and replay consume paths.
  TESTED:                   tests/test_step66c4_be3_r1_findings_remediation.py -- missing/unknown/
                             invalid reference, revoked, expired, already-consumed, wrong team/
                             project/resource/action, stale resource-state-version, concurrent
                             revoke-vs-consume (exactly one safe outcome), end-to-end through BOTH
                             resume and replay, real PostgreSQL 16.
  TRANSACTIONALLY VERIFIED: the approval row is locked (FOR UPDATE) and validated in the SAME
                             transaction as the authorization consume; a post-approval-consume
                             authorization CAS failure raises to force a full rollback (no
                             half-mutated state).
  FAIL-CLOSED:               a missing, unparsable, unknown, revoked, expired, already-consumed,
                             wrong-scope/resource/action, or stale-version reference is REJECTED --
                             the authorization is never consumed and no command/replay mutation
                             occurs.

Finding L-1 (per-actor replay rate-limit concurrency):
  CONCURRENCY-SAFE:          a PostgreSQL transaction-scoped advisory lock
                             (pg_advisory_xact_lock, keyed on team_id+project_id+actor_id) serializes
                             the count-then-insert sequence in replay_service.request_replay; the
                             count itself is now scoped by (team_id, project_id, requested_by), not
                             a global per-actor count.
  POSTGRESQL-VERIFIED:       tests/test_step66c4_be3_r1_findings_remediation.py -- 20-way and 50-way
                             concurrent bursts never exceed the configured hard cap, cross-team/
                             cross-project/cross-actor isolation, idempotent-retry-not-double-
                             counted, rolling-window expiry, platform_admin cannot bypass, invalid
                             config fails closed.
```

Design record: `be3-r1-m1-production-approval-contract.md` (planning checkpoint: derivable design
decisions cited from canonical governance, plus the three genuine Product Owner decisions this
required, and their answers). Remediation record: `be3-r1-required-findings-remediation-record.md`.

## A. Activation prerequisites (ALL required before any activation)

```text
1.  Migration 031 (BE2 outbox schema) applied to the target runtime database.
2.  BE3 authorization migration (durable authorization + request tables) applied to the target runtime.
3.  Lifecycle poller deployed and health/metrics verified in the target runtime.
4.  Outbox relay deployed and health/metrics verified in the target runtime.
5.  Retry/DLQ path verified end-to-end (bounded retries -> dead -> operator visibility).
6.  Rollback tested (a clean, verified path to disable resume/replay dispatch and revert the schema
    changes without data loss).
7.  Producer cutover plan approved (how, and whether, any existing producer begins writing the outbox).
8.  Resume/replay RBAC verified (permission matrix + two-person replay control enforced).
9.  Audit evidence verified (every resume/replay transition produces durable, content-safe evidence).
10. Runtime E2E passed (resume request -> authorization -> gated dispatch -> orchestrator confirmation;
    replay request -> authorization -> internal replay adapter -> dead->pending), on an isolated runtime.
11. Product Owner deployment authorization (explicit, per-runtime).
```

## B. Rollback boundary

```text
- Dispatch is GATED/DISABLED-BY-DEFAULT (dispatch_enabled hardcoded false); enabling it is a separate,
  explicit authorization distinct from deploying the code.
- Disabling dispatch must be a single, reversible switch that leaves durable requests/authorizations
  intact (no data loss) and stops only the execution/dispatch side effect.
- replay_dead stays internal-only until items 1-11 are met AND the replay RBAC + two-person control +
  durable authorization + audit evidence are all verified; only then may an operator-facing replay
  request/authorize surface be enabled.
- No producer cutover occurs implicitly; it is a distinct, PO-approved step (item 7).
```

## C. What this stage does NOT authorize

```text
- No deployment of any kind.
- No application of migration 031 or any BE3 migration to a shared database.
- No activation of the lifecycle poller, the outbox relay, resume dispatch, or replay.
- No producer cutover; no public replay endpoint; no Admin Console control.
production_executed_true_count remains 0.
```

## Statement

Planning/contract document only. No deployment, no migration application, no activation. No
production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
