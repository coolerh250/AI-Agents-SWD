# Release Governance — Release Evidence Package Model (Step 60)

- Model: `infra/release/release-evidence-package-model.yaml`
- SDK: `shared/sdk/release_governance/evidence.py`
- Verifier: `scripts/verify_release_evidence_package.py` → `RELEASE_EVIDENCE_PACKAGE_VERIFY`

The evidence package references existing platform evidence for a release candidate:
delivery package, work-item state, sandbox draft PR plan/result, security readiness,
SBOM status, runtime smoke status, ArgoCD manual-sync status, operational-metrics
snapshot, approval status, audit events, known limitations, rollback plan.

## Required for readiness
`security_readiness`, `rollback_plan`, `audit_events`. Missing required evidence is
reported in `missing_required` and **blocks production readiness** (which is false
regardless).

## Forbidden content
`secret`, `token`, `credential`, `chain-of-thought`, `raw_reasoning`. Secret-shaped
values are redacted by `shared/sdk/release_governance/redaction.py` before the summary
leaves the SDK.

## Invariants
- The package may state non-production readiness; it must **never** mark "production
  approved".
