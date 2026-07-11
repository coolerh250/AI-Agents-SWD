# AI Agents Team Work — Agent Workroom Blueprint (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no workflow execution, no external
> action, no production action.**
> **Q3 confirmed: minimum-viable chat workroom scope (D9 full workroom in MVP).**

## 1. Minimum viable workroom (MVP — must include)

- task-level conversation thread
- agent clarification question
- human reply
- agent progress message
- system / audit event embedded timeline
- request-changes discussion
- delivery-review discussion
- pause / resume context
- role-based message visibility
- message-to-audit correlation id

## 2. Deferred workroom features (out of MVP)

rich file annotation · multi-room per-agent private channels · voice input · real-time typing
indicator · advanced threaded branching.

## 3. Message types (minimum)

| Type | Sender | Purpose | Visibility |
| --- | --- | --- | --- |
| `human_message` | human | free message | participants per RBAC |
| `agent_message` | agent | free agent message | participants |
| `clarification_question` | agent | blocking question (pauses task) | task owner + assignees |
| `clarification_answer` | human | answer → resume | participants |
| `system_event` | system | state changes (running, blocked…) | participants |
| `audit_event` | system | audit timeline embed (corr id) | participants + Sec/Compliance |
| `delivery_comment` | human | delivery-review discussion | review roles |
| `request_changes_note` | human | change request detail | participants |
| `qa_result_note` | system/agent | QA outcome summary | participants |
| `approval_request_note` | system | governed-action approval ask | approvers + admin |

## 4. Sender types & visibility

- Sender types: `human`, `agent`, `system`.
- **Visibility model:** role-based per message type (table above); Requester sees own-task messages;
  Sec/Compliance sees audit/evidence messages read-only; no secrets/tokens/raw payloads in any message
  (redaction).

## 5. Threads, correlation, retention, RBAC, notifications

- **Conversation threads:** one primary task thread; clarification and delivery-review are typed
  sub-discussions within it (advanced branching deferred).
- **Correlation id:** every message carries a `correlation_id` linking to the audit event / work-item
  event, so the workroom timeline and audit trail reconcile.
- **Retention:** messages retained with the task; audit-linked messages follow audit retention.
- **RBAC:** posting a `clarification_answer` / `delivery_comment` / `request_changes_note` requires the
  matching capability (see rbac blueprint).
- **Notification rules:** `clarification_question`, `approval_request_note`, `delivery_comment` trigger
  lifecycle notifications (Console P0 + Discord P1, D7); debounced; no sensitive data.

## 6. Current-state grounding

The platform records per-hop "discussion" today but has no operator-facing chat workroom; this is new
work in **66C**, reusing discussion records + a new `task_messages` store (see data-model blueprint).

## Step 66C.1 implementation status (2026-07-10)

**Backend data/API foundation implemented (66C.1)** — no UI. `task_messages` (migration
`030_workroom_clarification_foundation.sql`) implements the message model above with
`message_type`/`visibility`/`sender_type` exactly as specified; `correlation_id` ties workroom
messages to audit events (§5, unchanged). Only `human_message`, `clarification_question`, and
`clarification_answer` are actually produced by the API today (no agent connector, delivery flow,
or QA flow exists yet to emit `agent_message`/`system_event`/`delivery_comment`/etc.) — modeled, not
fabricated. Role-based message **visibility filtering** (§4) is **not yet implemented**: all messages
are created with `visibility: task_participants` and returned to any caller who can view the
workroom, regardless of role — a documented gap, not the full visibility model. Notification rules
(§5) are **not implemented** — no Console/Discord notification fires on any message type in 66C.1.
See `step66c1-workroom-clarification-api-foundation-report.md`.

## Step 66C.2 implementation status (2026-07-11)

**Admin Console Workroom UI implemented (66C.2)** — `/tasks/{id}/workroom`
(`apps/admin-console/src/pages/TaskWorkroom.tsx`), reached via an "Open Workroom" link from
`/tasks/{id}`. Renders messages and clarification questions/answers as **plain text only** (React
text interpolation, no raw-HTML rendering escape hatch) — satisfies the "no secrets/tokens/raw
payloads" redaction intent from §4 by construction, since nothing is ever interpreted as markup.
Message composer (human message) and clarification answer form are implemented. Role-based message
**visibility filtering** (§4) remains not implemented (carried over from 66C.1's gap G1, now
assigned to 66C.3) — the UI shows every message the API returns. Notification rules (§5) remain not
implemented.

## Step 66C.2-R implementation status (2026-07-11)

**Clarification creation UI added (remediation).** Operator validation of 66C.2 returned
`NOT_VISIBLE` — the initial deferral of `createClarification()` meant a typed question could only
ever become a normal message, never a clarification, so no answer form could appear. Fixed: a
**Create Clarification** form now lives in the Workroom's Clarifications section, calling the
pre-existing, unmodified `POST /tasks/{id}/clarifications` backend endpoint (Step 66C.1). The message
composer is relabeled "Send Message" with an inline note distinguishing it from "Create
Clarification" — a normal message is never silently converted into a clarification. See
`step66c2-remediation-report.md`.

## Step 66C.2-R-V operator validation (2026-07-11)

Operator confirmed **`VISIBLE`** against all 14 items in the Step 66C.2-R operator validation
request — Send Message stays a normal message, Create Clarification works, `clarification_needed`
transition, answer flow, `dispatch_enabled`/`resume_dispatch_enabled=false`, and plain-text
rendering were all validated. **Step 66C.2 final status: `PASS_AFTER_REMEDIATION`.** Step 66C.3 is
READY_TO_UNBLOCK. Project/team RBAC scoping (G4) remains a documented gap, deferred to 66S. See
`step66c2-remediation-operator-validation-record.md`.

## Step 66C.3 implementation status (2026-07-11)

**Workroom Audit / Visibility / Edge-case Hardening implemented.** Closes G1, G3, G5 from
Step 66C.1-V. Role-based message **visibility filtering** (§4) is now implemented server-side
(`shared/sdk/tasks/workroom_rbac.py::filter_messages_by_visibility`, enforced in
`GET /tasks/{id}/workroom`) — the enforced matrix is deliberately conservative and documented in
`step66c3-message-visibility-evidence.md` rather than an attempt to fully reproduce every cell of an
illustrative table. A new **`GET /tasks/{id}/audit-evidence`** endpoint provides task-scoped audit
evidence (safe metadata only, allowlisted, RBAC-gated) — the first "per-task audit lookup" surface
for this subsystem (§6 current-state grounding is updated: the platform now has more than
per-hop "discussion", it has both a chat workroom AND a safe audit-evidence view). The
answered-twice guard (previously a non-atomic pre-check) is now atomic at the store level, closing a
real race-condition gap. See `step66c3-workroom-audit-visibility-hardening-report.md`.

## Statement

Workroom blueprint only — no implementation, no workflow execution, no external action, no production
action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
