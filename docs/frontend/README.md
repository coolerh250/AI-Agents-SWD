# Frontend Docs

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owned by **Codex** (Frontend Engineer). This directory holds implementation plans, test evidence,
and handoff reports for Admin Console frontend work — written by Codex while implementing against a
design brief (`docs/design/<stage>/`) and a contract (`docs/contracts/<stage>/`).

## Layout

- `templates/` — reusable templates for each frontend-doc type.
- `<stage>/` — one folder per Step 66 sub-stage, containing the actual frontend docs for that stage.

## Rule

Codex does not modify backend, database, workflow, policy, or infrastructure unless explicitly
authorized by Claude Code for that specific change — see
`docs/process/role-responsibility-matrix.md`.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
