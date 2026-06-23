# Local Security Scan Toolchain Baseline (Step 54.2)

**Status:** local secret scan / SAST / dependency scan baseline **modeled and locally
executable, NOT production-enforced**.

Step 54.2 makes the Step 54.1 scan policies *partially executable* with a local, offline
toolchain. It runs **no external scanner**, uploads **no source**, uses **no token**, makes
**no network call**, writes **no GitHub / PR / image**, and wires **no production release
gate**. SBOM, image vulnerability scanning, threat model, and release-risk integration are
deferred to Step 54.3 / 54.4.

This stage does **not** claim: `production security scans fully enforced`, `release gate
production-ready`, or `security findings all remediated`. **Claude Code must not decide
Production readiness.**

## What this stage produced

Committed models under [infra/security/](../../infra/security/):

| Area | Source of truth |
| --- | --- |
| Local scanner capability inventory | `local-scanner-capability-inventory.yaml` |
| Scanner execution boundary | `scanner-execution-boundary.yaml` |
| Scan target catalog | `scan-target-catalog.yaml` |
| Scan exclusion policy | `scan-exclusion-policy.yaml` |
| Scan result artifact schema | `scan-result-artifact-schema.yaml` |
| Scan status summary model | `security-scan-status-summary-model.yaml` |

SDK + runners:

- **SDK:** [shared/sdk/security_findings/](../../shared/sdk/security_findings/) — normalized
  `SecurityFinding` / `ScanResult` models (evidence redacted, no secret value), a result
  normalizer, redaction, and read-only scan posture loaders.
- **Runners:** `scripts/run_local_secret_scan.py`, `run_local_sast_scan.py`,
  `run_local_dependency_scan.py`, `normalize_security_scan_results.py`. Reports are written to
  `.runtime/security/` (gitignored — **never committed**).

Read-only surfaces:

- **API:** 9 GET `/operations/security/scans/*` endpoints + 16 scan fields on `/operations/safety`.
- **Admin Console:** the Security / Supply Chain view gains a read-only "Local Scan Toolchain
  Baseline" section (no run-scan / upload / connect / configure control).

## Toolchain posture

- **Secret scan:** `custom_repo_secret_scan` (bundled) — high-confidence credential shapes are
  confirmed `critical`; keyword/format heuristics (GUID, `secret`-named vars) are low-confidence
  review items. Strict committed-secret prevention remains Step 53's
  `SECRET_NO_INLINE_VALUES_VERIFY`.
- **SAST:** `custom_static_checks` (bundled, **limited** baseline — not a full SAST engine).
  bandit/semgrep are runtime-detected; absent → `tool_unavailable`.
- **Dependency scan:** `custom_dependency_inventory_check` (bundled, **manifest-policy only, no
  CVE lookup**). pip-audit/npm-audit/osv-scanner are network-dependent → reported unavailable.

A `tool_unavailable` scan is never `passed`; a missing scan is never `clean`; productionReady is
always false.

See [security-scan-toolchain-verification](../operations/security-scan-toolchain-verification.md)
and [non-production limitations](../operations/security-scan-non-production-limitations.md).
