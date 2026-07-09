# AI Agents Team Work — Delivery Inbox Blueprint (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no workflow execution, no external
> action, no production action.**
> **Q5 confirmed: Request Changes split criteria (small vs. major, D11).**

## 1. Delivery package structure

- delivery summary
- requirements summary
- implementation summary
- QA result
- GitHub draft PR link (sandbox rail; if applicable; no merge)
- LLM / cost usage (from budget/audit rail)
- audit trail
- risks & limitations
- recommended next action
- revision history

## 2. Acceptance-gate actions (D5)

| Action | Who (RBAC) | State transition | Workflow effect | Audit event | Notification | Limits |
| --- | --- | --- | --- | --- | --- | --- |
| **Accept** | PM / Lead / Reviewer / Admin | delivery_ready → accepted | closes task (terminal) | delivery.accepted | task accepted/completed | — |
| **Reject** | PM / Lead / Reviewer / Admin | delivery_ready → rejected | closes task (terminal) | delivery.rejected | task rejected | — |
| **Request Changes** | PM / Lead / Reviewer / Admin | small→changes_requested→running; major→linked workflow | reopen (small) or new linked workflow (major) | delivery.changes_requested | request changes submitted | classified small/major (§3) |
| **Re-run QA** | PM / Lead / Reviewer | delivery_ready → qa_rerun_requested → running | re-invoke qa-agent | delivery.qa_rerun | QA re-run started | **max 3 per delivery (D12)** |
| **Escalate** | any review role | delivery_ready → escalated | route to Action Center | delivery.escalated | escalation raised | — |
| **Archive** | PM / Admin | terminal → archived | remove from active inbox | delivery.archived | — | — |

## 3. Request Changes classification (Q5 / D11)

- **Small change → same work item / same delivery revision cycle** if it: does **not** change the
  original objective; does **not** add a major feature; does **not** alter the data model; does **not**
  affect security / permissions / deployment; does **not** require re-estimation.
- **Major change → linked workflow** if it: adds a major feature; changes scope; changes the data
  model; changes security / permissions; affects deployment; requires re-estimation; or requires new
  approval.
- The classification is recorded on the Request-Changes action (auditable); ambiguous cases default to
  **major** (safer) and may require reviewer confirmation.

## 4. Current-state grounding

Backend produces requirement/implementation/QA records + sandbox draft PRs today; there is no Delivery
Inbox / detail page / first-class action model — new work in **66D**.

## Statement

Delivery Inbox + acceptance gate blueprint only — no implementation, no workflow execution, no
external action, no production action.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
