# Product Owner Decision Summary — DESIGN-66UI.1

> Owner: Claude Design. Records Zachary's (Product Owner/Operator) decision on the three layout
> options in this stage. This is the binding scope reference for any follow-on design brief,
> contract, or frontend work — supersedes the open checkboxes in
> `product-owner-discussion-guide.md` for this round.

## Selected direction: Hybrid

```text
Option 1 (Operations Command Center) → used for IA / Navigation
Option 2 (Task Workspace)            → used for the Task Workspace interaction model
Option 3 (Lifecycle Pipeline)        → deferred, read-only lifecycle view toggle only
```

## 1. Near-term priority

- **Product experience priority:** single-task collaboration depth (Workroom quality) — this is
  the product's stated differentiator and takes precedence over cross-task operational tooling in
  the experience itself.
- **Implementation sequencing priority:** despite the experience priority above, the *first* thing
  built is the overall IA/Navigation restructure (Option 1's grouped nav), not the Task Workspace
  merge — this is a deliberate decoupling of "what matters most to the user" from "what should be
  built first," because the nav restructure is lower-risk, has no 66D/66C.4 dependency, and is a
  prerequisite shell for the Task Workspace to live inside regardless.

## 2. Category H — Platform Operations & DevOps Governance

- **Included** in the overall IA as its own grouped nav section ("Platform Ops"), per all three
  layout options' existing treatment.
- **Round 1 scope is grouping only.** No individual Platform Ops page (Runtime Baseline, Identity/
  Secret/Security Posture, Release Governance, Backup/DR, Production Readiness, Controlled Rollout
  Review, Sandbox GitHub, Cost/LLM Governance, Regression, Task Graph, Design Review, Workspace
  Execution, Mini Delivery Pilot, Executive Overview, Projects) is redesigned, restructured, or
  otherwise changed in this round — they move under the "Platform Ops" nav group as-is.

## 3. DeliveryPackage vs. Delivery Inbox — not merged yet

- **DeliveryPackage** (`DeliveryPackage.tsx`, existing) remains, for now, the existing delivery
  evidence / package record surface — unchanged, not folded into anything new.
- **Delivery Inbox** (66D, planned) is the future human-acceptance entry point for task-linked
  deliveries.
- **Delivery Detail** (66D, planned) is the future delivery review workspace, and — per the Hybrid
  decision — is expected to live as a tab inside the Option 2 Task Workspace once built.
- **Integration between the two is explicitly deferred** until Claude Code's 66D API/data contract
  exists. No design or frontend work should assume or pre-build a merged model before that contract
  is published.

## 4. Lifecycle Pipeline / Kanban — deferred, read-only only

- Kept on the roadmap as a **future Task List view toggle**, not the app's landing surface (as
  originally sketched as one possibility in Option 3).
- **First version, if and when built, must be read-only.** The board may display a task's current
  lifecycle stage (Intake/Requirement/Development/QA/Delivery/Review) but must **not** allow
  dragging a card between columns, and must not imply that a manual stage transition is available
  through the UI.
- No design brief, contract, or frontend work should introduce drag-and-drop or any client-side
  stage-transition control for this view until the Product Owner explicitly revisits this decision.

## 5. Placeholder policy for not-yet-available areas

Any area of the redesigned IA that depends on a stage not yet built (66D Delivery Inbox/Detail,
Approval Queue, DLQ/Retry; 66C.4 Clarification Reminder/Expiry) may ship as a placeholder rather
than being held back entirely. Every such placeholder must clearly state, in plain text, all of the
following as applicable — not a generic "coming soon":

- **Not yet available.**
- **Requires Step 66D.** (for Delivery Inbox, Delivery Detail, Accept/Reject/Request Changes,
  Re-run QA, Approval Queue, DLQ/Retry)
- **Requires Step 66C.4.** (for Clarification reminder/overdue indicators, expiry state)
- **No workflow action available.** — reinforcing, in the placeholder itself, that nothing in the
  placeholder can trigger workflow dispatch, workflow resume, or any production/external action.

This placeholder policy applies uniformly across whichever layout element is affected (nav badge,
dashboard card, workspace tab, pipeline column) and must be included in any future design brief or
component spec that covers a not-yet-built area.

## Scope confirmation

- **No Codex implementation is authorized by this decision.** This document records product
  direction; a design brief for the actual implementation stage (e.g. `66ui.2-navigation-ia` or
  similar) is the next Claude Design deliverable, not a jump straight to frontend work.
- **No API/contract change is requested by this decision.** Claude Code's contract work is not
  triggered by this document; the Lifecycle Pipeline read-only constraint above is a UI-side
  commitment, not a request for a new endpoint.
- **No workflow dispatch, no workflow resume, no external action, no production action** implied
  or authorized by this decision.

## Statement

Design specification only. No runtime code. No production action. No API/contract decision. No
Codex implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
