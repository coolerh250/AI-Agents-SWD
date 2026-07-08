# AI Agents Team Work — Operator Action Center Model (Step 66A.1)

> **Planning / discovery only. No UI implementation. No production action.**

A single operator surface that aggregates everything requiring human attention. This model explicitly
closes the Step 65 operator-flagged UX gaps.

## 1. Queues

| Queue | Source (backend today) | Step 65 gap addressed |
| --- | --- | --- |
| Pending approvals | approval-engine `/approval/*` | **#7 `/approvals` page (absent)** |
| Clarification requests | clarification thread (66C) | new |
| Delivery ready | Delivery Inbox (66D) | new |
| Request changes | acceptance gate (66D) | new |
| Failed workflows | orchestrator / incidents | partial (incidents exist) |
| DLQ / retry queue | retry-scheduler `/deadletter` + `/deadletter/replay/{id}` | **#6 DLQ/Retry page (operator-flagged, absent)** |
| Incidents | `/admin/incidents` (exists) | — |
| Blocked production-effect tasks | policy-engine `RESTRICTED_ACTIONS` | new surface |
| Integration health issues | `/operations/safety` + gateways | new surface |

## 2. Explicit Step 65 gap closure

- **#6 DLQ / Retry Admin Console page** — operator flagged in Step 65H.4 that DLQ indicators had **no
  admin page**. The Action Center provides a first-class **DLQ / Retry queue**: entries with reason
  class, retry count, and a **governed manual replay** action (agent-operator/admin only, audited),
  backed by the existing retry-scheduler APIs.
- **#7 `/approvals` page** — the Action Center provides a **Pending Approvals** queue backed by the
  existing approval-engine APIs, so approvals no longer require API-only interaction.

## 3. Per-queue item requirements

Each queue item shows: what needs attention, who can act (role), the governed action(s), a link-back
to the work item, and the audit trail. Actions honor the role model and emit audit + notification.

## 4. DLQ information purpose (for the operator)

The DLQ/Retry queue tells the manager **which tasks failed terminally and why** (reason class, retry
count, last error class — never secrets), so they can decide to **replay** (governed, audited) or
**abandon**. This is the surfacing the operator asked for in Step 65H.4.

## 5. Priority (decision item D8)

Recommendation (NON-FINAL): P0 = Pending Approvals + DLQ/Retry (close Step 65 gaps first) alongside
Delivery ready; P1 = clarification, failed workflows; P2 = integration health, blocked-production
surfaces. Final priority is **D8**.

## 6. Statement

No Action Center was implemented; no action was executed. No external action occurred. No production
action occurred. Priorities are recommendations pending D8.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
