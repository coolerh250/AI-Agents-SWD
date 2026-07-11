# Interaction Flow Template

> Copy into `docs/design/<stage>/interaction-flow.md` and fill in. Owner: Claude Design.

## Stage

`<stage id>`

## Flow name

`<e.g. "Create Clarification">`

## Trigger

What starts this flow (button click, page load, role change)?

## Steps

1. User action → system response
2. User action → system response
3. ...

## Success path

What does the user see when this flow completes successfully?

## Error / edge-case paths

- Validation error (client-side): what's shown?
- RBAC denial (server-side 403): what readable message is shown?
- Already-in-terminal-state / conflict (e.g. 409): what readable message is shown?
- Network/server error: what's shown?

## Role variations

Does this flow behave differently per RBAC role? List each variation.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
