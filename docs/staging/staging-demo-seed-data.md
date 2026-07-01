# Staging Demo Seed Data (Step 64D)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Records seeded for the Step 64D demo on the staging runtime (`10.0.1.32`).

## Seed method
- **Script:** `scripts/staging_seed_demo_workflow.py` — staging/demo-only, **idempotent**
  (reuses an existing project/work item by title rather than duplicating).
- **How it ran:** piped into the **orchestrator container** (`docker exec -i … python -`),
  which has the project/work-item SDK + PyYAML. Uses the existing `ProjectStore` /
  `WorkItemStore` SDK — the same code the communication-gateway mock intake uses — **not raw
  SQL**. `production_effect=False`; `environment_scope=nonprod`.
- **Why not the gateway endpoint:** `POST /intake/mock/project-work-item` on the gateway
  currently 500s (`ModuleNotFoundError: No module named 'yaml'` in the gateway image). Documented
  in [staging-demo-known-gaps.md](staging-demo-known-gaps.md).
- **Direct DB mutation used:** no (SDK inserts via its own governed store methods).

## Project created
| Field | Value |
|---|---|
| name | SaaS User Management Module |
| project_key | `PRJ-SAAS-USER-MANAGEMENT-MODULE-15F51D` |
| project_id | `f67ab2b2-…-7469736c191e` |
| environment_scope | `nonprod` |
| production_allowed | `false` |
| registry_status | `active` |
| requester | `staging-demo` |

## Work item created
| Field | Value |
|---|---|
| work_item_key | `WI-0001` |
| work_item_id | `386a3f95-…-4fae80e427cd` |
| title | Create user CRUD API |
| description | staging-only user management CRUD API (create/read/update/delete) + non-production delivery evidence |
| work_type (delivery_work_type) | `task` |
| priority | `medium` |
| item_source | `staging_demo` |
| lifecycle_state | `created` |
| requires_human_approval | `false` |
| production_effect | `false` |

## Idempotency
Re-running the seed reuses the existing project + work item (matched by title); no duplicate is
created.

## Required demo safety fields (per spec §9)
| Field | Value / equivalent |
|---|---|
| environment | `nonprod` (project `environment_scope`) |
| production_executed | `false` (workflow `execution_result.production_executed`) |
| external_write | none (`github_external_write_enabled=false`) |
| github_live_write | disabled |
| slack/discord_live_send | disabled (`discord_external_send_enabled=false`) |
| llm_live_call | disabled/mocked (LLM interactions = 0) |
| approval_required_for_production | production is gated — `production_allowed=false`, operator actions disabled |

## Safety
No production action; no production secret; no external write; live integrations
disabled/mocked; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false live-integrations=disabled demo-workflow-executed=true -->
