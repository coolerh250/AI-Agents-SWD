# Security Evidence Model (Step 54.1)

Source of truth: [infra/security/security-evidence-model.yaml](../../infra/security/security-evidence-model.yaml).

Defines the evidence types a future release will collect. `required: true`,
`configured: false`. No evidence is generated this stage.

- **Evidence types:** sast_report, dependency_scan_report, secret_scan_report, sbom,
  image_digest_report, image_vulnerability_report, threat_model, release_risk_summary,
  qa_report, audit_evidence.
- **Constraints:** evidence must never contain a secret value (`noSecretValueAllowed: true`),
  must be referenceable by the delivery package, and must carry
  `hash / path / generatedAt / tool / scope / status`.

Generation deferred to **Step 54.4**. Verified by
`scripts/verify_security_evidence_model.py` (`SECURITY_EVIDENCE_MODEL_VERIFY`).

Step 54.2 produces the first concrete evidence inputs (local secret/SAST/dependency scan
reports + normalized summary), redacted and written to `.runtime/security/` (never committed) —
see [security-finding-normalization.md](security-finding-normalization.md).

Step 54.3 adds container security evidence (local SBOM, image inventory/digest status, Dockerfile
security inventory, runtime alignment, image policy report) — see
[container-security-evidence-model.md](container-security-evidence-model.md).
