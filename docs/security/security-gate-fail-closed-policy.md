# Security Gate Fail-Closed Policy (Step 54.1)

Source of truth: [infra/security/security-gate-fail-closed-policy.yaml](../../infra/security/security-gate-fail-closed-policy.yaml).

Defines fail-closed gate behaviour. The gate is **not wired** to any release/deployment path
this stage; the production gate stays disabled and no non-production verification is blocked.

- **Fail-closed:** missing SAST / dependency scan / secret scan / SBOM / image digest /
  image vulnerability / threat model / release risk summary ⇒ **not ready**.
- **Findings:** confirmed secret leak ⇒ fail; critical finding ⇒ fail; high finding ⇒ fail
  or explicit approval.
- `productionGateEnabled: false`, `releaseGateMutationEnabled: false`,
  `blocksNonProductionVerification: false`.

**Claude Code must not decide Production readiness.** Enforcement deferred to **Step 54.4**.

Verified by `scripts/verify_security_gate_policy.py` (`SECURITY_GATE_POLICY_VERIFY`).
