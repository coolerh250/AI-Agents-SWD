# AI Agents Team Work — Task Lifecycle Model (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no workflow execution, no external
> action, no production action.**
> **Q2 confirmed: clarification timeout = 24h reminder, 72h blocked/expired, project-configurable,
> owner may extend once.**

## 1. Canonical states

| State | Entry condition | Allowed transitions | User label | Notification event | Audit event | Terminal |
| --- | --- | --- | --- | --- | --- | --- |
| `draft` | task being composed | submitted, canceled | Draft | — | task.draft_saved | no |
| `submitted` | requester submits | intake_review, canceled | Submitted | task submitted | task.submitted | no |
| `intake_review` | intake-agent picks up | clarification_needed, approved_for_execution, rejected | In intake review | task accepted by team | task.intake_started | no |
| `clarification_needed` | agent needs info | (answered→intake_review/running), clarification_expired, canceled | Needs your input | clarification needed | task.clarification_requested | no |
| `clarification_expired` | 72h no answer | (owner extend once→clarification_needed), blocked, canceled | Clarification expired | clarification expired | task.clarification_expired | no |
| `approved_for_execution` | intake complete / gate passed | running, waiting_approval | Approved to run | approval granted | task.approved_for_execution | no |
| `running` | team executing | waiting_approval, clarification_needed, delivery_ready, failed, blocked, canceled | In progress | agent started | task.running | no |
| `waiting_approval` | governed action hit | running, blocked, rejected | Waiting approval | approval required | task.waiting_approval | no |
| `blocked` | dependency/timeout/failure hold | running, failed, canceled | Blocked | task blocked | task.blocked | no |
| `failed` | unrecoverable / DLQ terminal | (replay→running), archived | Failed | task failed / DLQ created | task.failed | no |
| `delivery_ready` | package assembled | accepted, rejected, changes_requested, qa_rerun_requested, escalated, archived | Delivery ready | delivery ready | delivery.ready | no |
| `changes_requested` | Request Changes (small) | running | Changes requested | request changes submitted | delivery.changes_requested | no |
| `qa_rerun_requested` | Re-run QA (≤3) | running, delivery_ready | QA re-run | QA re-run started | delivery.qa_rerun | no |
| `accepted` | delivery accepted | archived | Accepted | task accepted / completed | delivery.accepted | **yes** |
| `rejected` | delivery/task rejected | archived | Rejected | task rejected | delivery.rejected | **yes** |
| `archived` | archived from any terminal/inbox | — | Archived | — | task.archived | **yes** |
| `canceled` | canceled before completion | — | Canceled | task canceled | task.canceled | **yes** |

Terminal states: `accepted`, `rejected`, `archived`, `canceled` (aligns with the platform's existing
`TERMINAL_STAGES`). Major-change Request Changes (D11) creates a **linked** workflow rather than
reopening the same one (see delivery-inbox blueprint).

## 2. Clarification timeout (Q2 / D4)

- On `clarification_needed`: notify human, wait.
- **24h:** send a reminder (still `clarification_needed`).
- **72h:** transition to `clarification_expired`.
- Timeout window is **project-level configurable**; the **task owner may manually extend once**
  (`clarification_expired` → `clarification_needed`), after which no further auto-extension.
- All reminders/extensions/expiries emit audit + notification events.

## 3. Statement

Task lifecycle model only. No implementation, no workflow execution, no external action, no production
action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
