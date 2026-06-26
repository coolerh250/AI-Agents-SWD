# Sandbox GitHub — Draft PR Limitations (Step 59)

This is a **sandbox-only draft PR baseline**. It must NOT be described as:

- production GitHub automation ready
- real customer repo automation ready
- merge automation ready
- production release ready

## What it does
- Builds (dry_run) or — when explicitly enabled with a credential — creates a **draft**
  pull request inside an allowlisted **sandbox** repository, linked to a project / work
  item with full audit.

## What it deliberately does NOT do
- No PR merge, no ready-for-review transition, no push to main / production branch.
- No write to a non-sandbox / customer repository (request carries a key, not raw
  owner/repo; unknown keys are rejected).
- No GitHub Actions workflow dispatch, no issue write, no release write, no deployment
  write.
- No ArgoCD sync, no Kubernetes mutation, no image push, no registry login, no external
  notification, no production action.
- A `production_effect` work item is never turned into a PR.

## Credential / runtime
- The token comes from `SANDBOX_GITHUB_TOKEN` (env / secret reference) only; it is never
  committed, logged, or returned. The orchestrator container carries no token, so
  `live_sandbox` is blocked there and only dry_run plans are produced.
- `live_sandbox` requires `SANDBOX_GITHUB_LIVE=true` AND a credential; otherwise the
  request is blocked — never a fabricated live success.

## Observations / next phase
- A draft PR record is not a merge, review, or production approval.
- Recommended next phase: **Step 60 — Release & Deployment Governance**.
- Claude Code must not decide Production readiness.
