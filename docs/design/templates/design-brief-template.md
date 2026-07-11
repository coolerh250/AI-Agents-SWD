# Design Brief Template

> Copy into `docs/design/<stage>/design-brief.md` and fill in. Owner: Claude Design.

## Stage

`<stage id, e.g. 66d-delivery-inbox>`

## Problem

What operator/user problem is this solving? What triggered this (product direction, gap, feedback)?

## Goals

- Goal 1
- Goal 2

## Non-goals

What this brief explicitly does not cover.

## Target roles / personas

Which of the six product RBAC roles (Requester, PM/Eng Lead, Reviewer/Approver, Platform Admin,
Agent Operator, Security/Compliance Reviewer) does this affect, and how?

## Constraints

- Plain-text rendering only where user/agent content is displayed (no `dangerouslySetInnerHTML`, no
  markdown-to-HTML, no URL auto-linking) unless separately reviewed.
- Server-side RBAC only — no client-side-only access control.
- No workflow dispatch/resume implied by any interaction in this brief.
- No production action implied.

## Open questions

Anything Claude Design needs from ChatGPT/Zachary before proceeding.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
