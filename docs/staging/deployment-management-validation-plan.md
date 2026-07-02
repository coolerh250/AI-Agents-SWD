# Staging Deployment Management — Validation Plan (Step 64F.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Validation design only — GET/HEAD checks; no runtime change executed by this document.**

The validation to run after any staging start / restart / rebuild / redeploy / rollback / restore,
before treating the runtime as good. All checks are **GET/HEAD** (plus `docker compose ps` / logs).

## 1. Runtime health
- `docker compose … ps` → orchestrator `running (healthy)`; dependencies healthy.
- `curl -fsS http://127.0.0.1:18000/health` → 200.
- `curl -fsSI http://127.0.0.1:18000/admin` → 307 → `/admin/` 200.
- `bash scripts/check_staging_runtime.sh` → PASS (critical surfaces reachable).

## 2. Safety posture
- `curl -fsS http://127.0.0.1:18000/operations/safety` →
  - `production_executed_true_count = 0`
  - `github_external_write_enabled = false`
  - `discord_external_send_enabled = false`
  - `llm_external_call_enabled = false`

## 3. Deployed bundle
- `/admin/` references `/admin/assets/index-*.js`; record the hash and confirm it matches the built
  image (guards against a stale bundle).

## 4. Formal product pages (acceptance path)
| Page | Route | Backing endpoint | Expected |
|---|---|---|---|
| Projects / Work Items | `/delivery` | `/operations/delivery/projects` + `.../work-items` | project + WI-0001 |
| Agent Executions | `/agent-executions` | `/operations/agent-executions` | pipeline executions |
| Workflows / Task Graph | `/task-graph` | `/operations/workflows` | workflow trace, `production_executed=false` |
| QA / Code | `/qa-code` | `/operations/qa/runs` + `/operations/code/workspaces` | QA + code summaries |
| Audit / Evidence | `/audit-evidence` | `/operations/delivery/work-items/{id}/events` | `work_item_created` |
| Safety Center | `/safety` | `/operations/safety` | `production_executed_true_count=0` |

- Navigate by top-nav tabs (deep-link 404 is a known accepted gap).
- The Demo Evidence / Diagnostics page is **not** part of acceptance validation.

## 5. Pass/fail
- **PASS:** all of §1–§4 hold.
- **PASS_WITH_GAPS:** §1–§2 hold and every evidence type is reachable, but a documented
  non-blocking gap remains (e.g. deep-link 404).
- **FAIL:** Admin Console unreachable, a safety flag non-compliant, or a required evidence type
  missing from its formal page → roll back / remediate per the SOP.

## Status
Step 64E: **PASS**. Step 64F: **SOP_DESIGN_COMPLETED**. Staging deployment management only, not
production readiness. No runtime change in this stage; no production action;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
