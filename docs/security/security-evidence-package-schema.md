# Security Evidence Package Schema (Step 54.4)

Source: [`infra/security/security-evidence-package-schema.yaml`](../../infra/security/security-evidence-package-schema.yaml)

Schema for the redacted evidence package produced by
[`generate_security_evidence_package.py`](../../scripts/generate_security_evidence_package.py).

Evidence sections: `sast`, `dependencyScan`, `secretScan`, `sbom`, `imagePolicy`,
`dockerfileSecurity`, `threatModel`, `releaseRisk`, `audit`, `qa`. Each carries a
status from `evidenceStatusEnum` = {`present`, `not_run`, `missing_evidence`,
`tool_unavailable`} — there is **no `clean` status**; absent evidence is never
marked clean.

Redaction rules (all true): no secret, no raw token, no raw source with secret, no
chain-of-thought, references only. `committedRuntimePackageAllowed: false` — runtime
packages are never committed. `productionReady: false`.

## Verify
`tests/test_security_evidence_package_schema.py`;
`python scripts/verify_security_evidence_package.py`.
