# Kubernetes Restore Job Safety (Step 51.2C2 / Stage 53E)

Restore is a **critical** operation. The Job is a **disabled scaffold** that is
never rendered in standard environments and never executed. No cluster, no
`kubectl`, no restore run, no production restore.

## Render policy

`templates/restore-job.yaml` has `batchJobs.restore.renderTemplate=false` in
**all** standard environment values (dev/test/staging/production). Only a
dedicated, non-production verifier fixture
([batch-restore-scaffold-fixture.yaml](../../infra/kubernetes/fixtures/batch-restore-scaffold-fixture.yaml))
renders the disabled scaffold so the restore verifier can inspect its shape.
`validate-values` fails closed if restore renders outside dev/test or if
execution is enabled.

## Target isolation

* The target DB name uses the fixed prefix **`aiagents_restore_drill_`**
  (`restore.targetPrefix`, a schema `const`). The wrapper
  [`scripts/k8s_restore_drill.py`](../../scripts/k8s_restore_drill.py) reuses the
  repo's tested guard `assert_isolated_restore_db`, which forbids `aiagents` /
  `postgres` / template catalogs.
* **Source ≠ target**; restoring into the source/primary catalog is refused.
* Source and target credentials use **separate** `secretKeyRef`s; the encryption
  key is a Secret reference.
* No service-traffic switch, no Service object, no production target.

## Command (fixed, shell-free)

```
python scripts/k8s_restore_drill.py
```

Execution-gated by `AIAGENTS_BATCH_EXECUTE=true` (false). The container-native
restore pipeline (host `scripts/run_restore_drill.sh`) is **not yet ported** →
`requires_cluster_smoke`. The wrapper performs NO database mutation in this stage.

Job shape: `restartPolicy: Never`, `backoffLimit: 0`, `activeDeadlineSeconds`,
`ttlSecondsAfterFinished`, dedicated `*-restore-job` SA
(`automountServiceAccountToken: false`), restricted SecurityContext, `/tmp`
emptyDir. No Helm hook, no ArgoCD hook.

Verify: `python scripts/verify_kubernetes_restore_job.py`
(`KUBERNETES_RESTORE_JOB_VERIFY: PASS`).

## Remaining limitations

Production restore approval/process and container-native restore execution are
deferred. Claude Code reports observations only and does not decide restore or
Production readiness.
