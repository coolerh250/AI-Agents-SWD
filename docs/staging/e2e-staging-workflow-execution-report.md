# E2E Staging Workflow Execution Report (Step 65G.2)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **One fresh intake; one controlled LLM call; one controlled GitHub sandbox draft-PR flow; one controlled Discord staging notification. All flags reset to safe. Operator UI validation pending.**

Records the **real** controlled end-to-end staging workflow validation on `10.0.1.32`, under operator
authorization: a fresh intake drove the real distributed agent pipeline, and the three validated
controlled rails (LLM / GitHub sandbox / Discord) were exercised exactly once each, correlated to
the same task id.

## Overall result
- Overall result: **PASS** (corrected by Step 65G.2-V — the operator confirmed **VISIBLE** on the
  formal Admin Console pages). Every technical step succeeded within the authorized counts and caps,
  staging was reset to safe, and the fresh E2E evidence is operator-visible. See
  [e2e-staging-operator-ui-validation-record.md](e2e-staging-operator-ui-validation-record.md).
- `production_executed_true_count=0` before and after. **Claude Code does not decide staging
  functional acceptance.**

## Authorization compliance
| Item | Authorized | Actual |
|---|---|---|
| Fresh intake | 1 | **1** |
| GitHub sandbox draft-PR flows | 1 | **1** (PR #16) |
| Discord sends | 1 | **1** |
| Official LLM calls | 1 | **1** |
| LLM cost | ≤ $1.00 | **$0.05073** |
| Direct diagnostic external calls | 0 | **0** |
| Production action | forbidden | **none** |

## Correlation
- **Task / correlation id:** `step65g2-e2e-20260706074202`.
- Pipeline agent executions, the LLM interaction, and the Discord delivery all carry this task id.
  The GitHub draft PR is tied to the project/work item created for this run (project key
  `PRJ-STEP-65G-2-E2E-CA0256`, work item `WI-0001`), whose project name embeds the correlation id.

## What happened (all real)
1. **Fresh intake:** `POST :18004/intake/mock {publish_to_stream:true}` → `task.created` on
   `stream.tasks` (`published_id=1783323767121-0`).
2. **Real distributed pipeline:** all **5 hops completed** — intake → requirement → development →
   qa → devops (agent_execution rows, ~730 ms end to end).
3. **Controlled LLM (65F rail):** one bounded plan-only Anthropic call
   (`claude-haiku-4-5-20251001`), budget-gated (≤$1, block mode), 990 tokens, actual cost
   **$0.05073**, `exceeded=false`, `plan_only=true`, `production_executed=false`.
4. **Controlled GitHub (65D rail):** one sandbox **draft PR #16** in `coolerh250/AI-Agents-SWD-sandbox`
   (`draft=true`, `merge_performed=false`, `non_sandbox_repo_write_performed=false`,
   `production_executed=false`).
5. **Controlled Discord (65E rail):** one `[STAGING]` notification to `MySanbox / #general`
   (`external_sent=true`) referencing the task id + PR #16 + `production_executed_true_count=0`.
6. **Reset:** all live flags returned to safe; the budget policy set to `inactive`; orchestrator +
   discord-gateway recreated; `/operations/safety` re-verified.

## Findings during execution (disclosed)
1. **`/intake/mock/project-work-item` is broken in staging** — the communication-gateway image is
   missing PyYAML (`ModuleNotFoundError: No module named 'yaml'`), so that convenience endpoint
   returns 500. **Not caused by this run; no image rebuild performed.** Worked around by creating the
   formal project + work item through the orchestrator's operator-authenticated multi-project API
   (`POST /operations/delivery/projects` + `.../work-items`), which has PyYAML. Tracked as a gap.
2. **Stream-mode fresh intake does not create a `workflow_state`** (the `/task-graph` surface) — it
   records agent_executions + audit only. This confirms the Step 65G.1 tracked hypothesis; the
   pipeline evidence is on `/agent-executions`, not `/task-graph`. Not fabricated. Tracked as a gap.
3. **Platform branch/title naming differs from the spec's suggestion** — the sandbox rail generates
   `sandbox/ai-agents/…` branches and `[Sandbox][Draft]` titles (its validated Step-59 scheme), not
   the spec's aspirational `staging/agents-sandbox/*` + `[STAGING-SANDBOX]`. The safety properties
   (sandbox repo only, draft only, no merge) all hold.

## Safety
- `production_executed_true_count=0` throughout. No GitHub merge/release/tag/deploy; no production
  channel; no DM; no direct diagnostic call; no secrets in prompt/message/logs; no production/
  customer data. Only the orchestrator + discord-gateway were recreated (never a full-stack
  restart, never `down`/`down -v`).

## Status
- Step 65G.2: **PASS** (operator confirmed **VISIBLE** on the formal Admin Console pages — Step
  65G.2-V; see
  [e2e-staging-operator-ui-validation-record.md](e2e-staging-operator-ui-validation-record.md)). Not
  production readiness.

## Companion records
- [e2e-staging-workflow-evidence.md](e2e-staging-workflow-evidence.md) ·
  [e2e-staging-agent-pipeline-record.md](e2e-staging-agent-pipeline-record.md) ·
  [e2e-staging-llm-record.md](e2e-staging-llm-record.md) ·
  [e2e-staging-github-record.md](e2e-staging-github-record.md) ·
  [e2e-staging-discord-record.md](e2e-staging-discord-record.md) ·
  [e2e-staging-admin-console-evidence-checklist.md](e2e-staging-admin-console-evidence-checklist.md) ·
  [e2e-staging-safety-reset-record.md](e2e-staging-safety-reset-record.md) ·
  [e2e-staging-known-gaps.md](e2e-staging-known-gaps.md) ·
  [e2e-staging-operator-validation-request.md](e2e-staging-operator-validation-request.md)

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=controlled-e2e github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
