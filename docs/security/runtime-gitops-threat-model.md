# Runtime / Kubernetes / GitOps Threat Model (Step 54.4)

Source: [`infra/security/runtime-gitops-threat-model.yaml`](../../infra/security/runtime-gitops-threat-model.yaml)

Runtime/GitOps threats (`RG-001`..`RG-011`): manifest drift, ArgoCD sync misuse,
Helm values secret leakage, NetworkPolicy bypass, privilege escalation,
ServiceAccount token misuse, PVC data exposure, migration/backup job misuse,
runtime non-root incompatibility, pg_dump/psql job missing runtime dependency,
production placeholder accidentally deployed.

**Static-baseline caveat (emphasised):**
- Step 51 static baseline ≠ real cluster validation.
- Step 55 required for non-production cluster smoke.
- Step 56 required for real ArgoCD manual sync.

`productionReady: false`.

## Verify
`python scripts/verify_runtime_gitops_threat_model.py` →
`RUNTIME_GITOPS_THREAT_MODEL_VERIFY: PASS`.
API: `GET /operations/security/threat-model/runtime-gitops`.
