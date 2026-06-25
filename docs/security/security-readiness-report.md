# Security Readiness Report (Step 54.4)

Generator: [`scripts/generate_security_readiness_report.py`](../../scripts/generate_security_readiness_report.py)
Output: `.runtime/security/security-readiness-report.json` (**never committed**).

Rolls up the Step 54.1–54.3 baselines, the threat model, the
[evidence package](security-evidence-package.md) and the
[release risk summary](release-risk-summary-model.md) into a single posture report.
It is a posture report, **NOT a production approval**: `productionReady: false`,
`releaseGateEnabled: false`. It lists production blockers, non-production
limitations, and the required next steps (Step 55 non-production cluster smoke,
Step 56 real ArgoCD manual sync, Step 60 production readiness review).

Run:
```bash
python scripts/generate_security_readiness_report.py
python scripts/verify_security_readiness_report.py   # SECURITY_READINESS_REPORT_VERIFY: PASS
```

Read-only view: `GET /operations/security/readiness/report` (degrades to `not_run`).
Claude Code does not decide Production readiness.
