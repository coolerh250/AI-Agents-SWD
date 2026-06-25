# Security Evidence Package (Step 54.4)

Generator: [`scripts/generate_security_evidence_package.py`](../../scripts/generate_security_evidence_package.py)
Output: `.runtime/security/security-evidence-package.json` (**never committed**).

Aggregates the committed Step 54.1–54.3 models and, if present, the latest redacted
runtime scan / SBOM / image-policy reports under `.runtime/security/`. A missing
runtime report is recorded as `not_run` / `missing_evidence` — never `present`/clean.
Each evidence entry references the report by path + sha256 + safe severity counts
only; no secret, no raw token, no raw finding evidence, no chain-of-thought.
`productionReady: false`.

Run:
```bash
python scripts/generate_security_evidence_package.py
python scripts/verify_security_evidence_package.py   # SECURITY_EVIDENCE_PACKAGE_VERIFY: PASS
```

Read-only view: `GET /operations/security/evidence/package` — degrades to `not_run`
in the orchestrator image (runtime artifact not present there). See the
[schema](security-evidence-package-schema.md).
