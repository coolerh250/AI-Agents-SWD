# Design Objective — DESIGN-66UI.1 Full UI/UX Redesign Options

> Owner: Claude Design. **Strategy/IA only — no runtime code, no final pick, no Codex work
> authorized by this document.**

## Stage

`66ui-full-redesign-options` (DESIGN-66UI.1)

## Problem

The Admin Console navigation (`apps/admin-console/src/components/Nav.tsx`) is currently a **flat
list of 27 route links** with no grouping, hierarchy, or role-based emphasis — everything from
`Executive Overview` to `Tasks` to `Controlled Rollout Review` sits at the same level. This was
adequate while pages were added incrementally (Steps 50–66C), but it no longer reflects the
product's actual mental model, and it does not scale as Step 66D–66S add Delivery Inbox,
Approvals, DLQ/Retry, Notifications, and Project/Team RBAC.

Separately, the Step 66 "AI Agents Team Work" human-in-the-loop workflow (Task → Workroom →
Clarification → Delivery → Approval) is conceptually distinct from the pre-existing "Operations
Platform" surface (Steps 50–64: Runtime Baseline, Identity/Secret/Security Posture, Release
Governance, Backup/DR, Production Readiness, Controlled Rollout Review, Sandbox GitHub, Cost/LLM,
Regression, Operational Metrics, Multi-project Delivery, Task Graph, Design Review, Workspace
Execution, Mini Delivery Pilot, Executive Overview, Projects). Both are real, both are live in the
same app, and neither has an agreed home in a single information architecture yet.

## Goals

- Reclassify all currently implemented and near-term-planned capabilities into a small number of
  named categories (Section 3 of the stage prompt).
- Produce three genuinely different top-level layout concepts for the Admin Console, each fully
  specified (nav structure, dashboard behavior, placement of Task/Workroom, Audit/Safety,
  Delivery/Review, Operator Center, pros/cons, risk, ASCII sketch).
- Make explicit, for every option, how the mandatory safety states are always visible:
  `dispatch_enabled=false`, `resume_dispatch_enabled=false`,
  `production_executed_true_count=0`, `production_effect` warnings, external-action-disabled,
  approval-required, RBAC-denied, audit-restricted.
- Give the Product Owner (Zachary) a real choice — Option 1 / Option 2 / Option 3 / Hybrid / need
  another round — with enough detail to choose without seeing a prototype first.
- Identify what current UI can be reused vs. reset, and what this implies for Codex's future phased
  implementation and for Claude Code's contract work.

## Non-goals

- Not producing final, high-fidelity design.
- Not deciding which option ships.
- Not writing or modifying any runtime code (`apps/admin-console/src/**`).
- Not deciding or changing API/backend behavior — that remains Claude Code's contract work,
  triggered only after an option is chosen.
- Not instructing Codex to start implementation.
- Not re-designing the pre-existing Operations Platform pages (Steps 50–64) in detail — see
  "Scope boundary" below.

## Product mental model

AI Agents Team Work is not a chatbot and not a plain ticket tracker. The correct mental model:

```text
AI Agents Team = a virtual team the user assigns work to, that reports back, asks questions,
produces deliverables, and must remain governable, auditable, and safe by default.
```

The interface must let a human, at a glance, answer:

```text
What is the AI team doing right now?
Where is it blocked?
What does it need from me?
What did it deliver?
What can I approve?
What will NOT happen automatically?
```

This mental model applies uniformly across all three layout options in this document — the
options differ in navigation/layout structure, not in this underlying model.

## Target roles / personas

All six product RBAC roles are in scope for this stage (see
`docs/product/operator-rbac-model.md` for the authoritative role/permission definitions):
Requester, PM / Engineering Lead, Reviewer / Approver, Platform Admin, Agent Operator,
Security / Compliance Reviewer. See `user-role-journey-map.md` for how each role's primary journey
plays out under the current (unstructured) navigation versus the three proposed layouts.

## Scope boundary — a finding, not an assumption

The stage prompt's Category A–G taxonomy (Task & Intake, Workroom & Collaboration,
Audit/Safety/Governance, Delivery & Review, Operator Center, Platform Settings, Metrics/Dashboard)
maps cleanly onto the **Step 66 AI Agents Team Work layer**. It does **not** mention the ~20 pages
that already exist under Steps 50–64 (Runtime Baseline, Identity Posture, Secret Posture,
Security/Supply Chain, Release Governance, Backup/Restore/DR, Production Readiness Gate,
Controlled Rollout Review, Sandbox GitHub Draft PR, Cost/LLM Governance, Regression, Operational
Metrics, Task Graph, Design Review, Workspace Execution, Mini Delivery Pilot, Executive Overview,
Projects).

This document treats that existing surface as **Category H — Platform Operations & DevOps
Governance (pre-existing, legacy)** and places it consistently across all three options as a
secondary/collapsed area rather than redesigning its internals. Whether Category H should be
folded into "Operator Center", kept as its own top-level section, or left entirely alone for a
future stage is flagged as an open question for the Product Owner — see
`product-owner-discussion-guide.md`.

## Constraints

- Plain-text rendering only for any user/agent-authored content (no `dangerouslySetInnerHTML`, no
  markdown-to-HTML, no URL auto-linking) — unchanged from existing constraint.
- Server-side RBAC only — no client-side-only access control implied by any layout.
- No layout may visually suggest that workflow dispatch, workflow resume, or any external/
  production action is currently enabled.
- No internal IP, SSH alias, private hostname, token, secret, or environment identifier appears
  anywhere in this document set — neutral labels only ("test host", "internal test runtime",
  "sandbox repo").

## Open questions

See `product-owner-discussion-guide.md` for the full list; the single highest-impact question is
the Category H scope boundary above.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
