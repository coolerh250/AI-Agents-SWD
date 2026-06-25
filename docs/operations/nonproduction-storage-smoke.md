# Non-production PVC / Storage Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_storage_smoke.py`](../../scripts/verify_nonproduction_storage_smoke.py) · Marker: `NONPROD_STORAGE_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: Postgres/Redis PVC bound; workspace ephemeral volumes mounted; no hostPath; no production storage class / PV; backup target disabled; restore job disabled.

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_STORAGE_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
