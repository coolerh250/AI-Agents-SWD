# AI Agents Team Work — Current Gap Analysis (Step 66A.1)

> **Planning / discovery only. No UI implementation. No workflow execution. No external action. No production action.**

Maps the target AI Agents Team Work experience against **what the platform actually has today** after
Step 65, so Step 66 builds on real capabilities and does not re-invent backend that already exists.

## 1. What exists today (backend / platform — from Step 65)

| Capability | Status | Surface today |
| --- | --- | --- |
| 5-agent delivery pipeline (intake→requirement→development→qa→devops) | **exists** | Redis streams; each hop records agent_execution + audit + discussion |
| Extra agent services (project-planner, design-review, delivery-package, mini-delivery-pilot, workspace-operator) | **exists (services)** | present in test compose; not all in default profile |
| API intake | **exists** | comm-gateway `/intake/mock` (+ project/work-item APIs) |
| Approval governance | **exists (API)** | approval-engine `/approval/request|approve|reject`; orchestrator `_approval_listener` auto-resume |
| Policy governance | **exists** | policy-engine `RESTRICTED_ACTIONS` (production/email/contract/cost/secret…) |
| Retry / DLQ | **exists (API)** | stream retry (max 3) → `stream.deadletter`; retry-scheduler `/deadletter` + `/deadletter/replay/{id}` |
| Cancel / abort / terminate | **exists** | orchestrator `_terminate_workflow`, terminal-stage guard |
| Audit + integrity | **exists** | audit-service, audit-worker, hash-chain |
| Admin Console | **partial** | has task-graph, incidents (`/admin/incidents`), audit views |
| GitHub sandbox draft-PR rail | **exists (controlled)** | `/operations/github/sandbox-draft-pr` (gated) |
| Discord notification rail | **exists (controlled)** | discord-gateway real send (gated) |
| LLM plan-only + budget/audit rail | **exists (controlled)** | `RealLLMPlanOnlyProvider` + `BudgetPolicyEvaluator` |

## 2. What is missing for AI Agents Team Work (the Step 66 product gap)

| Gap | Have backend? | Have operator UI? | Step 66 target |
| --- | --- | --- | --- |
| Operator task assignment (assign from UI, not only API) | partial (intake API) | **no** | 66B |
| Agent interaction / workroom (see & reply to agent conversation) | partial (discussion records) | **no** | 66C |
| Delivery inbox (manager-facing deliverables list) | partial (results in DB/audit) | **no** | 66D |
| Acceptance gate (Accept/Reject/Request Changes/Re-run QA) | **no first-class action model** | **no** | 66D |
| Approval management page | yes (API) | **no** (`/approvals` page absent — Step 65 gap #7) | 66D/66G |
| DLQ / Retry management page | yes (API) | **no** (Step 65 gap #6, operator-flagged) | 66D/66G |
| Multi-channel intake (Slack / Telegram) | **no gateway** (Discord exists for notify) | **no** | 66F |
| Lifecycle notifications across the full journey | partial (Discord notify) | **no unified model** | 66G |
| Operator Action Center (unified queues) | **no** | **no** | 66G |
| Web research / browsing connector | **no** | **no** | flagged as future connector requirement |
| Selectable / custom agent team composition | fixed pipeline only | **no** | post-MVP (templates → role → AI-suggested) |

## 3. Step 65 gaps this analysis absorbs

- **#6 DLQ / Retry Admin Console page** — operator-flagged; → Operator Action Center (66D/66G).
- **#7 `/approvals` page** — → Operator Action Center (66D/66G).
- **#2 safe approval-expiry/timeout** — pre-production product fix; relevant to clarification/approval
  timeout design (see decision register D4).

## 4. Honest capability caveats

- **No web browsing/search** is wired into agents today; "latest online info" tasks are **not**
  currently executable — recorded as a future connector requirement, not fabricated.
- Runtime here has **no live external write** by default (test posture); all Step 66 UI work proceeds
  against mock/dry-run unless a controlled rail is separately authorized per step.
- `production_executed_true_count=0` invariant continues to hold.

## 5. Statement

No UI was implemented and no workflow was executed for this analysis. No external action occurred.
No production action occurred. Recommendations are non-final and require operator review.

---
_Non-production only. No production action. No production data._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
