# Supply-Chain Threat Model (Step 54.4)

Source: [`infra/security/supply-chain-threat-model.yaml`](../../infra/security/supply-chain-threat-model.yaml)

Supply-chain threats (`SC-001`..`SC-014`): dependency compromise, missing Python
lockfile, malicious package, base-image compromise, mutable tag, missing image
digest, root container, missing SBOM, missing image vulnerability scan, missing
signing/attestation, scanner-tool compromise, secret leakage in reports, registry
credential compromise, future GitHub PR manipulation.

Each threat links to the Step 54.1–54.3 blockers (`linkedBaselineBlockers`) so the
[release risk summary](release-risk-summary-model.md) and
[readiness report](security-readiness-report.md) can roll them up.
`productionReady: false`.

## Verify
`python scripts/verify_supply_chain_threat_model.py` →
`SUPPLY_CHAIN_THREAT_MODEL_VERIFY: PASS`.
API: `GET /operations/security/threat-model/supply-chain`.
