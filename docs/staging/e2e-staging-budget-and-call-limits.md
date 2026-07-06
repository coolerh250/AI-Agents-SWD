# E2E Staging Budget & Call Limits (Step 65G.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — these limits govern Step 65G.2, which is not executed here.**

Strict limits for the Step 65G.2 controlled run.

## Hard limits
| Resource | Maximum | Notes |
|---|---|---|
| GitHub writes | **1 draft-PR flow** | one branch + evidence file + one draft PR in the sandbox repo; no merge |
| Discord sends | **1 workflow notification** | one `[STAGING]` message to `MySanbox/#general` |
| LLM official calls | **minimum required — planned as 1** | see below |
| LLM cost | **≤ $1** total for the run | unless the operator sets a stricter cap; budget policy in `block` mode |
| Automatic retries | **disabled** | no retry of any external call unless separately authorized |
| Direct diagnostic probes | **0** | forbidden unless separately authorized in advance |

## LLM call-count planning
- The **minimum required** official LLM call count for the E2E test case is **1** — a single bounded
  plan-only call through the 65F budget/audit rail (e.g., a requirement/plan summary for the
  user-preference-API task).
- The native agent pipeline uses the **mock** LLM provider, so the pipeline itself adds **0** real
  LLM calls. If, at 65G.2, the chosen flow would require **more than one** real LLM call, that must
  be documented and **explicitly authorized by the operator before 65G.2 runs** — the planned
  default is exactly one.
- "Exactly one call" counts **official + any diagnostic** calls together (Step 65F-C rule). The plan
  budgets **zero** diagnostic calls.

## Budget enforcement
- A budget policy (`provider=external_anthropic`, `max_cost_per_task_usd ≤ 1.00`,
  `max_cost_per_day_usd ≤ 1.00`, `enforcement_mode=block`) must be **created and active before** the
  LLM step, and **deactivated after**. Preflight must return `allowed`; post-call `record_usage`
  must report `exceeded=false`.

## This stage's posture
Planning only. No LLM call, no GitHub write, no Discord send, no workflow execution, no production
action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
