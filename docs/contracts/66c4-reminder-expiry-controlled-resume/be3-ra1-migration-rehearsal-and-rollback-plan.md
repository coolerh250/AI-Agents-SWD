# Step 66C.4-BE3-RA-1A — Isolated Migration Rehearsal and Rollback Plan

> **Rehearsal plan and findings record. NOT applied to any shared, test, staging, or production
> database. Self-verified only; independent review (RA-1R) is the next required gate. Migrations
> 031-035 are unmodified — this stage adds rehearsal tooling and evidence only.**

## 1. Objective

Build a repeatable, auditable isolated-PostgreSQL-16 rehearsal proving:

```text
pre-031 schema -> apply 031 -> 032 -> 033 -> 034 -> 035 -> validate -> rollback rehearsal -> reapply
-> validate again
```

No shared, test, staging, or production database is touched by this stage.

## 2. Migration chain inventory (preflight, confirmed by direct inspection)

```text
Baseline:      029_operator_task_api_foundation.sql (operator_tasks) +
               030_workroom_clarification_foundation.sql (task_messages,
               operator_clarification_requests) -- the actual pre-031 baseline is TWO files, not a
               single migration 030 in isolation; both were confirmed necessary (030's tables have
               FKs into 029's operator_tasks).
Chain:         031 (clarification_lifecycle_outbox foundation + 6 lifecycle columns on
               operator_clarification_requests) -> 032 (resume_replay_authorizations) -> 033
               (resume_requests) -> 034 (replay_requests) -> 035 (production_action_approvals).
Down scripts:  all five (031-035) have a matching *_down.sql; migration_catalog.py (Stage 51)
               independently classifies all five as "reversible".
Runner:        NO separate migration-runner tool and NO bookkeeping/ledger table exist anywhere in
               this repository. Every prior stage (BE1/BE2/BE3-A/B/C/R1/R2, and this project's own
               test suites) applies a migration by executing its file contents verbatim
               (`conn.execute(path.read_text())`) against a single connection; "already applied" is
               determined entirely by schema introspection, because every migration is idempotent
               (CREATE TABLE/INDEX IF NOT EXISTS, guarded ADD CONSTRAINT).
Ordering:      purely numeric-filename convention (029, 030, ..., 035); nothing enforces order at
               apply time beyond each migration's own FK/relation dependencies failing loudly if
               applied out of order (confirmed in §8 below).
Transaction
  model:       each migration file is a single self-contained `BEGIN; ... COMMIT;` block. It is
               NEVER wrapped in an additional Python-level `conn.transaction()` (that would nest
               incorrectly against the SQL text's own explicit transaction control).
Lock/
  concurrency: NONE existed before this stage. No advisory lock, no SELECT ... FOR UPDATE on a
               ledger row, nothing serialized two concurrent callers applying the same chain to the
               same database. This is a genuine, confirmed gap -- see §4 (RA-P's own finding,
               re-confirmed here) and §9 (the closure).
Startup
  behavior:    apps/orchestrator/src/main.py contains no migration-related code at all -- nothing
               auto-applies any migration on service startup, in docker-compose or otherwise.
Kubernetes
  Job:         infra/kubernetes/charts/ai-agents-platform/templates/migration-job.yaml is fail-closed
               by construction: renders ONLY for dev/test environments (never staging/production),
               and even then only when `batchJobs.migration.renderTemplate=true` AND execution is
               separately gated by `AIAGENTS_BATCH_EXECUTE`. It is not wired to any live cluster
               today. A Kubernetes Job's default `parallelism: 1` would structurally satisfy option
               B (single-Job guarantee) IF this path were ever activated, but that has not been
               exercised and is out of this stage's scope.
Backup/DR
  SOP:         `shared/sdk/backup_dr/` (Stage 51) provides backup/restore/migration-classification
               tooling for the OPERATIONAL data-protection story; it does not itself apply
               migrations. This stage's new `migration_runner.py` lives in the same package as a
               natural home for migration-apply tooling, consistent with `migration_catalog.py`.
```

No ambiguity was found in the migration sequence, its down scripts, or how migrations have
historically been applied — the "stop and report" condition in this stage's own instructions was
not triggered.

## 3. Binding safety distinction

### A. Pre-activation schema rollback (tested in this stage: §11)

Valid ONLY while:

```text
- migrations are applied
- all four BE3 feature gates remain false (confirmed unchanged throughout this stage: §14)
- the five new tables (031-035) contain NO runtime business data
```

Under these conditions, `035 down -> 034 down -> 033 down -> 032 down -> 031 down` is a safe,
lossless way to return to the pre-031 schema. This is rehearsed in §11/§12 of the evidence record.

### B. Post-write operational rollback (simulated in this stage: §13)

Once the five new tables carry real data, a `DROP TABLE`-based down migration is **NEVER** a safe
production rollback. The correct rollback, once data exists, is:

```text
- all four BE3 feature gates set to false (already the default; no code change needed)
- no worker/relay/consumer to stop (none exists yet for BE3 -- see be3-runtime-activation-
  readiness-plan.md's own finding)
- the application version may be rolled back; the new tables and their data are RETAINED, not
  dropped
- any further correction is a forward-fix or a separately-approved, purpose-built data migration --
  never a blind schema down-migration
```

This stage does NOT claim migration-down is a safe post-write rollback strategy under any
circumstance, and did not run a destructive down migration once synthetic data existed (§13 of the
evidence record is a NON-destructive simulation only).

## 4. Concurrency gap and its closure

RA-P (the prior planning stage) did not examine migration-apply concurrency directly. This stage's
own preflight (§2 above) found NO existing serialization mechanism for two concurrent callers
applying the same chain to the same database — a genuine gap, not previously closed. Per this
stage's own §5 allowance ("minimal migration-runner safeguard directly required for deterministic
rehearsal"), a new, additive module was built:

```text
shared/sdk/backup_dr/migration_runner.py
  apply_chain_locked(conn, migrations_dir, filenames, lock_key=...) -- wraps the chain in a
    session-level PostgreSQL advisory lock (pg_advisory_lock/pg_advisory_unlock, keyed by
    hashtextextended() -- a server-side hash, never Python's built-in hash()) held for the ENTIRE
    chain. A second concurrent caller blocks on pg_advisory_lock until the first finishes, rather
    than racing on DDL. Modifies NO existing migration file.
  schema_fingerprint(conn, table_names) -- a deterministic, order-independent snapshot of each
    table's columns/constraints/indexes, used to prove down+reapply produces an identical schema.
```

This closes the gap via option A ("one migrator obtains the lock, the other waits") — proven
directly in the evidence record (§10) via a non-blocking `pg_try_advisory_lock` probe, not merely
inferred from timing. No claim is made that migrations 031-035 were EVER safe to apply concurrently
without this new safeguard; before this stage, that would have been a blocking finding.

## 5. Scope discipline

```text
Allowed changes made:  shared/sdk/backup_dr/migration_runner.py (new, additive safeguard),
                       tests/test_step66c4_be3_ra1_migration_rehearsal.py (new rehearsal suite),
                       this plan, the evidence record, the handoff record, the verifier + its test.
Migrations 031-035:    UNCHANGED. No defect was found in them requiring remediation.
Not touched:           any shared/test/staging/production database; any feature gate; any
                       Compose/Helm/Kubernetes runtime value; any worker/relay/consumer.
```

## Statement

Rehearsal plan and findings record only. No shared migration application. No deployment. No
feature-gate change. No runtime validation. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
