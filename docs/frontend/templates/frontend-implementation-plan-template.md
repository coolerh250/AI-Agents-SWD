# Frontend Implementation Plan Template

> Copy into `docs/frontend/<stage>/implementation-plan.md` and fill in. Owner: Codex.

## Stage

`<stage id>`

## Inputs consumed

- Design brief: `docs/design/<stage>/design-brief.md`
- Contract: `docs/contracts/<stage>/frontend-contract.md`

## Components to add/change

List each component, its route (if a page), and which contract fields it consumes.

## API client changes

Which methods will be added to the relevant `src/tasks/*Client.ts` (or equivalent) module. Named
methods only — no generic `request(method, url)` helper (see the existing
`taskApiGuard.test.ts`/`readOnlyGuard.test.ts` architecture convention).

## Tests planned

List the test cases you intend to write, mapped to the contract's stated behaviors (RBAC allow/deny,
safety fields, plain-text rendering, any new error codes).

## Out of scope

Explicitly list anything this plan does not cover (defer to a future stage or to Claude Code if it
turns out to require a backend change).

## Statement

Implementation plan only at this point — no code shipped by this document alone. No production
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
