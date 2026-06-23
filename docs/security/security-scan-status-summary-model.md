# Security Scan Status Summary Model (Step 54.2)

Source of truth: [infra/security/security-scan-status-summary-model.yaml](../../infra/security/security-scan-status-summary-model.yaml).

Declares the per-scan-type status enum (`not_configured`, `tool_unavailable`, `not_run`,
`completed_no_findings`, `completed_with_findings`, `failed`) and the production-readiness rule
the normalized summary applies.

It also records the **baseline configuration** the `/operations/safety` scan fields read:
`localScanBaselineEnabled: true`, `secretScanConfigured: configured`,
`sastConfigured: limited_custom_baseline`, `dependencyScanConfigured: limited_manifest_baseline`,
and all of external-upload / network / token / run-endpoint / reports-committed / production-gate
= false. Runtime last-status comes from the latest redacted runtime summary, or `not_run` when
absent.

Production readiness rule (applied to the local baseline only; gate stays disabled): any
`not_configured` or `tool_unavailable` → not ready; any critical → fail; any high → fail or
approval; missing dependency lockfile → not ready before production; missing SBOM → not ready
before deployment.

Covered by `tests/test_security_scan_status_summary_model.py`.
