# AI Agents Team Work — Delivery Inbox & Acceptance Gate Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No workflow execution. No production action.**

Operator decision **D5: after delivery the manager can Accept / Reject / Request Changes / Re-run QA**
(plus Escalate to human, Archive). This model defines the Delivery Inbox, the delivery package, and
the acceptance-gate action semantics.

## 1. Delivery Inbox

A manager-facing list of agent deliverables to review and act on. Each row: task, team, status,
delivered-at, risk flag, pending-action.

## 2. Delivery detail page — package contents

- Requirement summary
- Implementation summary
- QA result
- GitHub **draft** PR link (sandbox rail; no merge)
- LLM / cost usage (from budget/audit rail)
- Audit trail
- Known risks
- Recommended next action

## 3. Acceptance-gate actions

| Action | State transition | Required role (default) | Audit event | Notification | Effect on workflow | Triggers new agent work? |
| --- | --- | --- | --- | --- | --- | --- |
| **Accept** | `delivered → accepted` | PM / Eng lead / Reviewer / owner | `delivery.accepted` | task accepted / completed | closes task (terminal) | no |
| **Reject** | `delivered → rejected` | PM / Eng lead / Reviewer / owner | `delivery.rejected` | task rejected | closes task (terminal) | no |
| **Request Changes** | `delivered → changes_requested → running` | PM / Eng lead / Reviewer / owner | `delivery.changes_requested` | request changes submitted | re-opens task | **yes** (decision D11: same vs new workflow) |
| **Re-run QA** | `delivered → qa_rerun` | Eng lead / Reviewer / agent operator / owner | `delivery.qa_rerun` | QA re-run started | re-invokes qa-agent | **yes** (decision D12: limits) |
| **Escalate to human** | `delivered → escalated` | any reviewer role | `delivery.escalated` | escalation raised | routes to Action Center | no (human decides) |
| **Archive** | any terminal → `archived` | PM / owner | `delivery.archived` | none/low | removes from active inbox | no |

## 4. Open decisions

- **D11 — Request Changes behavior:** same workflow (resume with feedback) vs. new workflow (fresh
  task linked to original). Recommendation (NON-FINAL): **same workflow with a change-request note**
  for MVP; new-workflow option later.
- **D12 — Re-run QA limits:** max re-runs per task, who pays cost, cooldown. Recommendation
  (NON-FINAL): cap re-runs (e.g. ≤3), agent-operator/eng-lead only, audit each.
- **D5 — full state-transition table** confirmation is an operator decision.

## 5. Current state (honest)

- Backend produces requirement/implementation/QA records + sandbox draft PRs today, but there is **no
  Delivery Inbox, no delivery detail page, and no first-class Accept/Reject/Request-Changes/Re-run-QA
  action model** surfaced to a manager. This is new work in **66D**.

## 6. Statement

No delivery action was executed and no workflow ran. No external action occurred. No production action
occurred. State transitions and limits are recommendations pending operator decisions (D5, D11, D12).

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
