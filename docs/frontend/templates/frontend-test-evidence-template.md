# Frontend Test Evidence Template

> Copy into `docs/frontend/<stage>/test-evidence.md` and fill in. Owner: Codex.

## Stage

`<stage id>`

## Test file(s)

List the vitest file(s) added/changed, and the test count (before → after).

## Coverage summary

- RBAC allow/deny cases covered:
- Safety fields (`dispatch_enabled`/`resume_dispatch_enabled`) asserted:
- Plain-text rendering / no-`dangerouslySetInnerHTML` guard:
- New error-code readable-message cases covered:

## `npm test` result

Paste the summary line (files/tests passed).

## `npm run build` result

Confirm success, module count, no TypeScript errors.

## Statement

Test evidence only. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
