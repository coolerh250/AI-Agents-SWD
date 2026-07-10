# AI Agents Team Work — RBAC Blueprint (Step 66A.3)

> **Blueprint / scope only. No implementation, no runtime change, no external action, no production action.**
> **Q1 confirmed: this is the final MVP role→capability matrix (D1 Conservative RBAC).**

## 1. Roles (final, D1)

Requester · PM / Engineering Lead · Reviewer / Approver · Platform Admin · Agent Operator ·
Security / Compliance Reviewer.

## 2. Role capabilities (final)

- **Requester:** create task, supplement requirements, view own tasks, reply to clarification.
- **PM / Engineering Lead:** review delivery, accept, reject, request changes, re-run QA (within
  limits).
- **Reviewer / Approver:** approve / reject gated actions, review risk + delivery evidence.
- **Platform Admin:** manage integrations, manage RBAC, manage system settings, manage approval policy.
- **Agent Operator:** retry, manual replay, DLQ operation, incident operation.
- **Security / Compliance Reviewer:** view audit evidence, view risk/security evidence, review
  compliance trail; **no direct workflow execution by default**.

## 3. Capability → role matrix (MVP default)

| Capability | Requester | PM / Eng Lead | Reviewer / Approver | Platform Admin | Agent Operator | Sec / Compliance |
| --- | --- | --- | --- | --- | --- | --- |
| Create task | ✔ | ✔ | ✖ | ✔ | ✖ | ✖ |
| Supplement requirements | ✔ (own) | ✔ | ✖ | ✔ | ✖ | ✖ |
| Reply to clarification | ✔ (own) | ✔ | ✔ | ✔ | ✔ | ✖ |
| View task / workroom | ✔ (own) | ✔ | ✔ | ✔ | ✔ | ✔ (audit view) |
| Review delivery | ✖ | ✔ | ✔ | ✔ | ✖ | ✔ (evidence) |
| Accept / Reject delivery | ✖ | ✔ | ✔ | ✔ | ✖ | ✖ |
| Request Changes | ✖ | ✔ | ✔ | ✔ | ✖ | ✖ |
| Re-run QA (≤3) | ✖ | ✔ | ✔ | ✔ | ✖ | ✖ |
| Approve / reject gated action | ✖ | ✖ | ✔ | ✔ | ✖ | ✖ |
| Retry / manual DLQ replay | ✖ | ✖ | ✖ | ✔ | ✔ | ✖ |
| Incident operation | ✖ | ✖ | ✖ | ✔ | ✔ | ✖ |
| Manage integrations / RBAC / settings / approval policy | ✖ | ✖ | ✖ | ✔ | ✖ | ✖ |
| Manage web-research sources | ✖ | ✖ | ✖ | ✔ | ✖ | ✔ (review) |
| View audit / compliance trail | ✔ (own) | ✔ | ✔ | ✔ | ✔ | ✔ |

Legend: ✔ allowed · ✖ denied · (own) scoped to own tasks.

## 4. Enforcement & audit model

- Every privileged action is checked **role → capability** server-side; UI hides disallowed actions but
  the server is the authority.
- Channel identity (Console session / API token / Slack / Discord / Telegram) maps to a platform role
  **before** any privileged action; unmapped = Requester-level or rejected.
- Retry/replay (D13) and Re-run-QA limit (D12) enforced server-side.
- Every action emits an **audit event** with actor role, capability, target, timestamp, correlation id.
- `production_executed_true_count=0` invariant preserved; no RBAC path enables production effect.

## 5. Statement

Security & RBAC model only — no implementation, no runtime change, no external action, no production
action. The MVP matrix is the operator-confirmed default (Q1).

## 6. Step 66B.1/66B.3 enforcement status (implemented subset — do not overclaim)

The Task API (66B.1, hardened in 66B.3) implements only the **create / view / submit** capabilities
of the matrix above — the rest of the matrix (review delivery, accept/reject/request-changes,
re-run QA, approve/reject gated action, retry/replay, incident operation, manage integrations/RBAC/
settings, web-research source management) is **not yet implemented**; it is deferred to 66C+ stages
per `ai-team-work-step66-implementation-sequence.md`.

Exact enforced behavior for the implemented subset (`shared/sdk/tasks/rbac.py`,
`apps/orchestrator/src/task_api.py`):

| Capability | requester | pm_engineering_lead | reviewer_approver | platform_admin | agent_operator | security_compliance_reviewer |
| --- | --- | --- | --- | --- | --- | --- |
| Create task | ✔ | ✔ | ✖ | ✔ | ✖ | ✖ |
| View task (own only for Requester; all others unscoped) | ✔ (own) | ✔ (all) | ✔ (all) | ✔ (all) | ✔ (all) | ✔ (all) |
| Submit task (own only for Requester) | ✔ (own) | ✔ | ✖ | ✔ | ✖ | ✖ |

- Denied role → `403 role_cannot_create_task` / `role_cannot_view_tasks` / `role_cannot_submit_task`.
- Requester targeting another actor's task (view or submit) → `403 not_own_task`.
- Every denial (Step 66B.3) is audited as `task_rbac_denied` — see
  `step66b3-audit-evidence-record.md`.
- `role_cannot_view_tasks` has no live trigger today (all six roles are view-allowed) — the code
  path exists for forward-compatibility only (documented in `step66b3-known-gaps.md`, not a gap in
  the current matrix).

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
