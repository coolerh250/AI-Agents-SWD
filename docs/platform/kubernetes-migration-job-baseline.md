# Kubernetes Migration Job Baseline (Step 51.2C2 / Stage 53E)

Controlled migration Job, **validated not executed**. No cluster connection, no
`kubectl`, no `helm install`, no migration run.

## Command (fixed, shell-free)

The migration command is fixed in
[batch-command-catalog.yaml](../../infra/kubernetes/batch-command-catalog.yaml)
and mirrored into `values.batchCommands` (the inventory verifier asserts they
match). It is never taken from free-form values and never uses a shell:

```
python scripts/k8s_apply_migrations.py
```

[`scripts/k8s_apply_migrations.py`](../../scripts/k8s_apply_migrations.py) is the
wrapper around the repo's forward-only `psql -f migrations/NNN_*.sql` apply
(there was no single apply-entrypoint before). It is **execution-gated** by
`AIAGENTS_BATCH_EXECUTE=true` (false in the baseline → prints a plan, no DB work).

## Locking + idempotency

* **Lock**: a Postgres **advisory lock** — `pg_advisory_lock(hashtext('aiagents_schema_migration_v1'))`
  held across all migrations (the repo's existing `audit_integrity` idiom). No
  Kubernetes Lease (the Job has zero Kubernetes API access).
* **Idempotency**: SQL-level (`IF NOT EXISTS` / `CREATE OR REPLACE`); there is no
  applied-migration tracking table, so migrations are safe to re-run.
* **Forward-only**: the wrapper never runs `*_down.sql`. Rollback stays the
  operator-driven catalog (`shared/sdk/backup_dr/migration_catalog.py`).

## Job shape

`templates/migration-job.yaml` renders **only in dev/test** (staging/production
render nothing — `validate-values` fail-closed). `restartPolicy: Never`,
`backoffLimit: 0`, `activeDeadlineSeconds: 900`, `ttlSecondsAfterFinished: 3600`,
dedicated `*-migration-job` ServiceAccount with `automountServiceAccountToken:
false`, restricted SecurityContext (runAsNonRoot 10001, RuntimeDefault, no
privesc, drop ALL, read-only root, `/tmp` emptyDir), resource limits, and
`DATABASE_URL` via `secretKeyRef` only. No Helm hook, no ArgoCD hook.

## Network

A minimal NetworkPolicy allows the migration pod egress to Postgres `5432` (+
shared DNS) and Postgres ingress from the batch job — specific
`ai-agents-swd/batch-job: migration` selector, dev/test only, never broad.

Verify: `python scripts/verify_kubernetes_migration_job.py`
(`KUBERNETES_MIGRATION_JOB_VERIFY: PASS`). Live behaviour is a deferred
cluster-smoke concern.
