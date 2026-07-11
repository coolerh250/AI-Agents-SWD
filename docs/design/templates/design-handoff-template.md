# Design Handoff Template

> Copy into `docs/handoffs/<stage>/design-to-engineering-handoff.md` (using
> `docs/handoffs/templates/design-to-engineering-handoff-template.md`) once this design is ready to
> hand to Claude Code / Codex. This file itself is the design-side checklist Claude Design fills in
> before that handoff. Owner: Claude Design.

## Stage

`<stage id>`

## Included artifacts

- [ ] Design brief (`design-brief.md`)
- [ ] Wireframe notes (`wireframe-notes.md`), if applicable
- [ ] Interaction flow(s) (`interaction-flow-*.md`)
- [ ] Component spec(s) (`component-spec-*.md`)

## Open questions for Claude Code

List anything that needs an API/contract decision before implementation can start.

## Constraints restated for the handoff

- Plain-text rendering only where applicable.
- Server-side RBAC only.
- No workflow dispatch/resume, no external action, no production action implied by this design.

## Ready for contract?

`yes` / `no` — if `no`, state what's blocking.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
