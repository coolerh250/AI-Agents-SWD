# Step 66C.4-BE3-P — Runtime Activation and Rollback Gate

> **Planning/contract document only. This stage authorizes NO activation and NO deployment. It
> defines the prerequisites that must ALL be satisfied, and explicitly Product-Owner-authorized,
> before any BE3 resume/replay capability is ever turned on.**

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
