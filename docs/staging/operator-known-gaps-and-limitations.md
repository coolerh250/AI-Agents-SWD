# Operator Known Gaps & Limitations (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Known gaps + limitations of the **staging** system, for the operator. None is a production
readiness sign-off; **Claude Code does not decide production readiness.** These are documented,
not fixed, in this stage.

## 1. communication-gateway missing PyYAML → mock-intake 500
`POST /intake/mock/project-work-item` on the communication-gateway returns HTTP **500**
(`ModuleNotFoundError: No module named 'yaml'`) because the gateway image does not bundle PyYAML.
- **Workaround used (Step 64D):** the demo seed ran the same SDK inside the **orchestrator**
  container (which has PyYAML) via `scripts/staging_seed_demo_workflow.py`.
- **Fix (future stage, requires authorization):** add `PyYAML` to the communication-gateway
  image dependencies and rebuild that image. Not done here.

## 2. Delivery package gated behind operator auth
The governed work-item **dispatch** requires operator auth + CSRF, and operator actions are
disabled in staging (`operator_actions_disabled`). No delivery package is produced.

## 3. Release candidate gated
Because there is no delivery package (gap #2), Release Governance shows no release candidate.

## 4. Vault dev / mock-vault
Vault runs in dev mode; `SECRET_PROVIDER=mock-vault`. This is a staging escape hatch, **not** a
production-ready secret store.

## 5. HTTP only through SSH tunnel
Access is HTTP (no TLS) through the SSH local port-forward. Acceptable for staging demo; TLS is
a future option.

## 6. No public exposure
Port `18000` is bound to loopback only; there is no public/LAN exposure. Access is via SSH
tunnel only.

## 7. LLM disabled / mocked
No live LLM calls; LLM interactions count is 0.

## 8. GitHub / Slack (Discord) live integration disabled
`github_external_write_enabled=false`, `real_github_test_enabled=false`,
`discord_external_send_enabled=false`. Any GitHub token present is a sandbox/mock token; no live
write occurs.

## Interpretation
The staging system demonstrates the non-production flow end-to-end (project → work item → agent
pipeline → audit → metrics) with a green safety posture. The gaps above are expected staging
limitations and gated governance points, not defects requiring operator action here.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
