# Dependency Scan Policy Model (Step 54.1)

Source of truth: [infra/security/dependency-scan-policy-model.yaml](../../infra/security/dependency-scan-policy-model.yaml).

Models the dependency vulnerability scan requirement. `required: true`, `configured: false`,
`productionReady: false`. No audit is run.

- **Ecosystems:** python, node, container_base_images.
- **Allowed tools (future):** pip-audit, npm-audit, osv-scanner.
- **Lockfile required:** true. Python lockfile **absent** (blocker
  `python_lockfile_missing`); Node lockfile present (`package-lock.json`).
- **Fail policy:** critical → fail; high → fail_or_approval_required; medium →
  approval_required.

Enforcement deferred to **Step 54.2**.
