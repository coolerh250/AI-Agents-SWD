# SBOM Artifact Schema (Step 54.3)

Source: [infra/security/sbom-artifact-schema.yaml](../../infra/security/sbom-artifact-schema.yaml).

Shape of a local SBOM report (sbomType / format / scope / generator / components / metadata /
limitations). Supported formats: cyclonedx-like, spdx-like, internal-manifest-baseline.
Invariants: `production_ready_always_false`, `no_secret_value`, `no_token`,
`no_registry_credential`, `runtime_sbom_not_committed`, `custom_manifest_baseline_is_limited`.
Runtime SBOMs live under `.runtime/security/sbom/` and are never committed.
