# AI Agents Team Work — Risk Register (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no external action, no production action.**

| # | Risk | Impact | Likelihood | Mitigation | Owner | Stage to address |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Chat-style workroom complexity | high | high | ship minimum-viable workroom first (Q3); defer voice/branching/rooms | Eng Lead | 66C |
| 2 | RBAC overreach / underreach | high | med | central server-side capability checks; matrix tests per role | Platform Admin | 66B–66D |
| 3 | Web research connector missing | med | high | design-only in MVP; connector built + authorized before any research | Platform Admin | future |
| 4 | Source whitelist maintenance | med | med | source approval workflow; Admin manage + Sec review; audit | Sec/Compliance | future |
| 5 | Request Changes classification ambiguity | med | med | crisp small/major criteria (Q5); default to major; reviewer confirm | PM/Eng Lead | 66D |
| 6 | Notification overload | med | med | debounce/rate-limit; per-role routing; Console P0 + Discord P1 | Platform Admin | 66G |
| 7 | DLQ replay safety | high | med | replay Admin/Agent-Op only (D13); audited; reason-class only | Agent Operator | 66D |
| 8 | Approval UI safety | high | med | server-enforced approver role; policy context shown; audited | Reviewer/Admin | 66D |
| 9 | Non-software task scope creep | med | med | hold D6/D14 boundary: non-software → intake/planning first | PM | 66E |
| 10 | Delivery acceptance semantics | med | med | explicit state transitions + limits (Re-run-QA ≤3); audit each | PM/Eng Lead | 66D |

## Non-goals (MVP)

Custom / AI-suggested team composition; specialized non-software pipelines; unrestricted browsing;
unapproved web sources; Telegram/Slack as P0; production deployment / secret handling / production
effect; automatic external writes without approval.

## Required operator controls

RBAC sign-off (Q1); whitelist confirmation + connector authorization (Q4); per-stage authorization +
operator validation; operator decides product acceptance (not Claude Code).

## Statement

Risk register only — no implementation, no runtime change, no external action, no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
