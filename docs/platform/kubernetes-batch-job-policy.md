# Kubernetes Batch Job Policy (Step 51.2C2 / Stage 53E)

Cross-cutting safety policy enforced on **every** rendered batch Job/CronJob
(migration / backup / restore), across the four standard environments + the
restore fixture. Templates are validated, **not executed**; no cluster connected.

## Fixed command model

Every batch command is a fixed `(command, args)` pair from
[batch-command-catalog.yaml](../../infra/kubernetes/batch-command-catalog.yaml),
mirrored into `values.batchCommands` (verified equal). No command/args come from
free-form values; `shell: false`; no `sh -c` / `bash -c`; no command
substitution; no executable composed from env values. Each command references an
existing repo entrypoint by source path.

## Enforced policy

* **No production batch resource** (staging/production render none).
* **No Helm hook, no ArgoCD hook** annotations.
* **Restricted security**: runAsNonRoot 10001, RuntimeDefault seccomp, no
  privilege escalation, not privileged, drop ALL capabilities, read-only root,
  `/tmp` bounded emptyDir only (no `/app`, no hostPath, no docker socket).
* **ServiceAccount token off** at pod + SA; **no Kubernetes RBAC** (no
  Role/ClusterRole) → zero Kubernetes API access. Secrets arrive via
  `secretKeyRef`, which needs no API.
* **CronJob suspended + `concurrencyPolicy: Forbid`**; **Jobs**
  `backoffLimit: 0` + `activeDeadlineSeconds` + `ttlSecondsAfterFinished`.
* **No secret literal**, **no real endpoint / cloud credential** in rendered
  output.
* **No active-datastore storage collision** (batch pods never mount
  `*-postgres-data` / `*-redis-data` PVCs).
* **Execution disabled**: `AIAGENTS_BATCH_EXECUTE` is false on every batch pod.

The 51.2A workload-security verifier was extended to also reach **CronJob**
nested pod specs (a coverage increase — the restricted baseline now applies to
CronJob pods too).

Verify: `python scripts/verify_kubernetes_batch_job_policy.py`
(`KUBERNETES_BATCH_JOB_POLICY_VERIFY: PASS`) and the combined
`scripts/verify_kubernetes_batch_jobs_baseline.sh`
(`KUBERNETES_BATCH_JOBS_BASELINE_VERIFY: PASS`).
