# Secret Scan Policy Model (Step 54.1)

Source of truth: [infra/security/secret-scan-policy-model.yaml](../../infra/security/secret-scan-policy-model.yaml).

Models the secret scanning requirement and ties into the Step 53 secret posture.
`required: true`, `configured: false`, `productionReady: false`.

- **Allowed tools (future):** gitleaks, detect-secrets, custom_repo_secret_scan.
- **Scan scope:** repository, infra, docs, tests.
- **Fail policy:** any confirmed secret → fail; suspicious high-entropy → review_required.
- **Existing controls (Step 53):** `scripts/verify_secret_no_inline_values.py`,
  `infra/secrets/secret-redaction-policy.yaml`, `tests/test_secret_leak_scanner.py`. These
  enforce *no committed inline secret today*; a CI secret scanner is still required.

Enforcement deferred to **Step 54.2**. See
[secret-management-foundation.md](secret-management-foundation.md).
