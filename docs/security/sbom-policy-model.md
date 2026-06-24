# SBOM Policy Model (Step 54.1)

Source of truth: [infra/security/sbom-policy-model.yaml](../../infra/security/sbom-policy-model.yaml).

Models the software bill of materials requirement. `required: true`, `configured: false`,
`productionReady: false`. **No SBOM is generated this stage** — placeholder schema + future
artifact path only.

- **Formats:** cyclonedx, spdx.
- **Scopes:** python, node, container.
- **Required before:** release_package, deployment_request.
- **Storage:** not committed to repo; artifact store required; future path
  `source/security-evidence/sbom/<release>/`.

Enforcement / generation deferred to **Step 54.3** — **done**: a local manifest SBOM baseline is
now generated (not a production SBOM, never uploaded). See
[local-sbom-baseline.md](local-sbom-baseline.md) and
[sbom-container-security-baseline.md](sbom-container-security-baseline.md).
