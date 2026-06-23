# Security Scan Policy Catalog (Step 54.1)

Source of truth: [infra/security/security-scan-policy-catalog.yaml](../../infra/security/security-scan-policy-catalog.yaml).

Declares **which** scans are required and **when**. Every policy is `modeled_not_enforced`;
`productionEnforced: false`; no existing non-production verification is blocked.

| Policy | Applies to | Future step |
| --- | --- | --- |
| `sast_required_before_pr` | source_code | 54.2 |
| `dependency_scan_required_before_release` | dependencies | 54.2 |
| `secret_scan_required_before_pr` | repository | 54.2 |
| `sbom_required_before_deployment` | release_artifact | 54.3 |
| `image_digest_required_before_cluster_smoke` | container_image | 54.3 |
| `image_vulnerability_policy_required_before_runtime` | container_image | 54.3 |
| `threat_model_required_before_production_gate` | release | 54.4 |
| `release_risk_summary_required_before_deployment_request` | release | 54.4 |

Verified by `scripts/verify_security_scan_policy_baseline.py`
(`SECURITY_SCAN_POLICY_BASELINE_VERIFY`).
