---
name: Operator validation task
about: Track an operator validation request awaiting Zachary's response
title: "[operator-validation] "
labels: operator-validation
---

## Stage

<!-- e.g. 66d-delivery-inbox -->

## Owner role

Zachary (Operator) — only Zachary may close this issue with a verdict.

## Scope

<!-- What was deployed and needs validation. Link to
docs/test/<stage>-operator-validation-request.md -->

## Out of scope

Claude Code, Codex, and Claude Design must not decide final product acceptance on this issue — see
`docs/process/operator-validation-standard.md`.

## Safety statement

No workflow dispatch. No workflow resume. No external action. No production action.

## Test evidence

<!-- Link to the implementation report(s) this validation covers -->

## Known gaps

<!-- Carried from the implementation report -->

## Operator validation needed

`yes` — this issue tracks it. Required response: `VISIBLE` / `NOT_VISIBLE` / `PARTIAL_WITH_GAPS`.

<!--
Masking rule: do not include internal IP addresses, SSH aliases, private hostnames, real tokens,
credentials, private URLs, or environment secrets in this issue, its comments, or attached
screenshots. Use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo".
-->
