# Staging Demo Admin Console Evidence (Step 64D)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Evidence that the demo data is present in the backing `/operations/*` endpoints on `10.0.1.32`
after the Step 64D execution. Values are from host-local `curl`.

> **Correction (Step 64E-R):** this evidence is **backend-API only**. The deployed console (the
> zero-build static fallback) does **not** render most of it. The operator walkthrough confirmed
> only aggregate counts (Operational Metrics) + safety posture (Safety Center) are visible; the
> **"Agent Executions / Workflows / QA / Code / Audit" pages listed below are NOT in the
> deployed console** and their per-item data is not visible to the operator. Do not read the
> "Pages populated" list as operator-visible. Root cause + remediation:
> [staging-admin-console-deployment-gap.md](staging-admin-console-deployment-gap.md);
> operator verdict: [operator-walkthrough-validation-report.md](operator-walkthrough-validation-report.md).

## Populated data (backing endpoints, all 200)
| Admin Console area | Endpoint | Demo evidence |
|---|---|---|
| Operational Metrics | `/operations/metrics/overview` | `project_count_total=1`, `work_item_count_total=1`, `dispatch_count_total=0`, `production_executed_true_count=0`, `production_ready=false` |
| Multi-Project Delivery | `/operations/delivery/projects` | 1 project — "SaaS User Management Module" (`nonprod`) |
| Work Items | `/operations/delivery/projects/{id}/work-items` | `WI-0001` "Create user CRUD API" (`created`, `production_effect=false`) |
| Agent Executions | `/operations/summary → agents_summary` | 5 agents; 10 executions; 10 completed; 0 failed; pipeline intake→requirement→development→qa→devops |
| Workflows | `/operations/summary → workflows_summary` | 2 total; 2 completed; 0 failed; 2 recent_24h |
| QA | `/operations/qa/runs` | 2 runs |
| Code | `/operations/code/workspaces` | 2 workspaces |
| Audit / Evidence | `/operations/summary → audit_summary` | `audit_logs_total=60`, `audit_logs_recent_24h=60` |
| Safety Posture | `/operations/safety` | `production_executed_true_count=0` |

## Pages populated
Operational Metrics, Multi-Project Delivery (project + work item), Agent Executions,
Workflows, QA, Code, Audit/Evidence, Safety Posture.

## Empty pages remaining
- **Release Governance** — no release candidate (governed dispatch gated; see
  [staging-demo-delivery-evidence.md](staging-demo-delivery-evidence.md)).
- **LLM interactions** — 0 (LLM disabled/mocked; expected).
- Other posture pages (identity/secrets/security/runtime/backup-dr/readiness) render their
  baseline read-only content, unaffected by the demo.

## Error states
None observed on probed endpoints (no 5xx).

## Operator-visible result
Through the SSH port-forward (`http://localhost:18000/admin`) the operator can see the SaaS
User Management Module project, its `WI-0001` work item, the completed agent pipeline, QA/code
outputs, audit log growth, and a safety posture with `production_executed_true_count=0`.

## Safety
No public exposure; live integrations disabled/mocked; no production action;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false live-integrations=disabled demo-workflow-executed=true -->
