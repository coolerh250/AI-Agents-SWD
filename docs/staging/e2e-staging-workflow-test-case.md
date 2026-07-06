# E2E Staging Workflow Test Case (Step 65G.1)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — this test case is not executed in this stage.**

Defines exactly **one** primary E2E staging test case for Step 65G.2.

## Test case
| Field | Value |
|---|---|
| Title | Create staging-only user profile preference API |
| Environment | staging (`10.0.1.32`) |
| Production effect | **false** |
| Fresh intake | yes — a new correlation id, not seeded/mock data |
| External systems | GitHub sandbox (65D rail), Discord staging channel (65E rail), Anthropic LLM (65F budget/audit rail) |

## Intake payload shape (non-production, harmless)
- Project/Work Item (formal `/delivery` objects), via
  `POST /intake/mock/project-work-item` with `environment_scope` in {`dev`,`test`,`nonprod`},
  `production_effect=false`, `requires_human_approval=false`.
- Fresh pipeline task, via `POST /intake/mock` `{ publish_to_stream: true, request: { type: "feature",
  title: "Create staging-only user profile preference API", description: "Add a staging-only
  read/write API for a user's UI preferences (theme, language). Non-production, no real user data." } }`.
- The request text contains **no** secrets, production data, personal data, or customer data.

## Expected outputs
- **Workflow / pipeline:** a fresh workflow trace + agent executions for intake → requirement →
  development → qa → devops.
- **LLM (controlled step):** bounded requirement/plan content produced through the platform
  budget/audit rail (metadata + interaction/usage records; `plan_only=true`,
  `requires_human_review=true`).
- **GitHub (controlled step):** one staging-only **evidence artifact + draft PR** in the sandbox
  repo `coolerh250/AI-Agents-SWD-sandbox` (draft only, no merge).
- **Discord (controlled step):** one `[STAGING]` workflow-completion notification to
  `MySanbox / #general`.
- **Admin Console:** project + work item, agent executions, workflow/task-graph trace, QA/code
  evidence, audit/evidence records, and a safe Safety Center — all on **formal** pages.

## Must NOT do
- Touch the production repo or any customer repo. Touch a production deployment. Send a production
  notification. Use production, personal, or customer data. Create a release or tag. Merge a PR.

## Success (high level; per-page detail in the checklist)
- Fresh workflow + agent executions visible; controlled LLM/GitHub/Discord artifacts present and
  correlated to the same task id; audit/evidence complete; Safety Center safe;
  `production_executed_true_count=0`.

## Failure / abort (high level; full list in the abort/reset plan)
- Any production side effect; any non-sandbox GitHub target; any non-staging Discord target; any
  direct diagnostic external call; any missing budget cap; any secret in output; more than the
  authorized number of calls/sends/writes.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
