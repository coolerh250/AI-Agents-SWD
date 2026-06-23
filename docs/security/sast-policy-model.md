# SAST Policy Model (Step 54.1)

Source of truth: [infra/security/sast-policy-model.yaml](../../infra/security/sast-policy-model.yaml).

Models the static application security testing requirement. `required: true`,
`configured: false`, `productionReady: false`. No tool is installed and no scan is run.

- **Allowed tools (future):** semgrep, bandit, ruff-security-rules-future.
- **Scan scope:** apps, agents, shared, scripts.
- **Fail policy:** critical → fail; high → fail_or_approval_required; medium →
  approval_required; low → record.
- **Not SAST:** ruff, black, mypy (style/type tooling, explicitly excluded).

Enforcement deferred to **Step 54.2**.
