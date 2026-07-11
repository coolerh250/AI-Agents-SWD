# Wireframe Notes Template

> Copy into `docs/design/<stage>/wireframe-notes.md` and fill in. Owner: Claude Design.

## Stage

`<stage id>`

## Screens / views

List each screen or view this stage introduces or changes, with a short description of its purpose
and its route (e.g. `/tasks/{id}/workroom`).

### `<screen name>`

- Purpose:
- Route:
- Key elements (list, not pixel-level):
- States: loading / empty / error / RBAC-denied / success

## Layout notes

Structural notes only (regions, hierarchy, responsive behavior) — not a pixel-perfect mockup unless
one is attached separately (link it here if so).

## Data displayed

What fields/values does each screen show, and where do they come from (which API field)? Flag
anything that must never be rendered as HTML/markup.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
