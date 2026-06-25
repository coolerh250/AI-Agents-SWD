# Non-production SecurityContext Runtime Smoke (Step 55)

Verifier: [`scripts/verify_nonproduction_securitycontext_smoke.py`](../../scripts/verify_nonproduction_securitycontext_smoke.py) · Marker: `NONPROD_SECURITYCONTEXT_SMOKE_VERIFY`

Cluster-runtime smoke against the `aiagents-smoke-*` namespace: runAsNonRoot effective; readOnlyRootFilesystem works; writable /tmp; allowPrivilegeEscalation=false; capabilities dropped; SA token automount false; Dockerfile-USER gaps identified, dev exceptions documented (postgres/redis/vault).

**Requires a safe non-production cluster.** With no safe cluster (no kubectl/helm/
kubeconfig or an unsafe context) the verifier honestly emits
`NONPROD_SECURITYCONTEXT_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER` — never a faked PASS. No production deploy, no
ArgoCD sync, `production_executed` stays false. Findings (e.g. Dockerfile USER /
runAsNonRoot gaps) are recorded exactly, never hidden.
