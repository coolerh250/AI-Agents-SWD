# AI Agents Team Work — Final UX Blueprint (Step 66A.3)

> **Blueprint / scope only. No UI implementation. No backend implementation. No runtime change. No
> workflow execution. No external action. No production action.**
> **Locks the MVP UX from the operator's D1–D14 decisions and Q1–Q5 confirmations.**

The authoritative MVP blueprint for **AI Agents Team Work** — a manager assigns work to an AI agent
team, interacts with agents in a workroom, and reviews/accepts delivery — built on the Step
65-validated platform layer. This is the umbrella; each area has a dedicated sub-blueprint.

## 1. Product vision

A multi-role team can operate an AI agent team like a real delivery team: **assign** a task from the
Admin Console/API, **watch and converse** with the fixed Software Delivery Team in a chat-style
workroom, **answer clarifications**, and **review + Accept / Reject / Request Changes / Re-run QA** a
packaged delivery — with approvals, DLQ/Retry, notifications, audit, and governed (whitelisted) web
research, all under RBAC and with `production_executed_true_count=0`.

## 2. Operator decisions reflected (D1–D14)

D1=Conservative RBAC · D2=software/docs/platform · D3=Console+API→Discord→Slack→Telegram ·
D4=reminder→blocked/expired (24h/72h, project-config, owner extend once) · D5=Accept/Reject/Request
Changes/Re-run QA/Escalate/Archive · D6=fixed team, others→intake/planning · D7=Console P0 + Discord
P1 · D8=Approvals + DLQ/Retry both P0 · D9=full chat workroom in MVP · D10=whitelist-only (v0.1) ·
D11=small→same / major→linked workflow · D12=PM/Lead/Reviewer, max 3 QA re-runs · D13=Admin/Agent-Op
only replay · D14=task-type selection, non-software→intake/planning first. Source of record:
`ai-team-work-operator-decision-record.md`.

## 3. Q1–Q5 operator confirmations reflected

The five open items from 66A.2 are now confirmed by the operator and locked into this blueprint:

| Q | Open item (from 66A.2) | Confirmed answer | Where in blueprint |
| --- | --- | --- | --- |
| **Q1** | D1 exact permission matrix | Final role→capability matrix (6 roles) | `ai-team-work-rbac-blueprint.md` |
| **Q2** | D4 timeout-config surface | 24h reminder, 72h blocked/expired, **project-level configurable**, **owner may extend once** | `ai-team-work-task-lifecycle-model.md` |
| **Q3** | D9 minimum-viable workroom boundary | MVP must-include set + deferred set | `ai-team-work-agent-workroom-blueprint.md` |
| **Q4** | D10 whitelist confirmation + connector | Approved **whitelist v0.1** (10 sources); connector still **not implemented/authorized** | `ai-team-work-web-research-governance-blueprint.md` |
| **Q5** | D11 change-classification criteria | Small vs. major change criteria defined | `ai-team-work-delivery-inbox-blueprint.md` |

## 4. Blueprint index (the 23 required areas)

| # | Area | Doc |
| --- | --- | --- |
| 1 | Product vision | this doc §1 |
| 2 | Roles & permission model | `ai-team-work-rbac-blueprint.md` |
| 3 | Task lifecycle | `ai-team-work-task-lifecycle-model.md` |
| 4 | Intake UX | `ai-team-work-frontend-page-map.md` (/tasks/new) |
| 5 | Agent Workroom UX | `ai-team-work-agent-workroom-blueprint.md` |
| 6 | Clarification flow | `ai-team-work-task-lifecycle-model.md` + workroom blueprint |
| 7 | Delivery Inbox UX | `ai-team-work-delivery-inbox-blueprint.md` |
| 8 | Acceptance gate | `ai-team-work-delivery-inbox-blueprint.md` |
| 9 | Operator Action Center | `ai-team-work-operator-action-center-blueprint.md` |
| 10 | Approvals UI | operator-action-center blueprint (Approvals queue, P0) |
| 11 | DLQ / Retry UI | operator-action-center blueprint (DLQ/Retry queue, P0) |
| 12 | Lifecycle notification model | `ai-team-work-lifecycle-notification-model.md` (66A.1, D7 recorded) |
| 13 | Web research governed capability | `ai-team-work-web-research-governance-blueprint.md` |
| 14 | Data model additions | `ai-team-work-data-model-blueprint.md` |
| 15 | API additions | `ai-team-work-api-blueprint.md` |
| 16 | Frontend page map | `ai-team-work-frontend-page-map.md` |
| 17 | Backend service changes | `ai-team-work-mvp-implementation-scope.md` + sequence |
| 18 | Audit & evidence model | rbac + workroom + action-center blueprints (audit sections) |
| 19 | Security & RBAC model | `ai-team-work-rbac-blueprint.md` |
| 20 | Implementation sequencing 66B–66H | `ai-team-work-step66-implementation-sequence.md` |
| 21 | Acceptance criteria | `ai-team-work-acceptance-criteria.md` |
| 22 | Testing strategy | `ai-team-work-mvp-implementation-scope.md` + per-stage |
| 23 | Risks & non-goals | `ai-team-work-risk-register.md` + scope doc out-of-scope |

## 5. End-to-end MVP journey (blueprint)

```
Requester/PM  →  /tasks/new (task-type select, D14)  →  task submitted
      → intake_review → (clarification_needed? → Workroom Q → human reply → resume)
      → approved_for_execution → Fixed Software Delivery Team runs (intake→…→devops)
      → Workroom shows progress + audit timeline (D9)
      → delivery_ready → /deliveries/{id} package
      → PM/Lead/Reviewer: Accept / Reject / Request Changes(small→same, major→linked) /
        Re-run QA(≤3) / Escalate / Archive (D5, D11, D12)
Operator Action Center: Approvals (P0), DLQ/Retry (P0, Admin/Agent-Op only), Incidents, queues (D8, D13)
Notifications: Admin Console center (P0) + Discord (P1) (D7)
Web research: whitelist-only, pending connector (D10) — not executed in MVP
```

## 6. Posture

66A.3 is blueprint/scope only. No UI implementation occurred. No backend implementation occurred. No
runtime behavior changed. No workflow was executed. No external action occurred. No production action
occurred. The operator — not Claude Code — decides product acceptance.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
