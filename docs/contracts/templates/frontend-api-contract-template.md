# Frontend API Contract Template

> Copy into `docs/contracts/<stage>/frontend-contract.md` (or a more specific name) and fill in.
> Owner: Claude Code.

## Stage

`<stage id>`

## Endpoints

For each endpoint the frontend will call:

### `<METHOD> <path>`

- Purpose:
- Required role(s):
- Request shape:
- Response shape:
- Safety fields present: `dispatch_enabled` / `resume_dispatch_enabled` — expected always `false`
  unless explicitly stated otherwise (should never be otherwise in this project's current scope).
- Audit event(s) emitted:

## Auth

How the frontend authenticates to these endpoints (reuse the existing fail-closed test-only header
mechanism unless this stage explicitly changes it — changing it requires a 66S-scope decision).

## Statement

Contract specification only. No runtime code change implied by this document alone. No production
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
