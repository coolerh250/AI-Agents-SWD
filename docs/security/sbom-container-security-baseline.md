# SBOM / Image Digest / Container Security Baseline (Step 54.3)

**Status:** SBOM / image digest / container security baseline **modeled and locally
verifiable, NOT production-enforced**.

Step 54.3 builds on the Step 54.1 supply-chain policy and the Step 54.2 local scan toolchain
with a local SBOM baseline, a container image inventory, image digest/tag policies, a Dockerfile
security inventory, runtime security alignment, an image vulnerability/policy model, and a
signing/attestation model. It runs **no registry login**, **no image pull/push**, **no image
signing**, **no production attestation**, **no external upload**, and wires **no production
gate**.

This stage does **not** claim: `production SBOM ready`, `production image supply chain ready`, or
`production image vulnerability gate ready`. **Claude Code must not decide Production readiness.**

## What this stage produced

Committed catalogs under [infra/security/](../../infra/security/):

| Area | Source of truth |
| --- | --- |
| SBOM capability inventory | `sbom-capability-inventory.yaml` |
| SBOM generation boundary | `sbom-generation-boundary.yaml` |
| SBOM artifact schema | `sbom-artifact-schema.yaml` |
| Container image inventory | `container-image-inventory.yaml` |
| Image digest policy | `image-digest-policy.yaml` |
| Image tag policy | `image-tag-policy.yaml` |
| Dockerfile security inventory | `dockerfile-security-inventory.yaml` |
| Container runtime security alignment | `container-runtime-security-alignment.yaml` |
| Image vulnerability scan capability | `image-vulnerability-scan-capability.yaml` |
| Image vulnerability result schema | `image-vulnerability-result-schema.yaml` |
| Image signing / attestation model | `image-signing-attestation-model.yaml` |
| Registry credential boundary | `registry-credential-boundary.yaml` |
| Container security evidence model | `container-security-evidence-model.yaml` |

SDK + runners:

- **SDK:** [shared/sdk/container_security/](../../shared/sdk/container_security/) — read-only
  posture loaders + safety fields + views.
- **Runners:** `scripts/run_local_sbom_baseline.py`, `scripts/run_local_image_policy_scan.py`.
  Reports are redacted and written to `.runtime/security/sbom/` and `.runtime/security/images/`
  (gitignored — **never committed**).

Read-only surfaces:

- **API:** 13 GET `/operations/security/{sbom,images}/*` endpoints + container/SBOM fields on
  `/operations/safety`.
- **Admin Console:** the Security view gains a read-only "SBOM / Image Digest / Container
  Security" section (no generate-SBOM / pull / scan / login / push / sign / attest control).

## Current posture

- SBOM: local manifest baseline (336 components inventoried); **not** a production SBOM; no upload.
- Images: 27 inventoried (20 first-party + batch + 6 third-party); **no digest pinned**, **no
  latest tag**; first-party use placeholder tag `step-51-1-placeholder`.
- Dockerfiles: 20, all `python:3.12-slim`, **all run as root** (no USER).
- Image policy scan: 50 policy findings (digest gaps, root gaps, job pg-client gap); **no CVE
  verdict** (trivy/grype/scout runtime-detected, absent).
- Signing/attestation: model only, disabled; no key committed.
- Registry: credential via Step 53 secret store only; no login/push/pull; production access disabled.

## Deferred

- **Step 54.4** — threat model, release risk summary, security evidence package, integrated
  Step 54 verification, full regression.
- **Step 55** — non-production cluster smoke (non-root / read-only-root / PVC / NetworkPolicy /
  `pg_dump`/`psql` job runtime).

See [sbom-container-security-verification](../operations/sbom-container-security-verification.md)
and [non-production limitations](../operations/sbom-container-security-non-production-limitations.md).

Step 54.4 integrates Steps 54.1–54.3 into a threat model, release risk summary,
security evidence package and readiness report (modeled, not production-enforced) — see
[application-security-supply-chain-integrated-baseline.md](application-security-supply-chain-integrated-baseline.md).

Step 55 takes this baseline to a non-production cluster runtime smoke (framework ready,
BLOCKED_NO_SAFE_CLUSTER on 10.0.1.31; never faked) — see
[../operations/nonproduction-kubernetes-smoke-plan.md](../operations/nonproduction-kubernetes-smoke-plan.md).
