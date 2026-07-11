# User Role Journey Map — DESIGN-66UI.1

> Owner: Claude Design. Baseline journeys under the **current flat nav**, then what changes for
> each role under each of the three proposed layouts. Full layout detail is in the three
> `layout-option-*.md` files; this file is the role-centric cross-cut.

## Role reference

Six product RBAC roles per `docs/product/operator-rbac-model.md` and
`docs/process/role-responsibility-matrix.md` (note: these are product-internal roles, distinct
from the development-team roles Zachary/ChatGPT/Claude Code/Codex/Claude Design).

### 1. Requester

- **Current journey:** find `Tasks` in a 27-item flat list → Create Task → wait → find their task
  again in `Task List` → open `Workroom` → answer Clarification if asked → check back later for
  Delivery (no Delivery Inbox yet).
- **Pain point today:** nothing in the nav signals "here is what's waiting on you" — the Requester
  must know to open a specific task to discover a Clarification is open.
- **What a good redesign fixes:** a personal "waiting on you" surface that does not require
  navigating into a specific task first.

### 2. PM / Engineering Lead

- **Current journey:** `Tasks` (team-wide) → `Task Detail` → `Workroom` → create/answer
  Clarifications → (future) `Delivery Inbox` → Accept/Reject/Request Changes/Re-run QA.
- **Pain point today:** no team-level "what needs my attention across all tasks" view; must open
  each task individually.
- **What a good redesign fixes:** a cross-task queue view (Clarifications awaiting reply,
  Deliveries awaiting review) rather than one-task-at-a-time.

### 3. Reviewer / Approver

- **Current journey:** no Approval Queue exists yet (66D); today this role has no dedicated
  landing page and would use `OperatorConsole.tsx` or `SafetyCenter.tsx` as a proxy.
- **What a good redesign fixes:** a real Approval Queue landing page (Category E) is a prerequisite
  regardless of which layout is chosen — this is a 66D dependency, not a 66UI.1 layout choice.

### 4. Platform Admin

- **Current journey:** everything — `Tasks`, `Safety Center`, all of Category H (Runtime,
  Identity, Secret, Security, Release Governance, Backup/DR, Production Readiness, Controlled
  Rollout), plus future `Settings/Roles`, `Settings/Integrations`.
- **Pain point today:** this role sees the *entire* 27-item flat nav with no way to distinguish
  "AI Agents Team Work product settings" from "platform DevOps governance instrumentation" — both
  categories are equally relevant to this role today, which is part of why Category H exists as a
  flat list rather than nested under something.
- **What a good redesign fixes:** grouping so Platform Admin can jump straight to either "Team Work
  governance" or "Platform DevOps governance" without scanning 27 items.

### 5. Agent Operator

- **Current journey:** `Operator Console`, `Agent Executions`, `Incidents`, and — once 66D ships —
  `DLQ/Retry`. Also uses `Workroom` and `Audit Evidence` when investigating a specific task's
  failure.
- **Pain point today:** operational items (retry candidates, overdue clarifications, incidents)
  are not unified into one action queue; this role currently jumps between 3–4 unrelated nav items
  to build a mental model of "what needs handling right now."
- **What a good redesign fixes:** a single Operator Action Center that aggregates DLQ, overdue
  clarifications, incidents, and approval-pending items (Category E) — this is the single biggest
  cross-role win identified in this pass.

### 6. Security / Compliance Reviewer

- **Current journey:** `Safety Center`, `Audit Evidence`, plus (arguably) `Identity Posture`,
  `Secret Posture`, `Security / Supply Chain` from Category H.
- **Pain point today:** this role's material is split across Category C (Team Work safety/audit)
  and Category H (platform security posture) with no indication they are related views of "is this
  system safe."
- **What a good redesign fixes:** depends on the Category H scope decision (see
  `feature-categorization.md` open questions) — if Category H stays separate, this role's journey
  necessarily spans two IA areas regardless of which layout wins.

## Cross-role finding

The single clearest, layout-independent finding: **Reviewer/Approver and Agent Operator both lack
a real landing page today** (Approval Queue, unified Operator Action Center) — this is a Step 66D
dependency that applies no matter which of the three layout options is chosen. The three options
differ in *where* that landing page sits and *how prominent* it is, not in *whether* it needs to
exist.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._
