# RBAC Error Contract Template

> Copy into `docs/contracts/<stage>/rbac-error-contract.md` and fill in. Owner: Claude Code.

## Stage

`<stage id>`

## RBAC-relevant endpoints

For each endpoint with role restrictions, list allowed roles and denied roles explicitly (do not
just say "role-checked" — name the roles), matching the existing convention in
`shared/sdk/tasks/*_rbac.py`.

| Endpoint | Allowed roles | Denied roles | Denial status code | Denial detail code |
| --- | --- | --- | --- | --- |
| | | | | |

## Readable error mapping

The frontend must map each `detail` code to a readable message (see `workroomClient.ts`'s
`READABLE_ERRORS` for the established pattern) — list the mapping here so Codex implements the same
messages Claude Code expects.

| `detail` code | Readable message |
| --- | --- |
| | |

## Enforcement

State explicitly: **RBAC is server-enforced only.** The frontend may pre-emptively hide an action for
UX polish, but must never rely on client-side hiding as the actual access control — the server must
independently reject a disallowed request regardless of what the UI shows.

## Statement

Contract specification only. No runtime code change implied by this document alone. No production
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
