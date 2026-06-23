# Scan Result Artifact Schema (Step 54.2)

Source of truth: [infra/security/scan-result-artifact-schema.yaml](../../infra/security/scan-result-artifact-schema.yaml).

Shape of a single local scan report (`ScanResult` in the SDK). Reports are written to
`.runtime/security/` (gitignored) and are **never committed** (except redacted sample fixtures
under `tests/`).

Status enum: `passed`, `completed_with_findings`, `tool_unavailable`, `config_error`, `failed`.

Invariants (enforced by model + tests):

- `tool_unavailable` is never `passed`.
- `completed_with_findings` is never clean.
- `production_ready` is always false.
- no secret value in a report.
- runtime reports are not committed.

Covered by `tests/test_scan_result_artifact_schema.py`.
