# SBOM Generation Boundary (Step 54.3)

Source: [infra/security/sbom-generation-boundary.yaml](../../infra/security/sbom-generation-boundary.yaml).

Hard limits for the local SBOM runner: `localOnly: true`; no network, token, registry login,
image push/pull, or production attestation; runtime SBOM output to `.runtime/security/sbom/`
(never committed); allowed scopes python/node manifests + container image inventory;
`productionReady: false`. Verified by `scripts/verify_sbom_generation_boundary.py`
(`SBOM_GENERATION_BOUNDARY_VERIFY`).
