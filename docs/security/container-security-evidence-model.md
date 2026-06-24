# Container Security Evidence Model (Step 54.3)

Source: [infra/security/container-security-evidence-model.yaml](../../infra/security/container-security-evidence-model.yaml).

Evidence types the Step 54.4 release risk summary will reference: local_sbom_baseline,
image_inventory_report, image_digest_status, dockerfile_security_inventory,
runtime_security_alignment, image_policy_report, image_vulnerability_scan_report_future,
signing_attestation_future. Evidence carries no secret value; runtime reports are never committed;
`releaseRiskReferenceable: true`; `productionReady: false`. Extends the Step 54.1
[security-evidence-model.md](security-evidence-model.md). Covered by
`tests/test_container_security_evidence_model.py`.
