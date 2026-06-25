# Non-production Service Connectivity Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_service_connectivity.py`](../../scripts/verify_nonproduction_service_connectivity.py) · Marker: `NONPROD_SERVICE_CONNECTIVITY_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: orchestrator -> policy/approval/audit/Redis; services -> Postgres; gateway -> orchestrator; no external SaaS / production DB / production Redis / production IdP / production secret.

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_SERVICE_CONNECTIVITY_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
