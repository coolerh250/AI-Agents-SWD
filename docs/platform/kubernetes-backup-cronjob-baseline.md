# Kubernetes Backup CronJob Baseline (Step 51.2C2 / Stage 53E)

Controlled, **disabled** backup CronJob — validated not executed. No cluster, no
`kubectl`, no `helm install`, no backup run, no real cloud write.

## Command (fixed, shell-free)

```
python scripts/k8s_encrypted_backup.py
```

[`scripts/k8s_encrypted_backup.py`](../../scripts/k8s_encrypted_backup.py) is a
fixed, shell-free wrapper. It validates the controlled-only invariants and that
the encryption key is supplied via a Secret reference (never inline), and is
execution-gated by `AIAGENTS_BATCH_EXECUTE=true` (false in the baseline). The
container-native pg_dump pipeline (host `scripts/run_encrypted_backup.sh`) is
**not yet ported** → recorded `requires_cluster_smoke`.

## CronJob shape (disabled)

`templates/backup-cronjob.yaml` renders **only in dev/test**. In the baseline it
is **suspended** (`suspend: true`), `scheduleEnabled=false`, with
`concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 600`,
`successful/failedJobsHistoryLimit: 3`, and per-job `backoffLimit: 0` +
`activeDeadlineSeconds` + `ttlSecondsAfterFinished`. Dedicated `*-backup-job`
ServiceAccount (`automountServiceAccountToken: false`), restricted
SecurityContext, `/tmp` emptyDir. No Helm hook, no ArgoCD hook.

## Secrets + artifact target

* `DATABASE_URL` and `BACKUP_ENCRYPTION_KEY` are injected via `secretKeyRef`
  only — never an inline value.
* The artifact target is a **disabled placeholder** (`target.strategy: disabled`,
  `externalObjectStoreEnabled: false`, no real cloud endpoint). It is **never**
  an active workspace/database PVC. The backup store stays deferred (Step
  51.2C1) and `validate-values` blocks enabling the schedule without a target
  and blocks reusing `postgres-data`/`redis-data`.

Verify: `python scripts/verify_kubernetes_backup_cronjob.py`
(`KUBERNETES_BACKUP_CRONJOB_VERIFY: PASS`).

## Remaining limitations

Production schedule, real off-host target, encryption-key store, and retention
deletion are NOT configured here. Container-native backup execution is a
deferred cluster-smoke concern.
