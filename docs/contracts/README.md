# Contract Docs

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owned by **Claude Code** (Lead Engineer / Architecture Owner). A contract is the binding interface
between backend and frontend for a stage: the exact API endpoints, request/response shapes, allowed
vs. forbidden fields, RBAC rules, and safety fields. Codex implements against the contract; Codex
does not change it.

## Layout

- `templates/` — reusable templates for each contract type.
- `<stage>/` — one folder per Step 66 sub-stage, containing the actual contract(s) for that stage.

## Rule

Frontend does not change backend contract — see
`docs/process/frontend-design-engineering-collaboration-protocol.md`. If the frontend needs a
different shape, that requires a new or updated contract from Claude Code, not an ad-hoc frontend
workaround.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
