# Scan Target Catalog (Step 54.2)

Source of truth: [infra/security/scan-target-catalog.yaml](../../infra/security/scan-target-catalog.yaml).

Allowlisted include/exclude per scan type. No arbitrary path is accepted; excluded paths are
**not** treated as safe — exclusion only avoids false positives / heavy or irrelevant scans.

- **secretScan:** include apps/agents/shared/scripts/infra/docs/tests; exclude
  `.git`, `.venv`, `node_modules`, `dist`, `build`, `.runtime`.
- **sast:** include apps/agents/shared/scripts; exclude `tests/fixtures`, `generated`.
- **dependencyScan:** packageFiles `requirements.txt`, `pyproject.toml`, `package.json`,
  `package-lock.json`.

Production code dirs, package files, Dockerfiles, and Helm/GitOps manifests are never excluded
(enforced via [scan-exclusion-policy.md](scan-exclusion-policy.md)). Verified by
`scripts/verify_scan_target_catalog.py` (`SCAN_TARGET_CATALOG_VERIFY`).
