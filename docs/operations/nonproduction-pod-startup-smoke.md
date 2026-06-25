# Non-production Pod Startup Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_pod_startup.py`](../../scripts/verify_nonproduction_pod_startup.py) · Marker: `NONPROD_POD_STARTUP_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: pods reach Running/Completed; no CrashLoopBackOff / ImagePullBackOff / CreateContainerConfigError; no runAsNonRoot / readOnlyRootFilesystem / writable-path / missing-secret failure; events collected redacted.

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_POD_STARTUP_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
