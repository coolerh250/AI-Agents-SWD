# Application Security & Supply Chain Baseline (Step 54.1)

**Status:** application security and supply chain baseline **modeled, not enforced for production**.

Step 54.1 establishes the security & supply-chain *inventory*, *policy model*, *evidence
model*, and *fail-closed verification baseline* for the platform. It does **not** run any
scanner, generate an SBOM, push or scan an image, connect to a registry/scanner, write to
GitHub, or wire a production release gate. Those are deferred to Step 54.2 / 54.3 / 54.4.

This stage does **not** claim any of: `security scans production-ready`, `SBOM
production-ready`, `image supply chain production-ready`, `release gate production-ready`.
**Claude Code must not decide Production readiness.**

## What this stage produced

Committed catalogs under [infra/security/](../../infra/security/):

| Area | Source of truth |
| --- | --- |
| Application security asset inventory | `application-security-asset-inventory.yaml` |
| Supply chain inventory | `supply-chain-inventory.yaml` |
| Dependency surface inventory | `dependency-surface-inventory.yaml` |
| Security scan policy catalog | `security-scan-policy-catalog.yaml` |
| SAST policy model | `sast-policy-model.yaml` |
| Dependency scan policy model | `dependency-scan-policy-model.yaml` |
| Secret scan policy model | `secret-scan-policy-model.yaml` |
| SBOM policy model | `sbom-policy-model.yaml` |
| Container image security policy | `container-image-security-policy.yaml` |
| Threat model input catalog | `threat-model-input-catalog.yaml` |
| Release risk input catalog | `release-risk-input-catalog.yaml` |
| Security evidence model | `security-evidence-model.yaml` |
| Security finding taxonomy | `security-finding-taxonomy.yaml` |
| Security gate fail-closed policy | `security-gate-fail-closed-policy.yaml` |
| Anti-drift posture summary | `security-foundation-summary.yaml` (generated) |

Read-only surfaces:

- **SDK:** [shared/sdk/security_foundation/](../../shared/sdk/security_foundation/) —
  read-only aggregation; never runs a scanner or touches the network.
- **API:** `GET /operations/security/*` (17 endpoints) + security/supply-chain fields on
  `GET /operations/safety`.
- **Admin Console:** read-only "Security / Supply Chain" view (no run-scan / upload /
  connect / configure / create-PR / push-image / production-gate control).

## Current posture (modeled, not enforced)

- SAST / dependency scan / secret scan / SBOM / image scan: **not configured**.
- GitHub write, PR creation, image push, registry login, external scanner upload: **false**.
- Image digest pinning: **not pinned** (blocker). Dockerfiles: **no non-root USER** (blocker).
- Python dependencies: **unpinned, no lockfile** (blocker). Node: `package-lock.json` present.
- Production security gate: **disabled**. `production_executed_true_count = 0`.

## Deferred

- **Step 54.2** — Secret Scan / SAST / Dependency Scan toolchain baseline. **Done** — see
  [security-scan-toolchain-baseline.md](security-scan-toolchain-baseline.md).
- **Step 54.3** — SBOM / Image Digest / Container Security baseline.
- **Step 54.4** — Threat Model / Release Risk Summary / Integrated Verification.

See [security-supply-chain-verification.md](../operations/security-supply-chain-verification.md)
and [security-supply-chain-non-production-limitations.md](../operations/security-supply-chain-non-production-limitations.md).
