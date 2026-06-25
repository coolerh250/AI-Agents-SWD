# Non-production NetworkPolicy Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_networkpolicy_smoke.py`](../../scripts/verify_nonproduction_networkpolicy_smoke.py) · Marker: `NONPROD_NETWORKPOLICY_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: default-deny present; allowed service-to-service paths work; disallowed paths blocked; DNS allowed; Postgres/Redis reachable only from expected sources; no 0.0.0.0/0 egress unless documented.

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_NETWORKPOLICY_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
