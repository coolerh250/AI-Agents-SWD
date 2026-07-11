# Design Docs

> **Process documentation only. No backend/frontend runtime change. No production action.**

Owned by **Claude Design** (UI/UX Designer role — see
`docs/process/role-responsibility-matrix.md`). This directory holds design briefs, wireframe notes,
interaction flows, and component specs — specifications, not working code. Design does not equal
implementation; see `docs/process/frontend-design-engineering-collaboration-protocol.md`.

## Layout

- `templates/` — reusable templates for each design artifact type.
- `<stage>/` — one folder per Step 66 sub-stage (e.g. `66c3-workroom-audit-visibility/`), containing
  the actual design artifacts produced for that stage.

## Downstream

A design brief in this directory feeds `docs/contracts/<stage>/` (Claude Code writes the API/data
contract to match) and then `docs/frontend/<stage>/` (Codex implements against both). See
`docs/process/github-collaboration-hub.md` for the full data-exchange path.

## Masking rule

Do not include internal IP addresses, SSH aliases, private hostnames, real tokens, credentials,
private URLs, or environment secrets in docs, examples, screenshots, or validation evidence. Use
neutral labels such as "test host", "internal test runtime", "admin console local tunnel", "sandbox
repo".

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
