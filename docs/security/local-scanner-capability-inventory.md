# Local Scanner Capability Inventory (Step 54.2)

Source of truth: [infra/security/local-scanner-capability-inventory.yaml](../../infra/security/local-scanner-capability-inventory.yaml).

Static catalog of the scanner tools the local baseline may use, with each tool's properties
(localOnly, externalNetworkRequired, tokenRequired, installed, supported scopes,
unavailableBehavior, blockers).

- **Bundled (`installed: true`):** `custom_repo_secret_scan`, `custom_static_checks`,
  `custom_dependency_inventory_check` — local-only, token-free, always runnable.
- **External (`installed: false`, runtime-detected):** gitleaks, detect-secrets (secret);
  bandit, semgrep (SAST); pip-audit, npm-audit, osv-scanner (dependency). The runners detect
  these on PATH and emit `tool_unavailable` / `network_required` when absent — never a fake PASS.

No tool is installed by this stage, no version is checked over the network, and no scanner
declares `sourceUpload` or `productionReady`. Verified by
`scripts/verify_local_scanner_capabilities.py` (`LOCAL_SCANNER_CAPABILITIES_VERIFY`).
