# Handoff Docs

> **Process documentation only. No backend/frontend runtime change. No production action.**

Tracks the four handoff points in the collaboration flow (see
`docs/process/frontend-design-engineering-collaboration-protocol.md`):

1. **Design → Engineering** — Claude Design hands a completed design brief/flow/component spec to
   Claude Code.
2. **Contract → Frontend** — Claude Code hands a completed contract to Codex.
3. **Frontend → Integration** — Codex hands completed, tested frontend work to Claude Code for
   review/integration/deployment.
4. **Operator validation** — Claude Code hands a deployed feature to Zachary for the final verdict.

## Layout

- `templates/` — one template per handoff point.
- `<stage>/handoff-index.md` — the stage's running index of which handoffs have occurred and when.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
