# Non-production Service Health Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_service_health.py`](../../scripts/verify_nonproduction_service_health.py) · Marker: `NONPROD_SERVICE_HEALTH_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: orchestrator / policy-engine / approval-engine / audit-service / communication-gateway / agents /health via port-forward or an in-cluster curl job; no public ingress, no LoadBalancer, no production endpoint.

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_SERVICE_HEALTH_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
