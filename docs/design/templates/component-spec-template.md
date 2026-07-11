# Component Spec Template

> Copy into `docs/design/<stage>/component-spec-<name>.md` and fill in. Owner: Claude Design.

## Stage

`<stage id>`

## Component

`<component name, e.g. AuditEvidenceSection>`

## Purpose

One or two sentences.

## Props / inputs

What data does this component need? Reference the contract field names from
`docs/contracts/<stage>/frontend-contract.md` where applicable.

## States

- Loading
- Empty
- Error
- RBAC-denied / restricted
- Success (with data)

## Rendering rules

- Plain-text rendering only for any user/agent-provided content — no `dangerouslySetInnerHTML`, no
  markdown-to-HTML, no URL auto-linking, unless separately reviewed and stated otherwise here.
- List every field that must be treated as opaque text.

## Accessibility notes

Keyboard navigation, labels, focus order, if relevant.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
