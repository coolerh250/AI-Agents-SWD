# E2E Staging GitHub Record (Step 65G.2)

> **Staging only — non-production only. No production action. No production repo write.**
> **One controlled sandbox draft-PR flow. No merge / release / tag / deploy.**

Records the single controlled GitHub sandbox draft-PR flow for the Step 65G.2 E2E run, through the
Step 65D controlled rail, tied to the project + work item created for this run.

## Draft PR metadata
| Field | Value |
|---|---|
| target repo | `coolerh250/AI-Agents-SWD-sandbox` (sandbox only) |
| repository_key | `ai-agents-sandbox` |
| draft PR number | **#16** (`https://github.com/coolerh250/AI-Agents-SWD-sandbox/pull/16`) |
| draft state | `draft=true`, `ready_for_review=false` |
| branch | `sandbox/ai-agents/prj-step-65g-2-e2e-ca0256/wi-0001/5e4a975cf49c` |
| base branch | `main` |
| project | `PRJ-STEP-65G-2-E2E-CA0256` (`2abd5d2a-9486-4d7e-b528-5202661d44f9`) |
| work item | `WI-0001` (`2e9612ed-5c11-4c0d-8ddf-8fd567cec919`), `production_effect=false` |
| correlation id (rail) | `5e4a975cf49c45b6a1b3173352d8ae26` |
| request_id | `b90e93f1-627a-481c-8a54-b5146907a7b4` |
| audit_event_id | `ac9d0c13834d42a0a5dfcee97c7cd3f9` |
| status | `created`, `mode=live_sandbox` |

## Safety properties (all confirmed in the rail response + safety endpoint)
- `merge_performed=false`, `ready_for_review_performed=false`, `workflow_dispatch_performed=false`,
  `non_sandbox_repo_write_performed=false`, `production_executed=false`.
- Sandbox draft-PR safety after: `created_count=2` (PR #15 from 65D + this PR #16),
  `merge_enabled=false`.
- Only the sandbox repo was written; the main/production repo was never touched.

## Naming deviation (disclosed)
The controlled rail generated its own **validated Step-59 naming** — branch prefix
`sandbox/ai-agents/…` and PR title prefix `[Sandbox][Draft]` — rather than the spec's aspirational
`staging/agents-sandbox/*` branch and `[STAGING-SANDBOX]` commit prefix. The rail's naming is the
one that has been safety-validated; the safety scope (sandbox repo only, draft only, no merge) is
identical. Documented rather than forcing a code change.

## Guardrail compliance
- The write went through the controlled sandbox draft-PR rail (operator auth + CSRF → policy →
  allowlist → live gate → real GitHub API), gated on the allowlisted `ai-agents-sandbox` repo with
  `allow_merge=false`. Live mode was enabled only for the window and **reset to safe** after
  (`SANDBOX_GITHUB_LIVE=false`, operator actions disabled). No secret value was printed or committed.

## Status
Step 65G.2 GitHub: **1** controlled sandbox draft PR (#16), no merge;
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production repo write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=sandbox-controlled github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled-at-rest -->
