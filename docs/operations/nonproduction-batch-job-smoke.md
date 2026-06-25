# Non-production Batch Job Dependency Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_batch_job_smoke.py`](../../scripts/verify_nonproduction_batch_job_smoke.py) · Marker: `NONPROD_BATCH_JOB_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: migration job disabled unless explicit non-destructive test mode; backup CronJob suspended; restore job disabled; non-destructive command check (psql / pg_dump / pg_restore); no real backup target / restore / production DB / destructive op.

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_BATCH_JOB_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
