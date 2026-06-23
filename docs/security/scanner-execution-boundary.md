# Scanner Execution Boundary (Step 54.2)

Source of truth: [infra/security/scanner-execution-boundary.yaml](../../infra/security/scanner-execution-boundary.yaml).

The hard limits every local scan runner operates within:

- `localOnly: true`; `networkAllowed: false`; `tokenAllowed: false`; `credentialAllowed: false`.
- `externalUploadAllowed: false`; `githubWriteAllowed: false`; `prCreationAllowed: false`;
  `imagePushAllowed: false`.
- `userProvidedPathAllowed: false`; `allowlistedTargetsOnly: true` (apps, agents, shared,
  scripts, infra, tests, docs).
- `boundedRuntimeSeconds: 300`; `reportRedacted: true`; `reportContainsSecretValues: false`;
  `nonProductionReportOnly: true`.
- `productionGateMutationAllowed: false`; reports written to `.runtime/security/`,
  `runtimeReportsCommitted: false`.

Verified by `scripts/verify_scanner_execution_boundary.py` (`SCANNER_EXECUTION_BOUNDARY_VERIFY`).
