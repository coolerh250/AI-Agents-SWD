# Security Finding Normalization (Step 54.2)

Source of truth: [shared/sdk/security_findings/](../../shared/sdk/security_findings/).

## SecurityFinding

Normalized finding model. `evidence_redacted` is always passed through redaction (no secret
value survives); `file_path` must be repo-relative (absolute paths / `..` traversal rejected);
`finding_id` is a deterministic `sha256(scanner|category|rule|path|line)[:16]`. `severity_flags`
maps category + severity to `(production_blocker, requires_approval)` — any secret finding and
any critical is a production blocker; high → fail or approval; medium → approval.

## Normalizer

`normalize({secret, sast, dependency})` merges per-type `ScanResult`s into one redacted summary:
unified severity totals, `production_blocker` / `requires_approval` rollup, and
`not_ready_reasons`. A **missing** scan is recorded `not_run` (never clean); `tool_unavailable`
is preserved; standing non-production reasons (external CVE scan not performed, SBOM not
generated, production gate off) are always present. `production_ready` is always false.

Verified by `scripts/verify_security_scan_result_normalization.py`
(`SECURITY_SCAN_RESULT_NORMALIZATION_VERIFY`) and covered by
`tests/test_security_finding_schema.py` + `tests/test_security_finding_normalizer.py`.
