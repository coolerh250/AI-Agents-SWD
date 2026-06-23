# Release Risk Input Catalog (Step 54.1)

Source of truth: [infra/security/release-risk-input-catalog.yaml](../../infra/security/release-risk-input-catalog.yaml).

Defines the inputs a future release risk summary (**Step 54.4**) will aggregate. Every input
is `modeled_not_enforced`; `productionGateIntegrated: false`.

Inputs: SAST result, dependency scan result, secret scan result, SBOM presence, image digest
status, image vulnerability result, threat model status, QA verification, security findings,
human acceptance, approval status, rollback plan, backup status, production identity status,
secret readiness, runtime readiness.

None is wired to a production gate. Generation deferred to **Step 54.4**.
