# Step 66D-ARCH1 — Existing Capability Inventory

> **Re-derived from repository source at canonical main `ccfee8e`, not copied from a prior stage
> table. Read-only inspection. Nothing started, nothing modified.
> `production_executed_true_count: 0`.**

Classification values: `IMPLEMENTED_AND_TESTED`, `IMPLEMENTED_WITH_GAPS`, `BACKEND_ONLY`,
`FRONTEND_ONLY`, `DIAGNOSTIC_ONLY`, `PLACEHOLDER`, `HISTORICAL_ONLY`, `PLANNED_NOT_IMPLEMENTED`,
`ABSENT`.

## 1. Legacy DeliveryPackage family

### legacy DeliveryPackage object

```text
source path            shared/sdk/delivery_package/models.py
authoritative storage  migrations/021_delivery_package_acceptance_gate.sql
current API            apps/orchestrator/src/delivery_package_api.py
current UI             apps/admin-console/src/pages/DeliveryPackage.tsx
current audit          shared/sdk/delivery_package/audit_events.py
POC usability          evidence bundle only; not a human review aggregate
compatibility          REFERENCE
classification         IMPLEMENTED_AND_TESTED
known gap              human_acceptance_status is a single mutable string with no decision
                       history, no decider, no reason, no supersession -- cannot satisfy 66D-D02
```

### Delivery Package API

```text
source path            apps/orchestrator/src/delivery_package_api.py
shape                  15 read endpoints + 1 build POST
                       (/delivery-packages, /sections, /artifacts, /report, /handoff-summaries,
                        /readiness, /acceptance-gate, /acceptance-checks, /acceptance-checklist,
                        /operator-review, project-scoped variants)
compatibility          REFERENCE
classification         IMPLEMENTED_AND_TESTED
known gap              read-oriented; no review action, no decision, no follow-up endpoint
```

### delivery-package agent

```text
source path            agents/delivery-package-agent/src/agent.py, src/main.py
compatibility          REUSE (as an evidence producer)
classification         IMPLEMENTED_AND_TESTED
known gap              produces packages; has no concept of a reviewer or a decision
```

### Admin Console DeliveryPackage page

```text
source path            apps/admin-console/src/pages/DeliveryPackage.tsx
api types              apps/admin-console/src/api/types.ts (human_acceptance_status: string | null)
compatibility          REFERENCE
classification         FRONTEND_ONLY
known gap              displays a status string; no review action UI, no decision UI, no follow-ups
```

### human acceptance status

```text
source path            shared/sdk/delivery_package/models.py (human_acceptance_status, default
                       "pending"); surfaced in admin-console api/types.ts
compatibility          NEW_CONTRACT_REQUIRED
classification         IMPLEMENTED_WITH_GAPS
known gap              a mutable string, overwritten in place; no decider, reason, evidence,
                       timestamp or supersession -- the exact shape 66D-D02 forbids as authoritative
```

## 2. Approval, audit and RBAC

### approval requests / approval engine

```text
source path            apps/approval-engine/, apps/orchestrator/src/approval_policy_api.py,
                       shared/sdk/approval_policy/
compatibility          ADAPT
classification         IMPLEMENTED_AND_TESTED
known gap              models production/operational approval, not delivery acceptance; per
                       ADR-66D-07 these must stay distinct gates
```

### operator actions

```text
source path            shared/sdk/operator_actions/ (15 modules)
compatibility          ADAPT
classification         IMPLEMENTED_AND_TESTED
known gap              operator action vocabulary is resume/replay-oriented; no Review Gate Action
```

### audit events / audit service

```text
source path            apps/audit-service/, apps/audit-worker/, shared/sdk/audit/,
                       shared/sdk/audit_integrity/
compatibility          REUSE
classification         IMPLEMENTED_AND_TESTED
known gap              no delivery review or PO decision audit action names exist yet
```

### task and TASK_ROLES

```text
source path            shared/sdk/tasks/rbac.py, shared/sdk/tasks/authorization_policy.py,
                       apps/orchestrator/src/task_api.py
roles present          requester, pm_engineering_lead, reviewer_approver, platform_admin,
                       agent_operator, security_compliance_reviewer
compatibility          ADAPT
classification         IMPLEMENTED_AND_TESTED
known gap              no delivery review capability mapping; _ACTION_ROLES covers resume/replay
                       only. NOT modified by this stage.
```

## 3. Execution lineage and evidence

### project / work-item / workflow / run linkage

```text
source path            shared/sdk/projects/, shared/sdk/work_items/,
                       shared/sdk/workspace_operator/work_item_mapper.py,
                       migrations/024_multi_project_work_item_dispatch.sql
compatibility          REUSE
classification         IMPLEMENTED_AND_TESTED
known gap              no linkage from this lineage to any delivery submission aggregate
```

### task linkage

```text
source path            apps/orchestrator/src/task_api.py
compatibility          REUSE
classification         IMPLEMENTED_AND_TESTED
known gap              no delivery_review_task_id concept
```

### artifact storage

```text
source path            shared/sdk/delivery_package/artifact_collector.py
compatibility          ADAPT
classification         IMPLEMENTED_WITH_GAPS
known gap              no producer_actor_ref, no generation_mode, no content_hash, no
                       supersedes_artifact_id -- ADR-66D-06 provenance fields are all absent
```

### QA evidence

```text
source path            shared/sdk/qa/
compatibility          ADAPT
classification         IMPLEMENTED_WITH_GAPS
known gap              no acceptance-criterion result model (PASS/FAIL/PARTIAL/NOT_TESTED/
                       NOT_APPLICABLE) with assessor and reason; no rerun accounting
```

### GitHub branch/commit/draft PR evidence

```text
source path            shared/sdk/github/, apps/github-automation/
compatibility          REFERENCE
classification         IMPLEMENTED_AND_TESTED
known gap              not linked to a delivery submission; write paths remain gated
```

### external AI partner execution evidence

```text
source path            ABSENT as a first-class record
compatibility          NEW_CONTRACT_REQUIRED
classification         ABSENT
known gap              Claude Code / Codex / Claude Design work is evidenced only in documents;
                       no actor_type: ai_partner record exists
```

### runtime agent execution evidence

```text
source path            shared/sdk/agent_execution/
compatibility          REUSE
classification         IMPLEMENTED_AND_TESTED
known gap              not joined to acceptance; completion is not an assessment
```

## 4. Accounting and reliability

### cost accounting

```text
source path            shared/sdk/llm_budget/, shared/sdk/llm_routing/
compatibility          ADAPT
classification         IMPLEMENTED_WITH_GAPS
known gap              no per-submission cost_summary; no planned/attempted/successful/failed
                       breakdown against an authorized_limit
```

### external-operation accounting

```text
source path            partial, spread across github/, notifications/, llm/
compatibility          NEW_CONTRACT_REQUIRED
classification         IMPLEMENTED_WITH_GAPS
known gap              no unified external_action_summary; no per-provider limit_breach record
```

### retry / DLQ evidence

```text
source path            apps/retry-scheduler/, apps/clarification-outbox-relay/
compatibility          REUSE
classification         IMPLEMENTED_AND_TESTED
known gap              not surfaced in any delivery review context
```

### transactional outbox

```text
source path            present for the clarification path (apps/clarification-outbox-relay/)
compatibility          REUSE
classification         IMPLEMENTED_AND_TESTED
known gap              no delivery outbox; ADR-66D-08 specifies reuse, this stage does not wire it
```

## 5. The new aggregate and its companions

```text
DeliverySubmission          ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
DeliveryReviewTask          ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
DeliveryReviewAction        ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
ProductOwnerDecision        ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
AcceptanceFollowUpItem      ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
PO decision persistence     ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
follow-up persistence       ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
Delivery Inbox surface      ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
Delivery Review surface     ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
unified read model          ABSENT   PLANNED_NOT_IMPLEMENTED   NEW_CONTRACT_REQUIRED
```

## 6. Tally

```text
IMPLEMENTED_AND_TESTED      11
IMPLEMENTED_WITH_GAPS        5
FRONTEND_ONLY                1
ABSENT / PLANNED_NOT_IMPLEMENTED  11
DIAGNOSTIC_ONLY / PLACEHOLDER / HISTORICAL_ONLY   0

Compatibility:
  REUSE                      7
  REFERENCE                  4
  ADAPT                      6
  NEW_CONTRACT_REQUIRED     11
  DEPRECATE_LATER            0   (no legacy deprecation is decided in this stage)
```

Nothing in section 5 exists. The entire human-acceptance aggregate and both product surfaces are
new work, and none of it is authorized here.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
