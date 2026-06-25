# Threat Model Baseline (Step 54.4)

Source: [`infra/security/threat-model-baseline.yaml`](../../infra/security/threat-model-baseline.yaml)

A STRIDE-inspired + agentic-AI + supply-chain threat model over the platform.
**Modeled, NOT production-enforced.** `productionReady: false`. No production gate,
no approval, no deploy.

## Coverage
- **Assets** (20): admin console, operator actions, identity/OIDC, session/RBAC,
  secret management, audit integrity, runtime operations, Kubernetes/Helm/GitOps
  baseline, workspace operator, agent execution pipeline, delivery package, local
  scan toolchain, SBOM/image baseline, backup/restore, future GitHub PR flow,
  future ArgoCD sync, future production deployment, LLM integration, notifications,
  future Google Drive.
- **Trust boundaries / entrypoints / data flows** — see the YAML.
- **Threats** (`TM-001`..`TM-014`) each reference a category from the
  [threat category taxonomy](threat-category-taxonomy.md), with severity, existing
  mitigations, status and a `productionBlocker` flag.
- **Mitigations** — human approval, `production_executed` flag, HARD_SAFETY_ACTIONS,
  operator allowlist, tamper-evident audit, identity boundary, secret redaction,
  runtime read-only, no GitHub write, no deploy/sync, no external upload.
- **Residual risks + blockers** — production identity not validated, real CVE/SAST
  not run, digest pinning incomplete, non-root incomplete, cluster smoke (Step 55)
  and ArgoCD sync (Step 56) required.

## Verify
`python scripts/verify_threat_model_baseline.py` → `THREAT_MODEL_BASELINE_VERIFY: PASS`.
Read-only API: `GET /operations/security/threat-model/baseline`.
