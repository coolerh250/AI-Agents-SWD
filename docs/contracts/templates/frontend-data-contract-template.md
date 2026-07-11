# Frontend Data Contract Template

> Copy into `docs/contracts/<stage>/data-contract.md` and fill in. Owner: Claude Code.

## Stage

`<stage id>`

## Data shape(s)

For each object the frontend receives:

### `<TypeName>`

| Field | Type | Always present? | Notes |
| --- | --- | --- | --- |
| | | | |

## Allowed fields

List explicitly. Anything not listed here that appears in a real response should be treated as
implementation detail, not part of the contract — do not build frontend logic that silently depends
on an undocumented field.

## Forbidden fields

Fields that must **never** appear in this data shape (raw bodies, headers, cookies, tokens, secrets,
`.env` values, raw full payloads) — restate explicitly even if "obviously" true, so a reviewer can
grep for a violation.

## Statement

Contract specification only. No runtime code change implied by this document alone. No production
action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
